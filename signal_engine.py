"""
Signal Engine - Institutional Trend-Pullback & Liquidity Rejection (TPLR)
=========================================================================
Algoritma trading kuantitatif berbasis Price Action, Dynamic Value Zones (EMA 21/55),
Macro Trend Filter (1H), dan Rejection Wick Analysis.

Prinsip:
1. Macro Trend Anchor (1H): Hanya ambil posisi searah tren besar.
2. Value Zone Pullback (15m): Masuk saat harga diskon menyentuh area EMA 21/55.
3. Price Action Rejection: Konfirmasi adanya ekor penolakan (wick defense) atau engulfing.
4. Volume & RSI Sweet Spot: Volume buyer/seller terkonfirmasi dan RSI punya ruang gerak.
"""

import pandas as pd
import ta as ta_lib
import config
from logger_setup import logger


class SignalEngine:
    """Engine analisis teknikal institusional berbasis Trend-Pullback & Rejection."""
    
    def __init__(self, exchange):
        self.exchange = exchange
    
    def fetch_candles(self, symbol, timeframe, limit=None):
        """Fetch OHLCV candles dari exchange."""
        limit = limit or config.CANDLE_FETCH_LIMIT
        try:
            bars = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            df = pd.DataFrame(
                bars,
                columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            return df
        except Exception as e:
            logger.error(f"❌ Gagal fetch candles {symbol} {timeframe}: {e}")
            return pd.DataFrame()
    
    def calculate_indicators(self, df):
        """Hitung EMA 21, EMA 55, EMA 200, RSI, ATR, dan Volume SMA."""
        if df.empty or len(df) < 55:
            return df
        
        # Exponential Moving Averages (Value Zones)
        df["ema_21"] = ta_lib.trend.ema_indicator(df["close"], window=config.EMA_FAST)
        df["ema_55"] = ta_lib.trend.ema_indicator(df["close"], window=config.EMA_SLOW)
        
        if len(df) >= config.EMA_TREND:
            df["ema_200"] = ta_lib.trend.ema_indicator(df["close"], window=config.EMA_TREND)
        else:
            df["ema_200"] = df["ema_55"]
        
        # RSI & ATR
        df["rsi"] = ta_lib.momentum.rsi(df["close"], window=config.RSI_PERIOD)
        df["atr"] = ta_lib.volatility.average_true_range(df["high"], df["low"], df["close"], window=14)
        
        # Volume SMA
        df["vol_sma"] = ta_lib.trend.sma_indicator(df["volume"], window=config.VOLUME_SMA_PERIOD)
        
        return df

    def _get_macro_trend(self, symbol):
        """
        Evaluasi tren makro pada timeframe 1H.
        Returns:
            str: 'bullish' | 'bearish' | 'neutral'
        """
        df_1h = self.fetch_candles(symbol, config.HIGHER_TIMEFRAME)
        if df_1h.empty:
            return "neutral"
        
        df_1h = self.calculate_indicators(df_1h)
        if df_1h.empty or len(df_1h) < 2:
            return "neutral"
            
        last = df_1h.iloc[-1]
        ema_21 = last.get("ema_21", 0)
        ema_55 = last.get("ema_55", 0)
        ema_200 = last.get("ema_200", 0)
        close = last["close"]
        
        if ema_21 > ema_55 and close > ema_55:
            if ema_200 and close > ema_200:
                return "bullish"
            return "bullish"
        elif ema_21 < ema_55 and close < ema_55:
            if ema_200 and close < ema_200:
                return "bearish"
            return "bearish"
            
        return "neutral"

    def _check_pullback_long(self, df_15m):
        """
        Evaluasi pola Pullback & Bounce untuk sinyal LONG pada 15m.
        """
        if len(df_15m) < 5:
            return False, 0, {}
            
        last = df_15m.iloc[-1]
        prev = df_15m.iloc[-2]
        recent_3 = df_15m.iloc[-3:]
        
        ema_21 = last.get("ema_21", 0)
        ema_55 = last.get("ema_55", 0)
        rsi = last.get("rsi", 50)
        vol = last.get("volume", 0)
        vol_sma = last.get("vol_sma", 0)
        
        # 1. 15m Trend Alignment: EMA 21 harus di atas atau memotong EMA 55
        if ema_21 < ema_55 * 0.998:
            return False, 0, {"reason": "15m_ema_not_bullish"}
            
        # 2. Overextended Check: Jangan beli kalau harga sudah terbang > 1.5% di atas EMA 21
        distance_to_ema = ((last["close"] - ema_21) / ema_21) * 100
        if distance_to_ema > 1.5:
            return False, 0, {"reason": f"overextended_{distance_to_ema:.2f}%"}
            
        # 3. Pullback Zone Check: Dalam 3 candle terakhir, harga harus sempat menyentuh/menguji area EMA 21
        min_low_recent = recent_3["low"].min()
        if min_low_recent > ema_21 * 1.004:
            return False, 0, {"reason": "no_pullback_to_ema_zone"}
            
        # 4. Candlestick Price Action:
        # Range total candle
        candle_range = last["high"] - last["low"]
        if candle_range <= 0:
            return False, 0, {"reason": "flat_candle"}
            
        body = abs(last["close"] - last["open"])
        lower_wick = min(last["open"], last["close"]) - last["low"]
        lower_wick_ratio = lower_wick / candle_range
        is_green_candle = last["close"] >= last["open"]
        is_engulfing = (last["close"] > prev["open"] and last["open"] <= prev["close"] and is_green_candle)
        
        # Syarat trigger: ada rejection wick bawah >= 25% ATAU Bullish Engulfing, dan candle tutup di atas EMA 21
        has_rejection = lower_wick_ratio >= 0.25 or is_engulfing
        if not has_rejection:
            return False, 0, {"reason": f"no_lower_rejection_wick_{lower_wick_ratio:.2f}"}
            
        if last["close"] < ema_21 * 0.998:
            return False, 0, {"reason": "close_below_ema21"}
            
        # 5. RSI Sweet Spot (40 s/d 65): punya ruang untuk naik kencang
        if rsi < 40 or rsi > 68:
            return False, 0, {"reason": f"rsi_out_of_sweet_spot_{rsi:.1f}"}
            
        # 6. Volume Validation
        vol_ratio = vol / vol_sma if vol_sma > 0 else 1.0
        if vol_ratio < config.MIN_VOLUME_RATIO:
            return False, 0, {"reason": f"volume_too_low_{vol_ratio:.2f}x"}
            
        # Scoring kalkulasi
        score = 80
        if lower_wick_ratio >= 0.35:
            score += 8
        if is_engulfing:
            score += 7
        if vol_ratio >= 1.2:
            score += 5
            
        details = {
            "setup": "TPLR_LONG",
            "lower_wick_pct": f"{lower_wick_ratio*100:.1f}%",
            "rsi": round(rsi, 1),
            "vol_ratio": f"{vol_ratio:.2f}x",
            "dist_ema": f"{distance_to_ema:+.2f}%",
        }
        return True, min(100, score), details

    def _check_pullback_short(self, df_15m):
        """
        Evaluasi pola Pullback & Rejection untuk sinyal SHORT pada 15m.
        """
        if len(df_15m) < 5:
            return False, 0, {}
            
        last = df_15m.iloc[-1]
        prev = df_15m.iloc[-2]
        recent_3 = df_15m.iloc[-3:]
        
        ema_21 = last.get("ema_21", 0)
        ema_55 = last.get("ema_55", 0)
        rsi = last.get("rsi", 50)
        vol = last.get("volume", 0)
        vol_sma = last.get("vol_sma", 0)
        
        # 1. 15m Trend Alignment: EMA 21 harus di bawah atau memotong EMA 55
        if ema_21 > ema_55 * 1.002:
            return False, 0, {"reason": "15m_ema_not_bearish"}
            
        # 2. Overextended Check: Jangan sell kalau harga sudah jatuh > 1.5% di bawah EMA 21
        distance_to_ema = ((ema_21 - last["close"]) / ema_21) * 100
        if distance_to_ema > 1.5:
            return False, 0, {"reason": f"overextended_down_{distance_to_ema:.2f}%"}
            
        # 3. Pullback Zone Check: Dalam 3 candle terakhir, harga harus sempat rally/retest area EMA 21
        max_high_recent = recent_3["high"].max()
        if max_high_recent < ema_21 * 0.996:
            return False, 0, {"reason": "no_retest_to_ema_zone"}
            
        # 4. Candlestick Price Action:
        candle_range = last["high"] - last["low"]
        if candle_range <= 0:
            return False, 0, {"reason": "flat_candle"}
            
        upper_wick = last["high"] - max(last["open"], last["close"])
        upper_wick_ratio = upper_wick / candle_range
        is_red_candle = last["close"] <= last["open"]
        is_engulfing = (last["close"] < prev["open"] and last["open"] >= prev["close"] and is_red_candle)
        
        # Syarat trigger: ada rejection wick atas >= 25% ATAU Bearish Engulfing, dan candle tutup di bawah EMA 21
        has_rejection = upper_wick_ratio >= 0.25 or is_engulfing
        if not has_rejection:
            return False, 0, {"reason": f"no_upper_rejection_wick_{upper_wick_ratio:.2f}"}
            
        if last["close"] > ema_21 * 1.002:
            return False, 0, {"reason": "close_above_ema21"}
            
        # 5. RSI Sweet Spot (32 s/d 60): punya ruang untuk dump
        if rsi < 32 or rsi > 60:
            return False, 0, {"reason": f"rsi_out_of_sweet_spot_{rsi:.1f}"}
            
        # 6. Volume Validation
        vol_ratio = vol / vol_sma if vol_sma > 0 else 1.0
        if vol_ratio < config.MIN_VOLUME_RATIO:
            return False, 0, {"reason": f"volume_too_low_{vol_ratio:.2f}x"}
            
        # Scoring kalkulasi
        score = 80
        if upper_wick_ratio >= 0.35:
            score += 8
        if is_engulfing:
            score += 7
        if vol_ratio >= 1.2:
            score += 5
            
        details = {
            "setup": "TPLR_SHORT",
            "upper_wick_pct": f"{upper_wick_ratio*100:.1f}%",
            "rsi": round(rsi, 1),
            "vol_ratio": f"{vol_ratio:.2f}x",
            "dist_ema": f"{distance_to_ema:+.2f}%",
        }
        return True, min(100, score), details

    def analyze(self, symbol):
        """
        Analisis komprehensif menggunakan Algoritma TPLR (Trend-Pullback & Liquidity Rejection).
        """
        result = {
            "symbol": symbol,
            "signal": "WAIT",
            "score": 0,
            "details": {},
            "higher_tf_bias": "neutral",
            "price": 0,
        }
        
        try:
            # Blacklist check
            base_sym = symbol.replace(":USDT", "")
            if symbol in config.BLACKLIST_COINS or base_sym in config.BLACKLIST_COINS:
                result["details"] = {"reason": "blacklisted_coin"}
                return result
                
            # 1. Macro Trend Anchor (1H)
            macro_trend = self._get_macro_trend(symbol)
            result["higher_tf_bias"] = macro_trend
            
            # 2. Fetch Candle 15m
            df_15m = self.fetch_candles(symbol, config.TRADING_TIMEFRAME)
            if df_15m.empty:
                return result
                
            df_15m = self.calculate_indicators(df_15m)
            if df_15m.empty or len(df_15m) < 5:
                return result
                
            last = df_15m.iloc[-1]
            result["price"] = float(last["close"])
            
            # 3. Evaluasi Setup TPLR
            ema_21_val = float(last.get("ema_21", 0))
            atr_val = float(last.get("atr", 0))
            current_close = float(last["close"])
            atr_mult = getattr(config, "ATR_PULLBACK_MULTIPLIER", 0.35)
            
            # Hanya cari LONG jika macro 1H bullish atau neutral
            if macro_trend in ("bullish", "neutral"):
                is_long, score_long, details_long = self._check_pullback_long(df_15m)
                if is_long:
                    # Bonus skor jika macro 1H selaras
                    if macro_trend == "bullish":
                        score_long = min(100, score_long + 5)
                    result["signal"] = "LONG"
                    result["score"] = score_long
                    result["details"] = details_long
                    
                    # Hitung Dynamic Confluence Entry Price (EMA 21 & ATR Pullback)
                    if ema_21_val > 0 and atr_val > 0 and getattr(config, "DYNAMIC_PULLBACK_ENTRY_ENABLED", True):
                        atr_pullback = current_close - (atr_mult * atr_val)
                        suggested_entry = max(ema_21_val, atr_pullback)
                        # Batas aman: diskon antara 0.15% s/d 1.0% dari harga saat ini
                        max_discount_price = current_close * 0.990
                        min_discount_price = current_close * 0.9985
                        suggested_entry = max(max_discount_price, min(min_discount_price, suggested_entry))
                        result["suggested_entry_price"] = suggested_entry
                    
                    logger.info(
                        f"  🎯 TPLR LONG VALIDATED for {symbol} | Score: {score_long} | "
                        f"Wick: {details_long.get('lower_wick_pct')} | RSI: {details_long.get('rsi')}"
                    )
                    return result
            
            # Hanya cari SHORT jika macro 1H bearish atau neutral
            if macro_trend in ("bearish", "neutral"):
                is_short, score_short, details_short = self._check_pullback_short(df_15m)
                if is_short:
                    if macro_trend == "bearish":
                        score_short = min(100, score_short + 5)
                    result["signal"] = "SHORT"
                    result["score"] = score_short
                    result["details"] = details_short
                    
                    # Hitung Dynamic Confluence Entry Price (EMA 21 & ATR Pullback)
                    if ema_21_val > 0 and atr_val > 0 and getattr(config, "DYNAMIC_PULLBACK_ENTRY_ENABLED", True):
                        atr_pullback = current_close + (atr_mult * atr_val)
                        suggested_entry = min(ema_21_val, atr_pullback)
                        # Batas aman: premi tawar antara 0.15% s/d 1.0% dari harga saat ini
                        max_premium_price = current_close * 1.010
                        min_premium_price = current_close * 1.0015
                        suggested_entry = min(max_premium_price, max(min_premium_price, suggested_entry))
                        result["suggested_entry_price"] = suggested_entry
                    
                    logger.info(
                        f"  🎯 TPLR SHORT VALIDATED for {symbol} | Score: {score_short} | "
                        f"Wick: {details_short.get('upper_wick_pct')} | RSI: {details_short.get('rsi')}"
                    )
                    return result
                    
            result["signal"] = "WAIT"
            result["details"] = {"reason": "no_clean_pullback_rejection_setup"}
            
        except Exception as e:
            logger.error(f"❌ Error analyzing {symbol} with TPLR: {e}")
            
        return result
    
    def check_reversal(self, symbol, current_side):
        """
        Deteksi pembalikan arah dinamis pada TF 15m.
        Jika posisi LONG dan candle menembus ke bawah EMA 55 → Tutup posisi.
        Jika posisi SHORT dan candle menembus ke atas EMA 55 → Tutup posisi.
        """
        result = {
            "reversed": False,
            "signal": "HOLD",
            "score": 0,
            "details": {}
        }
        
        try:
            df = self.fetch_candles(symbol, config.TRADING_TIMEFRAME)
            if df.empty:
                return result
            
            df = self.calculate_indicators(df)
            if df.empty or len(df) < 3:
                return result
            
            last = df.iloc[-1]
            prev = df.iloc[-2]
            
            ema_21 = last.get("ema_21", 0)
            ema_55 = last.get("ema_55", 0)
            rsi = last.get("rsi", 50)
            close = last["close"]
            
            if current_side == "long":
                # Reversal LONG (Anti-Fakeout):
                # 1. Closed candle sebelumnya resmi tutup di bawah EMA 55, ATAU
                # 2. Harga live jebol valid > 0.5% di bawah EMA 55 (bukan cuma wick tipis), ATAU
                # 3. Terjadi Dead Cross EMA 21 tembus ke bawah EMA 55
                prev_ema55 = prev.get("ema_55", 0)
                is_closed_breakdown = prev["close"] < prev_ema55 and prev_ema55 > 0
                is_solid_breakdown = close < (ema_55 * 0.995) and ema_55 > 0
                is_dead_cross = (ema_21 < ema_55 and prev.get("ema_21", 0) >= prev.get("ema_55", 0))
                
                if is_closed_breakdown or is_solid_breakdown or is_dead_cross:
                    reason = "closed_below_ema55" if is_closed_breakdown else ("solid_breakdown" if is_solid_breakdown else "dead_cross_ema21_55")
                    result["reversed"] = True
                    result["signal"] = "CLOSE_LONG"
                    result["score"] = 90
                    result["details"] = {"reason": reason, "rsi": round(rsi, 1)}
                    logger.warning(f"⚠️ Confirmed Reversal for LONG {symbol}: {reason} | RSI: {rsi:.1f}")
                    
            elif current_side == "short":
                # Reversal SHORT (Anti-Fakeout):
                # 1. Closed candle sebelumnya resmi tutup di atas EMA 55, ATAU
                # 2. Harga live jebol valid > 0.5% di atas EMA 55, ATAU
                # 3. Terjadi Golden Cross EMA 21 tembus ke atas EMA 55
                prev_ema55 = prev.get("ema_55", 0)
                is_closed_breakout = prev["close"] > prev_ema55 and prev_ema55 > 0
                is_solid_breakout = close > (ema_55 * 1.005) and ema_55 > 0
                is_golden_cross = (ema_21 > ema_55 and prev.get("ema_21", 0) <= prev.get("ema_55", 0))
                
                if is_closed_breakout or is_solid_breakout or is_golden_cross:
                    reason = "closed_above_ema55" if is_closed_breakout else ("solid_breakout" if is_solid_breakout else "golden_cross_ema21_55")
                    result["reversed"] = True
                    result["signal"] = "CLOSE_SHORT"
                    result["score"] = 90
                    result["details"] = {"reason": reason, "rsi": round(rsi, 1)}
                    logger.warning(f"⚠️ Confirmed Reversal for SHORT {symbol}: {reason} | RSI: {rsi:.1f}")
            
        except Exception as e:
            logger.error(f"❌ Error checking reversal {symbol}: {e}")
        
        return result

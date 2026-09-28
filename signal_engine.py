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

import time
from datetime import datetime
import pandas as pd
import ta as ta_lib
import config
from logger_setup import logger


class SignalEngine:
    """Engine analisis teknikal institusional berbasis Trend-Pullback & Rejection."""
    
    def __init__(self, exchange):
        self.exchange = exchange
        self._last_btc_check_time = 0
        self._cached_btc_bias = "neutral"
        self._cached_btc_rsi_15m = 50.0
        self._cached_btc_15m_pct = 0.0
        self._cached_btc_15m_drop = 0.0
        self._cached_btc_15m_surge = 0.0
        self._cached_dom_chg = 0.0
        self._cached_dom_time = 0
        self._flash_lock_until = 0
        self._flash_lock_bias = None
    
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

    def _get_btc_bias(self):
        """
        Evaluasi arah Bitcoin (BTC) sebagai nakhoda pasar crypto.
        Returns:
            str: 'bullish' | 'bearish' | 'neutral'
        """
        now = time.time()
        if now - self._last_btc_check_time < 60:
            return self._cached_btc_bias
            
        btc_symbol = getattr(config, "BTC_SYMBOL", "BTC/USDT")
        try:
            df_1h = self.fetch_candles(btc_symbol, config.HIGHER_TIMEFRAME)
            if df_1h.empty:
                return "neutral"
            df_1h = self.calculate_indicators(df_1h)
            if df_1h.empty or len(df_1h) < 2:
                return "neutral"
                
            last_1h = df_1h.iloc[-1]
            ema_21 = last_1h.get("ema_21", 0)
            ema_55 = last_1h.get("ema_55", 0)
            close_1h = last_1h["close"]
            
            # Cek momentum 15m BTC untuk deteksi dump/pump mendadak
            df_15m = self.fetch_candles(btc_symbol, config.TRADING_TIMEFRAME)
            if not df_15m.empty and len(df_15m) >= 3:
                df_15m = self.calculate_indicators(df_15m)
                last_15m = df_15m.iloc[-1]
                prev_15m = df_15m.iloc[-2]
                rsi_15m = float(last_15m.get("rsi", 50))
                
                open_15m = float(last_15m["open"])
                low_15m = float(last_15m["low"])
                high_15m = float(last_15m["high"])
                close_15m = float(last_15m["close"])
                
                btc_flash_thresh = getattr(config, "BTC_FLASH_DUMP_THRESHOLD_PERCENT", 0.50)
                # Deteksi flash dump / pump kilat di lilin 15m (melihat Close DAN Low/High jarum live)
                btc_15m_pct = ((close_15m - open_15m) / open_15m) * 100 if open_15m > 0 else 0.0
                btc_15m_drop = ((low_15m - open_15m) / open_15m) * 100 if open_15m > 0 else 0.0
                btc_15m_surge = ((high_15m - open_15m) / open_15m) * 100 if open_15m > 0 else 0.0
                
                is_flash_dump_15m = (btc_15m_pct <= -btc_flash_thresh) or (btc_15m_drop <= -0.45) or (btc_15m_pct <= -0.35 and close_15m < float(prev_15m["low"]))
                is_flash_pump_15m = (btc_15m_pct >= +btc_flash_thresh) or (btc_15m_surge >= +0.45) or (btc_15m_pct >= +0.35 and close_15m > float(prev_15m["high"]))
            else:
                rsi_15m = 50
                is_flash_dump_15m = False
                is_flash_pump_15m = False
                btc_15m_pct = 0.0
                btc_15m_drop = 0.0
                btc_15m_surge = 0.0
            
            bias = "neutral"
            lock_duration = getattr(config, "BTC_FLASH_LOCK_MINUTES", 15) * 60

            if is_flash_dump_15m:
                bias = "bearish"
                self._flash_lock_until = now + lock_duration
                self._flash_lock_bias = "bearish"
                logger.warning(f"🚨 BTC Flash Dump terdeteksi di 15m (Drop: {btc_15m_drop:+.2f}%, Chg: {btc_15m_pct:+.2f}%)! Lock BEARISH {lock_duration//60}m aktif (Blokir LONG).")
            elif is_flash_pump_15m:
                bias = "bullish"
                self._flash_lock_until = now + lock_duration
                self._flash_lock_bias = "bullish"
                logger.info(f"🚀 BTC Flash Pump terdeteksi di 15m (Surge: {btc_15m_surge:+.2f}%, Chg: {btc_15m_pct:+.2f}%)! Lock BULLISH {lock_duration//60}m aktif (Blokir SHORT).")
            elif now < self._flash_lock_until and self._flash_lock_bias:
                bias = self._flash_lock_bias
                rem_m = (self._flash_lock_until - now) / 60
                logger.info(f"🛡️ BTC Flash {self._flash_lock_bias.upper()} Lock aktif (Sisa: {rem_m:.1f}m) - Mengunci arah pasar dari whipsaw.")
            elif ema_21 > ema_55 and close_1h > ema_55:
                # Jika 1h bullish tapi 15m mendadak dump (RSI < 40), jangan sebut bullish
                if rsi_15m < 40:
                    bias = "neutral"
                else:
                    bias = "bullish"
            elif ema_21 < ema_55 and close_1h < ema_55:
                # Jika 1h bearish tapi 15m mendadak pump (RSI > 60), jangan sebut bearish
                if rsi_15m > 60:
                    bias = "neutral"
                else:
                    bias = "bearish"
                    
            self._last_btc_check_time = now
            self._cached_btc_bias = bias
            self._cached_btc_rsi_15m = rsi_15m
            self._cached_btc_15m_pct = btc_15m_pct
            self._cached_btc_15m_drop = btc_15m_drop
            self._cached_btc_15m_surge = btc_15m_surge
            logger.info(f"🧭 BTC Market Regime: {bias.upper()} (1H Close: {close_1h:.1f}, 15m RSI: {rsi_15m:.1f}, 15m Chg: {btc_15m_pct:+.2f}%)")
            return bias
        except Exception as e:
            logger.warning(f"⚠️ Gagal evaluasi BTC bias: {e}")
            return "neutral"

    def _get_dom_momentum(self) -> float:
        """Ambil momentum perubahan BTCDOM di timeframe 15m (cached 30 detik)."""
        now = time.time()
        if now - getattr(self, "_cached_dom_time", 0) < 30:
            return getattr(self, "_cached_dom_chg", 0.0)
            
        try:
            dom_sym = getattr(config, "DOM_SYMBOL", "BTCDOM/USDT")
            df = self.fetch_candles(dom_sym, config.TRADING_TIMEFRAME, limit=3)
            if not df.empty and len(df) >= 1:
                last_c = df.iloc[-1]
                open_p = float(last_c.get("open", 0))
                close_p = float(last_c.get("close", 0))
                if open_p > 0:
                    chg = ((close_p - open_p) / open_p) * 100.0
                    self._cached_dom_chg = chg
                    self._cached_dom_time = now
                    return chg
        except Exception as e:
            logger.debug(f"Gagal fetch BTCDOM di signal engine: {e}")
            
        return 0.0

    def _get_btc_rsi_15m(self):
        """Ambil nilai RSI 15m BTC terkini (cache / fresh)."""
        self._get_btc_bias()
        return getattr(self, "_cached_btc_rsi_15m", 50.0)

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
            
        # 2. Anti-Climax Overbought Filter: Jangan beli jika dalam 8 candle terakhir (2 jam) baru saja meletup overbought
        lookback_climax = getattr(config, "ANTI_CLIMAX_LOOKBACK_CANDLES", 8)
        max_climax_rsi = getattr(config, "ANTI_CLIMAX_MAX_RSI", 70.0)
        recent_rsi = df_15m["rsi"].iloc[-lookback_climax:]
        if (recent_rsi > max_climax_rsi).any():
            return False, 0, {"reason": f"recent_overbought_climax_rsi_{recent_rsi.max():.1f}"}
            
        # 3. Risk Distance to EMA 55: Jarak entry ke benteng EMA 55 tidak boleh > 1.35% (agar resiko cut loss kecil)
        max_risk_dist = getattr(config, "MAX_ENTRY_RISK_EMA55_PERCENT", 1.35)
        dist_to_ema55 = ((last["close"] - ema_55) / last["close"]) * 100 if last["close"] > 0 else 0
        if dist_to_ema55 > max_risk_dist:
            return False, 0, {"reason": f"risk_to_ema55_too_wide_{dist_to_ema55:.2f}%"}
            
        # 4. Overextended Check: Jangan beli kalau harga sudah terbang > 1.5% di atas EMA 21
        distance_to_ema = ((last["close"] - ema_21) / ema_21) * 100
        if distance_to_ema > 1.5:
            return False, 0, {"reason": f"overextended_{distance_to_ema:.2f}%"}
            
        # 5. Pullback Zone Check: Dalam 3 candle terakhir, harga harus sempat menyentuh/menguji area EMA 21
        min_low_recent = recent_3["low"].min()
        if min_low_recent > ema_21 * 1.004:
            return False, 0, {"reason": "no_pullback_to_ema_zone"}
            
        # 6. Candlestick Price Action: Wajib ada rejection wick bawah kuat (>= 35%)
        candle_range = last["high"] - last["low"]
        if candle_range <= 0:
            return False, 0, {"reason": "flat_candle"}
            
        body = abs(last["close"] - last["open"])
        lower_wick = min(last["open"], last["close"]) - last["low"]
        lower_wick_ratio = lower_wick / candle_range
        is_green_candle = last["close"] >= last["open"]
        is_engulfing = (last["close"] > prev["open"] and last["open"] <= prev["close"] and is_green_candle)
        
        min_wick_ratio = getattr(config, "MIN_ENTRY_REJECTION_WICK_PERCENT", 22.0) / 100.0
        if lower_wick_ratio < min_wick_ratio:
            return False, 0, {"reason": f"weak_lower_wick_{lower_wick_ratio*100:.1f}%"}
            
        if last["close"] < ema_21 * 0.998:
            return False, 0, {"reason": "close_below_ema21"}
            
        # 7. RSI Sweet Spot (40 s/d 65): punya ruang untuk naik kencang
        if rsi < 40 or rsi > 68:
            return False, 0, {"reason": f"rsi_out_of_sweet_spot_{rsi:.1f}"}
            
        # 8. Volume Validation
        vol_ratio = vol / vol_sma if vol_sma > 0 else 1.0
        if vol_ratio < config.MIN_VOLUME_RATIO:
            return False, 0, {"reason": f"volume_too_low_{vol_ratio:.2f}x"}
            
        # Scoring kalkulasi
        score = 80
        if lower_wick_ratio >= 0.45:
            score += 10
        elif lower_wick_ratio >= 0.35:
            score += 5
        if is_engulfing:
            score += 5
        if vol_ratio >= 1.2:
            score += 5
            
        details = {
            "setup": "TPLR_LONG",
            "lower_wick_pct": f"{lower_wick_ratio*100:.1f}%",
            "rsi": round(rsi, 1),
            "vol_ratio": f"{vol_ratio:.2f}x",
            "dist_ema": f"{distance_to_ema:+.2f}%",
            "risk_ema55": f"{dist_to_ema55:.2f}%",
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
            
        # 2. Anti-Climax Oversold Filter: Jangan short jika dalam 8 candle terakhir baru saja meletup oversold
        lookback_climax = getattr(config, "ANTI_CLIMAX_LOOKBACK_CANDLES", 8)
        min_climax_rsi = getattr(config, "ANTI_CLIMAX_MIN_RSI", 30.0)
        recent_rsi = df_15m["rsi"].iloc[-lookback_climax:]
        if (recent_rsi < min_climax_rsi).any():
            return False, 0, {"reason": f"recent_oversold_climax_rsi_{recent_rsi.min():.1f}"}
            
        # 3. Risk Distance to EMA 55: Jarak entry ke benteng EMA 55 tidak boleh > 1.35%
        max_risk_dist = getattr(config, "MAX_ENTRY_RISK_EMA55_PERCENT", 1.35)
        dist_to_ema55 = ((ema_55 - last["close"]) / last["close"]) * 100 if last["close"] > 0 else 0
        if dist_to_ema55 > max_risk_dist:
            return False, 0, {"reason": f"risk_to_ema55_too_wide_{dist_to_ema55:.2f}%"}
            
        # 4. Overextended Check: Jangan sell kalau harga sudah jatuh > 1.5% di bawah EMA 21
        distance_to_ema = ((ema_21 - last["close"]) / ema_21) * 100
        if distance_to_ema > 1.5:
            return False, 0, {"reason": f"overextended_down_{distance_to_ema:.2f}%"}
            
        # 5. Pullback Zone Check: Dalam 3 candle terakhir, harga harus sempat rally/retest area EMA 21
        max_high_recent = recent_3["high"].max()
        if max_high_recent < ema_21 * 0.996:
            return False, 0, {"reason": "no_retest_to_ema_zone"}
            
        # 6. Candlestick Price Action: Wajib ada rejection wick atas kuat (>= 22%)
        candle_range = last["high"] - last["low"]
        if candle_range <= 0:
            return False, 0, {"reason": "flat_candle"}
            
        upper_wick = last["high"] - max(last["open"], last["close"])
        upper_wick_ratio = upper_wick / candle_range
        is_red_candle = last["close"] <= last["open"]
        is_engulfing = (last["close"] < prev["open"] and last["open"] >= prev["close"] and is_red_candle)
        
        min_wick_ratio = getattr(config, "MIN_ENTRY_REJECTION_WICK_PERCENT", 22.0) / 100.0
        if upper_wick_ratio < min_wick_ratio:
            return False, 0, {"reason": f"weak_upper_wick_{upper_wick_ratio*100:.1f}%"}
            
        if last["close"] > ema_21 * 1.002:
            return False, 0, {"reason": "close_above_ema21"}
            
        # 7. RSI Sweet Spot (32 s/d 60): punya ruang untuk dump
        if rsi < 32 or rsi > 60:
            return False, 0, {"reason": f"rsi_out_of_sweet_spot_{rsi:.1f}"}
            
        # 8. Volume Validation
        vol_ratio = vol / vol_sma if vol_sma > 0 else 1.0
        if vol_ratio < config.MIN_VOLUME_RATIO:
            return False, 0, {"reason": f"volume_too_low_{vol_ratio:.2f}x"}
            
        # Scoring kalkulasi
        score = 80
        if upper_wick_ratio >= 0.45:
            score += 10
        elif upper_wick_ratio >= 0.35:
            score += 5
        if is_engulfing:
            score += 5
        if vol_ratio >= 1.2:
            score += 5
            
        details = {
            "setup": "TPLR_SHORT",
            "upper_wick_pct": f"{upper_wick_ratio*100:.1f}%",
            "rsi": round(rsi, 1),
            "vol_ratio": f"{vol_ratio:.2f}x",
            "dist_ema": f"{distance_to_ema:+.2f}%",
            "risk_ema55": f"{dist_to_ema55:.2f}%",
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
            
            # Cek BTC Regime Filter (Nakhoda Pasar)
            btc_filter_on = getattr(config, "BTC_FILTER_ENABLED", True)
            btc_symbol = getattr(config, "BTC_SYMBOL", "BTC/USDT")
            is_btc = (symbol == btc_symbol or symbol.startswith("BTC/"))
            btc_bias = self._get_btc_bias() if (btc_filter_on and not is_btc) else "neutral"
            
            # Cek izin tren 1H (Strict vs Toleransi Neutral)
            strict_htf = getattr(config, "STRICT_HTF_REQUIRED", True)
            if strict_htf:
                can_long = (macro_trend == "bullish")
                can_short = (macro_trend == "bearish")
            else:
                can_long = macro_trend in ("bullish", "neutral")
                can_short = macro_trend in ("bearish", "neutral")
                
            # Filter BTC Regime: Smart mode (Satpam Anti-Crash) vs Strict mode
            if btc_filter_on and not is_btc:
                btc_mode = getattr(config, "BTC_FILTER_MODE", "smart")
                now = time.time()
                is_flash_locked = (now < self._flash_lock_until)
                btc_rsi_15m = self._get_btc_rsi_15m()
                
                # Traffic Light RSI 15m BTC (Lantai Dasar & Pucuk Guard)
                btc_rsi_oversold = getattr(config, "BTC_CHOP_RSI_OVERSOLD", 38.0)
                btc_rsi_overbought = getattr(config, "BTC_CHOP_RSI_OVERBOUGHT", 65.0)
                
                if can_short and btc_rsi_15m < btc_rsi_oversold:
                    logger.info(f"🚫 SHORT {symbol} diblokir: RSI 15m BTC ({btc_rsi_15m:.1f}) di lantai dasar (< {btc_rsi_oversold})! Anti-short saat rawan dead-cat bounce.")
                    can_short = False
                    
                if can_long and btc_rsi_15m > btc_rsi_overbought:
                    logger.info(f"🚫 LONG {symbol} diblokir: RSI 15m BTC ({btc_rsi_15m:.1f}) di pucuk jenuh (> {btc_rsi_overbought})! Anti-buy saat rawan koreksi.")
                    can_long = False
                
                if btc_mode == "smart":
                    # 1. Jika BTC AKTIF Flash Crash / Dump (lock aktif): Blokir LONG mutlak!
                    if is_flash_locked and self._flash_lock_bias == "bearish" and can_long:
                        rem_m = (self._flash_lock_until - now) / 60
                        logger.info(f"🚫 LONG {symbol} diblokir: BTC sedang Flash Crash / Dump aktif (Lock {rem_m:.1f}m)!")
                        can_long = False
                    # 2. Kebalikannya: Jika BTC AKTIF Flash Pump (lock aktif): Blokir SHORT mutlak!
                    elif is_flash_locked and self._flash_lock_bias == "bullish" and can_short:
                        rem_m = (self._flash_lock_until - now) / 60
                        logger.info(f"🚫 SHORT {symbol} diblokir: BTC sedang Flash Pump aktif (Lock {rem_m:.1f}m)!")
                        can_short = False
                    # 3. Saat BTC 1H Bearish tapi TIDAK sedang Flash Dump (15m tenang):
                    # Izinkan LONG HANYA jika koin ini tren 1H-nya murni BULLISH (Koin kuat decoupling seperti PEPE/XRP)
                    elif btc_bias == "bearish" and can_long and macro_trend != "bullish":
                        logger.info(f"🚫 LONG {symbol} diblokir: BTC Bearish & HTF 1H koin ini ({macro_trend}) bukan Bullish murni")
                        can_long = False
                    # 4. Kebalikannya saat BTC 1H Bullish tapi TIDAK sedang Flash Pump (15m tenang):
                    # Izinkan SHORT HANYA jika koin ini tren 1H-nya murni BEARISH (Koin lemah decoupling)
                    elif btc_bias == "bullish" and can_short and macro_trend != "bearish":
                        logger.info(f"🚫 SHORT {symbol} diblokir: BTC Bullish & HTF 1H koin ini ({macro_trend}) bukan Bearish murni")
                        can_short = False
                else:
                    # Strict Mode (Legacy kaku)
                    if btc_bias == "bearish" and can_long:
                        logger.info(f"🚫 LONG {symbol} diblokir oleh BTC Filter: BTC Regime sedang BEARISH")
                        can_long = False
                    elif btc_bias == "bullish" and can_short:
                        logger.info(f"🚫 SHORT {symbol} diblokir oleh BTC Filter: BTC Regime sedang BULLISH")
                        can_short = False
            
            if not can_long and not can_short:
                reason = "htf_not_trending" if strict_htf and macro_trend == "neutral" else "btc_filter_conflict"
                result["details"] = {"reason": reason, "macro_trend": macro_trend, "btc_bias": btc_bias}
                return result
                 
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
            
            # Hanya cari LONG jika lolos HTF & BTC filter
            if can_long:
                is_long, score_long, details_long = self._check_pullback_long(df_15m)
                if is_long:
                    # Validasi Anti-Berenang Melawan Arus BTC (Super Anomaly Check):
                    if btc_filter_on and not is_btc and btc_bias == "bearish":
                        anomaly_min_score = getattr(config, "ANOMALY_MIN_SCORE", 85)
                        anomaly_min_vol = getattr(config, "ANOMALY_MIN_VOL_RATIO", 1.45)
                        try:
                            vol_r = float(str(details_long.get("vol_ratio", "1.0")).replace("x", ""))
                        except Exception:
                            vol_r = 1.0
                        if score_long < anomaly_min_score or vol_r < anomaly_min_vol:
                            logger.info(
                                f"🚫 LONG {symbol} dibatalkan: BTC Bearish & Altcoin bukan super anomali "
                                f"(Score: {score_long}/{anomaly_min_score}, Vol: {vol_r:.2f}x/{anomaly_min_vol}x)"
                            )
                            is_long = False

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
            
            # Hanya cari SHORT jika lolos HTF & BTC filter
            if can_short:
                is_short, score_short, details_short = self._check_pullback_short(df_15m)
                if is_short:
                    # Validasi Anti-Berenang Melawan Arus BTC (Super Anomaly Check):
                    if btc_filter_on and not is_btc and btc_bias == "bullish":
                        anomaly_min_score = getattr(config, "ANOMALY_MIN_SCORE", 85)
                        anomaly_min_vol = getattr(config, "ANOMALY_MIN_VOL_RATIO", 1.45)
                        try:
                            vol_r = float(str(details_short.get("vol_ratio", "1.0")).replace("x", ""))
                        except Exception:
                            vol_r = 1.0
                        if score_short < anomaly_min_score or vol_r < anomaly_min_vol:
                            logger.info(
                                f"🚫 SHORT {symbol} dibatalkan: BTC Bullish & Altcoin bukan super anomali "
                                f"(Score: {score_short}/{anomaly_min_score}, Vol: {vol_r:.2f}x/{anomaly_min_vol}x)"
                            )
                            is_short = False

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
    
    def check_reversal(self, symbol, current_side, entry_time=None, entry_price=None):
        """
        Deteksi pembalikan arah dinamis pada TF 15m dengan proteksi tingkat lanjut:
        1. Grace Period (15m pertama): Tidak memotong posisi hanya karena goyangan candle awal.
        2. Timestamp Validator: Hanya membaca candle yang resmi tutup SETELAH entry (anti-SUI 12s bug).
        3. Buffer Filter: Penutupan lilin wajib tembus minimal 0.6% di bawah/atas EMA 55 (anti-0.05% noise cut).
        4. Crash Emergency: Penurunan live > 1.4% tetap dipotong instan untuk keselamatan.
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
            
            solid_break_pct = getattr(config, "REVERSAL_SOLID_BREAKDOWN_PERCENT", 1.08) / 100.0
            buffer_pct = getattr(config, "REVERSAL_EMA_BREAKDOWN_BUFFER_PERCENT", 0.58) / 100.0
            grace_min = getattr(config, "REVERSAL_GRACE_PERIOD_MINUTES", 15)
            
            trade_age_min = 999.0
            entry_ts_ms = 0.0
            if entry_time:
                try:
                    if isinstance(entry_time, str):
                        entry_dt = datetime.fromisoformat(entry_time)
                    else:
                        entry_dt = entry_time
                    trade_age_min = (datetime.now() - entry_dt).total_seconds() / 60.0
                    entry_ts_ms = entry_dt.timestamp() * 1000.0
                except Exception as e:
                    logger.debug(f"Error parsing entry_time {entry_time}: {e}")
            
            in_grace_period = trade_age_min < grace_min
            
            # Waktu candle prev: open time + 15 menit = close time
            prev_ts = prev.get("timestamp", 0)
            if hasattr(prev_ts, "timestamp"):
                prev_ts_ms = prev_ts.timestamp() * 1000.0
            else:
                prev_ts_ms = float(prev_ts) if prev_ts else 0.0
            prev_close_ts = prev_ts_ms + (15 * 60 * 1000.0)
            # Candle lampau (tutup sebelum entry) tidak boleh memicu breakdown
            is_prev_candle_valid = (entry_ts_ms <= 0) or (prev_close_ts >= (entry_ts_ms - 30000))
            
            # Cek status BTC dan momentum candle untuk deteksi dump/pump mendadak
            now_ts = time.time()
            btc_bias = self._get_btc_bias()
            # Fast Cut HANYA aktif jika BTC benar-benar sedang Flash Crash / Dump aktif (bukan sekadar tren 1h statis)
            is_btc_dumping = (now_ts < self._flash_lock_until and self._flash_lock_bias == "bearish")
            is_btc_pumping = (now_ts < self._flash_lock_until and self._flash_lock_bias == "bullish")
            
            # Momentum lilin koin itu sendiri (15m)
            open_price = float(last.get("open", close))
            candle_chg_pct = ((float(close) - open_price) / open_price) * 100 if open_price > 0 else 0.0
            is_alt_dumping = (candle_chg_pct <= -0.5) or (float(close) < float(prev.get("low", 0)) and candle_chg_pct <= -0.3)
            is_alt_pumping = (candle_chg_pct >= +0.5) or (float(close) > float(prev.get("high", 0)) and candle_chg_pct >= +0.3)
            
            # Deteksi Rejection Wick koin sendiri (shock absorber anti-cut saat candle kagetan pantul V-shape)
            candle_h = float(last.get("high", close))
            candle_l = float(last.get("low", close))
            candle_rng = candle_h - candle_l
            lower_wick_pct = ((min(open_price, float(close)) - candle_l) / candle_rng * 100.0) if candle_rng > 0 else 0.0
            upper_wick_pct = ((candle_h - max(open_price, float(close))) / candle_rng * 100.0) if candle_rng > 0 else 0.0
            wick_protect_thresh = getattr(config, "MACRO_WICK_RECOVERY_PROTECT_PERCENT", 28.0)
            is_wick_recovering_long = (lower_wick_pct >= wick_protect_thresh)
            is_wick_recovering_short = (upper_wick_pct >= wick_protect_thresh)

            # Cek status Makro (BTC live candle & BTCDOM momentum)
            dom_chg = self._get_dom_momentum()
            btc_15m_pct = getattr(self, "_cached_btc_15m_pct", 0.0)
            btc_15m_drop = getattr(self, "_cached_btc_15m_drop", 0.0)
            btc_15m_surge = getattr(self, "_cached_btc_15m_surge", 0.0)

            macro_cut_enabled = getattr(config, "MACRO_PRESSURE_CUT_ENABLED", True)
            macro_btc_drop_thresh = getattr(config, "MACRO_BTC_PRESSURE_DROP_PERCENT", 0.32)
            macro_dom_surge_thresh = getattr(config, "MACRO_DOM_PRESSURE_SURGE_PERCENT", 0.12)
            macro_ema_cut_thresh = getattr(config, "MACRO_PRESSURE_EMA_CUT_PERCENT", 0.54) / 100.0
            
            fast_cut_enabled = getattr(config, "REVERSAL_DUMP_FAST_CUT_ENABLED", True)
            dump_cut_thresh = getattr(config, "REVERSAL_DUMP_FAST_CUT_THRESHOLD_PERCENT", 0.54) / 100.0
            
            if current_side == "long":
                # Reversal LONG:
                # 1. Closed candle resmi tutup >= 0.52% di bawah EMA 55 (wajib tutup setelah entry & lewat grace period)
                # 2. ATAU Solid breakdown live > 0.78% di bawah EMA 55 (mutlak tanpa Grace Period)
                # 3. ATAU Dead Cross EMA 21 tembus ke bawah EMA 55 (setelah grace period)
                # 4. ATAU Macro Pressure Cut (Opsi A): Jika BTC drop >= 0.32% ATAU BTCDOM naik >= 0.12%
                #    DAN harga tembus 0.54% di bawah EMA 55 -> BYPASS Grace Period & Tebas instan!
                # 5. ATAU Normal Fast Dump Cut (setelah grace period)
                prev_ema55 = prev.get("ema_55", 0)
                is_closed_breakdown = (
                    is_prev_candle_valid and
                    (not in_grace_period) and
                    prev["close"] < (prev_ema55 * (1.0 - buffer_pct)) and
                    prev_ema55 > 0
                )
                is_solid_breakdown = close < (ema_55 * (1.0 - solid_break_pct)) and ema_55 > 0
                is_dead_cross = (not in_grace_period) and (ema_21 < ema_55 and prev.get("ema_21", 0) >= prev.get("ema_55", 0))
                
                # Tekanan makro melawan posisi LONG:
                is_btc_pressuring_down = (is_btc_dumping or btc_15m_pct <= -macro_btc_drop_thresh or btc_15m_drop <= -macro_btc_drop_thresh)
                is_dom_pressuring_up = (dom_chg >= macro_dom_surge_thresh)
                is_macro_adverse_long = is_btc_pressuring_down or is_dom_pressuring_up
                is_below_macro_ema = close < (ema_55 * (1.0 - macro_ema_cut_thresh)) and ema_55 > 0
                
                # Opsi A: Macro Pressure Cut:
                # Jangan panik cut saat posisi baru buka (< 15m) hanya gara-gara fluktuasi kecil BTC (-0.32%).
                # Di dalam Grace Period, Macro Cut HANYA boleh bypass jika BTC BENAR-BENAR Flash Crash nyata (is_btc_dumping).
                can_macro_cut = (not in_grace_period) or is_btc_dumping
                is_macro_cut_long = macro_cut_enabled and can_macro_cut and is_macro_adverse_long and is_below_macro_ema and (not is_wick_recovering_long)

                # Normal Fast cut di bawah EMA 55 (setelah lewat grace period 7m):
                is_below_ema55 = close < (ema_55 * (1.0 - dump_cut_thresh)) and ema_55 > 0
                is_normal_fast_cut_long = fast_cut_enabled and (not in_grace_period) and is_below_ema55 and (is_btc_dumping or is_alt_dumping)
                
                if is_closed_breakdown or is_solid_breakdown or is_dead_cross or is_macro_cut_long or is_normal_fast_cut_long:
                    if is_macro_cut_long:
                        press_cause = "BTC_DROP" if is_btc_pressuring_down else "BTCDOM_SURGE"
                        reason = f"macro_pressure_cut_0.54% ({press_cause} BTC:{btc_15m_pct:+.2f}%, DOM:{dom_chg:+.2f}%, Alt:{candle_chg_pct:+.2f}%)"
                    elif is_normal_fast_cut_long:
                        reason = f"dump_below_ema55_0.54% (BTC:{'BEAR' if is_btc_dumping else 'OK'}, Alt:{candle_chg_pct:+.2f}%)"
                    elif is_solid_breakdown:
                        reason = "solid_breakdown"
                    elif is_closed_breakdown:
                        reason = "closed_below_ema55_with_buffer"
                    else:
                        reason = "dead_cross_ema21_55"
                    result["reversed"] = True
                    result["signal"] = "CLOSE_LONG"
                    result["score"] = 90
                    result["details"] = {
                        "reason": reason,
                        "rsi": round(rsi, 1),
                        "trade_age_min": round(trade_age_min, 1),
                        "dist_ema55": f"{((close - ema_55) / ema_55 * 100):.2f}%"
                    }
                    logger.warning(f"⚠️ Confirmed Reversal for LONG {symbol}: {reason} | RSI: {rsi:.1f} | Age: {trade_age_min:.1f}m")
                    
            elif current_side == "short":
                # Reversal SHORT:
                prev_ema55 = prev.get("ema_55", 0)
                is_closed_breakout = (
                    is_prev_candle_valid and
                    (not in_grace_period) and
                    prev["close"] > (prev_ema55 * (1.0 + buffer_pct)) and
                    prev_ema55 > 0
                )
                is_solid_breakout = close > (ema_55 * (1.0 + solid_break_pct)) and ema_55 > 0
                is_golden_cross = (not in_grace_period) and (ema_21 > ema_55 and prev.get("ema_21", 0) <= prev.get("ema_55", 0))
                
                # Tekanan makro melawan posisi SHORT:
                is_btc_pressuring_up = (is_btc_pumping or btc_15m_pct >= macro_btc_drop_thresh or btc_15m_surge >= macro_btc_drop_thresh)
                is_dom_pressuring_down = (dom_chg <= -macro_dom_surge_thresh)
                is_macro_adverse_short = is_btc_pressuring_up or is_dom_pressuring_down
                is_above_macro_ema = close > (ema_55 * (1.0 + macro_ema_cut_thresh)) and ema_55 > 0
                
                # Opsi A: Macro Pressure Cut SHORT:
                can_macro_cut_short = (not in_grace_period) or is_btc_pumping
                is_macro_cut_short = macro_cut_enabled and can_macro_cut_short and is_macro_adverse_short and is_above_macro_ema and (not is_wick_recovering_short)

                # Normal Fast cut di atas EMA 55 (setelah lewat grace period 7m):
                # Catatan: Jika BTC tenang (OK), jangan panik cut saat lilin 15m running baru pump tipis (anti-wick shakeout).
                # Cut instan hanya berlaku jika BTC ikut pump, ATAU lilin altcoin benar-benar pump solid (candle_chg_pct >= +1.0%).
                is_above_ema55 = close > (ema_55 * (1.0 + dump_cut_thresh)) and ema_55 > 0
                is_alt_deep_pumping = (candle_chg_pct >= +1.0)
                is_normal_fast_cut_short = fast_cut_enabled and (not in_grace_period) and is_above_ema55 and (is_btc_pumping or is_alt_deep_pumping)
                
                if is_closed_breakout or is_solid_breakout or is_golden_cross or is_macro_cut_short or is_normal_fast_cut_short:
                    if is_macro_cut_short:
                        press_cause = "BTC_PUMP" if is_btc_pressuring_up else "BTCDOM_DUMP"
                        reason = f"macro_pressure_cut_0.54% ({press_cause} BTC:{btc_15m_pct:+.2f}%, DOM:{dom_chg:+.2f}%, Alt:{candle_chg_pct:+.2f}%)"
                    elif is_normal_fast_cut_short:
                        reason = f"pump_above_ema55_0.54% (BTC:{'BULL' if is_btc_pumping else 'OK'}, Alt:{candle_chg_pct:+.2f}%)"
                    elif is_solid_breakout:
                        reason = "solid_breakout"
                    elif is_closed_breakout:
                        reason = "closed_above_ema55_with_buffer"
                    else:
                        reason = "golden_cross_ema21_55"
                    result["reversed"] = True
                    result["signal"] = "CLOSE_SHORT"
                    result["score"] = 90
                    result["details"] = {
                        "reason": reason,
                        "rsi": round(rsi, 1),
                        "trade_age_min": round(trade_age_min, 1),
                        "dist_ema55": f"{((close - ema_55) / ema_55 * 100):.2f}%"
                    }
                    logger.warning(f"⚠️ Confirmed Reversal for SHORT {symbol}: {reason} | RSI: {rsi:.1f} | Age: {trade_age_min:.1f}m")
            
        except Exception as e:
            logger.error(f"❌ Error checking reversal {symbol}: {e}")
        
        return result

    def check_exhaustion(self, symbol, current_side, current_price, entry_price):
        """
        Deteksi Buying / Selling Climax (Exhaustion) saat harga menyentuh pucuk/dasar ekstrem.
        Membaca konfluensi candle 15m: Rejection Wick, RSI Overbought/Oversold, Jarak EMA 21,
        Volume Climax, dan konfirmasi bahwa harga sudah tergelincir dari puncak candle.
        
        Returns:
            dict: {
                "exhausted": bool,
                "reason": str,
                "details": dict
            }
        """
        result = {
            "exhausted": False,
            "reason": "",
            "details": {}
        }
        
        if not getattr(config, "EXHAUSTION_EXIT_ENABLED", False):
            return result
            
        try:
            df = self.fetch_candles(symbol, config.TRADING_TIMEFRAME)
            if df.empty or len(df) < 3:
                return result
                
            df = self.calculate_indicators(df)
            if df.empty:
                return result
                
            last = df.iloc[-1]
            high = float(last["high"])
            low = float(last["low"])
            open_p = float(last["open"])
            close_p = float(last["close"])
            volume = float(last["volume"])
            vol_sma = float(last.get("vol_sma", 0))
            ema_21 = float(last.get("ema_21", 0))
            rsi = float(last.get("rsi", 50))
            
            candle_range = high - low
            if candle_range <= 0:
                return result
                
            matched_criteria = []
            
            wick_thresh = getattr(config, "EXHAUSTION_WICK_PERCENT", 32.0)
            ema_thresh = getattr(config, "EXHAUSTION_EMA_DIST_PERCENT", 2.0)
            vol_thresh = getattr(config, "EXHAUSTION_VOLUME_RATIO", 1.8)
            pullback_thresh = getattr(config, "EXHAUSTION_PULLBACK_PERCENT", 0.4)
            min_confluence = getattr(config, "EXHAUSTION_MIN_CONFLUENCE", 2)
            
            if current_side == "long":
                upper_wick = high - max(open_p, close_p)
                upper_wick_pct = (upper_wick / candle_range) * 100.0
                pullback_pct = ((high - current_price) / high) * 100.0 if high > 0 else 0.0
                dist_ema = ((current_price - ema_21) / ema_21) * 100.0 if ema_21 > 0 else 0.0
                vol_ratio = (volume / vol_sma) if vol_sma > 0 else 1.0
                rsi_ob = getattr(config, "EXHAUSTION_RSI_OVERBOUGHT", 73.0)
                
                cond_wick = upper_wick_pct >= wick_thresh
                cond_rsi = rsi >= rsi_ob
                cond_ema = dist_ema >= ema_thresh
                cond_vol = vol_ratio >= vol_thresh
                cond_pullback = pullback_pct >= pullback_thresh
                
                if cond_wick:
                    matched_criteria.append(f"upper_wick_{upper_wick_pct:.1f}%")
                if cond_rsi:
                    matched_criteria.append(f"rsi_ob_{rsi:.1f}")
                if cond_ema:
                    matched_criteria.append(f"ema21_ext_{dist_ema:+.1f}%")
                if cond_vol:
                    matched_criteria.append(f"vol_spike_{vol_ratio:.1f}x")
                    
                result["details"] = {
                    "upper_wick_pct": round(upper_wick_pct, 1),
                    "rsi": round(rsi, 1),
                    "dist_ema_pct": round(dist_ema, 2),
                    "vol_ratio": round(vol_ratio, 2),
                    "pullback_from_high_pct": round(pullback_pct, 2),
                    "matched": matched_criteria
                }
                
                # Syarat eksekusi: Tergelincir dari high + Rejection wick + minimal N konfluensi
                if cond_wick and cond_pullback and len(matched_criteria) >= min_confluence:
                    result["exhausted"] = True
                    result["reason"] = (
                        f"Buying Climax Exhaustion on {symbol} (LONG) | "
                        f"Wick: {upper_wick_pct:.1f}% >= {wick_thresh}%, "
                        f"Pullback: -{pullback_pct:.2f}%, "
                        f"Signals: {', '.join(matched_criteria)}"
                    )
                    logger.warning(f"🚀 {result['reason']}")
                    
            elif current_side == "short":
                lower_wick = min(open_p, close_p) - low
                lower_wick_pct = (lower_wick / candle_range) * 100.0
                pullback_pct = ((current_price - low) / low) * 100.0 if low > 0 else 0.0
                dist_ema = ((ema_21 - current_price) / ema_21) * 100.0 if ema_21 > 0 else 0.0
                vol_ratio = (volume / vol_sma) if vol_sma > 0 else 1.0
                rsi_os = getattr(config, "EXHAUSTION_RSI_OVERSOLD", 27.0)
                
                cond_wick = lower_wick_pct >= wick_thresh
                cond_rsi = rsi <= rsi_os
                cond_ema = dist_ema >= ema_thresh
                cond_vol = vol_ratio >= vol_thresh
                cond_pullback = pullback_pct >= pullback_thresh
                
                if cond_wick:
                    matched_criteria.append(f"lower_wick_{lower_wick_pct:.1f}%")
                if cond_rsi:
                    matched_criteria.append(f"rsi_os_{rsi:.1f}")
                if cond_ema:
                    matched_criteria.append(f"ema21_ext_{dist_ema:+.1f}%")
                if cond_vol:
                    matched_criteria.append(f"vol_spike_{vol_ratio:.1f}x")
                    
                result["details"] = {
                    "lower_wick_pct": round(lower_wick_pct, 1),
                    "rsi": round(rsi, 1),
                    "dist_ema_pct": round(dist_ema, 2),
                    "vol_ratio": round(vol_ratio, 2),
                    "pullback_from_low_pct": round(pullback_pct, 2),
                    "matched": matched_criteria
                }
                
                if cond_wick and cond_pullback and len(matched_criteria) >= min_confluence:
                    result["exhausted"] = True
                    result["reason"] = (
                        f"Selling Climax Exhaustion on {symbol} (SHORT) | "
                        f"Wick: {lower_wick_pct:.1f}% >= {wick_thresh}%, "
                        f"Bounce: +{pullback_pct:.2f}%, "
                        f"Signals: {', '.join(matched_criteria)}"
                    )
                    logger.warning(f"🚀 {result['reason']}")
                    
        except Exception as e:
            logger.error(f"❌ Error checking exhaustion {symbol}: {e}")
            
        return result

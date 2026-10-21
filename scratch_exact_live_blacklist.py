import os, sys
sys.path.append(os.path.abspath("."))
sys.path.append(os.path.abspath("backtest"))
import config
from run_exact_vps_backtest import ExactVPSBacktest

def is_blacklisted(symbol):
    clean = symbol.replace(":USDT", "").replace("/USDT", "").split("/")[0]
    for b in config.BLACKLIST_COINS:
        b_clean = b.replace(":USDT", "").replace("/USDT", "").split("/")[0]
        if clean == b_clean or symbol == b:
            return True
    return False

class RealLiveVPSBacktest(ExactVPSBacktest):
    def __init__(self, use_anti_bleeding=False, min_1h_rejection_wick=0.0):
        super().__init__(initial_capital=287.0, margin_per_trade=245.0, leverage=3)
        self.use_anti_bleeding = use_anti_bleeding
        self.min_1h_rejection_wick = min_1h_rejection_wick

    def scan_for_entry(self, ts):
        btc_regime = self.get_btc_regime(ts)
        hour_ts = ts - (ts % (3600 * 1000))
        candidates = []
        
        for symbol, df15 in self.data_15m.items():
            # 1. CEK BLACKLIST PERSIS LIVE BOT
            if is_blacklisted(symbol):
                continue
                
            idx15 = self.ts_map_15m[symbol].get(ts)
            if idx15 is None or idx15 < 55:
                continue
            df1 = self.data_1h.get(symbol)
            idx1 = self.ts_map_1h[symbol].get(hour_ts)
            if df1 is None or idx1 is None or idx1 < 55:
                continue
                
            curr15 = df15.iloc[idx15]
            curr1 = df1.iloc[idx1]
            
            macro_bullish = curr1['close'] > curr1['ema50'] and curr1['ema20'] > curr1['ema50']
            macro_bearish = curr1['close'] < curr1['ema50'] and curr1['ema20'] < curr1['ema50']
            
            vol_ratio = curr15.get('vol_ratio', 1.0)
            if vol_ratio < config.MIN_VOLUME_RATIO:
                continue
                
            # Filter Anti Bleeding 3 Lilin 1H
            is_bleeding_drop = False
            is_bleeding_surge = False
            if self.use_anti_bleeding and idx1 >= 3:
                recent_1h = df1.iloc[idx1-2:idx1+1]
                all_red = all(row['close'] < row['open'] for _, row in recent_1h.iterrows())
                all_green = all(row['close'] > row['open'] for _, row in recent_1h.iterrows())
                
                # Cek wick lilin 1H terakhir jika diaktifkan
                rng_1h = curr1['high'] - curr1['low']
                lower_wick_1h = (min(curr1['open'], curr1['close']) - curr1['low']) / rng_1h if rng_1h > 0 else 0
                upper_wick_1h = (curr1['high'] - max(curr1['open'], curr1['close'])) / rng_1h if rng_1h > 0 else 0
                
                if all_red:
                    if self.min_1h_rejection_wick > 0:
                        if lower_wick_1h < self.min_1h_rejection_wick:
                            is_bleeding_drop = True
                    else:
                        is_bleeding_drop = True
                        
                if all_green:
                    if self.min_1h_rejection_wick > 0:
                        if upper_wick_1h < self.min_1h_rejection_wick:
                            is_bleeding_surge = True
                    else:
                        is_bleeding_surge = True

            if config.STRICT_HTF_REQUIRED:
                can_long = macro_bullish and (btc_regime in ["bullish", "neutral"]) and not is_bleeding_drop
                can_short = macro_bearish and (btc_regime in ["bearish", "neutral"]) and not is_bleeding_surge
            else:
                can_long = (btc_regime in ["bullish", "neutral"]) and not is_bleeding_drop
                can_short = (btc_regime in ["bearish", "neutral"]) and not is_bleeding_surge
                
            atr_pct = curr15.get('atr_pct', 1.0)
            price = curr15['close']
            ema20 = curr15['ema20']
            ema50 = curr15['ema50']
            
            if can_long:
                is_uptrend_15m = curr15['ema20'] > curr15['ema50']
                near_ema20 = abs(price - ema20) / ema20 * 100 <= 0.8
                near_ema50 = abs(price - ema50) / ema50 * 100 <= 1.0
                wick_ok = curr15['lower_wick_pct'] >= config.MIN_ENTRY_REJECTION_WICK_PERCENT
                rsi_ok = 38 <= curr15['rsi'] <= 68
                
                if (near_ema20 or near_ema50) and wick_ok and rsi_ok and is_uptrend_15m:
                    score = 70
                    if macro_bullish: score += 10
                    if btc_regime == "bullish": score += 5
                    if vol_ratio >= 1.2: score += 5
                    if curr15['lower_wick_pct'] >= 35: score += 5
                    if score >= config.SIGNAL_MIN_SCORE:
                        candidates.append({'symbol': symbol, 'side': 'long', 'score': score, 'price': price, 'atr_pct': atr_pct, 'timestamp': ts})
                        
            if can_short:
                is_downtrend_15m = curr15['ema20'] < curr15['ema50']
                near_ema20 = abs(price - ema20) / ema20 * 100 <= 0.8
                near_ema50 = abs(price - ema50) / ema50 * 100 <= 1.0
                wick_ok = curr15['upper_wick_pct'] >= config.MIN_ENTRY_REJECTION_WICK_PERCENT
                rsi_ok = 32 <= curr15['rsi'] <= 62
                
                if (near_ema20 or near_ema50) and wick_ok and rsi_ok and is_downtrend_15m:
                    score = 70
                    if macro_bearish: score += 10
                    if btc_regime == "bearish": score += 5
                    if vol_ratio >= 1.2: score += 5
                    if curr15['upper_wick_pct'] >= 35: score += 5
                    if score >= config.SIGNAL_MIN_SCORE:
                        candidates.append({'symbol': symbol, 'side': 'short', 'score': score, 'price': price, 'atr_pct': atr_pct, 'timestamp': ts})
                        
        if not candidates:
            return None
        candidates.sort(key=lambda x: x['score'], reverse=True)
        return candidates[0]

def main():
    print("Mempersiapkan data dan menerapkan BLACKLIST 100% PERSIS VPS...")
    base_engine = ExactVPSBacktest()
    base_engine.load_all_data()
    
    # 1. Baseline RIIL (Kondisi Bot VPS Saat Ini dengan Blacklist Aktif)
    print("\n--- RUNNING BASELINE RIIL LIVE BOT (BLACKLIST AKTIF) ---")
    live_base = RealLiveVPSBacktest(use_anti_bleeding=False)
    live_base.data_15m = base_engine.data_15m
    live_base.data_1h = base_engine.data_1h
    live_base.ts_map_15m = base_engine.ts_map_15m
    live_base.ts_map_1h = base_engine.ts_map_1h
    live_base.btc_15m = base_engine.btc_15m
    live_base.btc_1h = base_engine.btc_1h
    live_base.run()
    
    # 2. Live Bot + Anti Bleeding 3 Lilin 1H (Strict)
    print("\n--- RUNNING LIVE BOT + ANTI BLEEDING 3 LILIN 1H ---")
    live_knife = RealLiveVPSBacktest(use_anti_bleeding=True, min_1h_rejection_wick=0.0)
    live_knife.data_15m = base_engine.data_15m
    live_knife.data_1h = base_engine.data_1h
    live_knife.ts_map_15m = base_engine.ts_map_15m
    live_knife.ts_map_1h = base_engine.ts_map_1h
    live_knife.btc_15m = base_engine.btc_15m
    live_knife.btc_1h = base_engine.btc_1h
    live_knife.run()
    
    # 3. Live Bot + Anti Bleeding 3 Lilin 1H + Rejection Wick 30%
    print("\n--- RUNNING LIVE BOT + ANTI BLEEDING 1H WICK 30% ---")
    live_wick = RealLiveVPSBacktest(use_anti_bleeding=True, min_1h_rejection_wick=0.30)
    live_wick.data_15m = base_engine.data_15m
    live_wick.data_1h = base_engine.data_1h
    live_wick.ts_map_15m = base_engine.ts_map_15m
    live_wick.ts_map_1h = base_engine.ts_map_1h
    live_wick.btc_15m = base_engine.btc_15m
    live_wick.btc_1h = base_engine.btc_1h
    live_wick.run()
    
    print("\n" + "="*70)
    print("DETAIL ANALISIS PERBANDINGAN RIIL (DENGAN BLACKLIST BOT LIVE)")
    print("="*70)
    
    base_t = live_base.trades
    knife_t = live_knife.trades
    wick_t = live_wick.trades
    
    print(f"1. BASELINE RIIL (VPS Saat Ini) : {len(base_t)} trade | Cuan Net: {live_base.balance - 287.0:+.2f} USDT | Saldo: ${live_base.balance:.2f}")
    print(f"2. DENGAN FILTER 3 LILIN 1H     : {len(knife_t)} trade | Cuan Net: {live_knife.balance - 287.0:+.2f} USDT | Saldo: ${live_knife.balance:.2f}")
    print(f"3. DENGAN WICK 1H >= 30%        : {len(wick_t)} trade | Cuan Net: {live_wick.balance - 287.0:+.2f} USDT | Saldo: ${live_wick.balance:.2f}")

    # Cek yang terdenied dari Baseline vs Filter 3 Lilin 1H
    base_keys = set((t["entry_time"], t["symbol"], t["side"]) for t in base_t)
    knife_keys = set((t["entry_time"], t["symbol"], t["side"]) for t in knife_t)
    
    denied = [t for t in base_t if (t["entry_time"], t["symbol"], t["side"]) not in knife_keys]
    denied_wins = [t for t in denied if t["net_pnl"] > 0.05]
    denied_loss = [t for t in denied if t["net_pnl"] < -0.05]
    
    print(f"\n[DARI BASELINE RIIL]: Total trade yang ter-denied oleh 3 lilin 1H: {len(denied)} trade")
    print(f"  - Menang ter-denied: {len(denied_wins)} trade")
    print(f"  - Kalah berhasil dicegah: {len(denied_loss)} trade")
    
    print("\nDAFTAR SEMUA KOIN MENANG RIIL YANG TER-DENIED:")
    for t in sorted(denied_wins, key=lambda x: x["net_pnl"], reverse=True):
        clean_sym = t["symbol"].replace(":USDT", "").replace("/USDT", "").split("/")[0]
        et = t["entry_time"]
        sd = t["side"]
        pnl = t["net_pnl"]
        pk = t["highest_p"]
        rs = t["reason"]
        print(f"  * {et} | {clean_sym} ({sd}) | Cuan: +{pnl:.2f} USDT | Peak: +{pk:.2f}% | Alasan: {rs}")
        
    print("\nDAFTAR TOP 10 KOIN KALAH RIIL YANG BERHASIL DIBLOKIR:")
    for t in sorted(denied_loss, key=lambda x: x["net_pnl"])[:10]:
        clean_sym = t["symbol"].replace(":USDT", "").replace("/USDT", "").split("/")[0]
        et = t["entry_time"]
        sd = t["side"]
        pnl = t["net_pnl"]
        dd = t["max_dd_p"]
        rs = t["reason"]
        print(f"  - {et} | {clean_sym} ({sd}) | Rugi: {pnl:.2f} USDT | Drawdown: -{dd:.2f}% | Alasan: {rs}")
        
    # Koin baru yang terambil
    new_trades = [t for t in knife_t if (t["entry_time"], t["symbol"], t["side"]) not in base_keys]
    new_wins = [t for t in new_trades if t["net_pnl"] > 0.05]
    print(f"\nDAFTAR TOP 10 KOIN JUARA BARU RIIL YANG BERHASIL DIAMBIL (Total {len(new_wins)} trade baru menang):")
    for t in sorted(new_wins, key=lambda x: x["net_pnl"], reverse=True)[:10]:
        clean_sym = t["symbol"].replace(":USDT", "").replace("/USDT", "").split("/")[0]
        et = t["entry_time"]
        sd = t["side"]
        pnl = t["net_pnl"]
        pk = t["highest_p"]
        rs = t["reason"]
        print(f"  + {et} | {clean_sym} ({sd}) | Cuan: +{pnl:.2f} USDT | Peak: +{pk:.2f}% | Alasan: {rs}")

if __name__ == "__main__":
    main()

import os, sys
sys.path.append(os.path.abspath("."))
sys.path.append(os.path.abspath("backtest"))
import config
from scratch_exact_live_blacklist import is_blacklisted
from run_exact_vps_backtest import ExactVPSBacktest

class VolumeGateBacktest(ExactVPSBacktest):
    def __init__(self, super_wick_min_vol=0.50, default_min_vol=0.80):
        super().__init__(initial_capital=287.0, margin_per_trade=245.0, leverage=3)
        self.super_wick_min_vol = super_wick_min_vol
        self.default_min_vol = default_min_vol

    def scan_for_entry(self, ts):
        btc_regime = self.get_btc_regime(ts)
        hour_ts = ts - (ts % (3600 * 1000))
        candidates = []
        
        for symbol, df15 in self.data_15m.items():
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
            
            # CEK SUPER WICK DISCOUNT
            # Apakah candle punya super wick >= 50%?
            lower_wick_pct = curr15.get('lower_wick_pct', 0)
            upper_wick_pct = curr15.get('upper_wick_pct', 0)
            
            # Hitung minimum volume dinamis
            min_vol_long = self.default_min_vol
            if lower_wick_pct >= 50.0:
                min_vol_long = min(min_vol_long, self.super_wick_min_vol)
                
            min_vol_short = self.default_min_vol
            if upper_wick_pct >= 50.0:
                min_vol_short = min(min_vol_short, self.super_wick_min_vol)

            if config.STRICT_HTF_REQUIRED:
                can_long = macro_bullish and (btc_regime in ["bullish", "neutral"]) and (vol_ratio >= min_vol_long)
                can_short = macro_bearish and (btc_regime in ["bearish", "neutral"]) and (vol_ratio >= min_vol_short)
            else:
                can_long = (btc_regime in ["bullish", "neutral"]) and (vol_ratio >= min_vol_long)
                can_short = (btc_regime in ["bearish", "neutral"]) and (vol_ratio >= min_vol_short)
                
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
    print("Loading data...")
    base_engine = ExactVPSBacktest()
    base_engine.load_all_data()

    # Skenario 1: SUPER_WICK_MIN_VOL = 0.50 (Diskon Volume Aktif, ZK Bisa Lolos)
    print("\n--- SKENARIO 1: SUPER_WICK_MIN_VOL = 0.50 (Status Quo) ---")
    s1 = VolumeGateBacktest(super_wick_min_vol=0.50, default_min_vol=0.80)
    s1.data_15m = base_engine.data_15m
    s1.data_1h = base_engine.data_1h
    s1.ts_map_15m = base_engine.ts_map_15m
    s1.ts_map_1h = base_engine.ts_map_1h
    s1.btc_15m = base_engine.btc_15m
    s1.btc_1h = base_engine.btc_1h
    s1.run()
    
    # Skenario 2: SUPER_WICK_MIN_VOL = 0.80 (Diskon Ditutup, Syarat Tetap Sehat >= 0.80x)
    print("\n--- SKENARIO 2: KUNCI LUBANG VOLUME (SUPER_WICK_MIN_VOL = 0.80) ---")
    s2 = VolumeGateBacktest(super_wick_min_vol=0.80, default_min_vol=0.80)
    s2.data_15m = base_engine.data_15m
    s2.data_1h = base_engine.data_1h
    s2.ts_map_15m = base_engine.ts_map_15m
    s2.ts_map_1h = base_engine.ts_map_1h
    s2.btc_15m = base_engine.btc_15m
    s2.btc_1h = base_engine.btc_1h
    s2.run()

    # Perbandingan
    t1 = s1.trades
    t2 = s2.trades
    keys1 = set((t["entry_time"], t["symbol"], t["side"]) for t in t1)
    keys2 = set((t["entry_time"], t["symbol"], t["side"]) for t in t2)
    
    blocked = [t for t in t1 if (t["entry_time"], t["symbol"], t["side"]) not in keys2]
    new_t = [t for t in t2 if (t["entry_time"], t["symbol"], t["side"]) not in keys1]

    print("\n" + "="*70)
    print("HASIL ANALISIS PENGUNCIAN LUBANG VOLUME 0.50x -> 0.80x")
    print("="*70)
    print(f"Skenario 1 (Ada Diskon 0.50x): {len(t1)} Trade | Profit Net: {s1.balance - 287.0:+.2f} USDT | MDD: -{s1.max_drawdown:.2f} USDT")
    print(f"Skenario 2 (Terkunci 0.80x)  : {len(t2)} Trade | Profit Net: {s2.balance - 287.0:+.2f} USDT | MDD: -{s2.max_drawdown:.2f} USDT")
    
    print(f"\nTrade yang terblokir saat diskon 0.50x ditutup: {len(blocked)} trade")
    blocked_wins = [t for t in blocked if t["net_pnl"] > 0.05]
    blocked_loss = [t for t in blocked if t["net_pnl"] < -0.05]
    print(f"  - Menang terblokir: {len(blocked_wins)} trade")
    print(f"  - Kalah terblokir: {len(blocked_loss)} trade")
    
    if blocked_loss:
        print("\nContoh Trade Rugi yang Terblokir:")
        for t in blocked_loss[:5]:
            sym = t["symbol"].replace(":USDT", "").replace("/USDT", "").split("/")[0]
            print(f"  - {t['entry_time']} | {sym} ({t['side']}) | Rugi: {t['net_pnl']:.2f} USDT | Alasan: {t['reason']}")
            
    if blocked_wins:
        print("\nContoh Trade Menang yang Terblokir:")
        for t in blocked_wins[:5]:
            sym = t["symbol"].replace(":USDT", "").replace("/USDT", "").split("/")[0]
            print(f"  * {t['entry_time']} | {sym} ({t['side']}) | Cuan: +{t['net_pnl']:.2f} USDT | Alasan: {t['reason']}")

if __name__ == "__main__":
    main()

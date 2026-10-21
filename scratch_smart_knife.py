import os, sys
sys.path.append(os.path.abspath("."))
sys.path.append(os.path.abspath("backtest"))
import config
from run_exact_vps_backtest import ExactVPSBacktest

class TestSmartKnife(ExactVPSBacktest):
    def __init__(self, min_vol=0.80, whale_override_vol=1.20):
        super().__init__(initial_capital=287.0, margin_per_trade=245.0, leverage=3)
        self.min_vol = min_vol
        self.whale_override_vol = whale_override_vol

    def load_all_data(self):
        if not self.data_15m:
            super().load_all_data()

    def scan_for_entry(self, ts):
        btc_regime = self.get_btc_regime(ts)
        hour_ts = ts - (ts % (3600 * 1000))
        candidates = []
        
        for symbol, df15 in self.data_15m.items():
            if "BTC" in symbol:
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
            if vol_ratio < self.min_vol:
                continue
                
            # Smart Anti-Bleeding Check:
            # 3 lilin 1H berturut-turut merah/hijau
            is_bleeding_drop = False
            is_bleeding_surge = False
            if idx1 >= 3:
                recent_1h = df1.iloc[idx1-2:idx1+1]
                all_red = all(row['close'] < row['open'] for _, row in recent_1h.iterrows())
                all_green = all(row['close'] > row['open'] for _, row in recent_1h.iterrows())
                
                # Pintu penyelamat: Kalau ada volume paus (>= whale_override_vol), diampuni!
                if all_red and vol_ratio < self.whale_override_vol:
                    is_bleeding_drop = True
                if all_green and vol_ratio < self.whale_override_vol:
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

def run():
    print("Loading data...")
    base = ExactVPSBacktest()
    base.load_all_data()
    
    # 1. Baseline
    print("\n--- Running Baseline ---")
    base.run()
    
    # 2. Smart Knife Test (Whale Override 1.20x)
    print("\n--- Running Smart Knife Filter (Whale Override >= 1.20x) ---")
    smart = TestSmartKnife(min_vol=0.80, whale_override_vol=1.20)
    smart.data_15m = base.data_15m
    smart.data_1h = base.data_1h
    smart.ts_map_15m = base.ts_map_15m
    smart.ts_map_1h = base.ts_map_1h
    smart.btc_15m = base.btc_15m
    smart.btc_1h = base.btc_1h
    smart.run()
    
    # Check champions status
    base_trades = base.trades
    smart_trades = smart.trades
    
    champions = ["GTC", "XPL", "SNXX", "MSTR", "LSK", "RKLB"]
    print("\nStatus Koin-Koin Juara di Smart Filter:")
    for champ in champions:
        found_in_base = [t for t in base_trades if champ in t['symbol'] and t['net_pnl'] > 5.0]
        found_in_smart = [t for t in smart_trades if champ in t['symbol'] and t['net_pnl'] > 5.0]
        print(f"  {champ}: Baseline ada {len(found_in_base)} win besar | Smart Filter ada {len(found_in_smart)} win besar")

if __name__ == "__main__":
    run()

import os, sys
sys.path.append(os.path.abspath("."))
sys.path.append(os.path.abspath("backtest"))
import config
from run_exact_vps_backtest import ExactVPSBacktest

class TestWickFilter(ExactVPSBacktest):
    def __init__(self, min_vol=0.80, min_1h_rejection_wick=0.30):
        super().__init__(initial_capital=287.0, margin_per_trade=245.0, leverage=3)
        self.min_vol = min_vol
        self.min_1h_rejection_wick = min_1h_rejection_wick

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
                
            # Cek 3 lilin 1H berturut-turut
            is_bleeding_drop = False
            is_bleeding_surge = False
            if idx1 >= 3:
                recent_1h = df1.iloc[idx1-2:idx1+1]
                all_red = all(row['close'] < row['open'] for _, row in recent_1h.iterrows())
                all_green = all(row['close'] > row['open'] for _, row in recent_1h.iterrows())
                
                # Cek wick lilin 1H terakhir (curr1):
                rng_1h = curr1['high'] - curr1['low']
                if rng_1h > 0:
                    lower_wick_1h = (min(curr1['open'], curr1['close']) - curr1['low']) / rng_1h
                    upper_wick_1h = (curr1['high'] - max(curr1['open'], curr1['close'])) / rng_1h
                else:
                    lower_wick_1h = 0
                    upper_wick_1h = 0
                    
                # Kalau 3 lilin merah, tapi lilin 1H punya lower wick kuat (rejection buyer kuat):
                # maka TIDAK dianggap bleeding!
                if all_red:
                    if lower_wick_1h < self.min_1h_rejection_wick:
                        is_bleeding_drop = True
                        
                if all_green:
                    if upper_wick_1h < self.min_1h_rejection_wick:
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
    
    wick_thresholds = [0.20, 0.30, 0.40, 0.50]
    for wth in wick_thresholds:
        bt = TestWickFilter(min_vol=0.80, min_1h_rejection_wick=wth)
        bt.data_15m = base.data_15m
        bt.data_1h = base.data_1h
        bt.ts_map_15m = base.ts_map_15m
        bt.ts_map_1h = base.ts_map_1h
        bt.btc_15m = base.btc_15m
        bt.btc_1h = base.btc_1h
        
        bt.run()
        total = len(bt.trades)
        wins = [t for t in bt.trades if t['net_pnl'] > 0.05]
        wr = len(wins) / total * 100 if total > 0 else 0
        net = bt.balance - bt.initial_capital
        print(f"\n[HASIL] Min 1H Wick Rejection: {wth*100:.0f}%")
        print(f"  Trades: {total} | Win Rate: {wr:.1f}% | Net Profit: {net:+.2f} USDT | Saldo Akhir: ${bt.balance:.2f}")

if __name__ == "__main__":
    run()

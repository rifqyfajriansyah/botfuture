import os
import sys
import glob
import time
import pandas as pd
import numpy as np

BOT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BOT_ROOT)
import config
from backtest_engine import calculate_indicators

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def load_data():
    data_15m = {}
    data_1h = {}
    ts_map_15m = {}
    ts_map_1h = {}
    btc_15m = None
    btc_1h = None
    
    files_15m = glob.glob(os.path.join(DATA_DIR, "*_15m.csv"))
    for f in files_15m:
        sym_clean = os.path.basename(f).replace("_15m.csv", "")
        f_1h = os.path.join(DATA_DIR, f"{sym_clean}_1h.csv")
        if not os.path.exists(f_1h):
            continue
        try:
            df15 = pd.read_csv(f)
            df1 = pd.read_csv(f_1h)
            if len(df15) < 300 or len(df1) < 100:
                continue
            df15 = calculate_indicators(df15, is_1h=False)
            df1 = calculate_indicators(df1, is_1h=True)
            symbol = sym_clean.replace("_USDT", "/USDT:USDT").replace("_", "/")
            if not symbol.endswith(":USDT"):
                symbol += ":USDT"
            data_15m[symbol] = df15
            data_1h[symbol] = df1
            ts_map_15m[symbol] = {ts: idx for idx, ts in enumerate(df15['timestamp'])}
            ts_map_1h[symbol] = {ts: idx for idx, ts in enumerate(df1['timestamp'])}
            if "BTC" in symbol:
                btc_15m = df15
                btc_1h = df1
        except Exception:
            continue
    return data_15m, data_1h, ts_map_15m, ts_map_1h, btc_15m, btc_1h

def run_simulation(start_trigger, trail_dist, data_15m, data_1h, ts_map_15m, ts_map_1h, btc_15m, btc_1h):
    initial_capital = 300.0
    balance = initial_capital
    margin = 250.0
    pos_size = margin * 3.0 # $750
    daily_target = initial_capital * 0.10 # $30
    
    trades = []
    active_trade = None
    cooldown_until = 0
    current_day = None
    daily_pnl = 0.0
    
    timestamps = sorted(btc_15m['timestamp'].tolist())
    
    for ts in timestamps:
        # Cek pergantian hari (UTC)
        day_str = time.strftime('%Y-%m-%d', time.gmtime(ts / 1000))
        if day_str != current_day:
            current_day = day_str
            daily_pnl = 0.0 # Reset target harian
            
        # Manage active trade
        if active_trade is not None:
            trade = active_trade
            sym = trade['symbol']
            side = trade['side']
            ep = trade['entry_price']
            
            df15 = data_15m.get(sym)
            idx15 = ts_map_15m.get(sym, {}).get(ts)
            if df15 is not None and idx15 is not None:
                bar = df15.iloc[idx15]
                high = bar['high']
                low = bar['low']
                close = bar['close']
                adx = bar.get('adx', 25.0)
                is_choppy = (adx < config.CHOPPY_ADX_THRESHOLD)
                
                if side == "long":
                    candle_max = ((high - ep) / ep) * 100
                    candle_min = ((low - ep) / ep) * 100
                    curr_profit = ((close - ep) / ep) * 100
                else:
                    candle_max = ((ep - low) / ep) * 100
                    candle_min = ((ep - high) / ep) * 100
                    curr_profit = ((ep - close) / ep) * 100
                    
                trade['highest_p'] = max(trade['highest_p'], candle_max)
                hp = trade['highest_p']
                
                # ATURAN USER: Koin Choppy + Target Harian Belum Tercapai (< $30)
                if is_choppy and daily_pnl < daily_target:
                    if hp >= start_trigger:
                        # Kawal ketat per jarak trail_dist
                        # Contoh: hp=0.60, trail_dist=0.20 -> lock=0.40
                        # hp=0.80 -> lock=0.60
                        lock_level = hp - trail_dist
                        # Jangan sampai lock di bawah BEP (+0.12%)
                        lock_level = max(0.12, lock_level)
                        if trade['stop_profit_level'] < lock_level:
                            trade['stop_profit_level'] = lock_level
                            if side == "long":
                                trade['stop_price'] = max(trade['stop_price'], ep * (1 + lock_level / 100))
                            else:
                                trade['stop_price'] = min(trade['stop_price'], ep * (1 - lock_level / 100))
                else:
                    # Trailing normal
                    if hp >= config.DYNAMIC_TP_MIN_PERCENT:
                        lock_level = hp - 0.45
                        if trade['stop_profit_level'] < lock_level:
                            trade['stop_profit_level'] = lock_level
                            if side == "long":
                                trade['stop_price'] = max(trade['stop_price'], ep * (1 + lock_level / 100))
                            else:
                                trade['stop_price'] = min(trade['stop_price'], ep * (1 - lock_level / 100))

                # Cek Stop Hit
                stop_hit = False
                if side == "long" and low <= trade['stop_price']:
                    stop_hit = True
                    exit_price = trade['stop_price']
                elif side == "short" and high >= trade['stop_price']:
                    stop_hit = True
                    exit_price = trade['stop_price']
                    
                if stop_hit:
                    pnl_pct = trade['stop_profit_level']
                    trade_pnl = pos_size * (pnl_pct / 100) - (pos_size * 0.0008)
                    if trade_pnl < -5.50: trade_pnl = -5.50
                    balance += trade_pnl
                    daily_pnl += trade_pnl
                    trades.append(trade_pnl)
                    active_trade = None
                    cooldown_until = ts + (60 * 60 * 1000)
                    continue
                    
                # Bounded cutloss
                if curr_profit <= -0.75:
                    pnl_pct = -0.75
                    trade_pnl = pos_size * (pnl_pct / 100) - (pos_size * 0.0008)
                    if trade_pnl < -5.50: trade_pnl = -5.50
                    balance += trade_pnl
                    daily_pnl += trade_pnl
                    trades.append(trade_pnl)
                    active_trade = None
                    cooldown_until = ts + (60 * 60 * 1000)
                    continue

        # Scan entry jika nganggur
        if active_trade is None and ts >= cooldown_until:
            hour_ts = ts - (ts % (3600 * 1000))
            for sym, df15 in data_15m.items():
                if "BTC" in sym: continue
                idx15 = ts_map_15m[sym].get(ts)
                if idx15 is None or idx15 < 55: continue
                df1 = data_1h.get(sym)
                idx1 = ts_map_1h[sym].get(hour_ts)
                if df1 is None or idx1 is None or idx1 < 55: continue
                
                curr15 = df15.iloc[idx15]
                curr1 = df1.iloc[idx1]
                
                if curr15.get('vol_ratio', 1.0) < 0.8: continue
                price = curr15['close']
                ema20 = curr15['ema20']
                ema50 = curr15['ema50']
                
                # Simple entry condition
                if curr15['ema20'] > curr15['ema50'] and abs(price - ema20)/ema20 * 100 <= 0.8 and curr15['lower_wick_pct'] >= 25:
                    active_trade = {
                        'symbol': sym,
                        'side': 'long',
                        'entry_price': price,
                        'stop_price': price * (1 - 1.15 / 100),
                        'stop_profit_level': -1.15,
                        'highest_p': 0.0
                    }
                    break
                elif curr15['ema20'] < curr15['ema50'] and abs(price - ema20)/ema20 * 100 <= 0.8 and curr15['upper_wick_pct'] >= 25:
                    active_trade = {
                        'symbol': sym,
                        'side': 'short',
                        'entry_price': price,
                        'stop_price': price * (1 + 1.15 / 100),
                        'stop_profit_level': -1.15,
                        'highest_p': 0.0
                    }
                    break

    # Evaluasi hasil
    if not trades:
        return 0, 0, 0, 0
    df_t = pd.Series(trades)
    wins = (df_t > 0).sum()
    total = len(df_t)
    win_rate = (wins / total) * 100
    net_pnl = balance - initial_capital
    gross_win = df_t[df_t > 0].sum()
    gross_loss = abs(df_t[df_t < 0].sum())
    pf = gross_win / (gross_loss + 1e-9)
    return net_pnl, win_rate, pf, total

if __name__ == "__main__":
    print("⏳ Memuat data 3 bulan (120 koin)...")
    d15, d1, t15, t1, b15, b1 = load_data()
    print("✅ Data dimuat. Menjalankan pengujian kombinasi parameter (Sweep Grid)...\n")
    
    triggers = [0.45, 0.50, 0.55, 0.60, 0.65]
    distances = [0.15, 0.18, 0.20, 0.25]
    
    results = []
    print(f"{'Mulai Aktif':12} | {'Jarak Kawal':12} | {'Net Cuan (USDT)':16} | {'Win Rate':10} | {'Profit Factor':14} | {'Total Trade'}")
    print("-" * 80)
    for trg in triggers:
        for dst in distances:
            if dst >= trg: continue
            net_pnl, wr, pf, tot = run_simulation(trg, dst, d15, d1, t15, t1, b15, b1)
            results.append({'trigger': trg, 'dist': dst, 'net_pnl': net_pnl, 'wr': wr, 'pf': pf, 'trades': tot})
            print(f"+{trg:.2f}%       | {dst:.2f}%       | {net_pnl:+8.2f} USDT     | {wr:5.1f}%    | {pf:6.2f}         | {tot}")
            
    df_res = pd.DataFrame(results)
    best = df_res.sort_values('net_pnl', ascending=False).iloc[0]
    print("\n" + "=" * 80)
    print(f"🏆 KOMBINASI TERBAIK SECARA MATEMATIS:")
    print(f"👉 Mulai Aktif : +{best['trigger']:.2f}%")
    print(f"👉 Jarak Kawal : {best['dist']:.2f}%")
    print(f"👉 Net Cuan    : +{best['net_pnl']:.2f} USDT")
    print(f"👉 Win Rate    : {best['wr']:.1f}%")
    print(f"👉 Profit Factor: {best['pf']:.2f}")
    print("=" * 80)

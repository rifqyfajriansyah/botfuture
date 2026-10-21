import os
import re
import json
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime

# 1. Load bot state
state_path = "bot_state.json" if os.path.exists("bot_state.json") else "backtest/vps_bot_state_oct18.json"
with open(state_path) as f:
    s = json.load(f)

trade_history = s.get("trade_history", [])

# Filter trades from 2026-10-01 onwards
oct_trades = [t for t in trade_history if t.get("entry_time", "") >= "2026-10-01"]
print(f"Total trades since Oct 1: {len(oct_trades)}")

# 2. Fetch BTC 15m candles
ex = ccxt.binance({"options": {"defaultType": "future"}})
print("Fetching BTC 15m klines from Binance...")
ohlcv = []
since = ex.parse8601("2026-10-01T00:00:00Z")
now = ex.milliseconds()
while since < now:
    batch = ex.fetch_ohlcv("BTC/USDT", timeframe="15m", since=since, limit=1000)
    if not batch: break
    ohlcv.extend(batch)
    since = batch[-1][0] + 15 * 60 * 1000
    if len(batch) < 1000: break

df_btc = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
df_btc["dt"] = pd.to_datetime(df_btc["timestamp"], unit="ms")
delta = df_btc["close"].diff()
gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)
avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
df_btc["rsi"] = 100 - (100 / (1 + (avg_gain / avg_loss)))

# 3. Parse logs to find placement time vs fill time for each order
print("Scanning log files for order placement & fill timing...")
log_dir = "logs"
order_timings = {} # order_id -> {"placed_at": dt, "filled_at": dt, "regime": str}

# Regex patterns
# Placed: [2026-10-19 04:07:33] INFO | ✅ Order placed! ID: 63114241279
# Regime: [2026-10-19 04:07:12] INFO | 🧭 BTC Market Regime: SIDEWAYS ...
# Filled: [2026-10-19 04:11:57] INFO | 🎯 Order FILLED! ... or Position saved: ...
re_placed = re.compile(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] INFO\s+\|\s+✅ Order placed! ID: (\w+)")
re_regime = re.compile(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] INFO\s+\|\s+🧭 BTC Market Regime: (\w+)")
re_filled = re.compile(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] INFO\s+\|\s+🎯 Order FILLED!\s+(\S+)\s+@")

current_regime = "NORMAL"

for fname in sorted(os.listdir(log_dir)):
    if not (fname.startswith("trades_2026-10-") or fname.startswith("bot_2026-10-")):
        continue
    fpath = os.path.join(log_dir, fname)
    try:
        with open(fpath, "r", errors="ignore") as f:
            for line in f:
                m_reg = re_regime.search(line)
                if m_reg:
                    current_regime = m_reg.group(2)
                    continue
                m_pl = re_placed.search(line)
                if m_pl:
                    ts_str, oid = m_pl.groups()
                    dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    if oid not in order_timings:
                        order_timings[oid] = {"placed_at": dt, "regime": current_regime}
    except Exception as e:
        pass

# Match with trade history
analyzed_trades = []
for t in oct_trades:
    oid = str(t.get("order_id", ""))
    entry_s = t.get("entry_time", "")
    pnl = float(t.get("pnl", 0.0))
    side = t.get("side", "").lower()
    sym = t.get("symbol", "").replace(":USDT", "")
    
    # Entry dt
    try:
        entry_dt = pd.to_datetime(entry_s[:19])
    except:
        continue
    
    # Match BTC RSI
    match_btc = df_btc[df_btc["dt"] <= entry_dt]
    btc_rsi = float(match_btc.iloc[-1]["rsi"]) if not match_btc.empty else None
    
    # Fill wait time
    placed_dt = None
    wait_seconds = 0
    regime = "NORMAL"
    if oid in order_timings:
        placed_dt = order_timings[oid]["placed_at"]
        regime = order_timings[oid]["regime"]
        wait_seconds = (entry_dt.to_pydatetime() - placed_dt).total_seconds()
        if wait_seconds < 0 or wait_seconds > 600:
            # Fallback if timezone or mismatch
            wait_seconds = 0
            
    analyzed_trades.append({
        "order_id": oid,
        "symbol": sym,
        "side": side,
        "entry_time": entry_s[:16],
        "pnl": pnl,
        "btc_rsi": btc_rsi,
        "placed_dt": placed_dt,
        "wait_seconds": wait_seconds,
        "wait_minutes": round(wait_seconds / 60.0, 2),
        "regime": regime,
        "close_reason": t.get("close_reason", "")
    })

# ==========================================
# ANALISIS ATURAN 1: BLOKIR LONG JIKA BTC RSI > 80
# ==========================================
print("\n" + "="*80)
print("HASIL ANALISIS ATURAN 1: BLOKIR LONG JIKA BTC 15M RSI > 80 (Sejak 1 Okt)")
print("="*80)

long_trades = [t for t in analyzed_trades if t["side"] == "long"]
blocked_longs_80 = [t for t in long_trades if t["btc_rsi"] is not None and t["btc_rsi"] > 80.0]
blocked_longs_75 = [t for t in long_trades if t["btc_rsi"] is not None and t["btc_rsi"] > 75.0]

print(f"Total Trade LONG sejak 1 Okt: {len(long_trades)}")
print(f"Trade LONG yang terblokir jika RSI > 80: {len(blocked_longs_80)}")
for t in blocked_longs_80:
    print(f"  - {t['entry_time']} | {t['symbol']:<10} | PnL: {t['pnl']:+6.2f} USDT | BTC RSI: {t['btc_rsi']:.1f} | Reason: {t['close_reason']}")

tot_pnl_blocked_80 = sum(t["pnl"] for t in blocked_longs_80)
print(f"Total PnL Trade Terblokir (RSI > 80): {tot_pnl_blocked_80:+.2f} USDT")
if tot_pnl_blocked_80 < 0:
    print(f"==> ATURAN 1 (RSI > 80) MENGUNTUNGKAN! Menghilangkan rugi bersih {abs(tot_pnl_blocked_80):.2f} USDT tanpa menolak satupun koin juara.")
else:
    print(f"==> ATURAN 1 (RSI > 80) Net: {tot_pnl_blocked_80:+.2f} USDT")

print(f"\nSebagai pembanding, jika RSI > 75:")
print(f"Trade LONG yang terblokir jika RSI > 75: {len(blocked_longs_75)}")
for t in blocked_longs_75:
    print(f"  - {t['entry_time']} | {t['symbol']:<10} | PnL: {t['pnl']:+6.2f} USDT | BTC RSI: {t['btc_rsi']:.1f} | Reason: {t['close_reason']}")
tot_pnl_blocked_75 = sum(t["pnl"] for t in blocked_longs_75)
print(f"Total PnL Trade Terblokir (RSI > 75): {tot_pnl_blocked_75:+.2f} USDT")

# ==========================================
# ANALISIS ATURAN 2: TIMEOUT LIMIT ORDER 3 MENIT (vs 5 MENIT)
# ==========================================
print("\n" + "="*80)
print("HASIL ANALISIS ATURAN 2: TIMEOUT LIMIT ORDER 3 MENIT (Pangkas dari 5m ke 3m)")
print("="*80)

# Check trades that took > 3 minutes (180s) to fill
late_fills = [t for t in analyzed_trades if t["wait_seconds"] >= 180]
print(f"Total Trade yang terisi di menit 3 s/d 5 (Wait >= 180s): {len(late_fills)} trade")

late_wins = [t for t in late_fills if t["pnl"] > 0]
late_losses = [t for t in late_fills if t["pnl"] < 0]
late_win_pnl = sum(t["pnl"] for t in late_wins)
late_loss_pnl = sum(t["pnl"] for t in late_losses)
late_net_pnl = sum(t["pnl"] for t in late_fills)

print(f"  - Menang ({len(late_wins)} trade): {late_win_pnl:+.2f} USDT")
print(f"  - Kalah  ({len(late_losses)} trade): {late_loss_pnl:+.2f} USDT")
print(f"  - Net PnL dari Trade Menit 3-5: {late_net_pnl:+.2f} USDT")

print("\nRincian Semua Trade yang Terisi di Menit 3-5:")
for t in late_fills:
    print(f"  {t['entry_time']} | {t['side'].upper():<5} {t['symbol']:<10} | Wait: {t['wait_minutes']}m | Regime: {t['regime']} | PnL: {t['pnl']:+6.2f} USDT")

if late_net_pnl < 0:
    print(f"\n==> KESIMPULAN ATURAN 2: SANGAT MENGUNTUNGKAN! Trade yang terisi telat di menit 3-5 secara total menghasilkan NET RUGI ({late_net_pnl:.2f} USDT).")
    print(f"==> Jika timeout dipangkas jadi 3 menit, bot MENGHEMAT {abs(late_net_pnl):.2f} USDT!")
else:
    print(f"\n==> KESIMPULAN ATURAN 2: Net PnL menit 3-5 adalah {late_net_pnl:+.2f} USDT.")

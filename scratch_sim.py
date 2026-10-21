import json
import re
import glob
import pandas as pd
from datetime import datetime, timedelta

with open("/home/ubuntu/binance-bot/bot_state.json") as f:
    d = json.load(f)

trades = [t for t in d.get("trade_history", []) if t.get("entry_time", "") >= "2026-10-17"]

files = sorted(glob.glob("/home/ubuntu/binance-bot/logs/bot_2026-10-*.log"))
log_content = ""
for fn in files:
    with open(fn, encoding="utf-8", errors="ignore") as f:
        log_content += f.read() + "\n"

pattern = re.compile(r"ENTRY SIGNAL: (LONG|SHORT) ([^\n]+)\n\s+Score: (\d+)/100[^\n]*\n\s+HTF Bias[^\n]*\n\s+Details: (\{[^\}]+\})")

entry_signals = {}
for m in pattern.finditer(log_content):
    side, sym, score, details_str = m.group(1), m.group(2).strip(), m.group(3), m.group(4)
    start_pos = max(0, m.start() - 250)
    snippet = log_content[start_pos:m.start()]
    ts_m = re.findall(r"\[(2026-10-\d\d \d\d:\d\d:\d\d)\]", snippet)
    if ts_m:
        ts = ts_m[-1]
        vol_m = re.search(r"'vol_ratio': '([^']+)x'", details_str)
        vol_val = float(vol_m.group(1)) if vol_m else 1.0
        wick_m = re.search(r"'(?:lower|upper)_wick_pct': '([^'%]+)%?'", details_str)
        wick_val = float(wick_m.group(1)) if wick_m else 0.0
        entry_signals[(sym, ts[:16])] = {"vol": vol_val, "wick": wick_val, "score": score}

print(f"Total parsed entry signals: {len(entry_signals)}")

enriched_trades = []
for t in trades:
    sym = t["symbol"]
    e_time = t.get("entry_time", "")
    e_dt = datetime.fromisoformat(e_time) if e_time else None
    
    found_sig = None
    if e_dt:
        for m_offset in range(-4, 5):
            check_key = (sym, (e_dt + timedelta(minutes=m_offset)).strftime("%Y-%m-%d %H:%M"))
            if check_key in entry_signals:
                found_sig = entry_signals[check_key]
                break
    
    vol = found_sig["vol"] if found_sig else None
    wick = found_sig["wick"] if found_sig else None
    
    enriched_trades.append({
        "symbol": sym.split("/")[0],
        "full_sym": sym,
        "side": t["side"],
        "entry_time": e_time,
        "close_time": t.get("close_time", ""),
        "pnl": t.get("pnl", 0),
        "hp": t.get("highest_profit_pct", 0),
        "lp": t.get("lowest_profit_pct", 0),
        "vol": vol,
        "wick": wick,
        "reason": t.get("close_reason", "")[:30]
    })

df = pd.DataFrame(enriched_trades)
print(f"Total trades since Saturday: {len(df)}")
print(f"Trades with volume data matched: {df['vol'].notna().sum()}/{len(df)}")

# Analysis 1: Volume correlation
win_df = df[df["pnl"] > 0]
loss_df = df[df["pnl"] <= 0]
print("\n=== 1. ANALISA VOLUME (WINS vs LOSSES) ===")
print(f"Avg Vol of Winners: {win_df['vol'].mean():.2f}x")
print(f"Avg Vol of Losers : {loss_df['vol'].mean():.2f}x")

# Simulation: What if we blocked trades with vol < 1.05x?
low_vol = df[df["vol"] < 1.05]
print(f"\nTrades with Volume < 1.05x: {len(low_vol)}")
for idx, r in low_vol.iterrows():
    print(f"  {r['symbol']:<8} | {r['side']:<5} | Vol: {r['vol']}x | PnL: {r['pnl']:+6.2f} | Reason: {r['reason']}")

low_vol_loss = low_vol[low_vol["pnl"] <= 0]["pnl"].sum()
low_vol_win = low_vol[low_vol["pnl"] > 0]["pnl"].sum()
print(f"Summary Vol < 1.05x: Wins: +{low_vol_win:.2f} | Losses: {low_vol_loss:.2f} | Net: {low_vol_win + low_vol_loss:.2f} USDT")

# Analysis 2: Cooldown 4h on losing coins
print("\n=== 2. ANALISA COOLDOWN 4 JAM PADA KOIN KALAH ===")
blocked_by_cooldown = []
last_loss_time = {}
for idx, r in df.iterrows():
    sym = r["full_sym"]
    e_dt = datetime.fromisoformat(r["entry_time"])
    pnl = r["pnl"]
    
    if sym in last_loss_time:
        diff_hours = (e_dt - last_loss_time[sym]).total_seconds() / 3600.0
        if diff_hours < 4.0:
            blocked_by_cooldown.append((r["symbol"], diff_hours, pnl, r["entry_time"]))
    
    if pnl < 0:
        c_dt = datetime.fromisoformat(r["close_time"]) if r["close_time"] else e_dt
        last_loss_time[sym] = c_dt

print(f"Trades that would have been BLOCKED by 4h Loss Cooldown: {len(blocked_by_cooldown)}")
total_saved_by_cooldown = 0
for b in blocked_by_cooldown:
    print(f"  {b[0]:<8} entered {b[1]:.1f}h after loss | PnL was: {b[2]:+6.2f} USDT | Time: {b[3][:16]}")
    total_saved_by_cooldown += b[2]
print(f"Net PnL impact of 4h Cooldown: {-total_saved_by_cooldown:+6.2f} USDT (Hemat uang)")

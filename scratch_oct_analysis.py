import json
from datetime import datetime

with open("backtest/vps_bot_state_oct18.json") as f:
    state = json.load(f)

trades = [t for t in state.get("trade_history", []) if t.get("entry_time", "") >= "2026-10-01"]

days = {}
for t in trades:
    d_str = t["entry_time"][:10]
    if d_str not in days:
        days[d_str] = []
    days[d_str].append(t)

print("DAY BY DAY ORIGINAL PERFORMANCE (1 - 18 Oct):")
print(f"{'Date':<12} | {'Trades':<6} | {'Wins':<5} | {'WR %':<6} | {'Original PnL':<14}")
print("-" * 55)

tot_orig = 0.0
for d in sorted(days.keys()):
    d_trades = days[d]
    d_wins = [t for t in d_trades if t.get("pnl", 0.0) > 0]
    d_pnl = sum(t.get("pnl", 0.0) for t in d_trades)
    tot_orig += d_pnl
    wr = len(d_wins) / len(d_trades) * 100 if d_trades else 0
    print(f"{d:<12} | {len(d_trades):<6} | {len(d_wins):<5} | {wr:<6.1f} | {d_pnl:+10.2f} USDT")

print("-" * 55)
total_wins = sum(1 for t in trades if t.get("pnl", 0) > 0)
print(f"{'TOTAL':<12} | {len(trades):<6} | {total_wins:<5} | {total_wins/len(trades)*100:<6.1f} | {tot_orig:+10.2f} USDT")

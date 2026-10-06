import sys
import os
import pandas as pd

BOT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BOT_ROOT)

from backtest_user_idea_snowball import UserIdeaSnowballBacktest

b = UserIdeaSnowballBacktest(initial_capital=287.0, leverage=3, margin_ratio=0.85)
b.load_all_data()

timestamps = sorted(b.btc_15m["timestamp"].tolist())
for ts in timestamps:
    if b.active_trade is not None:
        b.manage_active_trade(ts)
    if b.active_trade is None and ts >= b.cooldown_until:
        setup = b.scan_for_entry(ts)
        if setup:
            b.open_trade(setup)

df = pd.DataFrame(b.trades)
print("=" * 80)
print("🏆 DAFTAR 10 KOIN JUARA (SUPER ROKET) DENGAN SISTEM INI:")
print("=" * 80)
top_runners = df.sort_values("highest_p", ascending=False).head(10)
for _, r in top_runners.iterrows():
    sym = r["symbol"]
    side = r["side"].upper()
    hp = r["highest_p"]
    margin = r["margin"]
    pnl = r["net_pnl"]
    reason = r["reason"]
    print(f"- {sym:12} {side:5} | Peak Terbang: +{hp:5.2f}% | Margin: ${margin:3.0f} | Cuan Masuk: +${pnl:5.2f} USDT | Alasan Keluar: {reason}")
print("=" * 80)

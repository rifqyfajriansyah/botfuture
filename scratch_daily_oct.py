import json
import pandas as pd

with open("/home/ubuntu/binance-bot/bot_state.json") as f:
    d = json.load(f)

trades = [t for t in d.get("trade_history", []) if t.get("entry_time", "") >= "2026-10-01"]
df = pd.DataFrame(trades)
df["pnl"] = df["pnl"].astype(float)
df["entry_date"] = df["entry_time"].str[:10]

daily = df.groupby("entry_date").agg(
    trades=("pnl", "count"),
    wins=("pnl", lambda x: (x > 0).sum()),
    losses=("pnl", lambda x: (x <= 0).sum()),
    total_pnl=("pnl", "sum"),
    win_pnl=("pnl", lambda x: x[x > 0].sum()),
    loss_pnl=("pnl", lambda x: x[x <= 0].sum())
).reset_index()

daily["winrate"] = (daily["wins"] / daily["trades"]) * 100
daily["cum_pnl"] = daily["total_pnl"].cumsum()

print("=== REKAP HARIAN PERJALANAN BOT SEJAK 1 OKTOBER 2026 ===")
print("Tanggal      | Trades | Win/Loss | Winrate | Win USDT  | Loss USDT  | Net Hari  | Kumulatif")
print("-" * 88)
for idx, r in daily.iterrows():
    print(f"{r['entry_date']}   | {r['trades']:>6} | {r['wins']:>3}W/{r['losses']:>2}L | {r['winrate']:>6.1f}% | +{r['win_pnl']:>8.2f} | {r['loss_pnl']:>10.2f} | {r['total_pnl']:>+9.2f} | {r['cum_pnl']:>+9.2f}")

print("-" * 88)
wins_df = df[df['pnl'] > 0]
losses_df = df[df['pnl'] <= 0]
print(f"TOTAL: {len(df)} Trades | {len(wins_df)} Menang ({len(wins_df)/len(df)*100:.1f}%) | {len(losses_df)} Kalah")
print(f"Total Cuan  : +{wins_df['pnl'].sum():.2f} USDT (Avg Win : +{wins_df['pnl'].mean():.2f} USDT)")
print(f"Total Boncos: {losses_df['pnl'].sum():.2f} USDT (Avg Loss: {losses_df['pnl'].mean():.2f} USDT)")
print(f"Net Realized: {df['pnl'].sum():+.2f} USDT")

print("\n=== TOP 5 TRADE PALING CUAN SEJAK 1 OKT ===")
top_wins = df.sort_values("pnl", ascending=False).head(5)
for idx, r in top_wins.iterrows():
    print(f"  {r['symbol']:<15} | +{r['pnl']:>6.2f} USDT | {r['entry_time'][:16]} | {r.get('close_reason', '')[:35]}")

print("\n=== TOP 5 TRADE PALING BONCOS SEJAK 1 OKT ===")
top_losses = df.sort_values("pnl", ascending=True).head(5)
for idx, r in top_losses.iterrows():
    print(f"  {r['symbol']:<15} | {r['pnl']:>6.2f} USDT | {r['entry_time'][:16]} | {r.get('close_reason', '')[:35]}")

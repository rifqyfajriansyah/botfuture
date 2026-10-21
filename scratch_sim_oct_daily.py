import json
import pandas as pd

with open("/home/ubuntu/binance-bot/bot_state.json") as f:
    d = json.load(f)

trades = [t for t in d.get("trade_history", []) if t.get("entry_time", "") >= "2026-10-01"]
df = pd.DataFrame(trades)
df["pnl"] = df["pnl"].astype(float)
df["entry_dt"] = pd.to_datetime(df["entry_time"])
df["close_dt"] = pd.to_datetime(df["close_time"])
df["entry_date"] = df["entry_time"].str[:10]

# 1. Simulate Cooldown 4h & Smart Cut per trade
blocked_indices = set()
last_loss = {}

for idx, r in df.sort_values("entry_dt").iterrows():
    sym = r["symbol"]
    if sym in last_loss:
        diff_h = (r["entry_dt"] - last_loss[sym]).total_seconds() / 3600.0
        if diff_h < 4.0:
            blocked_indices.add(idx)
    if r["pnl"] < 0:
        c_dt = r["close_dt"] if pd.notna(r["close_dt"]) else r["entry_dt"]
        last_loss[sym] = c_dt

new_pnls = []
for idx, r in df.iterrows():
    if idx in blocked_indices:
        new_pnls.append(0.0) # Trade didn't happen
    else:
        orig = r["pnl"]
        if orig < -7.80:
            new_pnls.append(-7.80) # Capped at smart invalidation cut
        else:
            new_pnls.append(orig)

df["new_pnl"] = new_pnls
df["is_blocked"] = [i in blocked_indices for i in df.index]

daily = df.groupby("entry_date").agg(
    trades=("pnl", "count"),
    orig_pnl=("pnl", "sum"),
    new_pnl=("new_pnl", "sum"),
    saved=("pnl", lambda x: 0) # placeholder
).reset_index()

daily["diff"] = daily["new_pnl"] - daily["orig_pnl"]
daily["cum_orig"] = daily["orig_pnl"].cumsum()
daily["cum_new"] = daily["new_pnl"].cumsum()

print("=== PERBANDINGAN HARIAN: KONDISI ASLI VS JIKA DITERAPKAN (1 - 21 OKT) ===")
print("Tanggal      | Trades | PnL Asli    | PnL Baru (Diterapkan) | Uang Diselamatkan | Kumulatif Baru")
print("-" * 92)
for idx, r in daily.iterrows():
    sign = "+" if r['diff'] > 0 else " "
    print(f"{r['entry_date']}   | {r['trades']:>6} | {r['orig_pnl']:>+9.2f}   | {r['new_pnl']:>+17.2f}   | {sign}{r['diff']:>14.2f}    | {r['cum_new']:>+13.2f}")

print("-" * 92)
print(f"TOTAL AKHIR : {len(df)} Trades")
print(f"Saldo Asli Saat Ini    : {df['pnl'].sum():+.2f} USDT")
print(f"Saldo Baru (Diterapkan): {df['new_pnl'].sum():+.2f} USDT")
print(f"TOTAL UANG DIHEMAT     : +{df['new_pnl'].sum() - df['pnl'].sum():.2f} USDT (Rp {(df['new_pnl'].sum() - df['pnl'].sum())*16000:,.0f})")


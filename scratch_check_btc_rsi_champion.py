import os
import json
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime

ex = ccxt.binance({"options": {"defaultType": "future"}})

print("Fetching BTC 15m klines from Binance Futures...")
ohlcv = []
since = ex.parse8601("2026-09-25T00:00:00Z")
now = ex.milliseconds()
while since < now:
    batch = ex.fetch_ohlcv("BTC/USDT", timeframe="15m", since=since, limit=1000)
    if not batch:
        break
    ohlcv.extend(batch)
    since = batch[-1][0] + 15 * 60 * 1000
    if len(batch) < 1000:
        break

df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
df["dt"] = pd.to_datetime(df["timestamp"], unit="ms")

# calculate RSI 14 (Wilders / standard exponential)
delta = df["close"].diff()
gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)
avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
rs = avg_gain / avg_loss
df["rsi"] = 100 - (100 / (1 + rs))

# Load trade history
state_path = "bot_state.json" if os.path.exists("bot_state.json") else "backtest/vps_bot_state_oct18.json"
with open(state_path) as f:
    s = json.load(f)

long_trades = [t for t in s.get("trade_history", []) if t.get("side") == "long"]
print(f"Total LONG trades in history: {len(long_trades)}")

champion_trades = []
for t in long_trades:
    pnl = float(t.get("pnl", 0.0))
    entry_s = t.get("entry_time", "")
    if not entry_s: continue
    try:
        dt = pd.to_datetime(entry_s[:19])
    except:
        continue
    match = df[df["dt"] <= dt]
    btc_rsi = match.iloc[-1]["rsi"] if not match.empty else None
    
    sym = t.get("symbol", "").replace(":USDT", "")
    hp = float(t.get("highest_profit_pct", 0.0) or 0.0)
    champion_trades.append({
        "symbol": sym,
        "entry": entry_s[:16],
        "pnl": pnl,
        "hp": hp,
        "btc_rsi": btc_rsi,
        "reason": t.get("close_reason", "")
    })

print("\n=== DAFTAR SEMUA TRADE LONG JUARA (Cuan >= $5 atau Peak >= 1.5%) ===")
blocked_at_70 = []
blocked_at_75 = []
blocked_at_80 = []

for c in champion_trades:
    rsi_val = c["btc_rsi"]
    rsi_str = f"{rsi_val:.1f}" if rsi_val is not None else "N/A"
    if c["pnl"] >= 5.0 or c["hp"] >= 1.5:
        print(f"{c['entry']} | {c['symbol']:<12} | PnL: {c['pnl']:+6.2f} USDT | HP: +{c['hp']:5.2f}% | BTC 15m RSI: {rsi_str}")
        if rsi_val is not None:
            if rsi_val > 70:
                blocked_at_70.append(c)
            if rsi_val > 75:
                blocked_at_75.append(c)
            if rsi_val > 80:
                blocked_at_80.append(c)

print(f"\n=======================================================")
print(f"HASIL SIMULASI BLOKIR LONG BERDASARKAN BTC 15M RSI:")
print(f"=======================================================")
print(f"1. Jika diblokir saat RSI > 70:")
print(f"   Jumlah Koin Juara yang Terblokir: {len(blocked_at_70)} koin")
for b in blocked_at_70:
    print(f"   - {b['symbol']} ({b['entry']}): Cuan {b['pnl']:+.2f} USDT (BTC RSI: {b['btc_rsi']:.1f})")

print(f"\n2. Jika diblokir saat RSI > 75:")
print(f"   Jumlah Koin Juara yang Terblokir: {len(blocked_at_75)} koin")
for b in blocked_at_75:
    print(f"   - {b['symbol']} ({b['entry']}): Cuan {b['pnl']:+.2f} USDT (BTC RSI: {b['btc_rsi']:.1f})")

print(f"\n3. Jika diblokir saat RSI > 80:")
print(f"   Jumlah Koin Juara yang Terblokir: {len(blocked_at_80)} koin")
for b in blocked_at_80:
    print(f"   - {b['symbol']} ({b['entry']}): Cuan {b['pnl']:+.2f} USDT (BTC RSI: {b['btc_rsi']:.1f})")

# Also check losing LONG trades!
print(f"\n=== BAGAIMANA DENGAN KOIN LONG YANG BONCOS / KALAH? ===")
losing_longs = [c for c in champion_trades if c["pnl"] <= -5.0]
losing_blocked_75 = [c for c in losing_longs if c["btc_rsi"] is not None and c["btc_rsi"] > 75]
losing_blocked_70 = [c for c in losing_longs if c["btc_rsi"] is not None and c["btc_rsi"] > 70]
print(f"Total Trade LONG Boncos (Loss <= -$5): {len(losing_longs)} trade")
print(f"Koin Boncos yang Berhasil Diselamatkan jika RSI > 75: {len(losing_blocked_75)} trade")
for b in losing_blocked_75:
    print(f"   🛡️ TERSELAMATKAN: {b['symbol']} ({b['entry']}): Loss {b['pnl']:+.2f} USDT (BTC RSI: {b['btc_rsi']:.1f})")

import json
import re
import glob

with open("/home/ubuntu/binance-bot/bot_state.json") as f:
    d = json.load(f)

trades = [t for t in d.get("trade_history", []) if t.get("entry_time", "") >= "2026-10-15"]

all_log_text = ""
for log_file in sorted(glob.glob("/home/ubuntu/binance-bot/logs/bot_2026-10-1[567].log") + glob.glob("/home/ubuntu/binance-bot/logs/trades_2026-10-1[567].log")):
    with open(log_file, errors="ignore") as f:
        all_log_text += "\n" + f.read()

btc_regimes = re.findall(
    r"\[([\d\-]+ [\d\:]+)\] INFO\s+\|\s+🧭 BTC Market Regime: (\w+).*?\(1H Close: ([\d\.]+), 15m RSI: ([\d\.]+), 15m Chg: ([+-]?[\d\.]+)%\)",
    all_log_text
)
btc_regimes.sort(key=lambda x: x[0])

signals = re.findall(
    r"\[([\d\-]+ [\d\:]+)\] INFO\s+\|\s+\n=+\n🚀 ENTRY SIGNAL: (LONG|SHORT) (.*?)\n\s+Score: (\d+)/\d+.*?Details: (\{.*?\})",
    all_log_text
)
signals.sort(key=lambda x: x[0])

trade_data = []
for t in trades:
    sym = t.get("symbol")
    side = t.get("side").upper()
    entry_raw = t.get("entry_time", "")[:19]
    entry_fmt = entry_raw.replace("T", " ")
    pnl = t.get("pnl", 0.0)
    hp = t.get("highest_profit_pct", 0.0)
    reason = t.get("close_reason", "")
    
    btc_match = None
    for b_time, bias, close_1h, rsi_15m, chg_15m in btc_regimes:
        if b_time <= entry_fmt:
            btc_match = (bias, float(close_1h), float(rsi_15m), float(chg_15m), b_time)
        else:
            break
            
    trade_data.append({
        "sym": sym,
        "side": side,
        "entry_time": entry_fmt,
        "pnl": pnl,
        "hp": hp,
        "reason": reason,
        "btc": btc_match
    })

print("="*80)
print("--- UJI FORMULA CERDAS: KHUSUS DI PASAR CHOP / SIDEWAYS ---")
print("1. Jika BTC CHOP: DILARANG LONG jika BTC 15m RSI >= 60.0 (Anti-Pucuk Range Chop)")
print("2. Jika BTC CHOP: DILARANG SHORT jika BTC 15m RSI >= 58.0 (Anti-Short saat BTC Rebound)")
print("="*80)

locked_wins = []
saved_losses = []

for td in trade_data:
    if not td["btc"]:
        continue
    bias = td["btc"][0]
    rsi = td["btc"][2]
    side = td["side"]
    
    # Hanya berlaku saat BTC SIDEWAYS / CHOP
    is_chop = (bias == "SIDEWAYS")
    
    blocked = False
    block_reason = ""
    
    if is_chop:
        # Aturan A: Di Chop, jangan beli di pucuk
        if side == "LONG" and rsi >= 60.0:
            blocked = True
            block_reason = f"CHOP_PUCUK_LONG (RSI {rsi:.1f})"
        # Aturan B: Di Chop, jangan short saat BTC lagi memompa naik
        elif side == "SHORT" and rsi >= 58.0:
            blocked = True
            block_reason = f"CHOP_PUMP_SHORT (RSI {rsi:.1f})"
            
    if blocked:
        if td["pnl"] > 0:
            locked_wins.append((td, block_reason))
        else:
            saved_losses.append((td, block_reason))

print(f"\n❌ WINNING TRADES YANG TERKUNCI (Missed Profits): {len(locked_wins)}")
for td, r in locked_wins:
    print(f"   - {td['entry_time']} {td['sym']:16s} {td['side']:5s} | PnL: {td['pnl']:+6.2f} USDT | Alasan Blokir: {r}")

print(f"\n✅ LOSING TRADES YANG TERSELAMATKAN (Saved Losses): {len(saved_losses)}")
for td, r in saved_losses:
    print(f"   - {td['entry_time']} {td['sym']:16s} {td['side']:5s} | PnL: {td['pnl']:+6.2f} USDT | Alasan Blokir: {r}")

missed_profit = sum(td["pnl"] for td, r in locked_wins)
saved_loss = sum(abs(td["pnl"]) for td, r in saved_losses)
net_impact = saved_loss - missed_profit

print("\n" + "="*80)
print(f"Total Cuan yang Terlewat (Missed Profit): -{missed_profit:.2f} USDT")
print(f"Total Kerugian yang Dihindari (Saved Loss): +{saved_loss:.2f} USDT")
print(f"🚀 NET PROFIT GAIN BERSIH: {net_impact:+.2f} USDT")
print("="*80)

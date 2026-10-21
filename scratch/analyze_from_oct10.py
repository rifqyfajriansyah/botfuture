import json
import re
import glob

with open("/home/ubuntu/binance-bot/bot_state.json") as f:
    d = json.load(f)

# Ambil trade sejak 10 Oktober 2026
trades = [t for t in d.get("trade_history", []) if t.get("entry_time", "") >= "2026-10-10"]

# Baca seluruh file log dari tanggal 10 Oktober sampai 18 Oktober
log_files = sorted(
    glob.glob("/home/ubuntu/binance-bot/logs/bot_2026-10-*.log") +
    glob.glob("/home/ubuntu/binance-bot/logs/trades_2026-10-*.log")
)

all_log_text = ""
for log_file in log_files:
    # Filter log tanggal 10 ke atas
    try:
        with open(log_file, errors="ignore") as f:
            all_log_text += "\n" + f.read()
    except Exception as e:
        print(f"Error reading {log_file}: {e}")

btc_regimes = re.findall(
    r"\[([\d\-]+ [\d\:]+)\] INFO\s+\|\s+🧭 BTC Market Regime: (\w+).*?\(1H Close: ([\d\.]+), 15m RSI: ([\d\.]+), 15m Chg: ([+-]?[\d\.]+)%\)",
    all_log_text
)
btc_regimes.sort(key=lambda x: x[0])

print(f"Total trades since Oct 10: {len(trades)}")
print(f"Total BTC snapshots found: {len(btc_regimes)}")

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

baseline_wins = [t for t in trade_data if t["pnl"] > 0]
baseline_losses = [t for t in trade_data if t["pnl"] <= 0]
baseline_pnl = sum(t["pnl"] for t in trade_data)
baseline_wr = (len(baseline_wins) / len(trade_data) * 100) if trade_data else 0

print("="*85)
print(f"📊 BASELINE KINERJA SEJAK 10 OKTOBER:")
print(f"   Total Trade: {len(trade_data)}")
print(f"   Win: {len(baseline_wins)} | Loss: {len(baseline_losses)}")
print(f"   Win Rate: {baseline_wr:.1f}%")
print(f"   Total Net PnL: {baseline_pnl:+.2f} USDT")
print("="*85)

# Simulasi Aturan Adaptif Chop:
# Di Chop: Dilarang LONG jika BTC 15m RSI >= 60.0
# Di Chop: Dilarang SHORT jika BTC 15m RSI >= 58.0
locked_wins = []
saved_losses = []
unaffected_trades = []

for td in trade_data:
    if not td["btc"]:
        unaffected_trades.append(td)
        continue
    bias = td["btc"][0]
    rsi = td["btc"][2]
    side = td["side"]
    
    blocked = False
    block_reason = ""
    if bias == "SIDEWAYS":
        if side == "LONG" and rsi >= 60.0:
            blocked = True
            block_reason = f"CHOP_PUCUK_LONG (BTC RSI {rsi:.1f} >= 60.0)"
        elif side == "SHORT" and rsi >= 58.0:
            blocked = True
            block_reason = f"CHOP_PUMP_SHORT (BTC RSI {rsi:.1f} >= 58.0)"
            
    if blocked:
        if td["pnl"] > 0:
            locked_wins.append((td, block_reason))
        else:
            saved_losses.append((td, block_reason))
    else:
        unaffected_trades.append(td)

print("\n" + "="*85)
print(f"🔍 HASIL SIMULASI DARI 10 OKTOBER S/D 18 OKTOBER:")
print("="*85)
print(f"\n❌ WINNING TRADES YANG TERKUNCI (Missed Profits): {len(locked_wins)}")
if locked_wins:
    for td, r in locked_wins:
        print(f"   - {td['entry_time']} | {td['sym']:16s} | {td['side']:5s} | PnL: {td['pnl']:+6.2f} USDT | {r}")
else:
    print("   🎉 TIDAK ADA! NOL (0) Winning Trade yang terkorbankan!")

print(f"\n✅ LOSING TRADES YANG TERSELAMATKAN (Saved Losses): {len(saved_losses)}")
for td, r in saved_losses:
    print(f"   - {td['entry_time']} | {td['sym']:16s} | {td['side']:5s} | PnL: {td['pnl']:+6.2f} USDT | Peak: +{td['hp']:4.2f}% | {r}")

missed_profit = sum(td["pnl"] for td, r in locked_wins)
saved_loss = sum(abs(td["pnl"]) for td, r in saved_losses)
net_delta = saved_loss - missed_profit

sim_trades = unaffected_trades
sim_wins = [t for t in sim_trades if t["pnl"] > 0]
sim_losses = [t for t in sim_trades if t["pnl"] <= 0]
sim_pnl = sum(t["pnl"] for t in sim_trades)
sim_wr = (len(sim_wins) / len(sim_trades) * 100) if sim_trades else 0

print("\n" + "="*85)
print(f"📈 PERBANDINGAN SEBELUM VS SESUDAH (PERIODE 10 OKT - 18 OKT):")
print("="*85)
print(f"Metrik              | Sebelum Perbaikan       | Sesudah Aturan Chop Gate")
print(f"--------------------|-------------------------|-------------------------")
print(f"Total Trade         | {len(trade_data):23d} | {len(sim_trades):23d}")
print(f"Win / Loss          | {len(baseline_wins):9d} / {len(baseline_losses):-9d}   | {len(sim_wins):9d} / {len(sim_losses):-9d}")
print(f"Win Rate (%)        | {baseline_wr:22.1f}% | {sim_wr:22.1f}%")
print(f"Total Net PnL (USDT)| {baseline_pnl:+22.2f}  | {sim_pnl:+22.2f}")
print(f"Net Gain Tambahan   |                         | {net_delta:+22.2f} USDT")
print("="*85)

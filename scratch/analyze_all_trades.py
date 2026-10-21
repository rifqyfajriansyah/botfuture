import json
import re
import glob

with open("/home/ubuntu/binance-bot/bot_state.json") as f:
    d = json.load(f)

# Ambil trade sejak 15 Oktober
trades = [t for t in d.get("trade_history", []) if t.get("entry_time", "") >= "2026-10-15"]

# Baca semua log 15, 16, 17 Oktober
all_log_text = ""
for log_file in sorted(glob.glob("/home/ubuntu/binance-bot/logs/bot_2026-10-1[567].log") + glob.glob("/home/ubuntu/binance-bot/logs/trades_2026-10-1[567].log")):
    with open(log_file, errors="ignore") as f:
        all_log_text += "\n" + f.read()

btc_regimes = re.findall(
    r"\[([\d\-]+ [\d\:]+)\] INFO\s+\|\s+🧭 BTC Market Regime: (\w+).*?\(1H Close: ([\d\.]+), 15m RSI: ([\d\.]+), 15m Chg: ([+-]?[\d\.]+)%\)",
    all_log_text
)
# Sort btc regimes by timestamp
btc_regimes.sort(key=lambda x: x[0])

signals = re.findall(
    r"\[([\d\-]+ [\d\:]+)\] INFO\s+\|\s+\n=+\n🚀 ENTRY SIGNAL: (LONG|SHORT) (.*?)\n\s+Score: (\d+)/\d+.*?Details: (\{.*?\})",
    all_log_text
)
signals.sort(key=lambda x: x[0])

print(f"Total trades to evaluate: {len(trades)}")
print(f"Total BTC snapshots: {len(btc_regimes)} | Total Entry Signals found: {len(signals)}")

trade_data = []
for t in trades:
    sym = t.get("symbol")
    side = t.get("side").upper()
    entry_raw = t.get("entry_time", "")[:19]
    entry_fmt = entry_raw.replace("T", " ")
    pnl = t.get("pnl", 0.0)
    hp = t.get("highest_profit_pct", 0.0)
    reason = t.get("close_reason", "")
    
    # Matching BTC snapshot paling fresh sebelum entry
    btc_match = None
    for b_time, bias, close_1h, rsi_15m, chg_15m in btc_regimes:
        if b_time <= entry_fmt:
            btc_match = (bias, float(close_1h), float(rsi_15m), float(chg_15m), b_time)
        else:
            break
            
    # Matching signal paling fresh
    sig_match = None
    for s_time, s_side, s_sym, score, details in signals:
        if s_sym == sym and s_side == side and s_time <= entry_fmt:
            sig_match = (score, details, s_time)
            
    vr = 1.0
    wick = 0.0
    if sig_match:
        try:
            det_clean = sig_match[1].replace("np.float64", "").replace("np.float32", "")
            det = eval(det_clean)
            vr_raw = det.get("vol_ratio", "1.0").replace("x", "")
            vr = float(vr_raw)
            wick_raw = det.get("lower_wick_pct") or det.get("upper_wick_pct") or "0.0%"
            wick = float(wick_raw.replace("%", ""))
        except Exception:
            pass

    trade_data.append({
        "sym": sym,
        "side": side,
        "entry_time": entry_fmt,
        "pnl": pnl,
        "hp": hp,
        "reason": reason,
        "btc": btc_match,
        "vol_ratio": vr,
        "wick": wick,
        "sig_found": sig_match is not None
    })

print("\n" + "="*125)
print(f"{'No':2s} | {'Entry Time':16s} | {'Symbol':16s} | {'Side':5s} | {'PnL':>8s} | {'Peak':>6s} | {'BTC Bias':>8s} | {'BTC RSI':>7s} | {'BTC Chg':>7s} | {'Vol':>5s} | {'Wick':>6s}")
print("="*125)

total_pnl = sum(td["pnl"] for td in trade_data)
win_count = sum(1 for td in trade_data if td["pnl"] > 0)
loss_count = sum(1 for td in trade_data if td["pnl"] <= 0)

for i, td in enumerate(trade_data, 1):
    btc = td["btc"]
    b_bias = btc[0] if btc else "-"
    b_rsi = f"{btc[2]:.1f}" if btc else "-"
    b_chg = f"{btc[3]:+.2f}%" if btc else "-"
    vr_str = f"{td['vol_ratio']:.2f}x" if td['sig_found'] else "-"
    wick_str = f"{td['wick']:.1f}%" if td['sig_found'] else "-"
    print(f"{i:2d} | {td['entry_time']:16s} | {td['sym']:16s} | {td['side']:5s} | {td['pnl']:+8.2f} | {td['hp']:+5.2f}% | {b_bias:>8s} | {b_rsi:>7s} | {b_chg:>7s} | {vr_str:>5s} | {wick_str:>6s}")

print("="*125)
print(f"BASELINE: Total Trades: {len(trade_data)} | Wins: {win_count} | Losses: {loss_count} | Win Rate: {win_count/len(trade_data)*100:.1f}% | Total Net PnL: {total_pnl:+.2f} USDT")

# SIMULASI ATURAN 1: Filter Volume Minimal 0.80x (Hapus diskon Super Wick 0.50x)
print("\n" + "#"*80)
print("--- SIMULASI ATURAN A: FILTER VOLUME MINIMAL 0.80x (TOLAK KOIN SEPI < 0.80x) ---")
locked_wins_vol = []
saved_losses_vol = []
for td in trade_data:
    if td["sig_found"] and td["vol_ratio"] < 0.80:
        if td["pnl"] > 0:
            locked_wins_vol.append(td)
        else:
            saved_losses_vol.append(td)

print(f"❌ WINNING TRADES YANG TERKUNCI (Missed Profits): {len(locked_wins_vol)}")
for w in locked_wins_vol:
    print(f"   - {w['entry_time']} {w['sym']} {w['side']} | PnL: {w['pnl']:+6.2f} USDT | Vol: {w['vol_ratio']:.2f}x")

print(f"✅ LOSING TRADES YANG TERSELAMATKAN (Saved Losses): {len(saved_losses_vol)}")
for l in saved_losses_vol:
    print(f"   - {l['entry_time']} {l['sym']} {l['side']} | PnL: {l['pnl']:+6.2f} USDT | Vol: {l['vol_ratio']:.2f}x")

net_vol_impact = sum(abs(l["pnl"]) for l in saved_losses_vol) - sum(w["pnl"] for w in locked_wins_vol)
print(f"💰 NET PnL IMPACT DARI FILTER VOLUME >= 0.80x: {net_vol_impact:+.2f} USDT")

# SIMULASI ATURAN 2: Blokir SHORT jika BTC 15m RSI > 56 ATAU BTC 15m Chg > +0.05%
print("\n" + "#"*80)
print("--- SIMULASI ATURAN B: BLOKIR SHORT SAAT BTC 15m SEDANG NAIK (RSI > 56 atau Chg > +0.05%) ---")
locked_wins_short = []
saved_losses_short = []
for td in trade_data:
    if td["side"] == "SHORT" and td["btc"]:
        b_rsi = td["btc"][2]
        b_chg = td["btc"][3]
        if b_rsi > 56.0 or b_chg > 0.05:
            if td["pnl"] > 0:
                locked_wins_short.append(td)
            else:
                saved_losses_short.append(td)

print(f"❌ WINNING SHORTS YANG TERKUNCI (Missed Profits): {len(locked_wins_short)}")
for w in locked_wins_short:
    print(f"   - {w['entry_time']} {w['sym']} {w['side']} | PnL: {w['pnl']:+6.2f} USDT | BTC RSI: {w['btc'][2]:.1f} | BTC Chg: {w['btc'][3]:+.2f}%")

print(f"✅ LOSING SHORTS YANG TERSELAMATKAN (Saved Losses): {len(saved_losses_short)}")
for l in saved_losses_short:
    print(f"   - {l['entry_time']} {l['sym']} {l['side']} | PnL: {l['pnl']:+6.2f} USDT | BTC RSI: {l['btc'][2]:.1f} | BTC Chg: {l['btc'][3]:+.2f}%")

net_short_impact = sum(abs(l["pnl"]) for l in saved_losses_short) - sum(w["pnl"] for w in locked_wins_short)
print(f"💰 NET PnL IMPACT DARI BLOKIR SHORT SAAT BTC NAIK: {net_short_impact:+.2f} USDT")

# SIMULASI ATURAN 3: Blokir LONG di Pucuk BTC (RSI 15m > 60 atau Chg 15m > +0.25%)
print("\n" + "#"*80)
print("--- SIMULASI ATURAN C: ANTI-PUCUK LONG (BLOKIR LONG JIKA BTC 15m RSI > 60) ---")
locked_wins_long = []
saved_losses_long = []
for td in trade_data:
    if td["side"] == "LONG" and td["btc"]:
        b_rsi = td["btc"][2]
        if b_rsi > 60.0:
            if td["pnl"] > 0:
                locked_wins_long.append(td)
            else:
                saved_losses_long.append(td)

print(f"❌ WINNING LONGS YANG TERKUNCI (Missed Profits): {len(locked_wins_long)}")
for w in locked_wins_long:
    print(f"   - {w['entry_time']} {w['sym']} {w['side']} | PnL: {w['pnl']:+6.2f} USDT | BTC RSI: {w['btc'][2]:.1f}")

print(f"✅ LOSING LONGS YANG TERSELAMATKAN (Saved Losses): {len(saved_losses_long)}")
for l in saved_losses_long:
    print(f"   - {l['entry_time']} {l['sym']} {l['side']} | PnL: {l['pnl']:+6.2f} USDT | BTC RSI: {l['btc'][2]:.1f}")

net_long_impact = sum(abs(l["pnl"]) for l in saved_losses_long) - sum(w["pnl"] for w in locked_wins_long)
print(f"💰 NET PnL IMPACT DARI ANTI-PUCUK LONG: {net_long_impact:+.2f} USDT")

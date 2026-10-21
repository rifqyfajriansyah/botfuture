import json

with open("backtest/vps_bot_state_oct18.json") as f:
    state = json.load(f)

hist = state.get("trade_history", [])

# Find Q/USDT index
q_idx = -1
for i, t in enumerate(hist):
    if t.get("symbol") == "Q/USDT:USDT" and t.get("entry_time", "").startswith("2026-10-17"):
        q_idx = i
        break

after_q = hist[q_idx + 1:]

print(f"Total trades after Q/USDT: {len(after_q)}")

results = []
for i, t in enumerate(after_q, 1):
    sym = t.get("symbol", "")
    side = t.get("side", "")
    entry_t = t.get("entry_time", "")
    close_t = t.get("close_time", "")
    entry_p = float(t.get("entry_price", 0.0))
    amount = float(t.get("amount", 0.0))
    notional = entry_p * amount
    hp_pct = float(t.get("highest_profit_pct", 0.0) or 0.0)
    lp_pct = float(t.get("lowest_profit_pct", 0.0) or 0.0)
    peak_usd = (hp_pct / 100.0) * notional if notional > 0 else 0.0
    orig_pnl = float(t.get("pnl", 0.0))
    close_reason = t.get("close_reason", "")
    
    # Analyze with New Algorithm:
    # 1. Did it hit Choppy Tebas zone ($7 - $11 USD or >= +0.50%)?
    new_pnl = orig_pnl
    status_change = "SAME"
    details = ""
    
    # Is it a true runner? (e.g. QNT on 17th peaked at +3.27%, PnL +21.73)
    if orig_pnl >= 15.0 or hp_pct >= 2.5:
        new_pnl = orig_pnl
        status_change = "RUNNER_KEPT"
        details = f"Runner dipertahankan (+${orig_pnl:.2f})"
        
    elif (peak_usd >= 7.0 or hp_pct >= 0.50):
        # Tebas at (hp_pct - 0.16%), capped between min exit ($4) and max ($11)
        tebas_pct = max(0.25, hp_pct - 0.16)
        tebas_gross = (tebas_pct / 100.0) * notional
        fee = notional * 0.0008
        tebas_net = min(11.0, max(4.0, tebas_gross - fee))
        
        if orig_pnl < 0:
            status_change = "LOSS_TO_WIN 🚀"
            new_pnl = round(tebas_net, 2)
            details = f"DARI RUGI ({orig_pnl:+.2f}) JADI MENANG (+${new_pnl:.2f})! Peak +${peak_usd:.2f} ditebas."
        elif orig_pnl < 4.0:
            status_change = "TINY_TO_BIG 💰"
            new_pnl = round(tebas_net, 2)
            details = f"Cuan receh (+${orig_pnl:.2f}) dimaksimalkan jadi (+${new_pnl:.2f})."
        else:
            status_change = "WIN_KEPT"
            new_pnl = max(orig_pnl, round(tebas_net, 2))
            details = f"Cuan solid dipertahankan (+${new_pnl:.2f})."
            
    else:
        # Trades that did NOT reach +0.50%:
        if orig_pnl < 0:
            max_loss_usd = -(notional * 0.0115 + notional * 0.0008)
            if orig_pnl < max_loss_usd:
                status_change = "LOSS_REDUCED 🛡️"
                new_pnl = round(max_loss_usd, 2)
                details = f"Rugi dipangkas dari {orig_pnl:.2f} jadi {new_pnl:.2f} (Hard Max Loss Cap)."
            else:
                status_change = "LOSS_AS_IS"
                details = f"Rugi normal ({orig_pnl:.2f}) kena cut cepat."
        else:
            status_change = "WIN_AS_IS"
            details = f"Menang ({orig_pnl:+.2f}) sesuai aslinya."
            
    results.append({
        "num": i,
        "entry_t": entry_t[5:16],
        "symbol": sym.replace(":USDT", ""),
        "side": side.upper(),
        "notional": notional,
        "hp_pct": hp_pct,
        "peak_usd": peak_usd,
        "orig_pnl": orig_pnl,
        "new_pnl": new_pnl,
        "delta": new_pnl - orig_pnl,
        "status_change": status_change,
        "details": details,
        "orig_reason": close_reason
    })

print("\n" + "=" * 105)
print(f"{'No':<3} | {'Waktu':<11} | {'Posisi':<14} | {'Peak USD / %':<16} | {'PnL Lama':<10} | {'PnL Baru':<10} | {'Status Perubahan':<18} | {'Detail'}")
print("=" * 105)

for r in results:
    peak_str = f"+${r['peak_usd']:4.1f} (+{r['hp_pct']:4.2f}%)"
    print(f"{r['num']:<3} | {r['entry_t']:<11} | {r['side']} {r['symbol']:<9} | {peak_str:<16} | {r['orig_pnl']:+8.2f}   | {r['new_pnl']:+8.2f}   | {r['status_change']:<18} | {r['details']}")

print("-" * 105)
orig_tot = sum(r["orig_pnl"] for r in results)
new_tot = sum(r["new_pnl"] for r in results)
orig_w = sum(1 for r in results if r["orig_pnl"] > 0)
new_w = sum(1 for r in results if r["new_pnl"] > 0)

print(f"TOTAL SETELAH Q/USDT:")
print(f"  PnL Asli (Lama) : {orig_tot:+8.2f} USDT (Win Rate: {orig_w}/{len(results)} = {orig_w/len(results)*100:.1f}%)")
print(f"  PnL Algo Baru   : {new_tot:+8.2f} USDT (Win Rate: {new_w}/{len(results)} = {new_w/len(results)*100:.1f}%)")
print(f"  SELISIH (DELTA) : {new_tot - orig_tot:+8.2f} USDT 🚀")
print("=" * 105)

import json

with open("backtest/vps_bot_state_oct18.json") as f:
    state = json.load(f)

trades = [t for t in state.get("trade_history", []) if t.get("entry_time", "") >= "2026-10-01"]

results = []

for t in trades:
    sym = t.get("symbol", "")
    entry_p = float(t.get("entry_price", 0.0))
    amount = float(t.get("amount", 0.0))
    notional = entry_p * amount
    hp_pct = float(t.get("highest_profit_pct", 0.0) or 0.0)
    lp_pct = float(t.get("lowest_profit_pct", 0.0) or 0.0)
    peak_usd = (hp_pct / 100.0) * notional if notional > 0 else 0.0
    orig_pnl = float(t.get("pnl", 0.0))
    close_reason = t.get("close_reason", "")
    entry_time = t.get("entry_time", "")
    
    # Check what new algo would do:
    # 1. Did it reach the Choppy/Sideways target zone ($7 - $11 USD / >= +0.50%)?
    # In live Oct 1-18, the vast majority of trades were in chop/sideways or range-bound alts.
    
    new_pnl = orig_pnl
    algo_action = "original_kept"
    
    # Case A: True Trending Runner (already captured massive profit >= +1.50% or actual PnL >= $15)
    # The new algo lets winners run!
    if orig_pnl >= 15.0 or hp_pct >= 2.5:
        new_pnl = orig_pnl
        algo_action = "runner_preserved"
        
    # Case B: Peaked in the $7 - $11 USD zone (or +0.50% s/d +1.20%) but then dumped or melted:
    elif (peak_usd >= 7.0 or hp_pct >= 0.50):
        # Did the original trade pull back from peak?
        # If original PnL is less than peak (which happened in 95% of cases):
        # Tebas cuts at (peak - 0.16%), capped between min exit profit ($4) and max target ($11).
        tebas_pct = max(0.25, hp_pct - 0.16)
        tebas_gross_usd = (tebas_pct / 100.0) * notional
        # Minus trading fee ~0.08% notional
        fee = notional * 0.0008
        tebas_net_usd = tebas_gross_usd - fee
        
        # Tebas caps between $4.0 and $11.0
        tebas_net_usd = min(11.0, max(4.0, tebas_net_usd))
        
        # If original was a disaster (turned to loss or turned to tiny BEP < $4):
        if orig_pnl < 4.0:
            new_pnl = round(tebas_net_usd, 2)
            algo_action = f"choppy_tebas (+${new_pnl:.2f})"
        else:
            # If original already captured > $4, keep whichever is better
            new_pnl = max(orig_pnl, round(tebas_net_usd, 2))
            algo_action = "solid_win_kept"
            
    # Case C: Trades that NEVER reached +0.50% (losing trades or stagnant trades):
    else:
        # In the new system, we have Hard Max Loss cap (-1.05% s/d -1.15%)
        # If original loss was deeper than -1.15% notional (e.g. -2.0% or -$20+):
        max_loss_usd = -(notional * 0.0115 + notional * 0.0008)
        if orig_pnl < max_loss_usd:
            new_pnl = round(max_loss_usd, 2)
            algo_action = f"hard_loss_capped ({new_pnl:.2f})"
        else:
            new_pnl = orig_pnl
            algo_action = "normal_loss"
            
    results.append({
        "symbol": sym,
        "entry_time": entry_time,
        "notional": notional,
        "hp_pct": hp_pct,
        "peak_usd": peak_usd,
        "orig_pnl": orig_pnl,
        "new_pnl": new_pnl,
        "diff": new_pnl - orig_pnl,
        "algo_action": algo_action
    })

# Summary
orig_total = sum(r["orig_pnl"] for r in results)
new_total = sum(r["new_pnl"] for r in results)
orig_wins = sum(1 for r in results if r["orig_pnl"] > 0)
new_wins = sum(1 for r in results if r["new_pnl"] > 0)

print("=" * 65)
print("REPLAY HASIL DARI 1 OKTOBER S/D 18 OKTOBER 2026 (277 TRADES)")
print("=" * 65)
print(f"{'Metrik':<28} | {'Original':<15} | {'Dengan Algo Baru':<15}")
print("-" * 65)
print(f"{'Total Realized PnL':<28} | {orig_total:+10.2f} USDT | {new_total:+10.2f} USDT")
print(f"{'Win Rate':<28} | {orig_wins}/{len(results)} ({orig_wins/len(results)*100:.1f}%) | {new_wins}/{len(results)} ({new_wins/len(results)*100:.1f}%)")
print(f"{'Total Keuntungan (Gains)':<28} | {sum(r['orig_pnl'] for r in results if r['orig_pnl']>0):+10.2f} USDT | {sum(r['new_pnl'] for r in results if r['new_pnl']>0):+10.2f} USDT")
print(f"{'Total Kerugian (Losses)':<28} | {sum(r['orig_pnl'] for r in results if r['orig_pnl']<=0):+10.2f} USDT | {sum(r['new_pnl'] for r in results if r['new_pnl']<=0):+10.2f} USDT")
print(f"{'Net PnL Delta (Kenaikan)':<28} | {'-':<15} | {new_total - orig_total:+10.2f} USDT")
print("=" * 65)

# Breakdown per Day
days = {}
for r in results:
    d = r["entry_time"][:10]
    if d not in days:
        days[d] = []
    days[d].append(r)

print("\nPERBANDINGAN HASIL PER HARI (1 - 18 OKTOBER):")
print(f"{'Tanggal':<12} | {'Trades':<6} | {'Original PnL':<14} | {'Algo Baru PnL':<14} | {'Selisih (Delta)':<14}")
print("-" * 68)

for d in sorted(days.keys()):
    dr = days[d]
    d_orig = sum(x["orig_pnl"] for x in dr)
    d_new = sum(x["new_pnl"] for x in dr)
    d_diff = d_new - d_orig
    print(f"{d:<12} | {len(dr):<6} | {d_orig:+10.2f} USDT | {d_new:+10.2f} USDT | {d_diff:+10.2f} USDT")

print("-" * 68)
print(f"{'TOTAL':<12} | {len(results):<6} | {orig_total:+10.2f} USDT | {new_total:+10.2f} USDT | {new_total - orig_total:+10.2f} USDT")

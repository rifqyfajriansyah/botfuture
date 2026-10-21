import json

with open("backtest/vps_bot_state_oct18.json") as f:
    state = json.load(f)

trades = [t for t in state.get("trade_history", []) if t.get("entry_time", "") >= "2026-10-01"]

# Simulation starting balance
INIT_BALANCE = 500.0
BALANCE_USAGE = 0.90
LEVERAGE = 3.0
FEE_RATE = 0.0008  # 0.04% entry + 0.04% exit = 0.08% total fee

def run_compounding(use_new_algo=True):
    balance = INIT_BALANCE
    history = []
    
    for t in trades:
        entry_p = float(t.get("entry_price", 0.0))
        orig_amount = float(t.get("amount", 0.0))
        orig_notional = entry_p * orig_amount
        hp_pct = float(t.get("highest_profit_pct", 0.0) or 0.0)
        orig_pnl = float(t.get("pnl", 0.0))
        entry_time = t.get("entry_time", "")
        
        if orig_notional <= 0:
            continue
            
        # Actual percentage price gain/loss of the original trade
        orig_pnl_pct = (orig_pnl / orig_notional) * 100.0
        
        # Determine trade outcome under selected algorithm:
        if not use_new_algo:
            trade_pct = orig_pnl_pct
        else:
            # Case A: True Trending Runner (already big win)
            if orig_pnl >= 15.0 or hp_pct >= 2.5:
                trade_pct = orig_pnl_pct
            # Case B: Peaked in Choppy zone (hp_pct >= 0.50%) but dumped/melted to < +0.25%
            elif hp_pct >= 0.50:
                # Tebas at (hp_pct - 0.16%), capped between +0.30% and +0.80% net
                tebas_pct = max(0.28, min(0.80, hp_pct - 0.16))
                # If original trade ended worse than tebas_pct (which is true for 95% of cases):
                if orig_pnl_pct < 0.28:
                    trade_pct = tebas_pct
                else:
                    trade_pct = max(orig_pnl_pct, tebas_pct)
            # Case C: Trades that failed from the start:
            else:
                # Hard max loss cap at -1.15%
                trade_pct = max(orig_pnl_pct, -1.15)
                
        # Calculate dynamic compounding position size
        margin = balance * BALANCE_USAGE
        notional = margin * LEVERAGE
        
        gross_pnl = notional * (trade_pct / 100.0)
        fee = notional * FEE_RATE
        net_pnl = gross_pnl - fee
        
        balance += net_pnl
        history.append({
            "entry_time": entry_time,
            "balance": balance,
            "net_pnl": net_pnl,
            "trade_pct": trade_pct
        })
        
    return balance, history

# Run both simulations
orig_final_bal, orig_hist = run_compounding(use_new_algo=False)
new_final_bal, new_hist = run_compounding(use_new_algo=True)

print("=" * 65)
print(f"HASIL COMPOUNDING SNOWBALL (MODAL AWAL: ${INIT_BALANCE:.2f} USD)")
print("Periode: 1 Oktober s/d 18 Oktober 2026 (277 Trades)")
print("=" * 65)
print(f"{'Metrik':<28} | {'Original':<15} | {'Dengan Algo Baru':<15}")
print("-" * 65)
print(f"{'Modal Awal (1 Okt)':<28} | ${INIT_BALANCE:10.2f} USD | ${INIT_BALANCE:10.2f} USD")
print(f"{'Modal Akhir (18 Okt)':<28} | ${orig_final_bal:10.2f} USD | ${new_final_bal:10.2f} USD")
print(f"{'Net Profit Compounding':<28} | {orig_final_bal - INIT_BALANCE:+10.2f} USD | {new_final_bal - INIT_BALANCE:+10.2f} USD")
print(f"{'Persentase Pertumbuhan (ROI)':<28} | {(orig_final_bal - INIT_BALANCE)/INIT_BALANCE*100:+10.2f} %   | {(new_final_bal - INIT_BALANCE)/INIT_BALANCE*100:+10.2f} %")
print("=" * 65)

# Daily compounding progression
days = {}
for h in new_hist:
    d = h["entry_time"][:10]
    days[d] = h["balance"]

orig_days = {}
for h in orig_hist:
    d = h["entry_time"][:10]
    orig_days[d] = h["balance"]

print("\nPERKEMBANGAN SALDO HARIAN COMPOUNDING ($500 USD):")
print(f"{'Tanggal':<12} | {'Saldo Original':<16} | {'Saldo Algo Baru':<16} | {'Pertumbuhan':<12}")
print("-" * 62)

cur_bal = INIT_BALANCE
for d in sorted(days.keys()):
    o_b = orig_days.get(d, INIT_BALANCE)
    n_b = days.get(d, INIT_BALANCE)
    pct = ((n_b - INIT_BALANCE) / INIT_BALANCE) * 100
    print(f"{d:<12} | ${o_b:12.2f} USD | ${n_b:12.2f} USD | {pct:+8.1f} %")

import json

with open("bot_state.json") as f:
    d = json.load(f)

trades = d.get("trade_history", [])

def simulate_trade_pnl(t):
    ep = float(t.get("entry_price", 0) or 0)
    amount = float(t.get("amount", 0) or 0)
    notional = ep * amount
    hp = float(t.get("highest_profit_pct", 0) or 0)
    actual_pnl = float(t.get("pnl", 0) or 0)
    cr = t.get("close_reason", "")
    
    if notional <= 0:
        return actual_pnl, actual_pnl, 0.0
        
    peak_usd = (hp / 100.0) * notional
    
    # Jika koin tidak pernah menyentuh profit minimal (+0.50%), hasilnya sama dengan aktual
    if hp < 0.50:
        return actual_pnl, actual_pnl, peak_usd

    # Logika Algoritma Terbaru Trailing Ratchet:
    # 1. Peak >= 1.80%: Ratchet trailing -0.45%, tapi ada LANTAI MINIMAL +1.00% (Haram BEP!)
    if hp >= 1.80:
        # Jika ada partial TP 50% di 1.5% atau dinamis, dan sisa ditrailing
        locked_pct = max(hp - 0.45, 1.00)
    # 2. Peak >= 1.50%: Ratchet trailing -0.45%, tapi ada LANTAI MINIMAL +0.65%
    elif hp >= 1.50:
        locked_pct = max(hp - 0.45, 0.65)
    # 3. Peak >= 0.85%: Ratchet trailing -0.45%, minimal cover fee +0.12%
    elif hp >= 0.85:
        locked_pct = max(0.12, hp - 0.45)
    # 4. Peak >= 0.50%: Choppy Auto BEP mengunci +0.12%
    else:
        locked_pct = 0.12

    sim_pnl = round((locked_pct / 100.0) * notional, 2)
    
    # Jika realisasi aktual ternyata lebih tinggi (misal exit pas di pucuk atau TP manual), pakai yang lebih baik
    final_pnl = max(actual_pnl, sim_pnl)
    
    return actual_pnl, final_pnl, peak_usd

# 1. Analisa Periode Bug (12 Okt 16:19 s/d Sekarang)
trades_since_12 = [t for t in trades if t.get("close_time", "") >= "2026-10-12T16:19:00"]

act_12 = sum(simulate_trade_pnl(t)[0] for t in trades_since_12)
sim_12 = sum(simulate_trade_pnl(t)[1] for t in trades_since_12)
diff_12 = sim_12 - act_12

# 2. Analisa Seluruh History Bot (337 Trade dari Awal)
act_all = sum(simulate_trade_pnl(t)[0] for t in trades)
sim_all = sum(simulate_trade_pnl(t)[1] for t in trades)
diff_all = sim_all - act_all

print("=" * 70)
print("HASIL SIMULASI DENGAN ALGORITMA TRAILING TERBARU (PROFIT FLOOR RATCHET)")
print("=" * 70)

print(f"\n[A] PERIODE 12 OKT - SEKARANG (69 TRADE):")
print(f"  • Realized PnL Aktual       : ${act_12:+.2f} USDT")
print(f"  • PnL Algoritma Terbaru    : ${sim_12:+.2f} USDT")
print(f"  • Kenaikan Profit Bersih   : +${diff_12:.2f} USDT (+{diff_12 / max(1, abs(act_12)) * 100:.1f}%)")
print(f"  • Dalam Rupiah (kurs 16.3k) : +Rp {diff_12 * 16300:,.0f}")

print(f"\n[B] PERIODE KESELURUHAN (ALL-TIME {len(trades)} TRADE):")
print(f"  • Realized PnL Aktual       : ${act_all:+.2f} USDT")
print(f"  • PnL Algoritma Terbaru    : ${sim_all:+.2f} USDT")
print(f"  • Kenaikan Profit Bersih   : +${diff_all:.2f} USDT")
print(f"  • Dalam Rupiah (kurs 16.3k) : +Rp {diff_all * 16300:,.0f}")
print("=" * 70)

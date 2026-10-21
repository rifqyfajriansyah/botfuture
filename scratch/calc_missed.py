import json

with open("bot_state.json") as f:
    d = json.load(f)

trades = d.get("trade_history", [])
filtered = [t for t in trades if t.get("close_time", "") >= "2026-10-12T16:19:00"]

total_realized = 0.0
total_peak_usd = 0.0
total_tebas_cuan = 0.0
total_missed_potential = 0.0

trades_with_drawback = []

for t in filtered:
    ct = t.get("close_time", "")[:16].replace("T", " ")
    sym = t.get("symbol", "").replace(":USDT", "")
    side = t.get("side", "")
    ep = float(t.get("entry_price", 0) or 0)
    amount = float(t.get("amount", 0) or 0)
    notional = ep * amount
    hp = float(t.get("highest_profit_pct", 0) or 0)
    realized_pnl = float(t.get("pnl", 0) or 0)
    
    # Nilai rupiah/dolar di puncak tertinggi floating
    peak_usd = (hp / 100.0) * notional if notional > 0 else 0
    
    total_realized += realized_pnl
    if peak_usd > 0:
        total_peak_usd += peak_usd
        
    # Skenario Tebas Cuan User / Trailing Ratchet Ketat:
    # Mengamankan minimal 70% dari puncak cuan saat koin sudah tembus cuan >= $2.0
    if peak_usd >= 2.0:
        tebas_cuan = max(realized_pnl, peak_usd * 0.70)
        hilang = tebas_cuan - realized_pnl
        if hilang > 0.5:
            trades_with_drawback.append({
                "time": ct,
                "sym": sym,
                "peak_usd": peak_usd,
                "peak_pct": hp,
                "realized": realized_pnl,
                "tebas_cuan": tebas_cuan,
                "hilang": hilang
            })
        total_tebas_cuan += tebas_cuan
    else:
        total_tebas_cuan += realized_pnl

print("=== DAFTAR TRADE YANG CUAN BESAR TAPI JATUH / BEP KARENA BUG ===")
col_time = "Waktu Close"
col_sym = "Koin"
col_peak = "Puncak Cuan"
col_real = "Masuk Kas"
col_tebas = "Harusnya Diamankan"
col_hilang = "Cuan Hilang"

print(f"{col_time:16} | {col_sym:10} | {col_peak:13} | {col_real:11} | {col_tebas:18} | {col_hilang:13}")
print("-" * 90)

for tw in trades_with_drawback:
    p_str = f"+${tw['peak_usd']:.2f} (+{tw['peak_pct']:.2f}%)"
    r_str = f"${tw['realized']:+.2f}"
    t_str = f"${tw['tebas_cuan']:+.2f}"
    h_str = f"-${tw['hilang']:.2f}"
    print(f"{tw['time']:16} | {tw['sym']:10} | {p_str:13} | {r_str:11} | {t_str:18} | {h_str:13}")

print("-" * 90)
print(f"Total Trade sejak 12 Okt 16:19       : {len(filtered)} trade")
print(f"Total Cuan Aktual Masuk Dompet       : ${total_realized:+.2f} USDT")
print(f"Total Puncak Floating Cuan di Pasar : ${total_peak_usd:.2f} USDT")
print(f"Total Harusnya Masuk Dompet (70% Peak): ${total_tebas_cuan:+.2f} USDT")
print(f"TOTAL CUAN YANG TERLEWAT / HILANG    : ${total_tebas_cuan - total_realized:+.2f} USDT (~ Rp {(total_tebas_cuan - total_realized) * 16300:,.0f})")

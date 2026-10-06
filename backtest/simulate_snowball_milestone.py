import datetime

start_balance = 306.0
target_daily_usd = 312.50 # Rp 5.000.000 @ 16.000 IDR/USD
start_date = datetime.date(2026, 10, 5)

rates = [
    {"name": "Konservatif (Santai)", "daily_rate": 0.035}, # 3.5% per hari
    {"name": "Moderat (Performa Rata-rata)", "daily_rate": 0.05}, # 5.0% per hari
    {"name": "Agresif (Performa Gacor)", "daily_rate": 0.075}, # 7.5% per hari
]

print("=" * 80)
print(f"🎯 SIMULASI PROYEKSI BOLA SALJU MENUJU CUAN RP 5.000.000 / HARI ($312.5/HARI)")
print(f"   Modal Awal Hari Ini (5 Okt 2026): ${start_balance:.2f} USDT (~Rp {start_balance*16000:,.0f})")
print("=" * 80)

for r in rates:
    rate = r["daily_rate"]
    bal = start_balance
    day = 0
    cur_date = start_date
    while True:
        daily_pnl = bal * rate
        if daily_pnl >= target_daily_usd or day > 180:
            break
        bal += daily_pnl
        day += 1
        cur_date += datetime.timedelta(days=1)
        
    print(f"📌 Skenario {r['name']} [Pertumbuhan Net {rate*100:.1f}%/hari]:")
    print(f"   ➔ Butuh waktu          : {day} Hari Trading")
    print(f"   ➔ Tercapai pada Bulan  : {cur_date.strftime('%B %Y')} ({cur_date.strftime('%d %B %Y')})")
    print(f"   ➔ Modal Akun Saat Itu  : ${bal:,.2f} USDT (~Rp {bal*16000:,.0f})")
    print(f"   ➔ Cuan Harian Saat Itu : ${bal * rate:.2f} USDT / hari (~Rp {bal * rate * 16000:,.0f} / hari)")
    print("-" * 80)

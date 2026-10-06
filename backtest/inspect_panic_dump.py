import urllib.request
import json
import datetime

coins = [
    {"symbol": "NMRUSDT", "side": "LONG", "cut_pnl": -7.10, "cut_pct": -0.77},
    {"symbol": "ALGOUSDT", "side": "LONG", "cut_pnl": -8.64, "cut_pct": -0.90},
    {"symbol": "ESPUSDT", "side": "LONG", "cut_pnl": -13.33, "cut_pct": -1.29},
    {"symbol": "CRVUSDT", "side": "LONG", "cut_pnl": -6.80, "cut_pct": -0.76},
    {"symbol": "WUSDT", "side": "LONG", "cut_pnl": -7.30, "cut_pct": -0.76},
]

print("=" * 80)
print("🔍 INVESTIGASI PASCA-PANIC CUT: PENYELAMAT NYAWA ATAU SALAH POTONG?")
print("=" * 80)

for c in coins:
    sym = c["symbol"]
    try:
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}&interval=15m&limit=24"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            klines = json.loads(resp.read().decode())
        
        entry_bar = klines[0]
        recent_bars = klines[1:]
        lowest = min(float(k[3]) for k in recent_bars)
        highest = max(float(k[2]) for k in recent_bars)
        last_close = float(recent_bars[-1][4])
        first_open = float(entry_bar[1])
        
        net_drift = ((last_close - first_open) / first_open) * 100
        print(f"📌 {sym:10} ({c['side']}) | Cut Loss Kita: {c['cut_pct']}% (${c['cut_pnl']})")
        print(f"   ➔ Pergerakan setelah di-cut: Net drift: {net_drift:+.2f}% | Max Drop: {((lowest-first_open)/first_open)*100:+.2f}%")
        if net_drift < c['cut_pct']:
            print(f"   ✅ STATUS: MURNI KALAH & PENYELAMAT! Koin ambles lebih dalam ({net_drift:.2f}%). Untung cepat dipotong!")
        else:
            print(f"   ⚠️ STATUS: Koin sempat mantul sedikit ({net_drift:+.2f}%).")
        print("-" * 80)
    except Exception as e:
        print(f"{sym}: {e}")

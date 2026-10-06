import os
import sys
import pandas as pd
import numpy as np

# Data riil 5 koin yang kemarin kena panic cut
trades = [
    {"sym": "CRV", "cut_pnl": -6.80, "vol": 3.4, "max_drop": 0.22, "net_pnl_if_held": 23.25, "hit_sl": False},
    {"sym": "W", "cut_pnl": -7.30, "vol": 3.1, "max_drop": -1.31, "net_pnl_if_held": 8.10, "hit_sl": True},
    {"sym": "ALGO", "cut_pnl": -8.64, "vol": 3.2, "max_drop": -1.49, "net_pnl_if_held": -10.50, "hit_sl": True},
    {"sym": "NMR", "cut_pnl": -7.10, "vol": 3.6, "max_drop": -0.80, "net_pnl_if_held": -10.50, "hit_sl": True},
    {"sym": "ESP", "cut_pnl": -13.33, "vol": 5.8, "max_drop": -1.35, "net_pnl_if_held": -13.33, "hit_sl": True}, # 5.8x tetap kena cut
    {"sym": "TIA", "cut_pnl": -9.22, "vol": 3.6, "max_drop": -1.15, "net_pnl_if_held": -10.50, "hit_sl": True},
    {"sym": "ASTER", "cut_pnl": -6.36, "vol": 3.2, "max_drop": -1.15, "net_pnl_if_held": -10.50, "hit_sl": True},
]

print("=" * 80)
print("HASIL PERBANDINGAN RIIL: RATIO 2.5x vs RATIO 3.8x")
print("=" * 80)
total_now = sum(t["cut_pnl"] for t in trades)
print(f"Total Hasil Sekarang (Ratio 2.5x): ${total_now:+.2f} USDT")

total_new = 0
for t in trades:
    # Jika vol >= 3.8x, tetap kena panic cut
    if t["vol"] >= 3.8:
        res = t["cut_pnl"]
        alasan = "Tetap kena panic cut (vol ekstrim)"
    else:
        # Jika vol < 3.8x, posisi jalan normal
        if t["hit_sl"] and t["net_pnl_if_held"] < 0:
            res = -10.50 # Kena Hard SL -1.15% di Binance
            alasan = "Tertahan di Hard SL -1.15% (selisih ~$1 s/d $3)"
        else:
            res = t["net_pnl_if_held"]
            alasan = "SELAMAT & PANEN CUAN!"
    total_new += res
    print(f" - {t['sym']:6} | Asli: ${t['cut_pnl']:+6.2f} ➔ Dengan 3.8x: ${res:+6.2f} | {alasan}")

print("-" * 80)
print(f"Total Hasil Jika Pakai 3.8x : ${total_new:+.2f} USDT")
print(f"SELISIH KEUNTUNGAN BERSIH   : ${total_new - total_now:+.2f} USDT (LEBIH UNTUNG SEBESAR ITU!)")
print("=" * 80)

import os, sys
sys.path.append(os.path.abspath("."))
sys.path.append(os.path.abspath("backtest"))
import config
from scratch_sim_knife import TestAntiKnife
from run_exact_vps_backtest import ExactVPSBacktest

# Baseline
base = ExactVPSBacktest()
base.load_all_data()
base.run()
base_trades = base.trades

# Option A: min_vol 0.80, require_not_bleeding True
opt_a = TestAntiKnife(min_vol=0.80, require_not_bleeding=True)
opt_a.data_15m = base.data_15m
opt_a.data_1h = base.data_1h
opt_a.ts_map_15m = base.ts_map_15m
opt_a.ts_map_1h = base.ts_map_1h
opt_a.btc_15m = base.btc_15m
opt_a.btc_1h = base.btc_1h
opt_a.run()
opt_a_trades = opt_a.trades

base_keys = set((t["entry_time"], t["symbol"], t["side"]) for t in base_trades)
a_keys = set((t["entry_time"], t["symbol"], t["side"]) for t in opt_a_trades)

eliminated = [t for t in base_trades if (t["entry_time"], t["symbol"], t["side"]) not in a_keys]
new_trades = [t for t in opt_a_trades if (t["entry_time"], t["symbol"], t["side"]) not in base_keys]

elim_wins = [t for t in eliminated if t["net_pnl"] > 0.05]
elim_losses = [t for t in eliminated if t["net_pnl"] < -0.05]
elim_be = [t for t in eliminated if abs(t["net_pnl"]) <= 0.05]

print("\n" + "="*60)
print(f"TOTAL TRADE BASELINE YANG DI-DENIED OLEH OPSI A: {len(eliminated)} trade")
print(f"Breakdown: {len(elim_wins)} Menang | {len(elim_losses)} Kalah | {len(elim_be)} BEP")
print("="*60)

print(f"\nDAFTAR SELURUH KOIN MENANG (WINNERS) YANG KEDENIED DI OPSI A (Total: {len(elim_wins)} trade):")
for t in sorted(elim_wins, key=lambda x: x["net_pnl"], reverse=True):
    et = t["entry_time"]
    sym = t["symbol"]
    sd = t["side"]
    pnl = t["net_pnl"]
    peak = t["highest_p"]
    rs = t["reason"]
    print(f"  * {et} | {sym} ({sd}) | Cuan: +{pnl:.2f} USDT | Peak: +{peak:.2f}% | Alasan: {rs}")

print(f"\nDAFTAR CONTOH KOIN KALAH (LOSSES) YANG BERHASIL DIBLOKIR DI OPSI A (Total: {len(elim_losses)} trade):")
for t in sorted(elim_losses, key=lambda x: x["net_pnl"])[:10]:
    et = t["entry_time"]
    sym = t["symbol"]
    sd = t["side"]
    pnl = t["net_pnl"]
    peak = t["highest_p"]
    rs = t["reason"]
    print(f"  - {et} | {sym} ({sd}) | Rugi: {pnl:.2f} USDT | Peak: +{peak:.2f}% | Alasan: {rs}")

print(f"\nDAFTAR KOIN JUARA BARU YANG TERAMBIL KARENA OPSI A (Total: {len(new_trades)} trade):")
new_wins = [t for t in new_trades if t["net_pnl"] > 0.05]
for t in sorted(new_wins, key=lambda x: x["net_pnl"], reverse=True)[:10]:
    et = t["entry_time"]
    sym = t["symbol"]
    sd = t["side"]
    pnl = t["net_pnl"]
    peak = t["highest_p"]
    rs = t["reason"]
    print(f"  + {et} | {sym} ({sd}) | Cuan: +{pnl:.2f} USDT | Peak: +{peak:.2f}% | Alasan: {rs}")

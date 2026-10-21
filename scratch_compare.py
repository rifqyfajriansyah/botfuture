import os, sys
sys.path.append(os.path.abspath("."))
sys.path.append(os.path.abspath("backtest"))
import config
from scratch_sim_knife import TestAntiKnife
from run_exact_vps_backtest import ExactVPSBacktest

# Run Baseline
base = ExactVPSBacktest()
base.load_all_data()
base.run()
base_trades = base.trades

# Run Filtered (Scenario 5)
filt = TestAntiKnife(min_vol=1.00, require_not_bleeding=True)
filt.data_15m = base.data_15m
filt.data_1h = base.data_1h
filt.ts_map_15m = base.ts_map_15m
filt.ts_map_1h = base.ts_map_1h
filt.btc_15m = base.btc_15m
filt.btc_1h = base.btc_1h
filt.run()
filt_trades = filt.trades

print("\n" + "="*60)
net_base = base.balance - base.initial_capital
net_filt = filt.balance - filt.initial_capital
print(f"BASELINE: {len(base_trades)} trades | Net PnL: {net_base:+.2f}")
print(f"FILTERED: {len(filt_trades)} trades | Net PnL: {net_filt:+.2f}")
print("="*60)

# Compare by timestamp and symbol
base_keys = set((t["entry_time"], t["symbol"], t["side"]) for t in base_trades)
filt_keys = set((t["entry_time"], t["symbol"], t["side"]) for t in filt_trades)

eliminated = [t for t in base_trades if (t["entry_time"], t["symbol"], t["side"]) not in filt_keys]
new_trades = [t for t in filt_trades if (t["entry_time"], t["symbol"], t["side"]) not in base_keys]

elim_losses = [t for t in eliminated if t["net_pnl"] < -0.05]
elim_be = [t for t in eliminated if abs(t["net_pnl"]) <= 0.05]
elim_wins = [t for t in eliminated if t["net_pnl"] > 0.05]
pnl_elim = sum(t["net_pnl"] for t in eliminated)

print(f"\n1. TRADE YANG BERHASIL DIBUANG OLEH FILTER: {len(eliminated)} trade")
print(f"   Breakdown: {len(elim_losses)} Loss | {len(elim_be)} BEP | {len(elim_wins)} Win")
print(f"   Total Net PnL dari trade yang dibuang: {pnl_elim:+.2f} USDT")

print("\n   Daftar Trade Loss yang Berhasil Dibuang (Contoh 10 Terburuk):")
for t in sorted(elim_losses, key=lambda x: x["net_pnl"])[:10]:
    entry_t = t['entry_time']
    sym = t['symbol']
    side = t['side']
    pnl = t['net_pnl']
    reason = t['reason']
    print(f"   - {entry_t} | {sym} ({side}) | PnL: {pnl:+.2f} USDT | Alasan: {reason}")

if elim_wins:
    print(f"\n   Daftar Trade Win yang Ikut Terfilter (Total {len(elim_wins)} trade):")
    for t in sorted(elim_wins, key=lambda x: x["net_pnl"], reverse=True)[:5]:
        entry_t = t['entry_time']
        sym = t['symbol']
        side = t['side']
        pnl = t['net_pnl']
        reason = t['reason']
        print(f"   * {entry_t} | {sym} ({side}) | Cuan: {pnl:+.2f} USDT | Alasan: {reason}")

new_wins = [t for t in new_trades if t["net_pnl"] > 0.05]
new_losses = [t for t in new_trades if t["net_pnl"] < -0.05]
new_be = [t for t in new_trades if abs(t["net_pnl"]) <= 0.05]
pnl_new = sum(t["net_pnl"] for t in new_trades)

print(f"\n2. TRADE BARU YANG DIAMBIL (KARENA SLOT MODAL TIDAK TERJEBAK DI KOIN DUMP): {len(new_trades)} trade")
print(f"   Breakdown: {len(new_wins)} Win | {len(new_losses)} Loss | {len(new_be)} BEP")
print(f"   Total Net PnL dari trade baru yang didapat: {pnl_new:+.2f} USDT")

print("\n   Daftar Trade Baru Juara (Top Winners Baru):")
for t in sorted(new_wins, key=lambda x: x["net_pnl"], reverse=True)[:8]:
    entry_t = t['entry_time']
    sym = t['symbol']
    side = t['side']
    pnl = t['net_pnl']
    reason = t['reason']
    print(f"   + {entry_t} | {sym} ({side}) | Cuan: {pnl:+.2f} USDT | Alasan: {reason}")

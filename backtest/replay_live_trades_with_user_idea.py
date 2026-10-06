import json
import os

state_file = "/Users/macpro/Documents/Aplikasiku/Binance Bot/backtest/vps_bot_state.json"
with open(state_file) as f:
    state = json.load(f)

history = state.get("trade_history", [])

initial_balance = 287.0
balance_vps_real = initial_balance
balance_with_user_idea = initial_balance
balance_user_snowball = initial_balance

tebas_trades = []

for i, t in enumerate(history):
    sym = t.get("symbol", "").split(":")[0]
    side = t.get("side", "")
    pnl_usd = t.get("pnl_usd", 0.0)
    peak_p = t.get("highest_profit_pct", 0.0)
    reason = t.get("reason", t.get("close_reason", ""))
    
    # 1. Real PnL as it actually occurred on VPS
    balance_vps_real += pnl_usd
    
    # 2. Replay with User's Tebas Cuan (Fixed $245 margin)
    # Jika peak >= +0.85% harga (setara $6.25+ USD) dan melorot turun ke BEP/mid_range:
    # Tebas di +0.54% harga (+$4.00 USD)
    pos_fixed = 245.0 * 3 # $735
    if peak_p >= 0.85 and ("mid_range_guard" in reason or "position_closed_on_exchange" in reason or "stall_guard" in reason or pnl_usd < 1.0):
        tebas_pnl = pos_fixed * (0.54 / 100) - (pos_fixed * 0.0008)
        balance_with_user_idea += tebas_pnl
        tebas_trades.append({'sym': sym, 'side': side, 'peak': peak_p, 'real_pnl': pnl_usd, 'tebas_pnl': tebas_pnl, 'reason': reason})
    elif peak_p >= 0.65 and ("mid_range_guard" in reason or "position_closed_on_exchange" in reason or pnl_usd < 1.0):
        tebas_pnl = pos_fixed * (0.35 / 100) - (pos_fixed * 0.0008)
        balance_with_user_idea += tebas_pnl
        tebas_trades.append({'sym': sym, 'side': side, 'peak': peak_p, 'real_pnl': pnl_usd, 'tebas_pnl': tebas_pnl, 'reason': reason})
    else:
        balance_with_user_idea += pnl_usd

    # 3. Replay with User's Tebas Cuan + BOLA SALJU (COMPOUNDING)
    dynamic_margin = balance_user_snowball * 0.85
    pos_dynamic = dynamic_margin * 3
    if peak_p >= 0.85 and ("mid_range_guard" in reason or "position_closed_on_exchange" in reason or "stall_guard" in reason or pnl_usd < 1.0):
        snowball_pnl = pos_dynamic * (0.54 / 100) - (pos_dynamic * 0.0008)
        balance_user_snowball += snowball_pnl
    elif peak_p >= 0.65 and ("mid_range_guard" in reason or "position_closed_on_exchange" in reason or pnl_usd < 1.0):
        snowball_pnl = pos_dynamic * (0.35 / 100) - (pos_dynamic * 0.0008)
        balance_user_snowball += snowball_pnl
    else:
        if pnl_usd > 0:
            scale = dynamic_margin / 245.0
            balance_user_snowball += (pnl_usd * scale)
        else:
            # cutloss max cap
            loss_cap = - (dynamic_margin * 0.0225)
            balance_user_snowball += max(loss_cap, pnl_usd)

print("=" * 80)
print(f"📊 REPLAY KE SELURUH {len(history)} TRADE NYATA YANG PERNAH BOT KITA JALANKAN")
print("=" * 80)
print(f"Modal Awal                             : ${initial_capital_str:s}" if False else f"Modal Awal                             : ${initial_balance:.2f} USDT")
print(f"SALDO ASLI SAAT INI (Riil di Akun)    : ${balance_vps_real:.2f} USDT")
print(f"SALDO JIKA PAKAI IDE TEBAS CUAN USER   : ${balance_with_user_idea:.2f} USDT 💎 (+${balance_with_user_idea - balance_vps_real:+.2f} USDT)")
print(f"SALDO JIKA IDE USER + BOLA SALJU       : ${balance_user_snowball:.2f} USDT 🚀🔥 (+${balance_user_snowball - balance_vps_real:+.2f} USDT)")
print("-" * 80)
print(f"🛡️ Total Trade yang Jadi Korban BEP/Receh : {len(tebas_trades)} Trade!")
print("Contoh koin yang melayang cuannya:")
for t in tebas_trades[-8:]:
    print(f"   - {t['sym']:10} {t['side'].upper():5} | Peak Sempat: +{t['peak']:.2f}% | Hasil Asli: ${t['real_pnl']:+.2f} -> DITEBAS AMAN: ${t['tebas_pnl']:+.2f} USDT | Alasan Asli: {t['reason']}")
print("=" * 80)

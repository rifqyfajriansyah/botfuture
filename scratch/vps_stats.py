import json, ccxt
from config import BINANCE_API_KEY, BINANCE_API_SECRET

ex = ccxt.binance({
    'apiKey': BINANCE_API_KEY,
    'secret': BINANCE_API_SECRET,
    'options': {'defaultType': 'future'}
})

bal = ex.fetch_balance()
usdt = bal.get('USDT', {})
total_equity = float(usdt.get('total', 0) or 0)
free_bal = float(usdt.get('free', 0) or 0)

with open('/home/ubuntu/binance-bot/bot_state.json') as f:
    d = json.load(f)

trades = d.get('trade_history', [])

# Today
today_trades = [t for t in trades if t.get('close_time', '').startswith('2026-10-17')]
wins_today = [t for t in today_trades if float(t.get('pnl', 0)) > 0]
loss_today = [t for t in today_trades if float(t.get('pnl', 0)) <= 0]
pnl_wins_today = sum(float(t.get('pnl', 0)) for t in wins_today)
pnl_loss_today = sum(float(t.get('pnl', 0)) for t in loss_today)
net_today = pnl_wins_today + pnl_loss_today

# Since Oct 12
trades_12 = [t for t in trades if t.get('close_time', '') >= '2026-10-12T16:19:00']
wins_12 = [t for t in trades_12 if float(t.get('pnl', 0)) > 0]
loss_12 = [t for t in trades_12 if float(t.get('pnl', 0)) <= 0]
pnl_wins_12 = sum(float(t.get('pnl', 0)) for t in wins_12)
pnl_loss_12 = sum(float(t.get('pnl', 0)) for t in loss_12)
net_12 = pnl_wins_12 + pnl_loss_12

# All Time
wins_all = [t for t in trades if float(t.get('pnl', 0)) > 0]
loss_all = [t for t in trades if float(t.get('pnl', 0)) <= 0]
pnl_wins_all = sum(float(t.get('pnl', 0)) for t in wins_all)
pnl_loss_all = sum(float(t.get('pnl', 0)) for t in loss_all)
net_all = pnl_wins_all + pnl_loss_all

print(f"TOTAL MODAL / EQUITY LIVE: ${total_equity:.2f} USDT (~ Rp {total_equity * 16300:,.0f})")
print(f"SALDO KAS TERSEDIA (FREE): ${free_bal:.2f} USDT")
print("=" * 60)
print(f"1. HARI INI (17 OKT 2026):")
print(f"   • Total Trade : {len(today_trades)}")
print(f"   • Menang      : {len(wins_today)} trade (+${pnl_wins_today:.2f} USDT)")
print(f"   • Kalah       : {len(loss_today)} trade (${pnl_loss_today:.2f} USDT)")
print(f"   • Win Rate    : {len(wins_today)/len(today_trades)*100:.1f}%")
print(f"   • Net Cuan    : {net_today:+.2f} USDT (~ Rp {net_today * 16300:,.0f})")
print(f"   • Rata-rata Win  : +${pnl_wins_today/max(1, len(wins_today)):.2f} USDT")
print(f"   • Rata-rata Loss : ${pnl_loss_today/max(1, len(loss_today)):.2f} USDT")
print("=" * 60)
print(f"2. PERIODE PASCA-UPDATE (12 - 17 OKT):")
print(f"   • Total Trade : {len(trades_12)}")
print(f"   • Menang      : {len(wins_12)} trade (+${pnl_wins_12:.2f} USDT)")
print(f"   • Kalah       : {len(loss_12)} trade (${pnl_loss_12:.2f} USDT)")
print(f"   • Win Rate    : {len(wins_12)/len(trades_12)*100:.1f}%")
print(f"   • Net Cuan    : {net_12:+.2f} USDT (~ Rp {net_12 * 16300:,.0f})")
print("=" * 60)
print(f"3. SELURUH HISTORI (ALL-TIME):")
print(f"   • Total Trade : {len(trades)}")
print(f"   • Menang      : {len(wins_all)} trade (+${pnl_wins_all:.2f} USDT)")
print(f"   • Kalah       : {len(loss_all)} trade (${pnl_loss_all:.2f} USDT)")
print(f"   • Win Rate    : {len(wins_all)/len(trades)*100:.1f}%")
print(f"   • Net PnL     : {net_all:+.2f} USDT (~ Rp {net_all * 16300:,.0f})")
print("=" * 60)

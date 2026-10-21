import json
import re
import glob

with open("/home/ubuntu/binance-bot/bot_state.json") as f:
    d = json.load(f)

trades = [t for t in d.get("trade_history", []) if t.get("entry_time", "") >= "2026-10-15"]

all_log_text = ""
for log_file in sorted(glob.glob("/home/ubuntu/binance-bot/logs/bot_2026-10-1[567].log") + glob.glob("/home/ubuntu/binance-bot/logs/trades_2026-10-1[567].log")):
    with open(log_file, errors="ignore") as f:
        all_log_text += "\n" + f.read()

btc_regimes = re.findall(
    r"\[([\d\-]+ [\d\:]+)\] INFO\s+\|\s+🧭 BTC Market Regime: (\w+).*?\(1H Close: ([\d\.]+), 15m RSI: ([\d\.]+), 15m Chg: ([+-]?[\d\.]+)%\)",
    all_log_text
)
btc_regimes.sort(key=lambda x: x[0])

trade_data = []
for t in trades:
    sym = t.get("symbol")
    side = t.get("side").upper()
    entry_raw = t.get("entry_time", "")[:19]
    entry_fmt = entry_raw.replace("T", " ")
    pnl = t.get("pnl", 0.0)
    hp = t.get("highest_profit_pct", 0.0)
    reason = t.get("close_reason", "")
    
    btc_match = None
    for b_time, bias, close_1h, rsi_15m, chg_15m in btc_regimes:
        if b_time <= entry_fmt:
            btc_match = (bias, float(close_1h), float(rsi_15m), float(chg_15m), b_time)
        else:
            break
            
    trade_data.append({
        "sym": sym,
        "side": side,
        "entry_time": entry_fmt,
        "pnl": pnl,
        "hp": hp,
        "reason": reason,
        "btc": btc_match
    })

print("="*80)
print("--- UJI BOUNDARY LENGKAP: 4 PINTU PENGAMAN KHUSUS PASAR CHOP ---")
print("1. Di Chop, LONG dilarang jika BTC RSI >= 60.0 (Anti Pucuk Resisten)")
print("2. Di Chop, LONG dilarang jika BTC RSI <= 42.0 (Anti Pisau Jatuh saat BTC Melorot)")
print("3. Di Chop, SHORT dilarang jika BTC RSI >= 58.0 (Anti Tabrak Rebound BTC)")
print("4. Di Chop, SHORT dilarang jika BTC RSI <= 38.0 (Anti Short di Dasar Lantai Support)")
print("="*80)

for max_long_rsi in [59.0, 60.0, 61.0]:
    for min_short_rsi in [56.0, 57.0, 58.0]:
        locked_wins = []
        saved_losses = []
        for td in trade_data:
            if not td["btc"]: continue
            bias = td["btc"][0]
            rsi = td["btc"][2]
            side = td["side"]
            if bias == "SIDEWAYS":
                blocked = False
                if side == "LONG" and rsi >= max_long_rsi:
                    blocked = True
                elif side == "SHORT" and rsi >= min_short_rsi:
                    blocked = True
                
                if blocked:
                    if td["pnl"] > 0: locked_wins.append(td)
                    else: saved_losses.append(td)
        
        missed = sum(td["pnl"] for td in locked_wins)
        saved = sum(abs(td["pnl"]) for td in saved_losses)
        net = saved - missed
        print(f"MaxLongRSI: {max_long_rsi:.1f} | MinShortRSI: {min_short_rsi:.1f} --> Locked Wins: {len(locked_wins)} (-${missed:.2f}) | Saved Losses: {len(saved_losses)} (+${saved:.2f}) | NET: {net:+.2f} USDT")

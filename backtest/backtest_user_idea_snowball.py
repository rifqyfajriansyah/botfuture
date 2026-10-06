import os
import sys
import glob
import math
import time
from datetime import datetime
import pandas as pd
import numpy as np

BOT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BOT_ROOT)
import config
from backtest_engine import calculate_indicators

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

class UserIdeaSnowballBacktest:
    """
    Kombinasi Pamungkas:
    1. Ide Tebas Cuan Pengguna (Choppy + Belum Cuan 8% Modal diperketat)
    2. DITAMBAH SISTEM BOLA SALJU (COMPOUNDING):
       Margin mengikuti saldo dompet secara dinamis (85% balance, 3x leverage)!
    """
    def __init__(self, initial_capital=287.0, leverage=3, margin_ratio=0.85):
        self.initial_capital = initial_capital
        self.balance = initial_capital
        self.leverage = leverage
        self.margin_ratio = margin_ratio
        
        self.data_15m = {}
        self.data_1h = {}
        self.ts_map_15m = {}
        self.ts_map_1h = {}
        self.btc_15m = None
        self.btc_1h = None
        
        self.trades = []
        self.active_trade = None
        self.cooldown_until = 0

    def load_all_data(self):
        files_15m = glob.glob(os.path.join(DATA_DIR, "*_15m.csv"))
        for f in files_15m:
            sym_clean = os.path.basename(f).replace("_15m.csv", "")
            f_1h = os.path.join(DATA_DIR, f"{sym_clean}_1h.csv")
            if not os.path.exists(f_1h):
                continue
            try:
                df15 = pd.read_csv(f)
                df1 = pd.read_csv(f_1h)
                if len(df15) < 300 or len(df1) < 100:
                    continue
                df15 = calculate_indicators(df15, is_1h=False)
                df1 = calculate_indicators(df1, is_1h=True)
                
                symbol = sym_clean.replace("_USDT", "/USDT:USDT").replace("_", "/")
                if not symbol.endswith(":USDT"):
                    symbol += ":USDT"
                    
                self.data_15m[symbol] = df15
                self.data_1h[symbol] = df1
                self.ts_map_15m[symbol] = {ts: idx for idx, ts in enumerate(df15['timestamp'])}
                self.ts_map_1h[symbol] = {ts: idx for idx, ts in enumerate(df1['timestamp'])}
                
                if "BTC" in symbol:
                    self.btc_15m = df15
                    self.btc_1h = df1
            except Exception:
                continue

    def get_btc_regime(self, ts):
        if self.btc_1h is None:
            return "neutral"
        btc_ts_map = self.ts_map_1h.get("BTC/USDT:USDT") or self.ts_map_1h.get("BTC/USDT")
        if not btc_ts_map:
            return "neutral"
        hour_ts = ts - (ts % (3600 * 1000))
        idx_1h = btc_ts_map.get(hour_ts)
        if idx_1h is None or idx_1h < 55:
            return "neutral"
        last_1h = self.btc_1h.iloc[idx_1h]
        c = last_1h['close']
        ema50 = last_1h['ema50']
        idx_15m = self.ts_map_15m.get("BTC/USDT:USDT", {}).get(ts)
        rsi15 = self.btc_15m.iloc[idx_15m]['rsi'] if idx_15m is not None else 50.0
        
        if c > ema50 and rsi15 >= 42:
            return "bullish"
        elif c < ema50 and rsi15 <= 58:
            return "bearish"
        return "neutral"

    def scan_for_entry(self, ts):
        btc_regime = self.get_btc_regime(ts)
        hour_ts = ts - (ts % (3600 * 1000))
        candidates = []
        
        for symbol, df15 in self.data_15m.items():
            if "BTC" in symbol:
                continue
            idx15 = self.ts_map_15m[symbol].get(ts)
            if idx15 is None or idx15 < 55:
                continue
            df1 = self.data_1h.get(symbol)
            idx1 = self.ts_map_1h[symbol].get(hour_ts)
            if df1 is None or idx1 is None or idx1 < 55:
                continue
                
            curr15 = df15.iloc[idx15]
            curr1 = df1.iloc[idx1]
            
            macro_bullish = curr1['close'] > curr1['ema50'] and curr1['ema20'] > curr1['ema50']
            macro_bearish = curr1['close'] < curr1['ema50'] and curr1['ema20'] < curr1['ema50']
            
            if config.STRICT_HTF_REQUIRED:
                can_long = macro_bullish and (btc_regime in ["bullish", "neutral"])
                can_short = macro_bearish and (btc_regime in ["bearish", "neutral"])
            else:
                can_long = (btc_regime in ["bullish", "neutral"])
                can_short = (btc_regime in ["bearish", "neutral"])
                
            vol_ratio = curr15.get('vol_ratio', 1.0)
            if vol_ratio < config.MIN_VOLUME_RATIO:
                continue
                
            atr_pct = curr15.get('atr_pct', 1.0)
            price = curr15['close']
            ema20 = curr15['ema20']
            ema50 = curr15['ema50']
            
            if can_long:
                is_uptrend_15m = curr15['ema20'] > curr15['ema50']
                near_ema20 = abs(price - ema20) / ema20 * 100 <= 0.8
                near_ema50 = abs(price - ema50) / ema50 * 100 <= 1.0
                wick_ok = curr15['lower_wick_pct'] >= config.MIN_ENTRY_REJECTION_WICK_PERCENT
                rsi_ok = 38 <= curr15['rsi'] <= 68
                
                if (near_ema20 or near_ema50) and wick_ok and rsi_ok and is_uptrend_15m:
                    score = 70
                    if macro_bullish: score += 10
                    if btc_regime == "bullish": score += 5
                    if vol_ratio >= 1.2: score += 5
                    if curr15['lower_wick_pct'] >= 35: score += 5
                    if score >= config.SIGNAL_MIN_SCORE:
                        candidates.append({'symbol': symbol, 'side': 'long', 'score': score, 'price': price, 'atr_pct': atr_pct, 'timestamp': ts})
                        
            if can_short:
                is_downtrend_15m = curr15['ema20'] < curr15['ema50']
                near_ema20 = abs(price - ema20) / ema20 * 100 <= 0.8
                near_ema50 = abs(price - ema50) / ema50 * 100 <= 1.0
                wick_ok = curr15['upper_wick_pct'] >= config.MIN_ENTRY_REJECTION_WICK_PERCENT
                rsi_ok = 32 <= curr15['rsi'] <= 62
                
                if (near_ema20 or near_ema50) and wick_ok and rsi_ok and is_downtrend_15m:
                    score = 70
                    if macro_bearish: score += 10
                    if btc_regime == "bearish": score += 5
                    if vol_ratio >= 1.2: score += 5
                    if curr15['upper_wick_pct'] >= 35: score += 5
                    if score >= config.SIGNAL_MIN_SCORE:
                        candidates.append({'symbol': symbol, 'side': 'short', 'score': score, 'price': price, 'atr_pct': atr_pct, 'timestamp': ts})
                        
        if not candidates:
            return None
        candidates.sort(key=lambda x: x['score'], reverse=True)
        return candidates[0]

    def run(self):
        self.load_all_data()
        timestamps = sorted(self.btc_15m['timestamp'].tolist())
        print(f"⏱️ Memulai Replay Ide Tebas Cuan + BOLA SALJU COMPOUNDING ({len(timestamps)} lilin)...")
        t0 = time.time()
        for idx, ts in enumerate(timestamps):
            if self.active_trade is not None:
                self.manage_active_trade(ts)
            if self.active_trade is None and ts >= self.cooldown_until:
                setup = self.scan_for_entry(ts)
                if setup:
                    self.open_trade(setup)
        print(f"✅ Selesai dalam {time.time() - t0:.1f}s!")
        self.print_summary()

    def open_trade(self, setup):
        symbol = setup['symbol']
        side = setup['side']
        entry_price = setup['price']
        atr_pct = setup['atr_pct']
        
        # BOLA SALJU DINAMIS
        dynamic_margin = max(50.0, self.balance * self.margin_ratio)
        position_size_usd = dynamic_margin * self.leverage
        
        max_loss_pct = 1.15
        if side == "long":
            stop_price = entry_price * (1 - max_loss_pct / 100)
        else:
            stop_price = entry_price * (1 + max_loss_pct / 100)
            
        raw_tp = atr_pct * config.DYNAMIC_TP_ATR_MULTIPLIER
        tp1_target = max(config.DYNAMIC_TP_MIN_PERCENT, min(config.DYNAMIC_TP_MAX_PERCENT, raw_tp))
        
        raw_cp1 = atr_pct * config.TRAILING_FIRST_CHECKPOINT_ATR_RATIO
        cp1_target = max(config.TRAILING_FIRST_CHECKPOINT_MIN_PERCENT, min(config.TRAILING_FIRST_CHECKPOINT_MAX_PERCENT, raw_cp1))
        
        # Target 8% dari modal trade saat ini
        target_8pct_usd = dynamic_margin * 0.08
        
        self.active_trade = {
            'symbol': symbol,
            'side': side,
            'entry_time': setup['timestamp'],
            'entry_price': entry_price,
            'stop_price': stop_price,
            'current_stop_profit_level': -max_loss_pct,
            'highest_profit_pct': 0.0,
            'lowest_profit_pct': 0.0,
            'highest_profit_usd': 0.0,
            'partial_tp_done': False,
            'partial_tp_pnl': 0.0,
            'atr_pct': atr_pct,
            'tp1_target': tp1_target,
            'cp1_target': cp1_target,
            'remaining_ratio': 1.0,
            'position_size_usd': position_size_usd,
            'margin_used': dynamic_margin,
            'target_8pct_usd': target_8pct_usd
        }

    def manage_active_trade(self, ts):
        trade = self.active_trade
        symbol = trade['symbol']
        side = trade['side']
        entry_price = trade['entry_price']
        atr_pct = trade['atr_pct']
        pos_size = trade['position_size_usd']
        margin = trade['margin_used']
        
        df15 = self.data_15m.get(symbol)
        idx15 = self.ts_map_15m.get(symbol, {}).get(ts)
        if df15 is None or idx15 is None:
            return
            
        bar = df15.iloc[idx15]
        high = bar['high']
        low = bar['low']
        close = bar['close']
        adx = bar.get('adx', 25.0)
        is_choppy = (adx < config.CHOPPY_ADX_THRESHOLD)
        elapsed_hours = (ts - trade['entry_time']) / (1000 * 3600)
        
        if side == "long":
            candle_max_profit = ((high - entry_price) / entry_price) * 100
            candle_min_profit = ((low - entry_price) / entry_price) * 100
            curr_profit = ((close - entry_price) / entry_price) * 100
        else:
            candle_max_profit = ((entry_price - low) / entry_price) * 100
            candle_min_profit = ((entry_price - high) / entry_price) * 100
            curr_profit = ((entry_price - close) / entry_price) * 100
            
        trade['highest_profit_pct'] = max(trade['highest_profit_pct'], candle_max_profit)
        trade['lowest_profit_pct'] = min(trade['lowest_profit_pct'], candle_min_profit)
        hp = trade['highest_profit_pct']
        
        peak_usd = pos_size * (hp / 100)
        curr_usd = pos_size * (curr_profit / 100)
        trade['highest_profit_usd'] = max(trade['highest_profit_usd'], peak_usd)
        
        is_under_8pct = (trade['highest_profit_usd'] < trade['target_8pct_usd'])
        
        # 🎯 LOGIKA USER DALAM BOLA SALJU (PERSENTASE RELATIF TERHADAP MODAL DINAMIS):
        # Peak mencapai ~2.6% ROE (setara $6.50 pada margin $245)
        # Jika turun ke ~1.6% ROE (setara $4.00) -> TEBAS!
        # Dikonversi ke pergerakan harga koin (leverage 3x):
        # 2.6% ROE = +0.87% harga
        # 1.6% ROE = +0.54% harga
        if is_choppy and is_under_8pct:
            if hp >= 0.85: # Koin sempat naik +0.85% (cuan tebal)
                lock_price_pct = 0.54 # Kunci stop di +0.54% harga (cuan aman)
                if trade['current_stop_profit_level'] < lock_price_pct:
                    trade['current_stop_profit_level'] = lock_price_pct
                    if side == "long":
                        trade['stop_price'] = max(trade['stop_price'], entry_price * (1 + lock_price_pct / 100))
                    else:
                        trade['stop_price'] = min(trade['stop_price'], entry_price * (1 - lock_price_pct / 100))
                        
            elif hp >= 0.65:
                lock_price_pct = 0.35
                if trade['current_stop_profit_level'] < lock_price_pct:
                    trade['current_stop_profit_level'] = lock_price_pct
                    if side == "long":
                        trade['stop_price'] = max(trade['stop_price'], entry_price * (1 + lock_price_pct / 100))
                    else:
                        trade['stop_price'] = min(trade['stop_price'], entry_price * (1 - lock_price_pct / 100))
                        
            elif hp >= 0.45:
                lock_price_pct = 0.12 # Kunci BEP
                if trade['current_stop_profit_level'] < lock_price_pct:
                    trade['current_stop_profit_level'] = lock_price_pct
                    if side == "long":
                        trade['stop_price'] = max(trade['stop_price'], entry_price * (1 + lock_price_pct / 100))
                    else:
                        trade['stop_price'] = min(trade['stop_price'], entry_price * (1 - lock_price_pct / 100))

        # Standar Choppy Auto-BEP
        if is_choppy and config.CHOPPY_AUTO_BEP_ENABLED:
            if candle_max_profit >= config.CHOPPY_BEP_TRIGGER_PERCENT:
                lock_pct = getattr(config, "CHOPPY_BEP_LOCK_PERCENT", 0.12)
                if trade['current_stop_profit_level'] < lock_pct:
                    trade['current_stop_profit_level'] = lock_pct
                    if side == "long":
                        trade['stop_price'] = max(trade['stop_price'], entry_price * (1 + lock_pct / 100))
                    else:
                        trade['stop_price'] = min(trade['stop_price'], entry_price * (1 - lock_pct / 100))

        # Checkpoint 1 Ratchet Normal
        if not trade['partial_tp_done'] and candle_max_profit >= trade['cp1_target']:
            stop1 = max(config.TRAILING_FIRST_STOP_MIN_PERCENT, min(config.TRAILING_FIRST_STOP_MAX_PERCENT, atr_pct * config.TRAILING_FIRST_STOP_ATR_RATIO))
            if trade['current_stop_profit_level'] < stop1:
                trade['current_stop_profit_level'] = stop1
                if side == "long":
                    trade['stop_price'] = max(trade['stop_price'], entry_price * (1 + stop1 / 100))
                else:
                    trade['stop_price'] = min(trade['stop_price'], entry_price * (1 - stop1 / 100))

        # Partial TP1 Target Normal
        target_tp = config.CHOPPY_CP1_PERCENT if is_choppy else trade['tp1_target']
        if not trade['partial_tp_done'] and candle_max_profit >= target_tp:
            trade['partial_tp_done'] = True
            trade['remaining_ratio'] = 0.5
            tp1_pnl = (pos_size * 0.5) * (target_tp / 100)
            trade['partial_tp_pnl'] = tp1_pnl
            
            bep_lvl = 0.22
            trade['current_stop_profit_level'] = max(trade['current_stop_profit_level'], bep_lvl)
            if side == "long":
                trade['stop_price'] = max(trade['stop_price'], entry_price * (1 + bep_lvl / 100))
            else:
                trade['stop_price'] = min(trade['stop_price'], entry_price * (1 - bep_lvl / 100))

        # Moonbag Trailing untuk Sisa Posisi
        if trade['partial_tp_done']:
            offset = max(config.TRAILING_STOP_OFFSET_MIN, min(config.TRAILING_STOP_OFFSET_MAX, atr_pct * config.TRAILING_STOP_OFFSET_ATR_RATIO))
            trailing_level = hp - offset
            if trailing_level > trade['current_stop_profit_level']:
                trade['current_stop_profit_level'] = trailing_level
                if side == "long":
                    trade['stop_price'] = max(trade['stop_price'], entry_price * (1 + trailing_level / 100))
                else:
                    trade['stop_price'] = min(trade['stop_price'], entry_price * (1 - trailing_level / 100))

        # Timeout Moonbag 3.5 jam
        if trade['partial_tp_done'] and elapsed_hours >= config.MOONBAG_TIMEOUT_HOURS:
            if curr_profit <= config.MOONBAG_TIMEOUT_MAX_PROFIT:
                self.close_trade(ts, close, reason=f"moonbag_timeout_{elapsed_hours:.1f}h")
                return

        # Cek Stop Hit
        stop_hit = False
        if side == "long" and low <= trade['stop_price']:
            stop_hit = True
            exit_price = trade['stop_price']
        elif side == "short" and high >= trade['stop_price']:
            stop_hit = True
            exit_price = trade['stop_price']
            
        if stop_hit:
            reason = "stop_loss" if trade['current_stop_profit_level'] <= 0 else "tebas_cuan_trail_guard"
            self.close_trade(ts, exit_price, reason=reason)
            return

        # Bounded cutloss jika struktur rusak
        if not trade['partial_tp_done'] and curr_profit <= -0.75:
            self.close_trade(ts, close, reason="bounce_failure_cutloss")
            return

    def close_trade(self, ts, exit_price, reason):
        trade = self.active_trade
        side = trade['side']
        entry_price = trade['entry_price']
        rem_ratio = trade['remaining_ratio']
        pos_size = trade['position_size_usd']
        margin = trade['margin_used']
        
        if side == "long":
            pct = ((exit_price - entry_price) / entry_price) * 100
        else:
            pct = ((entry_price - exit_price) / entry_price) * 100
            
        rem_pnl = (pos_size * rem_ratio) * (pct / 100)
        total_pnl = trade['partial_tp_pnl'] + rem_pnl
        fee = pos_size * 0.0008
        net_pnl = total_pnl - fee
        
        max_loss_cap = - (margin * 0.0225)
        if net_pnl < max_loss_cap:
            net_pnl = max_loss_cap
            
        self.balance += net_pnl
        duration_hours = (ts - trade['entry_time']) / (1000 * 3600)
        
        trade_record = {
            'symbol': trade['symbol'].split(":")[0],
            'side': side,
            'entry_time': datetime.fromtimestamp(trade['entry_time'] / 1000).strftime('%Y-%m-%d %H:%M'),
            'close_time': datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d %H:%M'),
            'duration_h': round(duration_hours, 1),
            'entry_price': entry_price,
            'exit_price': exit_price,
            'margin': round(margin, 2),
            'net_pnl': round(net_pnl, 2),
            'highest_p': round(trade['highest_profit_pct'], 2),
            'lowest_p': round(trade['lowest_profit_pct'], 2),
            'reason': reason,
            'balance': round(self.balance, 2)
        }
        self.trades.append(trade_record)
        self.active_trade = None
        self.cooldown_until = ts + (60 * 60 * 1000)

    def print_summary(self):
        if not self.trades:
            print("❌ Tidak ada trade!")
            return
        df_trades = pd.DataFrame(self.trades)
        total_trades = len(df_trades)
        wins = df_trades[df_trades['net_pnl'] > 0]
        losses = df_trades[df_trades['net_pnl'] < 0]
        beps = df_trades[df_trades['net_pnl'] == 0]
        
        win_rate = (len(wins) / total_trades) * 100
        gross_profit = wins['net_pnl'].sum()
        gross_loss = abs(losses['net_pnl'].sum())
        profit_factor = gross_profit / (gross_loss + 1e-9)
        net_pnl = self.balance - self.initial_capital
        growth_pct = (net_pnl / self.initial_capital) * 100
        
        df_trades['cum_max'] = df_trades['balance'].cummax()
        df_trades['drawdown'] = df_trades['cum_max'] - df_trades['balance']
        max_dd = df_trades['drawdown'].max()
        max_dd_pct = (max_dd / df_trades['cum_max'].max()) * 100
        
        print("\n" + "=" * 75)
        print("❄️🚀 HASIL SIMULASI IDE TEBAS CUAN + BOLA SALJU (COMPOUNDING)")
        print("=" * 75)
        print(f"Periode Uji          : {df_trades.iloc[0]['entry_time']} s/d {df_trades.iloc[-1]['close_time']}")
        print(f"Modal Awal           : {self.initial_capital:.2f} USDT")
        print(f"SALDO AKHIR (BOLA SALJU): {self.balance:,.2f} USDT 💎🚀🔥")
        print(f"Total Keuntungan Net : {net_pnl:+,.2f} USDT ({growth_pct:+,.1f}%) 💥")
        print(f"Total Trade          : {total_trades}")
        print(f"Win / Loss / BEP     : {len(wins)} Win / {len(losses)} Loss / {len(beps)} BEP")
        print(f"Win Rate             : {win_rate:.1f}% 🔥")
        print(f"Profit Factor        : {profit_factor:.2f}")
        print(f"Max Drawdown (MDD)   : -{max_dd:.2f} USDT (-{max_dd_pct:.1f}%)")
        print(f"Margin Terkecil      : ${df_trades['margin'].min():.2f} USDT")
        print(f"Margin Terbesar      : ${df_trades['margin'].max():.2f} USDT")
        print("-" * 75)
        
        df_trades['month'] = pd.to_datetime(df_trades['entry_time']).dt.to_period('M')
        monthly = df_trades.groupby('month').agg(
            trades=('net_pnl', 'count'),
            win_count=('net_pnl', lambda x: (x > 0).sum()),
            pnl=('net_pnl', 'sum'),
            end_bal=('balance', 'last')
        )
        monthly['win_rate'] = (monthly['win_count'] / monthly['trades']) * 100
        print("\n📅 PERTUMBUHAN BOLA SALJU PER BULAN:")
        for m, row in monthly.iterrows():
            print(f"   - Bulan {str(m):7} : {row['trades']:2.0f} Trade | Win Rate: {row['win_rate']:5.1f}% | Cuan: {row['pnl']:+8.2f} USDT | Saldo Jadi: ${row['end_bal']:,.2f} USDT")
            
        print("\n🌟 5 TRADE TOP WINNERS (CUAN BOLA SALJU TERBESAR):")
        top_w = df_trades.sort_values('net_pnl', ascending=False).head(5)
        for _, r in top_w.iterrows():
            print(f"   - {r['entry_time']} | {r['symbol']:10} {r['side'].upper():5} | Margin: ${r['margin']:.0f} | Cuan: {r['net_pnl']:+7.2f} USDT | Peak: +{r['highest_p']:.2f}%")
        print("=" * 75)

if __name__ == "__main__":
    b = UserIdeaSnowballBacktest(initial_capital=287.0, leverage=3, margin_ratio=0.85)
    b.run()

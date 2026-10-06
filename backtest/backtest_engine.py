import os
import sys
import glob
import math
import time
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Setup path to import config
BOT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BOT_ROOT)
import config

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def calculate_indicators(df, is_1h=False):
    """Hitung semua indikator teknikal persis seperti signal_engine & trailing_manager."""
    if len(df) < 60:
        return df
        
    close = df['close']
    high = df['high']
    low = df['low']
    vol = df['volume']
    
    # EMAs
    df['ema20'] = close.ewm(span=20, adjust=False).mean()
    df['ema50'] = close.ewm(span=50, adjust=False).mean()
    df['ema200'] = close.ewm(span=200, adjust=False).mean()
    
    # RSI (14)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # ATR (14)
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()
    df['atr_pct'] = (df['atr'] / close) * 100
    
    # Volume MA (20)
    df['vol_ma20'] = vol.rolling(window=20).mean()
    df['vol_ratio'] = vol / (df['vol_ma20'] + 1e-9)
    
    # Wicks
    candle_range = high - low
    lower_wick = df[['open', 'close']].min(axis=1) - low
    upper_wick = high - df[['open', 'close']].max(axis=1)
    
    df['lower_wick_pct'] = (lower_wick / (candle_range + 1e-9)) * 100
    df['upper_wick_pct'] = (upper_wick / (candle_range + 1e-9)) * 100
    
    # ADX (14)
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    tr_s = tr.rolling(window=14).sum()
    p_dm_s = pd.Series(plus_dm, index=df.index).rolling(window=14).sum()
    m_dm_s = pd.Series(minus_dm, index=df.index).rolling(window=14).sum()
    
    plus_di = 100 * (p_dm_s / (tr_s + 1e-9))
    minus_di = 100 * (m_dm_s / (tr_s + 1e-9))
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-9)
    df['adx'] = dx.rolling(window=14).mean()
    
    return df

class BacktestEngine:
    def __init__(self, initial_capital=287.0, margin_per_trade=245.0, leverage=3):
        self.initial_capital = initial_capital
        self.balance = initial_capital
        self.margin_per_trade = margin_per_trade
        self.leverage = leverage
        self.position_size_usd = margin_per_trade * leverage # ~$735
        
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
        print("📂 Memuat & Memproses Data Lilin 15m & 1h...")
        t0 = time.time()
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
                
                # Format symbol
                symbol = sym_clean.replace("_USDT", "/USDT:USDT").replace("_", "/")
                if not symbol.endswith(":USDT"):
                    symbol += ":USDT"
                    
                self.data_15m[symbol] = df15
                self.data_1h[symbol] = df1
                
                # Build O(1) timestamp maps
                self.ts_map_15m[symbol] = {ts: idx for idx, ts in enumerate(df15['timestamp'])}
                self.ts_map_1h[symbol] = {ts: idx for idx, ts in enumerate(df1['timestamp'])}
                
                if "BTC" in symbol:
                    self.btc_15m = df15
                    self.btc_1h = df1
            except Exception as e:
                continue
                
        print(f"✅ Selesai memuat {len(self.data_15m)} koin siap uji ({time.time() - t0:.1f}s)!")

    def get_btc_regime(self, ts):
        if self.btc_1h is None:
            return "neutral"
            
        btc_ts_map = self.ts_map_1h.get("BTC/USDT:USDT") or self.ts_map_1h.get("BTC/USDT")
        if not btc_ts_map:
            return "neutral"
            
        # Cari timestamp 1h terakhir yang <= ts
        # Lilin 1h mulai setiap jam (misal 14:00, 15:00)
        hour_ts = ts - (ts % (3600 * 1000))
        idx_1h = btc_ts_map.get(hour_ts)
        if idx_1h is None or idx_1h < 55:
            return "neutral"
            
        last_1h = self.btc_1h.iloc[idx_1h]
        c = last_1h['close']
        ema50 = last_1h['ema50']
        
        # 15m RSI
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
            
            # 1. Macro Trend (1H)
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
            
            # --- EVALUASI PULLBACK LONG ---
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
                        candidates.append({
                            'symbol': symbol,
                            'side': 'long',
                            'score': score,
                            'price': price,
                            'atr_pct': atr_pct,
                            'timestamp': ts
                        })
                        
            # --- EVALUASI PULLBACK SHORT ---
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
                        candidates.append({
                            'symbol': symbol,
                            'side': 'short',
                            'score': score,
                            'price': price,
                            'atr_pct': atr_pct,
                            'timestamp': ts
                        })
                        
        if not candidates:
            return None
            
        candidates.sort(key=lambda x: x['score'], reverse=True)
        return candidates[0]

    def run(self):
        self.load_all_data()
        
        if self.btc_15m is None:
            print("❌ Data BTC 15m tidak ditemukan!")
            return
            
        timestamps = sorted(self.btc_15m['timestamp'].tolist())
        print(f"⏱️ Memulai Replay Simulasi Bar per Bar ({len(timestamps)} lilin 15m)...")
        t0 = time.time()
        
        for idx, ts in enumerate(timestamps):
            if self.active_trade is not None:
                self.manage_active_trade(ts)
                
            if self.active_trade is None and ts >= self.cooldown_until:
                setup = self.scan_for_entry(ts)
                if setup:
                    self.open_trade(setup)

        print(f"✅ Replay simulasi selesai dalam {time.time() - t0:.1f} detik!")
        self.print_summary()

    def open_trade(self, setup):
        symbol = setup['symbol']
        side = setup['side']
        entry_price = setup['price']
        atr_pct = setup['atr_pct']
        
        init_sl_pct = max(1.2, min(2.5, atr_pct * 1.5))
        if side == "long":
            stop_price = entry_price * (1 - init_sl_pct / 100)
        else:
            stop_price = entry_price * (1 + init_sl_pct / 100)
            
        cp1_pct = max(1.30, min(1.65, atr_pct * 1.4))
        
        self.active_trade = {
            'symbol': symbol,
            'side': side,
            'entry_time': setup['timestamp'],
            'entry_price': entry_price,
            'stop_price': stop_price,
            'current_stop_profit_level': -init_sl_pct,
            'highest_profit_pct': 0.0,
            'lowest_profit_pct': 0.0,
            'partial_tp_done': False,
            'partial_tp_pnl': 0.0,
            'atr_pct': atr_pct,
            'cp1_pct': cp1_pct,
            'checkpoint_level': 0,
            'remaining_ratio': 1.0,
            'position_size_usd': self.position_size_usd
        }

    def manage_active_trade(self, ts):
        trade = self.active_trade
        symbol = trade['symbol']
        side = trade['side']
        entry_price = trade['entry_price']
        
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
        
        # 1. CEK CHOPPY AUTO-BEP
        if is_choppy and config.CHOPPY_AUTO_BEP_ENABLED:
            if candle_max_profit >= config.CHOPPY_BEP_TRIGGER_PERCENT:
                lock_pct = getattr(config, "CHOPPY_BEP_LOCK_PERCENT", 0.12)
                if trade['current_stop_profit_level'] < lock_pct:
                    trade['current_stop_profit_level'] = lock_pct
                    if side == "long":
                        trade['stop_price'] = entry_price * (1 + lock_pct / 100)
                    else:
                        trade['stop_price'] = entry_price * (1 - lock_pct / 100)

        # 2. CEK PARTIAL TP 1 (50%)
        target_tp1 = config.CHOPPY_CP1_PERCENT if is_choppy else trade['cp1_pct']
        if not trade['partial_tp_done'] and candle_max_profit >= target_tp1:
            trade['partial_tp_done'] = True
            trade['remaining_ratio'] = 0.5
            tp1_pnl = (self.position_size_usd * 0.5) * (target_tp1 / 100)
            trade['partial_tp_pnl'] = tp1_pnl
            
            bep_lvl = 0.22
            trade['current_stop_profit_level'] = bep_lvl
            if side == "long":
                trade['stop_price'] = entry_price * (1 + bep_lvl / 100)
            else:
                trade['stop_price'] = entry_price * (1 - bep_lvl / 100)

        # 3. CEK MOONBAG TRAILING RATCHET
        if trade['partial_tp_done']:
            hp = trade['highest_profit_pct']
            if hp >= 1.8 and trade['current_stop_profit_level'] < 0.95:
                trade['current_stop_profit_level'] = 0.95
            elif hp >= 2.3 and trade['current_stop_profit_level'] < 1.45:
                trade['current_stop_profit_level'] = 1.45
            elif hp >= 2.8 and trade['current_stop_profit_level'] < 1.95:
                trade['current_stop_profit_level'] = 1.95
            elif hp >= 3.5 and trade['current_stop_profit_level'] < 2.50:
                trade['current_stop_profit_level'] = 2.50
                
            lvl = trade['current_stop_profit_level']
            if side == "long":
                trade['stop_price'] = max(trade['stop_price'], entry_price * (1 + lvl / 100))
            else:
                trade['stop_price'] = min(trade['stop_price'], entry_price * (1 - lvl / 100))

        # 4. CEK MOONBAG TIMEOUT
        if trade['partial_tp_done'] and elapsed_hours >= config.MOONBAG_TIMEOUT_HOURS:
            if curr_profit <= config.MOONBAG_TIMEOUT_MAX_PROFIT:
                self.close_trade(ts, close, reason=f"moonbag_timeout_{elapsed_hours:.1f}h")
                return

        # 5. CEK STOP LOSS / STOP HIT
        stop_hit = False
        if side == "long" and low <= trade['stop_price']:
            stop_hit = True
            exit_price = trade['stop_price']
        elif side == "short" and high >= trade['stop_price']:
            stop_hit = True
            exit_price = trade['stop_price']
            
        if stop_hit:
            reason = "stop_loss" if trade['current_stop_profit_level'] <= 0 else "trailing_stop"
            self.close_trade(ts, exit_price, reason=reason)
            return

        # 6. CEK BOUNDED CUTLOSS
        if not trade['partial_tp_done'] and curr_profit <= -1.2:
            self.close_trade(ts, close, reason="bounded_cutloss")
            return

    def close_trade(self, ts, exit_price, reason):
        trade = self.active_trade
        side = trade['side']
        entry_price = trade['entry_price']
        rem_ratio = trade['remaining_ratio']
        
        if side == "long":
            pct = ((exit_price - entry_price) / entry_price) * 100
        else:
            pct = ((entry_price - exit_price) / entry_price) * 100
            
        rem_pnl = (self.position_size_usd * rem_ratio) * (pct / 100)
        total_pnl = trade['partial_tp_pnl'] + rem_pnl
        fee = self.position_size_usd * 0.0008 # Fee taker
        net_pnl = total_pnl - fee
        
        self.balance += net_pnl
        
        duration_hours = (ts - trade['entry_time']) / (1000 * 3600)
        dt_entry = datetime.fromtimestamp(trade['entry_time'] / 1000).strftime('%Y-%m-%d %H:%M')
        dt_close = datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d %H:%M')
        
        trade_record = {
            'symbol': trade['symbol'].split(":")[0],
            'side': side,
            'entry_time': dt_entry,
            'close_time': dt_close,
            'duration_h': round(duration_hours, 1),
            'entry_price': entry_price,
            'exit_price': exit_price,
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
            print("❌ Tidak ada trade yang dieksekusi!")
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
        print("🏆 LAPORAN HASIL BACKTEST 3 BULAN PENUH (TOP 120 KOIN BINANCE FUTURES)")
        print("=" * 75)
        print(f"Periode Uji          : {df_trades.iloc[0]['entry_time']} s/d {df_trades.iloc[-1]['close_time']}")
        print(f"Modal Awal           : {self.initial_capital:.2f} USDT")
        print(f"Saldo Akhir          : {self.balance:.2f} USDT")
        print(f"Total Keuntungan Net : {net_pnl:+.2f} USDT ({growth_pct:+.1f}%) 🚀")
        print(f"Total Trade          : {total_trades}")
        print(f"Win / Loss / BEP     : {len(wins)} Win / {len(losses)} Loss / {len(beps)} BEP")
        print(f"Win Rate             : {win_rate:.1f}% 🔥")
        print(f"Profit Factor        : {profit_factor:.2f}")
        print(f"Max Drawdown (MDD)   : -{max_dd:.2f} USDT (-{max_dd_pct:.1f}%)")
        print(f"Rata-rata Menang     : +{wins['net_pnl'].mean():.2f} USDT per trade")
        print(f"Rata-rata Kalah      : {losses['net_pnl'].mean():.2f} USDT per trade")
        print("-" * 75)
        
        df_trades['month'] = pd.to_datetime(df_trades['entry_time']).dt.to_period('M')
        monthly = df_trades.groupby('month').agg(
            trades=('net_pnl', 'count'),
            win_count=('net_pnl', lambda x: (x > 0).sum()),
            pnl=('net_pnl', 'sum')
        )
        monthly['win_rate'] = (monthly['win_count'] / monthly['trades']) * 100
        print("\n📅 PERFORMA PER BULAN:")
        for m, row in monthly.iterrows():
            print(f"   - Bulan {str(m):7} : {row['trades']:2.0f} Trade | Win Rate: {row['win_rate']:5.1f}% | Net PnL: {row['pnl']:+8.2f} USDT")
            
        print("\n🌟 5 TRADE DENGAN KEUNTUNGAN TERBESAR (TOP WINNERS):")
        top_w = df_trades.sort_values('net_pnl', ascending=False).head(5)
        for _, r in top_w.iterrows():
            print(f"   - {r['entry_time']} | {r['symbol']:10} {r['side'].upper():5} | Cuan: {r['net_pnl']:+6.2f} USDT | Peak: +{r['highest_p']:.2f}% | Alasan: {r['reason']}")
            
        print("\n🛡️ 5 TRADE LOSS TERBURUK:")
        top_l = df_trades.sort_values('net_pnl', ascending=True).head(5)
        for _, r in top_l.iterrows():
            print(f"   - {r['entry_time']} | {r['symbol']:10} {r['side'].upper():5} | Rugi: {r['net_pnl']:+6.2f} USDT | Drawdown: {r['lowest_p']:.2f}% | Alasan: {r['reason']}")
        print("=" * 75)

if __name__ == "__main__":
    engine = BacktestEngine(initial_capital=287.0, margin_per_trade=245.0, leverage=3)
    engine.run()

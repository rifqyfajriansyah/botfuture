"""
Binance Futures Trading Bot - Main Orchestrator
================================================
Main loop yang mengatur semua module:
1. Scan market → 2. Analisis signal → 3. Place order → 
4. Monitor trailing stop → 5. Cek reversal

Flow:
- Jika TIDAK ada posisi/order → Scan & cari signal baru (jika tidak dalam cooldown)
- Jika ada PENDING ORDER → Monitor timeout, cek fill
- Jika ada POSISI AKTIF → Monitor trailing stop & reversal guard (TF 15m)
"""

import os
import time
import sys
from datetime import datetime
import signal as os_signal
import ccxt
import config
from logger_setup import logger
from state_manager import StateManager
from scanner import MarketScanner
from signal_engine import SignalEngine
from order_manager import OrderManager
from trailing_manager import TrailingManager
from reversal_guard import ReversalGuard


PID_FILE = "bot.pid"


def check_and_create_pid_file():
    """Cegah menjalankan bot secara ganda dengan file lock."""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                old_pid = int(f.read().strip())
            try:
                os.kill(old_pid, 0)
                logger.critical(
                    f"🚨 Bot sudah berjalan dengan PID {old_pid}! Hentikan dulu proses tersebut."
                )
                sys.exit(1)
            except OSError:
                pass
        except Exception:
            pass
            
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def remove_pid_file():
    """Hapus pid file saat shutdown."""
    if os.path.exists(PID_FILE):
        try:
            os.remove(PID_FILE)
        except Exception:
            pass


class TradingBot:
    """Main trading bot orchestrator."""
    
    def __init__(self):
        self.running = False
        self.exchange = None
        self.state = None
        self.scanner = None
        self.signal_engine = None
        self.order_mgr = None
        self.trailing_mgr = None
        self.reversal_guard = None
        self._last_cooldown_log = 0
    
    def initialize(self):
        """Initialize semua komponen bot."""
        check_and_create_pid_file()
        
        logger.info("=" * 60)
        logger.info("🤖 BINANCE FUTURES TRADING BOT (Institutional TPLR)")
        logger.info("=" * 60)
        
        if not config.BINANCE_API_KEY or not config.BINANCE_API_SECRET:
            logger.error("❌ API keys belum di-set! Edit file .env")
            sys.exit(1)
        
        logger.info(f"🔗 Connecting to Binance ({config.TRADING_MODE})...")
        
        exchange_config = {
            "apiKey": config.BINANCE_API_KEY,
            "secret": config.BINANCE_API_SECRET,
            "enableRateLimit": True,
            "options": {
                "defaultType": "future",
            },
        }
        
        if config.TRADING_MODE == "testnet":
            exchange_config["sandbox"] = True
            logger.info("  📋 MODE: TESTNET (paper trading)")
        else:
            logger.info("  💰 MODE: LIVE TRADING")
        
        self.exchange = ccxt.binance(exchange_config)
        self.exchange.load_markets()
        logger.info("  ✅ Markets loaded")
        
        self.state = StateManager()
        
        self.scanner = MarketScanner(self.exchange)
        self.signal_engine = SignalEngine(self.exchange)
        self.order_mgr = OrderManager(self.exchange, self.state)
        self.trailing_mgr = TrailingManager(self.order_mgr, self.state)
        self.reversal_guard = ReversalGuard(
            self.signal_engine, self.order_mgr,
            self.trailing_mgr, self.state
        )
        
        logger.info(f"  ⚙️  Timeframe: {config.TRADING_TIMEFRAME} (HTF: {config.HIGHER_TIMEFRAME})")
        logger.info(f"  ⚙️  Leverage: {config.LEVERAGE}x | Margin: {config.MARGIN_MODE}")
        logger.info(f"  ⚙️  Cooldown Global: {config.SIGNAL_COOLDOWN_MINUTES}m | Symbol: {config.SYMBOL_COOLDOWN_MINUTES}m")
        logger.info(f"  ⚙️  Trailing Ratchet: Checkpoint {config.TRAILING_CHECKPOINT_PERCENT}%, Stop {config.TRAILING_FIRST_STOP_PERCENT}%")
        logger.info(f"  ⚙️  Emergency SL Safety Net: -{config.EMERGENCY_SL_PERCENT}% ({'ON' if config.EMERGENCY_SL_ENABLED else 'OFF'})")
        
        balance = self.order_mgr.get_available_balance()
        logger.info(f"  💰 Available balance: {balance:.2f} USDT")
        
        # Bersihkan sisa conditional stop orders dari sesi/koin sebelumnya
        logger.info("🧹 Memeriksa dan membersihkan order conditional sisa...")
        self.order_mgr.sweep_orphaned_orders()
        
        logger.info("=" * 60)
        
        os_signal.signal(os_signal.SIGINT, self._shutdown_handler)
        os_signal.signal(os_signal.SIGTERM, self._shutdown_handler)
    
    def _shutdown_handler(self, signum, frame):
        """Handle graceful shutdown."""
        logger.info("\n🛑 Shutdown signal received. Stopping bot...")
        self.running = False
    
    # =========================================================================
    # Main Loop
    # =========================================================================
    
    def run(self):
        """Main trading loop."""
        self.initialize()
        self.running = True
        
        logger.info("🚀 Bot started! Entering main loop...\n")
        
        iteration = 0
        
        while self.running:
            try:
                iteration += 1
                
                if self.state.has_position():
                    self._handle_active_position()
                elif self.state.has_pending_order():
                    self._handle_pending_order()
                else:
                    self._scan_and_trade()
                
                time.sleep(config.MAIN_LOOP_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("🛑 KeyboardInterrupt. Stopping...")
                break
            except Exception as e:
                logger.error(f"❌ Error in main loop: {e}", exc_info=True)
                time.sleep(15)
        
        self._shutdown()
    
    # =========================================================================
    # Handle Active Position
    # =========================================================================
    
    def _handle_active_position(self):
        """Monitor posisi aktif: trailing stop & reversal guard."""
        pos = self.state.get_position()
        if not pos:
            return
        
        symbol = pos["symbol"]
        side = pos["side"]
        entry_price = pos["entry_price"]
        amount = pos["amount"]
        
        current_price = self.order_mgr.get_current_price(symbol)
        if current_price <= 0:
            logger.warning(f"⚠️ Gagal ambil harga {symbol}, skip cycle ini")
            return
        
        profit_pct = self.trailing_mgr.calculate_profit_pct(
            entry_price, current_price, side
        )
        checkpoint = self.state.get_current_checkpoint()
        
        # Hitung PnL dalam USDT dan ROE%
        if side == "long":
            unrealized_pnl_usdt = (current_price - entry_price) * amount
        else:
            unrealized_pnl_usdt = (entry_price - current_price) * amount
            
        roe_pct = profit_pct * config.LEVERAGE
        
        logger.info(
            f"📊 POSISI: {side.upper()} {symbol} | "
            f"Entry: {entry_price} | Now: {current_price} | "
            f"PnL: {unrealized_pnl_usdt:+.2f} USDT ({roe_pct:+.2f}% ROE {config.LEVERAGE}x | {profit_pct:+.2f}% Price) | "
            f"Checkpoint: {checkpoint}%"
        )
        
        exchange_pos = self.order_mgr.fetch_position(symbol)
        contracts = float(exchange_pos.get("contracts", 0)) if exchange_pos else 0.0
        notional_val = contracts * current_price
        
        # Jika posisi habis ATAU hanya tersisa debu pembulatan (< 1.0 USDT)
        if not exchange_pos or contracts <= 0 or (notional_val < 1.0 and contracts > 0):
            if contracts > 0:
                logger.warning(
                    f"🧹 Sisa debu pembulatan terdeteksi pada {symbol} ({contracts} contracts = ${notional_val:.2f} USDT < $1.00). "
                    f"Membersihkan posisi dan merapikan trade..."
                )
                try:
                    # Tutup sisa debu jika bisa via market order reduceOnly
                    close_side = "sell" if side == "long" else "buy"
                    clean_amount = float(self.order_mgr.exchange.amount_to_precision(symbol, contracts))
                    if clean_amount > 0:
                        self.order_mgr.exchange.create_order(
                            symbol=symbol,
                            type="market",
                            side=close_side,
                            amount=clean_amount,
                            params={"reduceOnly": True}
                        )
                        logger.info(f"✅ Sisa debu {clean_amount} {symbol} (${notional_val:.2f}) berhasil ditutup di Binance!")
                except Exception as e_dust:
                    logger.warning(f"⚠️ Gagal menutup sisa debu {symbol}: {e_dust}")
                    
            logger.warning(
                f"⚠️ Posisi {symbol} sudah selesai di Binance! Closing state & logging PnL..."
            )
            real_pnl = self.order_mgr.get_realized_pnl(
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                amount=amount,
                fallback_close_price=current_price
            )
            
            self.order_mgr.cancel_all_orders(symbol)
            self.state.clear_position(
                pnl=real_pnl,
                reason="position_closed_on_exchange",
                start_cooldown=True
            )
            logger.info(
                f"💰 TRADE FINISHED | {side.upper()} {symbol} | Realized PnL: {real_pnl:+.2f} USDT"
            )
            return
        
        if abs(exchange_pos["contracts"] - amount) > 0.0001:
            logger.warning(
                f"⚠️ Amount mismatch! State: {amount}, "
                f"Exchange: {exchange_pos['contracts']}. Syncing..."
            )
            pos["amount"] = exchange_pos["contracts"]
            amount = exchange_pos["contracts"]
            self.state.save()
        
        # Trailing Stop Ratchet Update
        trail_result = self.trailing_mgr.update(
            symbol, entry_price, current_price, side, amount
        )
        
        if trail_result["action"] == "stop_triggered":
            logger.warning("⚠️ Stop triggered detected! Verifying position...")
            verify_pos = self.order_mgr.fetch_position(symbol)
            v_contracts = float(verify_pos.get("contracts", 0)) if verify_pos else 0.0
            v_notional = v_contracts * current_price
            if not verify_pos or v_contracts <= 0 or (v_notional < 1.0 and v_contracts > 0):
                if v_contracts > 0:
                    try:
                        close_side = "sell" if side == "long" else "buy"
                        self.order_mgr.exchange.create_market_order(symbol, close_side, v_contracts, {"reduceOnly": True})
                    except Exception:
                        pass
                real_pnl = self.order_mgr.get_realized_pnl(
                    symbol=symbol,
                    side=side,
                    entry_price=entry_price,
                    amount=amount,
                    fallback_close_price=current_price
                )
                self.order_mgr.cancel_all_orders(symbol)
                self.state.clear_position(
                    pnl=real_pnl, reason="trailing_stop_triggered", start_cooldown=True
                )
                self.order_mgr.sweep_orphaned_orders()
                logger.info(
                    f"💰 TRADE FINISHED (Trailing Stop) | {side.upper()} {symbol} | "
                    f"Realized PnL: {real_pnl:+.2f} USDT"
                )
            return
            
        if trail_result["action"] == "closed":
            logger.info(
                f"🔴 Position already CLOSED by Trailing Manager ({trail_result.get('reason')})."
            )
            return
        
        # Reversal Guard (15m Timeframe)
        reversal_result = self.reversal_guard.check_and_act()
        if reversal_result["action"] == "closed":
            logger.info(
                f"🔴 Position closed by reversal guard: {reversal_result['reason']}"
            )
            return

        # Stagnation Timeout Check (Anti-Sideways Protection)
        # CATATAN: Posisi dibiarkan berjalan (let winners run) sepenuhnya dikawal Trailing Stop (by Price & by Time).
        # Force Market Close hanya aktif jika STAGNATION_EXIT_ENABLED = True dan posisi belum pernah tembus checkpoint.
        if getattr(config, "STAGNATION_EXIT_ENABLED", False):
            entry_time_str = pos.get("entry_time")
            if entry_time_str:
                try:
                    entry_dt = datetime.fromisoformat(entry_time_str)
                    elapsed_hours = (datetime.now() - entry_dt).total_seconds() / 3600.0
                except Exception:
                    elapsed_hours = 0.0
                    
                max_hours = getattr(config, "MAX_STAGNANT_HOURS", 3.0)
                min_stagnant_profit = getattr(config, "MAX_STAGNANT_MIN_PROFIT_PERCENT", 0.2)
                current_cp = self.state.get_current_checkpoint() or 0
                
                # Hanya close jika posisi macet dekat 0% dan belum mencapai checkpoint
                if elapsed_hours >= max_hours and current_cp == 0:
                    if profit_pct >= min_stagnant_profit:
                        logger.info(
                            f"⏰ STAGNATION TIMEOUT ({elapsed_hours:.1f}h >= {max_hours}h)! "
                            f"Posisi macet di profit +{profit_pct:.2f}%. Mengamankan profit via market close..."
                        )
                        self.trailing_mgr.remove_stop(symbol)
                        close_res = self.order_mgr.close_position(
                            symbol=symbol,
                            side=side,
                            amount=amount,
                            reason=f"stagnation_timeout_profit_{profit_pct:.2f}%",
                        )
                        if close_res:
                            real_pnl = self.order_mgr.get_realized_pnl(
                                symbol=symbol,
                                side=side,
                                entry_price=entry_price,
                                amount=amount,
                                fallback_close_price=current_price,
                            )
                            self.state.clear_position(
                                pnl=real_pnl,
                                reason=f"stagnation_timeout (+{profit_pct:.2f}%)",
                                start_cooldown=True,
                            )
                            logger.info(
                                f"💰 TRADE FINISHED (Stagnation Timeout) | {side.upper()} {symbol} | "
                                f"Realized PnL: {real_pnl:+.2f} USDT"
                            )
                            return
    
    # =========================================================================
    # Handle Pending Order
    # =========================================================================
    
    def _handle_pending_order(self):
        """Monitor pending limit order: cek fill atau timeout."""
        order = self.state.get_pending_order()
        if not order:
            return
        
        symbol = order["symbol"]
        order_id = order["order_id"]
        timeout_min = order.get("timeout_minutes", config.ORDER_TIMEOUT_MINUTES)

        if self.state.is_order_expired():
            logger.info(
                f"⏰ Limit Order timeout ({timeout_min} min)! "
                f"Canceling order {order_id} for {symbol}"
            )
            self.order_mgr.cancel_order(symbol, order_id)
            
            # Cek jika ternyata ada partial fill yang diadopsi resmi ke state
            pos = self.state.get_position()
            if pos and pos.get("symbol") == symbol:
                logger.warning(
                    f"🛡️ Partial fill terdeteksi & diadopsi untuk {symbol} ({pos['amount']})! "
                    f"Memasang Emergency SL..."
                )
                if config.EMERGENCY_SL_ENABLED:
                    self._place_emergency_sl(pos)
            return
        
        status = self.order_mgr.check_order_filled(symbol, order_id)
        
        if status in ("filled", "partial"):
            logger.info(
                f"🎯 Order {'FULLY' if status == 'filled' else 'PARTIALLY'} FILLED! "
                f"{symbol} @ {order.get('price')}. Starting position monitoring..."
            )
            pos = self.state.get_position()
            if pos and config.EMERGENCY_SL_ENABLED:
                self._place_emergency_sl(pos)
                
        elif status == "open":
            elapsed = time.time() - order["placed_time"]
            remaining = (timeout_min * 60) - elapsed
            logger.info(
                f"⏳ Waiting limit fill: {symbol} @ {order['price']} | "
                f"Remaining: {remaining/60:.1f} min"
            )
            
            # PRE-FILL WATCHDOG (Auto Gak Jadi jika momentum/market berbalik saat antri)
            if getattr(config, "PRE_FILL_WATCHDOG_ENABLED", True):
                should_abort, abort_reason = self._check_pre_fill_validity(order)
                if should_abort:
                    logger.warning(
                        f"🛑 PRE-FILL WATCHDOG TRIGGERED! {abort_reason}. "
                        f"Membatalkan antrian limit order {order_id} ({symbol}) agar tidak terseret!"
                    )
                    self.order_mgr.cancel_order(symbol, order_id)
                    self.state.clear_pending_order(start_cooldown=True, symbol=symbol)
                    return
    

    def _check_pre_fill_validity(self, order):
        """
        PRE-FILL WATCHDOG:
        Periksa apakah kondisi pasar atau pergerakan harga berbalik arah melawan order
        selama order limit sedang antri (belum terisi).
        Jika ya, batalkan order (Auto Gak Jadi) agar tidak terseret floating minus!
        """
        try:
            symbol = order["symbol"]
            side = order.get("side", "").lower()
            limit_price = float(order.get("price", 0))
            if limit_price <= 0:
                return False, None
                
            current_price = self.order_mgr.get_current_price(symbol)
            if current_price <= 0:
                return False, None
                
            max_drift_pct = getattr(config, "PRE_FILL_MAX_ADVERSE_DRIFT_PERCENT", 0.35)
            
            # 1. Adverse Price Drift Check:
            if side == "short":
                drift_pct = ((current_price - limit_price) / limit_price) * 100.0
                if drift_pct >= max_drift_pct:
                    return True, f"Harga market naik +{drift_pct:.2f}% di atas limit short (pump melawan antrian)"
            elif side == "long":
                drift_pct = ((limit_price - current_price) / limit_price) * 100.0
                if drift_pct >= max_drift_pct:
                    return True, f"Harga market anjlok -{drift_pct:.2f}% di bawah limit long (dump melawan antrian)"
                    
            # 2. BTC Flash Reversal Check:
            if getattr(config, "PRE_FILL_CHECK_BTC_REVERSAL", True):
                bias = self.signal_engine._get_btc_bias()
                flash_bias = getattr(self.signal_engine, "_flash_lock_bias", None)
                flash_until = getattr(self.signal_engine, "_flash_lock_until", 0)
                is_flash = (time.time() < flash_until and flash_bias)
                
                if side == "short" and (bias == "bullish" or (is_flash and flash_bias == "bullish")):
                    return True, "BTC mendadak Bullish / Flash Pump saat antri Short"
                elif side == "long" and (bias == "bearish" or (is_flash and flash_bias == "bearish")):
                    return True, "BTC mendadak Bearish / Flash Crash saat antri Long"
                    
            return False, None
        except Exception as e:
            logger.error(f"Error in _check_pre_fill_validity: {e}")
            return False, None

    def _place_emergency_sl(self, pos):
        """Pasang emergency stop loss safety net di Binance (-25%)."""
        symbol = pos["symbol"]
        entry = pos["entry_price"]
        side = pos["side"]
        amount = pos["amount"]
        
        if side == "long":
            sl_price = entry * (1 - config.EMERGENCY_SL_PERCENT / 100)
        else:
            sl_price = entry * (1 + config.EMERGENCY_SL_PERCENT / 100)
            
        logger.info(
            f"🛡️ Placing Emergency Safety SL for {symbol} at {sl_price:.4f} "
            f"(-{config.EMERGENCY_SL_PERCENT}%)"
        )
        
        stop_order = self.order_mgr.place_stop_order(
            symbol=symbol,
            side=side,
            amount=amount,
            stop_price=sl_price,
        )
        
        if stop_order:
            self.state.set_trailing_stop(
                stop_order_id=stop_order["id"],
                stop_price=sl_price,
                checkpoint_level=0,
            )
            logger.info(f"✅ Emergency SL active on Binance! ID: {stop_order['id']}")
        else:
            logger.error(f"❌ Gagal pasang emergency SL untuk {symbol}")

    # =========================================================================
    # Scan & Trade
    # =========================================================================
    
    def _scan_and_trade(self):
        """Scan market, analisis signal, dan place order jika ada signal."""
        now = time.time()
        
        # 0. Anti-Double Position Watchdog: Pastikan exchange benar-benar bersih sebelum scan
        open_positions = self.order_mgr.get_all_open_positions()
        if len(open_positions) >= config.MAX_POSITIONS:
            if now - self._last_cooldown_log >= 60:
                logger.warning(
                    f"🛑 Exchange Watchdog: Ditemukan {len(open_positions)} posisi aktif di Binance "
                    f"({[p['symbol'] for p in open_positions]}). Menolak scan/entry baru untuk mencegah double position!"
                )
                self._last_cooldown_log = now
            return
        
        # 1. Cek Cooldown
        is_cooldown, rem_sec, reason = self.state.is_cooldown_active()
        if is_cooldown:
            if now - self._last_cooldown_log >= 60:
                if rem_sec >= 999900:
                    logger.warning(f"🛑 Emergency Pause aktif: {reason}")
                else:
                    logger.info(f"⏳ Cooldown aktif ({int(rem_sec)}s tersisa). Alasan: {reason}")
                self._last_cooldown_log = now
            self.state.set_status("cooldown")
            return
            
        # 2. Cek Saldo Minimum
        balance = self.order_mgr.get_available_balance()
        if balance < config.MIN_WALLET_BALANCE_USDT:
            if now - self._last_cooldown_log >= 60:
                logger.warning(
                    f"⚠️ Saldo {balance:.2f} USDT dibawah batas minimum {config.MIN_WALLET_BALANCE_USDT} USDT. "
                    f"Menunggu isi saldo."
                )
                self._last_cooldown_log = now
            self.state.set_status("insufficient_balance")
            return
            
        self.state.set_status("scanning")
        
        candidates = self.scanner.scan()
        if not candidates:
            self.state.set_status("idle")
            return
        
        best_signal = None
        
        for candidate in candidates:
            symbol = candidate["symbol"]
            
            is_sym_cd, _, _ = self.state.is_cooldown_active(symbol)
            if is_sym_cd:
                continue
                
            signal_result = self.signal_engine.analyze(symbol)
            
            if signal_result["signal"] in ("LONG", "SHORT"):
                if best_signal is None or signal_result["score"] > best_signal["score"]:
                    best_signal = signal_result
                    best_signal["scan_score"] = candidate["scan_score"]
        
        if best_signal and best_signal["score"] >= config.SIGNAL_MIN_SCORE:
            symbol = best_signal["symbol"]
            signal = best_signal["signal"]
            price = best_signal["price"]
            score = best_signal["score"]
            
            logger.info(
                f"\n{'='*50}\n"
                f"🚀 ENTRY SIGNAL: {signal} {symbol}\n"
                f"   Score: {score}/100 | Price: {price}\n"
                f"   HTF Bias 1H: {best_signal['higher_tf_bias']}\n"
                f"   Details: {best_signal['details']}\n"
                f"{'='*50}"
            )
            
            self.state.set_last_signal(best_signal)
            self.state.set_status("trading")
            suggested_p = best_signal.get("suggested_entry_price")
            order = self.order_mgr.place_entry_order(
                symbol=symbol,
                signal=signal,
                current_price=price,
                score=score,
                suggested_price=suggested_p,
            )
            
            if order:
                logger.info(f"✅ Entry order placed! Waiting for fill...")
            else:
                self.state.set_status("idle")
        else:
            self.state.set_status("idle")
    
    # =========================================================================
    # Shutdown
    # =========================================================================
    
    def _shutdown(self):
        """Graceful shutdown."""
        remove_pid_file()
        logger.info("\n" + "=" * 60)
        logger.info("🛑 Bot shutting down...")
        
        state = self.state.get_state()
        logger.info(f"  📊 Total trades: {state.get('total_trades', 0)}")
        logger.info(f"  💰 Total profit: {state.get('total_profit', 0):.2f} USDT")
        
        self.state.save()
        logger.info("  💾 State saved")
        logger.info("=" * 60)
        logger.info("👋 Goodbye!\n")

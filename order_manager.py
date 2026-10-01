"""
Order Manager
=============
Mengelola lifecycle order: place limit, cek fill, cancel, close posisi.
- Entry via LIMIT order (-0.1% / -0.35% Tiered)
- Stepped Trailing stop via STOP_MARKET
- Close via MARKET order
- Real Binance realized PnL extraction

PENTING: Semua order operations di-wrap dengan retry dan validasi
agar tidak terjadi state inconsistency.
"""

import time
import ccxt
import config
from logger_setup import logger


class OrderManager:
    """Mengelola semua operasi order di Binance Futures."""
    
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # detik
    
    def __init__(self, exchange, state_manager):
        self.exchange = exchange
        self.state = state_manager
    
    # =========================================================================
    # Setup
    # =========================================================================
    
    def setup_symbol(self, symbol):
        """
        Set leverage dan margin mode untuk symbol tertentu.
        Harus dipanggil sebelum place order.
        """
        try:
            # Set margin mode (isolated)
            try:
                self.exchange.set_margin_mode(config.MARGIN_MODE, symbol)
                logger.info(f"  ✅ Margin mode: {config.MARGIN_MODE} for {symbol}")
            except ccxt.ExchangeError as e:
                # Biasanya error kalau sudah di-set sebelumnya
                if "No need to change" in str(e) or "already" in str(e).lower():
                    pass
                else:
                    logger.warning(f"  ⚠️ Set margin mode: {e}")
            
            # Set leverage
            self.exchange.set_leverage(config.LEVERAGE, symbol)
            logger.info(f"  ✅ Leverage: {config.LEVERAGE}x for {symbol}")
            
        except Exception as e:
            logger.error(f"❌ Gagal setup symbol {symbol}: {e}")
            raise
    
    # =========================================================================
    # Balance
    # =========================================================================
    
    def get_available_balance(self):
        """Ambil USDT balance yang tersedia untuk trading."""
        try:
            balance = self.exchange.fetch_balance()
            usdt = balance.get("USDT", {})
            free = usdt.get("free", 0)
            logger.info(f"  💰 Available USDT: {free:.2f}")
            return float(free)
        except Exception as e:
            logger.error(f"❌ Gagal fetch balance: {e}")
            return 0
    
    # =========================================================================
    # Entry Order (Limit)
    # =========================================================================
    
    def place_entry_order(self, symbol, signal, current_price, score=None, suggested_price=None):
        """
        Place limit order untuk entry posisi dengan Dynamic Confluence Limit & Tiered Fallback.
        - Jika suggested_price ada: gunakan harga optimal EMA21 / ATR pullback.
        - High Conviction (score >= 80): offset sangat rapat (0.1%), timeout 10m
        - Normal Conviction (score 70-79): offset tawar (0.35%), timeout 15m
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT:USDT')
            signal: 'LONG' atau 'SHORT'
            current_price: Harga saat ini
            score: Skor sinyal (0-100)
            suggested_price: Harga entry optimal dari SignalEngine (EMA21/ATR pullback)
        
        Returns:
            dict | None: Order info jika berhasil, None jika gagal
        """
        try:
            # Cek apakah sudah ada posisi/order aktif
            if self.state.has_position():
                logger.warning("⚠️ Sudah ada posisi aktif, skip entry.")
                return None
            
            if self.state.has_pending_order():
                logger.warning("⚠️ Sudah ada pending order, skip entry.")
                return None
            
            # Double-check: cek posisi langsung dari Binance
            exchange_pos = self.fetch_position(symbol)
            if exchange_pos:
                logger.warning(
                    f"⚠️ Posisi ditemukan di Binance tapi tidak di state! "
                    f"Syncing: {exchange_pos['side']} {exchange_pos['contracts']}"
                )
                self.state.set_position(
                    symbol=symbol,
                    side=exchange_pos["side"],
                    entry_price=exchange_pos["entry_price"],
                    amount=exchange_pos["contracts"],
                    order_id="synced_from_exchange",
                )
                return None
            
            # Setup leverage & margin
            self.setup_symbol(symbol)
            
            # Timeout durasi
            if score is not None and score >= config.HIGH_CONVICTION_SCORE:
                timeout_min = config.HIGH_CONVICTION_TIMEOUT_MINUTES
            else:
                timeout_min = config.NORMAL_CONVICTION_TIMEOUT_MINUTES
            
            # Hitung entry price: Dynamic Confluence vs Tiered Fixed Offset
            if suggested_price is not None and suggested_price > 0 and getattr(config, "DYNAMIC_PULLBACK_ENTRY_ENABLED", True):
                entry_price = float(suggested_price)
                gap_pct = abs(current_price - entry_price) / current_price * 100
                logger.info(
                    f"🎯 DYNAMIC CONFLUENCE ENTRY: {signal} {symbol} @ {entry_price} "
                    f"(Diskon: {gap_pct:.2f}% dari harga pasar {current_price}) | Timeout: {timeout_min}m"
                )
                if signal == "LONG":
                    side = "buy"
                elif signal == "SHORT":
                    side = "sell"
                else:
                    return None
            else:
                # Tentukan offset & timeout berdasarkan kualitas sinyal (Tiered Limit)
                if score is not None and score >= config.HIGH_CONVICTION_SCORE:
                    offset_pct = config.HIGH_CONVICTION_OFFSET_PERCENT
                    tier_desc = f"🔥 HIGH CONVICTION (Score {score} >= {config.HIGH_CONVICTION_SCORE})"
                else:
                    offset_pct = config.NORMAL_CONVICTION_OFFSET_PERCENT
                    score_str = str(score) if score is not None else "N/A"
                    tier_desc = f"⚖️ NORMAL CONVICTION (Score {score_str})"
                
                logger.info(f"🎯 Tiered Limit Setup: {tier_desc}")
                logger.info(f"   Offset: {offset_pct}% | Timeout: {timeout_min} min")

                offset = current_price * (offset_pct / 100)
                if signal == "LONG":
                    side = "buy"
                    entry_price = current_price - offset  # Antri dibawah
                elif signal == "SHORT":
                    side = "sell"
                    entry_price = current_price + offset  # Antri diatas
                else:
                    logger.warning(f"⚠️ Signal tidak valid: {signal}")
                    return None
            
            # Hitung jumlah kontrak
            balance = self.get_available_balance()
            if balance <= config.MIN_WALLET_BALANCE_USDT:
                logger.error(f"❌ Balance {balance:.2f} USDT dibawah batas aman {config.MIN_WALLET_BALANCE_USDT} USDT.")
                return None
            
            usable_balance = balance * config.BALANCE_USAGE
            notional = usable_balance * config.LEVERAGE
            
            # Ambil info market untuk precision
            market = self.exchange.market(symbol)
            min_amount = market.get("limits", {}).get("amount", {}).get("min", 0)
            min_notional = market.get("limits", {}).get("cost", {}).get("min", 0)
            
            # Gunakan ccxt built-in precision (lebih reliable dari round manual)
            entry_price = float(self.exchange.price_to_precision(symbol, entry_price))
            amount = notional / entry_price
            amount = float(self.exchange.amount_to_precision(symbol, amount))
            
            if amount < min_amount:
                logger.error(
                    f"❌ Amount {amount} dibawah minimum {min_amount} "
                    f"untuk {symbol}"
                )
                return None
            
            if min_notional and (amount * entry_price) < min_notional:
                logger.error(
                    f"❌ Notional {amount * entry_price:.2f} dibawah minimum "
                    f"{min_notional} untuk {symbol}"
                )
                return None
            
            # Place limit order
            logger.info(
                f"📝 Placing LIMIT {side.upper()} {symbol} | "
                f"Price: {entry_price} | Amount: {amount} | "
                f"Notional: ${notional:.2f}"
            )
            
            order = self.exchange.create_order(
                symbol=symbol,
                type="limit",
                side=side,
                amount=amount,
                price=entry_price,
            )
            
            order_id = order.get("id")
            logger.info(f"✅ Order placed! ID: {order_id}")
            
            # Simpan ke state
            self.state.set_pending_order(
                symbol=symbol,
                side=signal.lower(),
                price=entry_price,
                amount=amount,
                order_id=order_id,
                timeout_minutes=timeout_min,
            )
            
            return order
            
        except ccxt.InsufficientFunds as e:
            logger.error(f"❌ Insufficient funds: {e}")
            return None
        except ccxt.ExchangeError as e:
            logger.error(f"❌ Exchange error placing order: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error placing order: {e}")
            return None
    
    # =========================================================================
    # Check Order Status
    # =========================================================================
    
    def check_order_filled(self, symbol, order_id):
        """
        Cek apakah pending order sudah terisi.
        Handles: fully filled, partially filled, canceled, expired.
        
        Returns:
            str: 'filled', 'partial', 'open', 'canceled', atau 'error'
        """
        try:
            order = self.exchange.fetch_order(order_id, symbol)
            status = order.get("status", "unknown")
            filled_amount = float(order.get("filled", 0))
            
            if status == "closed":
                # Order fully filled
                filled_price = order.get("average") or order.get("price", 0)
                
                logger.info(
                    f"🎯 Order FILLED! {symbol} @ {filled_price} | "
                    f"Amount: {filled_amount}"
                )
                
                # Update state: pending → position
                pending = self.state.get_pending_order()
                if not pending:
                    logger.error("❌ Pending order tidak ditemukan di state!")
                    return "error"
                
                self.state.clear_pending_order()
                self.state.set_position(
                    symbol=symbol,
                    side=pending["side"],
                    entry_price=float(filled_price),
                    amount=float(filled_amount),
                    order_id=order_id,
                )
                
                return "filled"
            
            elif status == "canceled" or status == "expired":
                # Cek apakah ada partial fill sebelum cancel
                if filled_amount > 0:
                    filled_price = order.get("average") or order.get("price", 0)
                    logger.warning(
                        f"⚠️ Order {order_id} canceled/expired tapi PARTIALLY FILLED! "
                        f"Filled: {filled_amount} @ {filled_price}"
                    )
                    
                    # Treat partial fill sebagai posisi aktif
                    pending = self.state.get_pending_order()
                    if pending:
                        self.state.clear_pending_order()
                        self.state.set_position(
                            symbol=symbol,
                            side=pending["side"],
                            entry_price=float(filled_price),
                            amount=float(filled_amount),
                            order_id=order_id,
                        )
                    return "partial"
                else:
                    logger.info(f"🚫 Order {order_id} was {status}.")
                    self.state.clear_pending_order(start_cooldown=False)
                    return "canceled"
            
            elif status == "open":
                return "open"
            
            else:
                logger.warning(f"⚠️ Unknown order status: {status}")
                return status
                
        except ccxt.OrderNotFound:
            logger.warning(
                f"⚠️ Order {order_id} not found di exchange! "
                f"Mungkin sudah expired/canceled."
            )
            self.state.clear_pending_order(start_cooldown=False)
            return "canceled"
        except ccxt.NetworkError as e:
            logger.error(f"❌ Network error checking order {order_id}: {e}")
            return "error"
        except Exception as e:
            logger.error(f"❌ Error checking order {order_id}: {e}")
            return "error"
    
    # =========================================================================
    # Cancel Order (dengan safety checks)
    # =========================================================================
    
    def cancel_order(self, symbol, order_id):
        """
        Cancel pending order dengan safety checks.
        """
        try:
            # SAFETY: Cek status order DULU sebelum cancel
            try:
                order = self.exchange.fetch_order(order_id, symbol)
                status = order.get("status", "unknown")
                filled_amount = float(order.get("filled", 0))
                
                if status == "closed":
                    filled_price = order.get("average") or order.get("price", 0)
                    logger.warning(
                        f"⚠️ RACE CONDITION: Order {order_id} sudah FILLED "
                        f"@ {filled_price}! Tidak jadi cancel."
                    )
                    
                    pending = self.state.get_pending_order()
                    if pending:
                        self.state.clear_pending_order()
                        self.state.set_position(
                            symbol=symbol,
                            side=pending["side"],
                            entry_price=float(filled_price),
                            amount=float(filled_amount),
                            order_id=order_id,
                        )
                    return False
                
                elif status == "canceled" or status == "expired":
                    if filled_amount > 0:
                        filled_price = order.get("average") or order.get("price", 0)
                        logger.warning(
                            f"⚠️ Order {order_id} sudah {status} "
                            f"tapi partial fill {filled_amount} @ {filled_price}"
                        )
                        pending = self.state.get_pending_order()
                        if pending:
                            self.state.clear_pending_order()
                            self.state.set_position(
                                symbol=symbol,
                                side=pending["side"],
                                entry_price=float(filled_price),
                                amount=float(filled_amount),
                                order_id=order_id,
                            )
                        return False
                    
                    logger.info(f"✅ Order {order_id} sudah {status}.")
                    self.state.clear_pending_order(start_cooldown=True, symbol=symbol)
                    return True
                    
            except ccxt.OrderNotFound:
                logger.info(f"✅ Order {order_id} already gone.")
                self.state.clear_pending_order(start_cooldown=True, symbol=symbol)
                return True
            except ccxt.NetworkError:
                logger.warning(f"⚠️ Network error saat cek order, coba cancel langsung...")
            
            # Order masih open → cancel sisa antrean di exchange
            try:
                self.exchange.cancel_order(order_id, symbol)
                logger.info(f"🚫 Sisa antrean order {order_id} canceled for {symbol}")
            except ccxt.OrderNotFound:
                logger.info(f"✅ Order {order_id} already gone when canceling.")
            except Exception as e:
                logger.warning(f"⚠️ Warning saat cancel order {order_id}: {e}")
            
            # KRUSIAL: Wajib sync posisi ke exchange untuk memastikan apakah sempat ada partial fill!
            # Jika ada partial fill > 0, _sync_position_from_exchange akan mengadopsinya ke bot state.
            return self._sync_position_from_exchange(symbol)
            
        except ccxt.OrderNotFound:
            logger.warning(
                f"⚠️ Order {order_id} not found saat cancel. "
                f"Checking exchange position..."
            )
            self._sync_position_from_exchange(symbol)
            return True
            
        except ccxt.NetworkError as e:
            logger.error(f"❌ Network error canceling order {order_id}: {e}")
            return self._retry_cancel(symbol, order_id)
            
        except Exception as e:
            logger.error(f"❌ Error canceling order {order_id}: {e}")
            return False
    
    def _retry_cancel(self, symbol, order_id, attempts=0):
        """Retry cancel order dengan backoff."""
        if attempts >= self.MAX_RETRIES:
            logger.error(
                f"❌ Cancel order {order_id} GAGAL setelah {self.MAX_RETRIES}x retry!"
            )
            return False
        
        time.sleep(self.RETRY_DELAY * (attempts + 1))
        logger.info(f"🔄 Retry cancel order #{attempts + 1}...")
        
        try:
            self.exchange.cancel_order(order_id, symbol)
            logger.info(f"✅ Order {order_id} canceled (retry #{attempts + 1})")
            self.state.clear_pending_order(start_cooldown=True, symbol=symbol)
            return True
        except ccxt.OrderNotFound:
            logger.info(f"✅ Order {order_id} already gone (retry #{attempts + 1})")
            self._sync_position_from_exchange(symbol)
            return True
        except Exception as e:
            logger.warning(f"⚠️ Retry #{attempts + 1} gagal: {e}")
            return self._retry_cancel(symbol, order_id, attempts + 1)
    
    def cancel_all_orders(self, symbol):
        """Cancel SEMUA open orders (termasuk conditional TP/SL) untuk symbol."""
        success = True
        try:
            self.exchange.cancel_all_orders(symbol)
            logger.info(f"🚫 All regular orders canceled for {symbol}")
        except Exception as e:
            logger.warning(f"⚠️ Error canceling regular orders: {e}")
            success = False
        
        # Raw Binance Futures Purge (hapus semua conditional stop order seketika)
        try:
            market = self.exchange.market(symbol)
            raw_id = market.get("id", symbol.replace("/", "").split(":")[0])
            self.exchange.fapiPrivateDeleteAllOpenOrders({"symbol": raw_id})
            logger.info(f"🧹 Raw Binance regular orders purged for {raw_id}")
        except Exception:
            pass

        try:
            market = self.exchange.market(symbol)
            raw_id = market.get("id", symbol.replace("/", "").split(":")[0])
            self.exchange.fapiPrivateDeleteAlgoOpenOrders({"symbol": raw_id})
            logger.info(f"🧹 Raw Binance algo & conditional stop orders purged for {raw_id}")
        except Exception:
            pass
        
        try:
            open_orders = self.exchange.fetch_open_orders(symbol)
            for order in open_orders:
                try:
                    self.exchange.cancel_order(order["id"], symbol)
                    logger.info(f"  🚫 Canceled remaining order: {order['id']} ({order.get('type')})")
                except ccxt.OrderNotFound:
                    pass
                except Exception as e:
                    logger.warning(f"  ⚠️ Failed to cancel {order['id']}: {e}")
                    success = False
        except Exception as e:
            logger.warning(f"⚠️ Error fetching open orders for cleanup: {e}")
        
        return success

    def sweep_orphaned_orders(self):
        """
        Sapu bersih semua sisa conditional / stop / limit order (termasuk Algo Orders)
        yang tidak memiliki posisi aktif di akun.
        Mencegah order Stop Loss atau TP lama tertinggal di exchange.
        """
        try:
            active_pos = self.state.get_position()
            pending = self.state.get_pending_order()
            
            allowed_symbols = set()
            if active_pos and active_pos.get("symbol"):
                allowed_symbols.add(active_pos["symbol"])
                allowed_symbols.add(active_pos["symbol"].replace("/", "").split(":")[0])
            if pending and pending.get("symbol"):
                allowed_symbols.add(pending["symbol"])
                allowed_symbols.add(pending["symbol"].replace("/", "").split(":")[0])
                
            # SAFETY: Tambahkan seluruh simbol yang memiliki posisi terbuka di Binance
            # agar order SL manual (seperti XMR) tidak pernah dihapus oleh sapu bersih!
            try:
                open_positions = self.get_all_open_positions()
                for op in open_positions:
                    allowed_symbols.add(op["symbol"])
                    allowed_symbols.add(op["symbol"].replace("/", "").split(":")[0])
            except Exception as e:
                logger.warning(f"⚠️ Warning fetching open positions for allowed_symbols: {e}")
                
            try:
                open_orders = self.exchange.fapiPrivateGetOpenOrders()
            except Exception:
                open_orders = []
                
            cleaned_count = 0
            for o in open_orders:
                raw_sym = o.get("symbol")
                order_id = o.get("orderId")
                
                # Check jika simbol ini bukan posisi aktif atau pending order bot
                if raw_sym not in allowed_symbols and raw_sym not in [s.replace("/", "").split(":")[0] for s in allowed_symbols]:
                    try:
                        self.exchange.fapiPrivateDeleteOrder({"symbol": raw_sym, "orderId": order_id})
                        logger.info(f"🧹 Canceled leftover conditional/open order on {raw_sym}: ID {order_id} ({o.get('type')})")
                        cleaned_count += 1
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to cancel leftover order {order_id} on {raw_sym}: {e}")

            # Sapu bersih open algo orders sisa
            try:
                open_algo = self.exchange.fapiPrivateGetOpenAlgoOrders()
                for ao in open_algo:
                    raw_sym = ao.get("symbol")
                    algo_id = ao.get("algoId")
                    if raw_sym not in allowed_symbols and raw_sym not in [s.replace("/", "").split(":")[0] for s in allowed_symbols]:
                        try:
                            self.exchange.fapiPrivateDeleteAlgoOrder({"symbol": raw_sym, "algoId": int(algo_id)})
                            logger.info(f"🧹 Canceled leftover algo order on {raw_sym}: ID {algo_id}")
                            cleaned_count += 1
                        except Exception as e:
                            logger.warning(f"⚠️ Failed to cancel leftover algo order {algo_id} on {raw_sym}: {e}")
            except Exception:
                pass
                        
            if cleaned_count > 0:
                logger.info(f"✨ Total {cleaned_count} leftover conditional/open orders cleaned up from Binance.")
        except Exception as e:
            logger.warning(f"⚠️ Error during sweep_orphaned_orders: {e}")
    
    def _sync_position_from_exchange(self, symbol):
        """Sync posisi dari Binance ke local state."""
        try:
            pos = self.fetch_position(symbol)
            if pos and pos["contracts"] > 0:
                logger.warning(
                    f"🔄 SYNC: Partial fill / posisi ditemukan di exchange! "
                    f"{pos['side']} {pos['contracts']} @ {pos['entry_price']}"
                )
                pending = self.state.get_pending_order()
                side = pending["side"] if pending else pos["side"]
                
                self.state.clear_pending_order()
                self.state.set_position(
                    symbol=symbol,
                    side=side,
                    entry_price=pos["entry_price"],
                    amount=pos["contracts"],
                    order_id="synced_from_exchange",
                )
                return True
            else:
                self.state.clear_pending_order(start_cooldown=True, symbol=symbol)
                return False
        except Exception as e:
            logger.error(f"❌ Error syncing position: {e}")
            self.state.clear_pending_order(start_cooldown=True, symbol=symbol)
            return False
    
    # =========================================================================
    # Realized PnL & Close Position
    # =========================================================================
    
    def get_realized_pnl(self, symbol, side, entry_price, amount, fallback_close_price=None, close_order_id=None, entry_time=None):
        """
        Dapatkan PnL riil dari Binance API berdasarkan trades history (menjumlahkan seluruh fills dan memotong fee komisi).
        Hanya membaca trade yang terjadi SETELAH entry_time untuk mencegah mengambil data lama.
        Jika tidak tersedia, gunakan fallback calculation dari harga close riil dikurangi estimasi fee.
        """
        if not entry_time:
            pos = self.state.get_position()
            if pos and pos.get("symbol") == symbol:
                entry_time = pos.get("entry_time")

        entry_ts_ms = 0
        if entry_time:
            try:
                from datetime import datetime
                if isinstance(entry_time, str):
                    entry_dt = datetime.fromisoformat(entry_time)
                else:
                    entry_dt = entry_time
                entry_ts_ms = entry_dt.timestamp() * 1000.0 - 10000.0  # buffer 10 detik
            except Exception:
                entry_ts_ms = 0

        try:
            # Beri jeda singkat agar Binance selesai mengindeks fills dari order yang baru dieksekusi
            time.sleep(0.6)
            
            # Coba fetch trades dengan retry jika close_order_id belum terindeks
            trades = []
            for _ in range(3):
                since_param = int(entry_ts_ms) if entry_ts_ms > 0 else None
                trades = self.exchange.fetch_my_trades(symbol, since=since_param, limit=100)
                if entry_ts_ms > 0:
                    trades = [t for t in trades if (t.get("timestamp") or 0) >= entry_ts_ms]
                
                if close_order_id:
                    matched = [
                        t for t in trades 
                        if str(t.get("order")) == str(close_order_id) or 
                           str(t.get("info", {}).get("orderId")) == str(close_order_id)
                    ]
                    if matched:
                        trades = matched
                        break
                elif trades:
                    break
                time.sleep(0.5)

            if trades:
                def _calc_net_pnl(trade_batch):
                    gross_pnl = sum(float(t.get("info", {}).get("realizedPnl", 0)) for t in trade_batch)
                    total_fee = sum(
                        float(t.get("fee", {}).get("cost", 0)) if (t.get("fee") and t.get("fee", {}).get("cost") is not None)
                        else float(t.get("info", {}).get("commission", 0))
                        for t in trade_batch
                    )
                    net_pnl = gross_pnl - total_fee
                    return gross_pnl, total_fee, net_pnl

                # 1. Jika close_order_id diketahui, cari semua fill dari order tersebut
                if close_order_id:
                    matching_trades = [
                        t for t in trades 
                        if str(t.get("order")) == str(close_order_id) or 
                           str(t.get("info", {}).get("orderId")) == str(close_order_id)
                    ]
                    if matching_trades:
                        gross, fee, net = _calc_net_pnl(matching_trades)
                        logger.info(
                            f"📊 Binance Realized PnL (Close Order #{close_order_id}, {len(matching_trades)} fills): "
                            f"Gross {gross:+.4f} | Fee -{fee:.4f} | Net: {net:+.4f} USDT"
                        )
                        return round(net, 4)

                # 2. Jika close_order_id tidak ada (misal closed on exchange / SL triggered), cari batch order penutupan terakhir SETELAH entry
                close_side = "sell" if side == "long" else "buy"
                closing_trades = [
                    t for t in trades 
                    if t.get("side") == close_side and float(t.get("info", {}).get("realizedPnl", 0)) != 0
                ]
                if closing_trades:
                    last_close_order_id = closing_trades[-1].get("order") or closing_trades[-1].get("info", {}).get("orderId")
                    if last_close_order_id:
                        batch_trades = [
                            t for t in closing_trades 
                            if (t.get("order") == last_close_order_id or t.get("info", {}).get("orderId") == last_close_order_id)
                        ]
                        gross, fee, net = _calc_net_pnl(batch_trades)
                        logger.info(
                            f"📊 Binance Realized PnL (Last Close Batch #{last_close_order_id}, {len(batch_trades)} fills): "
                            f"Gross {gross:+.4f} | Fee -{fee:.4f} | Net: {net:+.4f} USDT"
                        )
                        return round(net, 4)

                # 3. Fallback ke harga trade terakhir jika realizedPnl tidak ditemukan
                trade_price = float(trades[-1].get("price", 0))
                if trade_price > 0:
                    fallback_close_price = trade_price
        except Exception as e:
            logger.warning(f"⚠️ Gagal fetch trades dari exchange: {e}")
            
        # Fallback calculation dengan estimasi fee roundtrip
        if fallback_close_price is None or fallback_close_price <= 0:
            fallback_close_price = self.get_current_price(symbol)
            
        if fallback_close_price > 0 and entry_price > 0 and amount > 0:
            if side == "long":
                gross_fallback_pnl = (fallback_close_price - entry_price) * amount
            else:
                gross_fallback_pnl = (entry_price - fallback_close_price) * amount
                
            fee_rate = getattr(config, "ESTIMATED_ROUNDTRIP_FEE_PERCENT", 0.08) / 100.0
            estimated_fee = (amount * entry_price) * fee_rate
            net_fallback_pnl = gross_fallback_pnl - estimated_fee
            logger.info(
                f"📊 Fallback Calculated PnL: Gross {gross_fallback_pnl:+.4f} | "
                f"Est. Fee -{estimated_fee:.4f} | Net: {net_fallback_pnl:+.4f} USDT"
            )
    def close_partial(self, symbol, side, amount, reason="partial_tp"):
        """
        Close sebagian posisi aktif via MARKET order reduceOnly.
        Tidak menghapus state posisi secara keseluruhan, hanya mengeksekusi order pengurangan kontrak.
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                close_side = "sell" if side == "long" else "buy"
                amount_str = self.exchange.amount_to_precision(symbol, amount)
                amount = float(amount_str)
                
                logger.info(
                    f"💰 Partial Closing {side.upper()} {symbol} | "
                    f"Amount: {amount} | Reason: {reason} (attempt {attempt + 1})"
                )
                
                order = self.exchange.create_order(
                    symbol=symbol,
                    type="market",
                    side=close_side,
                    amount=amount,
                    params={"reduceOnly": True},
                )
                
                close_price = order.get("average") or order.get("price", 0)
                if not close_price or float(close_price) <= 0:
                    close_price = self.get_current_price(symbol)
                logger.info(f"✅ Partial position closed @ {close_price}")
                return order
                
            except ccxt.NetworkError as e:
                logger.error(f"❌ Network error partial closing position (attempt {attempt + 1}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
            except Exception as e:
                logger.error(f"❌ Error during partial close (attempt {attempt + 1}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
                    continue
        return None

    def close_position(self, symbol, side, amount, reason="manual"):
        """
        Close posisi aktif via MARKET order.
        Dengan retry mechanism jika gagal.
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                close_side = "sell" if side == "long" else "buy"
                
                logger.info(
                    f"🔴 Closing {side.upper()} {symbol} | "
                    f"Amount: {amount} | Reason: {reason} "
                    f"(attempt {attempt + 1})"
                )
                
                order = self.exchange.create_order(
                    symbol=symbol,
                    type="market",
                    side=close_side,
                    amount=amount,
                    params={"reduceOnly": True},
                )
                
                close_order_id = order.get("id") if order else None
                close_price = order.get("average") or order.get("price", 0)
                if not close_price or float(close_price) <= 0:
                    close_price = self.get_current_price(symbol)
                logger.info(f"✅ Position closed @ {close_price}")
                
                # Hitung PnL riil (mengagregasi seluruh fills dari order penutupan)
                pos = self.state.get_position()
                pnl = 0.0
                if pos:
                    entry = pos["entry_price"]
                    pnl = self.get_realized_pnl(
                        symbol=symbol,
                        side=side,
                        entry_price=entry,
                        amount=amount,
                        fallback_close_price=float(close_price) if close_price else None,
                        close_order_id=close_order_id
                    )
                
                # Cancel semua remaining orders (trailing stop, dll)
                self.cancel_all_orders(symbol)
                
                # Update state (ini otomatis mengaktifkan cooldown 30m)
                self.state.clear_position(pnl=pnl, reason=reason, start_cooldown=True)
                
                logger.info(f"💰 Realized PnL: {pnl:+.2f} USDT")
                
                return order
                
            except ccxt.InsufficientFunds:
                logger.warning(
                    f"⚠️ Insufficient funds to close. "
                    f"Fetching actual position size..."
                )
                actual_pos = self.fetch_position(symbol)
                if actual_pos and actual_pos["contracts"] > 0:
                    amount = actual_pos["contracts"]
                    logger.info(f"  🔄 Retrying with actual amount: {amount}")
                    continue
                else:
                    logger.info("  ✅ Position already closed (mungkin kena stop)")
                    self.cancel_all_orders(symbol)
                    pos = self.state.get_position()
                    pnl = 0.0
                    if pos:
                        pnl = self.get_realized_pnl(
                            symbol=symbol,
                            side=side,
                            entry_price=pos["entry_price"],
                            amount=pos["amount"]
                        )
                    self.state.clear_position(pnl=pnl, reason=f"{reason}_already_closed", start_cooldown=True)
                    return None
                    
            except ccxt.NetworkError as e:
                logger.error(
                    f"❌ Network error closing position (attempt {attempt + 1}): {e}"
                )
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
                    
            except ccxt.ExchangeError as e:
                error_msg = str(e).lower()
                if "position side does not match" in error_msg or \
                   "reduce only" in error_msg:
                    logger.warning(f"⚠️ Position mungkin sudah closed: {e}")
                    self.cancel_all_orders(symbol)
                    pos = self.state.get_position()
                    pnl = 0.0
                    if pos:
                        pnl = self.get_realized_pnl(
                            symbol=symbol,
                            side=side,
                            entry_price=pos["entry_price"],
                            amount=pos["amount"]
                        )
                    self.state.clear_position(pnl=pnl, reason=f"{reason}_already_closed", start_cooldown=True)
                    return None
                else:
                    logger.error(f"❌ Exchange error closing position: {e}")
                    if attempt < self.MAX_RETRIES - 1:
                        time.sleep(self.RETRY_DELAY)
                        continue
                        
            except Exception as e:
                logger.error(f"❌ Unexpected error closing position: {e}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
                    continue
        
        logger.critical(
            f"🚨 CRITICAL: Gagal close position setelah {self.MAX_RETRIES}x! "
            f"{side.upper()} {symbol} amount={amount}. MANUAL ACTION REQUIRED!"
        )
        return None
    
    # =========================================================================
    # Stop Market Order (untuk trailing stop ratchet)
    # =========================================================================
    
    def place_stop_order(self, symbol, side, amount, stop_price):
        """
        Place STOP_MARKET order (digunakan oleh trailing manager).
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                stop_side = "sell" if side == "long" else "buy"
                stop_price_rounded = float(self.exchange.price_to_precision(symbol, stop_price))
                
                logger.info(
                    f"🛡️ Placing STOP_MARKET {stop_side.upper()} {symbol} | "
                    f"Stop: {stop_price_rounded} | Amount: {amount}"
                )
                
                order = self.exchange.create_order(
                    symbol=symbol,
                    type="STOP_MARKET",
                    side=stop_side,
                    amount=amount,
                    price=None,
                    params={
                        "stopPrice": stop_price_rounded,
                        "reduceOnly": True,
                    },
                )
                
                order_id = order.get("id")
                logger.info(f"✅ Stop order placed! ID: {order_id}")
                return order
            
            except ccxt.NetworkError as e:
                logger.warning(f"⚠️ Network error placing stop (attempt {attempt + 1}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
                    continue
                    
            except ccxt.ExchangeError as e:
                error_msg = str(e).lower()
                if "would immediately trigger" in error_msg:
                    logger.warning(
                        f"⚠️ Stop price {stop_price_rounded} sudah terlewati! "
                        f"Harga sudah melewati level stop."
                    )
                    return None
                logger.error(f"❌ Exchange error placing stop: {e}")
                return None
                
            except Exception as e:
                logger.error(f"❌ Error placing stop order: {e}")
                return None
        
        return None
    
    def cancel_stop_order(self, symbol, order_id):
        """Cancel stop order dengan pengecekan apakah sudah triggered (mendukung Binance Algo Order)."""
        if not order_id:
            return "not_found"

        market_sym = symbol.replace("/", "").split(":")[0]

        # 1. Cek & cancel via Binance Algo Order API (karena STOP_MARKET di Futures pakai algoId)
        try:
            algo_info = self.exchange.fapiPrivateGetAlgoOrder({"algoId": int(order_id)})
            if algo_info:
                status = algo_info.get("algoStatus", "").upper()
                if status in ("FINISHED", "TRIGGERED"):
                    logger.warning(
                        f"⚠️ Stop order {order_id} sudah TRIGGERED ({status})! "
                        f"Posisi mungkin sudah ter-close."
                    )
                    return "triggered"
                elif status in ("CANCELLED", "EXPIRED", "REJECTED"):
                    logger.info(f"✅ Stop order {order_id} sudah {status}")
                    return "canceled"
                elif status in ("NEW", "ACTIVE"):
                    del_res = self.exchange.fapiPrivateDeleteAlgoOrder({
                        "symbol": market_sym,
                        "algoId": int(order_id)
                    })
                    logger.info(f"🚫 Algo stop order {order_id} canceled: {del_res.get('msg')}")
                    return "canceled"
        except Exception:
            pass

        # 2. Fallback ke standard order API
        try:
            try:
                order = self.exchange.fetch_order(order_id, symbol)
                status = order.get("status", "unknown")
                
                if status == "closed":
                    logger.warning(
                        f"⚠️ Stop order {order_id} sudah TRIGGERED! "
                        f"Posisi mungkin sudah ter-close."
                    )
                    return "triggered"
                
                elif status == "canceled" or status == "expired":
                    logger.info(f"✅ Stop order {order_id} sudah {status}")
                    return "canceled"
                    
            except ccxt.OrderNotFound:
                pass
            
            self.exchange.cancel_order(order_id, symbol)
            logger.info(f"🚫 Stop order {order_id} canceled")
            return "canceled"
            
        except ccxt.OrderNotFound:
            logger.info(f"✅ Stop order {order_id} already gone")
            return "not_found"
        except Exception as e:
            logger.error(f"❌ Error canceling stop order {order_id}: {e}")
            return "error"
    
    # =========================================================================
    # Get Current Position & Price
    # =========================================================================
    
    def fetch_position(self, symbol):
        """Fetch posisi aktif dari exchange (bukan dari local state)."""
        try:
            positions = self.exchange.fetch_positions([symbol])
            for pos in positions:
                contracts = float(pos.get("contracts", 0))
                if contracts > 0:
                    return {
                        "symbol": pos["symbol"],
                        "side": pos["side"],
                        "contracts": contracts,
                        "entry_price": float(pos.get("entryPrice", 0)),
                        "mark_price": float(pos.get("markPrice", 0)),
                        "unrealized_pnl": float(pos.get("unrealizedPnl", 0)),
                        "leverage": pos.get("leverage"),
                        "margin_mode": pos.get("marginMode"),
                    }
            return None
        except Exception as e:
            logger.error(f"❌ Error fetching position for {symbol}: {e}")
            return None
    
    def get_current_price(self, symbol):
        """Ambil harga terkini untuk symbol."""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker.get("last", 0)
        except Exception as e:
            logger.error(f"❌ Error fetching price for {symbol}: {e}")
            return 0
    
    def get_all_open_positions(self):
        """Fetch seluruh posisi yang sedang terbuka di Binance Futures (Anti-Double Position)."""
        try:
            positions = self.exchange.fetch_positions()
            open_positions = []
            for pos in positions:
                contracts = float(pos.get("contracts", 0) or pos.get("amount", 0) or 0)
                notional = abs(float(pos.get("notional", 0) or 0))
                # Abaikan sisa debu pembulatan (< 1.0 USDT)
                if abs(contracts) > 0.0001 and (notional >= 1.0 or notional == 0):
                    open_positions.append({
                        "symbol": pos["symbol"],
                        "side": pos.get("side", "long").lower(),
                        "amount": abs(contracts),
                        "entry_price": float(pos.get("entryPrice", 0)),
                        "mark_price": float(pos.get("markPrice", 0)),
                        "unrealized_pnl": float(pos.get("unrealizedPnl", 0)),
                    })
            return open_positions
        except Exception as e:
            logger.warning(f"⚠️ Error fetching all open positions: {e}")
            return []

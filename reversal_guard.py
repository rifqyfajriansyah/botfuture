"""
Reversal Guard
==============
Otomatis close posisi saat signal berbalik arah.
- LONG → Signal berubah ke SHORT → Close LONG
- SHORT → Signal berubah ke LONG → Close SHORT
- Signal WAIT/Netral → TIDAK close (biarkan trailing stop bekerja)
"""

import time
import config
from logger_setup import logger


class ReversalGuard:
    """Monitor signal reversal dan auto-close posisi."""
    
    def __init__(self, signal_engine, order_manager, trailing_manager, state_manager):
        self.signal_engine = signal_engine
        self.order_mgr = order_manager
        self.trailing_mgr = trailing_manager
        self.state = state_manager
        self.last_check_time = 0
    
    def should_check(self):
        """
        Cek apakah sudah waktunya cek reversal.
        Interval dikontrol oleh REVERSAL_CHECK_INTERVAL.
        """
        now = time.time()
        if now - self.last_check_time >= config.REVERSAL_CHECK_INTERVAL:
            self.last_check_time = now
            return True
        return False
    
    def check_and_act(self):
        """
        Cek reversal signal dan close posisi jika perlu.
        
        Returns:
            dict: {
                "action": "none" | "closed",
                "reason": str,
                "details": dict
            }
        """
        result = {"action": "none", "reason": "", "details": {}}
        
        if not self.should_check():
            return result
        
        pos = self.state.get_position()
        if not pos:
            return result
        
        symbol = pos["symbol"]
        side = pos["side"]
        
        # 1. CEK EXHAUSTION / CLIMAX DI PUCUK (Hanya jika posisi sudah cuan tebal)
        if getattr(config, "EXHAUSTION_EXIT_ENABLED", False):
            try:
                entry_price = float(pos.get("entry_price", 0))
                current_price = self.order_mgr.get_current_price(symbol)
                
                if entry_price > 0 and current_price > 0:
                    if side == "long":
                        profit_pct = ((current_price - entry_price) / entry_price) * 100.0
                    else:
                        profit_pct = ((entry_price - current_price) / entry_price) * 100.0
                    
                    min_profit = getattr(config, "EXHAUSTION_MIN_PROFIT_PERCENT", 2.2)
                    
                    if profit_pct >= min_profit:
                        exhaustion = self.signal_engine.check_exhaustion(
                            symbol=symbol,
                            current_side=side,
                            current_price=current_price,
                            entry_price=entry_price
                        )
                        
                        if exhaustion.get("exhausted"):
                            logger.warning(
                                f"🚀 CLIMAX/EXHAUSTION CONFIRMED at peak (+{profit_pct:.2f}%) for {symbol}! "
                                f"{exhaustion['reason']}"
                            )
                            
                            # Hapus trailing stop lama dari Binance
                            self.trailing_mgr.remove_stop(symbol)
                            
                            # Market close posisi untuk mengunci profit pucuk
                            close_result = self.order_mgr.close_position(
                                symbol=symbol,
                                side=side,
                                amount=pos["amount"],
                                reason=f"climax_exhaustion_exit (+{profit_pct:.2f}%)",
                            )
                            
                            if close_result:
                                result["action"] = "closed"
                                result["reason"] = exhaustion["reason"]
                                result["details"] = exhaustion.get("details", {})
                                logger.info(
                                    f"💰 Position CLOSED by Exhaustion Guard at PEAK! "
                                    f"Profit locked: +{profit_pct:.2f}%"
                                )
                                return result
                            else:
                                logger.error("❌ Failed to close position on exhaustion!")
            except Exception as e:
                logger.error(f"❌ Error during exhaustion guard check: {e}")
        
        # 1b. CEK BOUNCE FAILURE GUARD (Dead-Cat Bounce Rejection Cut)
        if getattr(config, "BOUNCE_FAILURE_GUARD_ENABLED", False):
            try:
                entry_price = float(pos.get("entry_price", 0))
                current_price = self.order_mgr.get_current_price(symbol)
                if entry_price > 0 and current_price > 0:
                    profit_pct = ((current_price - entry_price) / entry_price * 100.0) if side == "long" else ((entry_price - current_price) / entry_price * 100.0)
                    lowest_pct = float(pos.get("lowest_profit_pct", 0.0))
                    raw_rebound = pos.get("rebound_peak_pct")
                    rebound_peak_pct = float(raw_rebound) if raw_rebound is not None else lowest_pct
                    
                    min_drawdown = getattr(config, "BOUNCE_FAILURE_MIN_DRAWDOWN_PERCENT", -0.75)
                    min_rebound = getattr(config, "BOUNCE_FAILURE_MIN_REBOUND_PERCENT", 0.35)
                    slip_tol = getattr(config, "BOUNCE_FAILURE_SLIPPAGE_TOLERANCE", 0.25)
                    max_loss_pct = getattr(config, "BOUNCE_FAILURE_MAX_LOSS_PERCENT", -1.15)
                    max_loss_usdt = getattr(config, "MAX_LOSS_USDT_CAP", -8.80)
                    
                    # Kondisi Dead-Cat Bounce yang Valid:
                    # 1. Pernah mengalami drawdown minimal (lowest_pct <= min_drawdown)
                    # 2. PENTING: Harga WAJIB sudah pernah menguji / menembus batas lantai EMA 55 (Safe Pocket Protection)
                    #    Jika harga masih bermain aman di atas lantai EMA 55 (seperti TRB), rem TIDAK BOLEH memotong prematur!
                    require_ema55_test = getattr(config, "BOUNCE_FAILURE_REQUIRE_EMA55_TEST", True)
                    has_tested_ema55 = True
                    if require_ema55_test and hasattr(self, "signal_engine") and hasattr(self.signal_engine, "get_ema55"):
                        ema_55 = self.signal_engine.get_ema55(symbol)
                        if ema_55 and ema_55 > 0:
                            buffer_pct = getattr(config, "BOUNCE_FAILURE_EMA_BUFFER_PERCENT", 
                                                 getattr(config, "REVERSAL_EMA_BREAKDOWN_BUFFER_PERCENT", 0.52)) / 100.0
                            if side == "long":
                                floor_price = ema_55 * (1.0 - buffer_pct)
                                lowest_price = entry_price * (1.0 + lowest_pct / 100.0)
                                has_tested_ema55 = (lowest_price <= floor_price) or (current_price <= floor_price)
                                if not has_tested_ema55:
                                    logger.debug(
                                        f"🛡️ Bounce Failure Guard skip untuk {symbol}: Harga ({current_price:.4f}, low {lowest_price:.4f}) "
                                        f"masih di atas batas lantai EMA 55 ({floor_price:.4f}, ema55 {ema_55:.4f}). Safe pocket!"
                                    )
                            else:
                                ceiling_price = ema_55 * (1.0 + buffer_pct)
                                highest_price = entry_price * (1.0 - lowest_pct / 100.0)
                                has_tested_ema55 = (highest_price >= ceiling_price) or (current_price >= ceiling_price)
                                if not has_tested_ema55:
                                    logger.debug(
                                        f"🛡️ Bounce Failure Guard skip untuk {symbol}: Harga ({current_price:.4f}, high {highest_price:.4f}) "
                                        f"masih di bawah batas atap EMA 55 ({ceiling_price:.4f}, ema55 {ema_55:.4f}). Safe pocket!"
                                    )

                    had_significant_drawdown = (lowest_pct <= min_drawdown) and has_tested_ema55
                    has_real_rebound_data = (raw_rebound is not None) and (rebound_peak_pct > lowest_pct)
                    rebound_height = (rebound_peak_pct - lowest_pct) if has_real_rebound_data else 0.0
                    had_rebound = has_real_rebound_data and (rebound_height >= min_rebound)
                    lost_momentum = had_rebound and (rebound_peak_pct - profit_pct >= slip_tol) and (profit_pct < 0)
                    is_dead_cat_bounce = had_significant_drawdown and had_rebound and lost_momentum

                    # Bounded Cutloss (Circuit Breaker):
                    # Jika harga SUDAH di luar batas benteng EMA 55 (has_tested_ema55)
                    # dan meluncur lurus melawan kita hingga menyentuh batas rugi maksimal (% harga atau nominal USDT),
                    # tebas langsung tanpa perlu menunggu siklus pantulan!
                    approx_pnl_usdt = (profit_pct / 100.0) * (entry_price * float(pos.get("amount", 0)))
                    is_max_loss_breached = has_tested_ema55 and ((profit_pct <= max_loss_pct) or (approx_pnl_usdt <= max_loss_usdt))
                    
                    if is_dead_cat_bounce or is_max_loss_breached:
                        cut_cause = "dead_cat_bounce_rejection" if is_dead_cat_bounce else f"max_loss_ema_breached ({profit_pct:.2f}% | ${approx_pnl_usdt:.2f})"
                        logger.warning(
                            f"🛑 BOUNCE FAILURE / BOUNDED LOSS GUARD CONFIRMED ({cut_cause}) for {symbol}! "
                            f"Profit: {profit_pct:.2f}% (${approx_pnl_usdt:.2f}) | Drawdown: {lowest_pct:.2f}% | EMA55 tested: {has_tested_ema55} -> Membatasi kerugian maksimal!"
                        )
                        self.trailing_mgr.remove_stop(symbol)
                        close_result = self.order_mgr.close_position(
                            symbol=symbol,
                            side=side,
                            amount=pos["amount"],
                            reason=f"bounce_failure_guard: {cut_cause}",
                        )
                        if close_result:
                            result["action"] = "closed"
                            result["reason"] = f"bounce_failure_{cut_cause}"
                            result["details"] = {
                                "profit_pct": profit_pct,
                                "pnl_usdt": approx_pnl_usdt,
                                "lowest_pct": lowest_pct,
                                "rebound_peak_pct": rebound_peak_pct
                            }
                            logger.info(
                                f"🔴 Position CLOSED by Bounce Failure Guard | "
                                f"Kerugian dibatasi di profit {profit_pct:.2f}% (${approx_pnl_usdt:.2f}) sebelum membengkak lebih dalam!"
                            )
                            return result

                    # Kondisi 3: PANIC VOLUME DUMP CUT (Deteksi Air Terjun vs Gojekan Jarum di Lilin 1m)
                    if getattr(config, "PANIC_VOLUME_CUT_ENABLED", False):
                        panic_drawdown_thresh = getattr(config, "PANIC_VOLUME_CUT_MIN_DRAWDOWN", -0.75)
                        if profit_pct <= panic_drawdown_thresh:
                            # Ambil 10 lilin 1m untuk cek apakah ini air terjun volume nyata
                            try:
                                candles_1m = self.order_mgr.exchange.fetch_ohlcv(symbol, "1m", limit=12)
                                if candles_1m and len(candles_1m) >= 6:
                                    last_vol = candles_1m[-1][5]
                                    hist_vols = [c[5] for c in candles_1m[-6:-1]]
                                    avg_1m_vol = sum(hist_vols) / len(hist_vols) if hist_vols else 1.0
                                    rvol_1m = last_vol / avg_1m_vol if avg_1m_vol > 0 else 1.0
                                    panic_vol_ratio = getattr(config, "PANIC_VOLUME_CUT_RATIO", 2.5)
                                    
                                    if rvol_1m >= panic_vol_ratio:
                                        logger.warning(
                                            f"🚨 PANIC VOLUME DUMP CONFIRMED for {symbol}! "
                                            f"Drawdown: {profit_pct:.2f}% | Volume 1m meledak {rvol_1m:.1f}x (>= {panic_vol_ratio}x)! "
                                            f"Bukan gojekan jarum, ini air terjun Smart Money! Tebas instan!"
                                        )
                                        self.trailing_mgr.remove_stop(symbol)
                                        close_result = self.order_mgr.close_position(
                                            symbol=symbol,
                                            side=side,
                                            amount=pos["amount"],
                                            reason=f"panic_volume_dump_cut_{rvol_1m:.1f}x ({profit_pct:.2f}%)",
                                        )
                                        if close_result:
                                            result["action"] = "closed"
                                            result["reason"] = f"panic_volume_dump_cut_{rvol_1m:.1f}x"
                                            result["details"] = {
                                                "profit_pct": profit_pct,
                                                "rvol_1m": rvol_1m
                                            }
                                            logger.info(
                                                f"🔴 Position CLOSED by Panic Volume Cut | "
                                                f"Ditebas cepat di profit {profit_pct:.2f}% sebelum tergulung air terjun!"
                                            )
                                            return result
                                    else:
                                        logger.info(
                                            f"🛡️ Drawdown {profit_pct:.2f}% terdeteksi untuk {symbol}, "
                                            f"tetapi Volume 1m sepi/normal ({rvol_1m:.2f}x < {panic_vol_ratio}x). "
                                            f"Indikasi gojekan jarum likuidasi, posisi dipertahankan untuk memantul!"
                                        )
                            except Exception as e_vol:
                                logger.debug(f"Volume 1m check skip: {e_vol}")
            except Exception as e:
                logger.error(f"❌ Error during bounce failure guard check: {e}")
        
        # 2. CEK REVERSAL TREND (EMA 55 breakdown / Dead cross)
        logger.info(f"🔄 Checking signal reversal for {symbol} ({side.upper()})...")
        
        # Cek reversal menggunakan signal engine dengan proteksi Grace Period & Timestamp
        reversal = self.signal_engine.check_reversal(
            symbol=symbol,
            current_side=side,
            entry_time=pos.get("entry_time"),
            entry_price=pos.get("entry_price")
        )
        
        if reversal["reversed"]:
            logger.warning(
                f"⚠️ SIGNAL REVERSAL CONFIRMED for {symbol}! "
                f"{reversal['signal']} | Details: {reversal['details']}"
            )
            
            # Remove trailing stop dari Binance dulu
            self.trailing_mgr.remove_stop(symbol)
            
            # Close posisi via market order
            close_result = self.order_mgr.close_position(
                symbol=symbol,
                side=side,
                amount=pos["amount"],
                reason=f"signal_reversal: {reversal['signal']}",
            )
            
            if close_result:
                result["action"] = "closed"
                result["reason"] = reversal["signal"]
                result["details"] = reversal["details"]
                logger.info(
                    f"🔴 Position CLOSED by reversal guard | "
                    f"{reversal['signal']} | {reversal['details']}"
                )
            else:
                logger.error("❌ Failed to close position on reversal!")
        else:
            logger.info(f"  ✅ No reversal - position is safe")
        
        return result

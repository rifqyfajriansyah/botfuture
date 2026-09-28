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
                    rebound_peak_pct = float(pos.get("rebound_peak_pct", lowest_pct))
                    
                    min_drawdown = getattr(config, "BOUNCE_FAILURE_MIN_DRAWDOWN_PERCENT", -0.75)
                    min_rebound = getattr(config, "BOUNCE_FAILURE_MIN_REBOUND_PERCENT", 0.35)
                    slip_tol = getattr(config, "BOUNCE_FAILURE_SLIPPAGE_TOLERANCE", 0.25)
                    max_loss = getattr(config, "BOUNCE_FAILURE_MAX_LOSS_PERCENT", -0.85)
                    
                    # Kondisi Dead-Cat Bounce yang Valid:
                    # 1. Pernah mengalami drawdown signifikan (lowest_pct <= min_drawdown)
                    # 2. Harus ada rebound nyata: rebound_peak_pct harus dicatat setelah drawdown (bukan nilai default 0.0)
                    had_significant_drawdown = (lowest_pct <= min_drawdown)
                    
                    # Validasi apakah rebound_peak_pct benar-benar terjadi setelah drawdown
                    has_real_rebound_data = ("rebound_peak_pct" in pos) and (rebound_peak_pct > lowest_pct)
                    rebound_height = (rebound_peak_pct - lowest_pct) if has_real_rebound_data else 0.0
                    had_rebound = has_real_rebound_data and (rebound_height >= min_rebound)
                    lost_momentum = had_rebound and (rebound_peak_pct - profit_pct >= slip_tol) and (profit_pct < 0)
                    is_dead_cat_bounce = had_significant_drawdown and had_rebound and lost_momentum
                    
                    if is_dead_cat_bounce:
                        # Verifikasi Volume 1m: Jangan tebas jika volume sepi (koreksi wajar / gojekan jarum)
                        # Tebas HANYA jika terkonfirmasi volume sell di 1m >= 1.8x rata-rata (ada buang barang nyata)
                        is_volume_dumping = True
                        try:
                            c_1m = self.order_mgr.exchange.fetch_ohlcv(symbol, "1m", limit=10)
                            if c_1m and len(c_1m) >= 6:
                                last_v = c_1m[-1][5]
                                h_v = [c[5] for c in c_1m[-6:-1]]
                                avg_v = sum(h_v) / len(h_v) if h_v else 1.0
                                rvol = last_v / avg_v if avg_v > 0 else 1.0
                                if rvol < 1.8:
                                    is_volume_dumping = False
                                    logger.info(
                                        f"🛡️ Dead-Cat Bounce sinyal terdeteksi pada {symbol}, TETAPI Volume 1m sepi ({rvol:.2f}x < 1.8x). "
                                        f"Indikasi koreksi wajar tanpa buangan bandar. Posisi dipertahankan!"
                                    )
                        except Exception as e_v:
                            logger.debug(f"Volume check skip: {e_v}")

                        if is_volume_dumping:
                            cut_cause = "dead_cat_bounce_rejection"
                            logger.warning(
                                f"🛑 BOUNCE FAILURE GUARD CONFIRMED ({cut_cause}) for {symbol}! "
                                f"Profit: {profit_pct:.2f}% | Drawdown: {lowest_pct:.2f}% | Rebound Peak: {rebound_peak_pct:.2f}%"
                            )
                            self.trailing_mgr.remove_stop(symbol)
                            close_result = self.order_mgr.close_position(
                                symbol=symbol,
                                side=side,
                                amount=pos["amount"],
                                reason=f"bounce_failure_guard: {cut_cause} ({profit_pct:.2f}%)",
                            )
                        if close_result:
                            result["action"] = "closed"
                            result["reason"] = f"bounce_failure_guard_{cut_cause}"
                            result["details"] = {
                                "profit_pct": profit_pct,
                                "lowest_pct": lowest_pct,
                                "rebound_peak_pct": rebound_peak_pct
                            }
                            logger.info(
                                f"🔴 Position CLOSED by Bounce Failure Guard | "
                                f"Modal diselamatkan dari jurang di profit {profit_pct:.2f}%"
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

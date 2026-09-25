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

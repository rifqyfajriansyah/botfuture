"""
Trailing Stop Manager
=====================
Mengelola trailing stop dengan sistem Pro Breathing Room Ratchet.

Mekanisme:
- Entry: Emergency Stop Loss di -25% (safety net anti-likuidasi).
- Profit +5.0% → Kunci BEP (+0.5%) dengan ruang napas 4.5% agar tidak gampang kejilat.
- Profit +8.0% → Geser stop ke +4.0% (mulai amankan profit bersih).
- Profit +11.0% → Geser stop ke +7.0%.
- Profit +14.0% → Geser stop ke +10.0%.
- Tiap kenaikan +3.0% → Stop digeser naik +3.0% (selalu beri 4.0% breathing room).
- Instan Jump: Jika harga melonjak tiba-tiba (misal ke +20%), stop langsung lompat ke level tertinggi (+16%) dalam 1 order.
"""

from datetime import datetime
import config
from logger_setup import logger


class TrailingManager:
    """Mengelola pro stepped trailing stop berdasarkan checkpoint profit."""
    
    def __init__(self, order_manager, state_manager):
        self.order_mgr = order_manager
        self.state = state_manager
    
    def calculate_profit_pct(self, entry_price, current_price, side):
        """Hitung profit percentage berdasarkan posisi."""
        if entry_price <= 0:
            return 0.0
        
        if side == "long":
            return ((current_price - entry_price) / entry_price) * 100
        else:
            return ((entry_price - current_price) / entry_price) * 100
    
    def calculate_stop_price(self, entry_price, stop_profit_pct, side):
        """Hitung harga stop berdasarkan target profit percentage."""
        if side == "long":
            return entry_price * (1 + stop_profit_pct / 100)
        else:
            return entry_price * (1 - stop_profit_pct / 100)
    
    def get_stop_level_for_checkpoint(self, checkpoint):
        """
        Tentukan level stop profit berdasarkan checkpoint.
        - Checkpoint 5.0% → Stop di 0.5% (BEP + cover fee)
        - Checkpoint 8.0% → Stop di 4.0%
        - Checkpoint 11.0% → Stop di 7.0%
        - dst...
        """
        first_cp = getattr(config, "TRAILING_FIRST_CHECKPOINT_PERCENT", 5.0)
        first_stop = getattr(config, "TRAILING_FIRST_STOP_PERCENT", 0.5)
        offset = getattr(config, "TRAILING_STOP_OFFSET", 4.0)
        
        if checkpoint <= first_cp:
            return first_stop
        else:
            return checkpoint - offset
    
    def get_highest_reached_checkpoint(self, profit_pct):
        """
        Hitung checkpoint tertinggi yang sudah tercapai oleh profit saat ini.
        Mendukung lompatan harga instan (misal loncat langsung ke +20%).
        """
        first_cp = getattr(config, "TRAILING_FIRST_CHECKPOINT_PERCENT", 5.0)
        step = getattr(config, "TRAILING_CHECKPOINT_STEP", 3.0)
        
        if profit_pct < first_cp:
            return 0
            
        steps = int((profit_pct - first_cp) // step)
        return first_cp + (steps * step)
    
    def update(self, symbol, entry_price, current_price, side, amount):
        """
        Update trailing stop berdasarkan profit saat ini.
        Dipanggil secara periodik dari main loop.
        """
        result = {
            "action": "none",
            "profit_pct": 0,
            "checkpoint": self.state.get_current_checkpoint(),
            "stop_price": 0,
        }
        
        profit_pct = self.calculate_profit_pct(entry_price, current_price, side)
        result["profit_pct"] = round(profit_pct, 2)
        
        self.state.update_highest_profit(profit_pct)
        pos = self.state.get_position() or {}
        
        # 1. Emergency SL Check
        if config.EMERGENCY_SL_ENABLED and profit_pct <= -config.EMERGENCY_SL_PERCENT:
            logger.critical(
                f"🚨 EMERGENCY STOP LOSS! {symbol} | "
                f"Profit: {profit_pct:.2f}% | "
                f"Threshold: -{config.EMERGENCY_SL_PERCENT}%"
            )
            result["action"] = "emergency_sl"
            return result
        
        # 2. Cek apakah stop order lama masih ada di exchange
        old_stop = self.state.get_trailing_stop()
        if old_stop and old_stop.get("order_id"):
            stop_status = self._verify_stop_order(symbol, old_stop["order_id"])
            if stop_status == "triggered":
                logger.warning(
                    f"⚠️ Trailing stop {old_stop['order_id']} sudah TRIGGERED! "
                    f"Posisi kemungkinan sudah ter-close oleh Binance."
                )
                result["action"] = "stop_triggered"
                return result
        
        # 3. Hitung checkpoint tertinggi yang sudah tercapai
        current_checkpoint = self.state.get_current_checkpoint() or 0
        highest_cp = self.get_highest_reached_checkpoint(profit_pct)
        
        if highest_cp > current_checkpoint:
            # Loncat langsung ke checkpoint tertinggi yang tercapai
            stop_profit_level = self.get_stop_level_for_checkpoint(highest_cp)
            stop_price = self.calculate_stop_price(entry_price, stop_profit_level, side)
            
            # Cek apakah stop price baru ini benar-benar LEBIH BAIK daripada stop price saat ini
            # JANGAN PERNAH DOWNGRADE STOP PRICE!
            should_update = False
            if not old_stop or not old_stop.get("stop_price"):
                should_update = True
            else:
                cur_stop = old_stop["stop_price"]
                if side == "long" and stop_price > cur_stop:
                    should_update = True
                elif side == "short" and stop_price < cur_stop:
                    should_update = True
            
            if should_update:
                logger.info(
                    f"🎯 Checkpoint +{highest_cp}% REACHED! "
                    f"Profit: {profit_pct:.2f}% | "
                    f"Locking Stop Level: +{stop_profit_level}% | "
                    f"Stop Price: {stop_price}"
                )
                
                # Cancel stop order lama
                if old_stop and old_stop.get("order_id"):
                    cancel_result = self.order_mgr.cancel_stop_order(
                        symbol, old_stop["order_id"]
                    )
                    if cancel_result == "triggered":
                        logger.warning("⚠️ Old stop already triggered during checkpoint update!")
                        result["action"] = "stop_triggered"
                        return result
                
                # Place stop order baru di Binance langsung di level tertinggi
                stop_order = self.order_mgr.place_stop_order(
                    symbol=symbol,
                    side=side,
                    amount=amount,
                    stop_price=stop_price,
                )
                
                if stop_order:
                    self.state.set_trailing_stop(
                        stop_order_id=stop_order["id"],
                        stop_price=stop_price,
                        checkpoint_level=highest_cp,
                    )
                    
                    result["action"] = "new_stop" if current_checkpoint == 0 else "update_stop"
                    result["checkpoint"] = highest_cp
                    result["stop_price"] = stop_price
                    
                    logger.info(
                        f"  ✅ Trailing stop RATIFIED: "
                        f"checkpoint +{highest_cp}% → "
                        f"stop locked @ +{stop_profit_level}% (price: {stop_price})"
                    )
                else:
                    logger.error("  ❌ Gagal pasang stop order baru!")
                return result
            else:
                # Stop price saat ini sudah lebih baik (misal dari time progressive lock),
                # simpan checkpoint_level tertinggi di state agar Step 3 tidak terus terpanggil
                if highest_cp > current_checkpoint:
                    self.state.state["current_checkpoint"] = highest_cp
                    self.state.save()
        
        # 4. Time-Progressive Profit Lock (Dynamic Ratchet by Time)
        # Jika trade berjalan lama (>= 90m / 1.5 jam), kerek stop order lebih tinggi
        # agar tidak keluar di 0 koma sekian persen jika harga sudah sempat profit lumayan.
        if getattr(config, "TIME_PROGRESSIVE_LOCK_ENABLED", True):
            entry_time_str = pos.get("entry_time")
            if entry_time_str:
                try:
                    entry_dt = datetime.fromisoformat(entry_time_str)
                    elapsed_minutes = (datetime.now() - entry_dt).total_seconds() / 60.0
                except Exception:
                    elapsed_minutes = 0.0
                
                highest_p = pos.get("highest_profit_pct", 0.0)
                eff_profit = max(highest_p, profit_pct)
                
                tiers = getattr(config, "TIME_PROGRESSIVE_TIERS", [])
                active_tier = None
                for req_min, req_profit, lock_stop_pct in tiers:
                    if elapsed_minutes >= req_min and eff_profit >= req_profit:
                        active_tier = (req_min, req_profit, lock_stop_pct)
                        
                if active_tier:
                    tier_min, tier_req_profit, target_stop_pct = active_tier
                    target_stop_price = self.calculate_stop_price(entry_price, target_stop_pct, side)
                    
                    should_update_progressive = False
                    if not old_stop or not old_stop.get("stop_price"):
                        should_update_progressive = True
                    else:
                        cur_stop_price = old_stop["stop_price"]
                        if side == "long" and cur_stop_price < target_stop_price:
                            should_update_progressive = True
                        elif side == "short" and cur_stop_price > target_stop_price:
                            should_update_progressive = True
                            
                    if should_update_progressive:
                        logger.info(
                            f"⏰ TIME-PROGRESSIVE LOCK ACTIVATED! Trade age: {elapsed_minutes:.1f}m >= {tier_min}m | "
                            f"Peak/Now Profit: +{eff_profit:.2f}% >= {tier_req_profit}% | "
                            f"Ratcheting Stop to: +{target_stop_pct}% (Price: {target_stop_price})"
                        )
                        if old_stop and old_stop.get("order_id"):
                            cancel_result = self.order_mgr.cancel_stop_order(
                                symbol, old_stop["order_id"]
                            )
                            if cancel_result == "triggered":
                                logger.warning("⚠️ Old stop already triggered during progressive lock!")
                                result["action"] = "stop_triggered"
                                return result
                                
                        stop_order = self.order_mgr.place_stop_order(
                            symbol=symbol,
                            side=side,
                            amount=amount,
                            stop_price=target_stop_price,
                        )
                        if stop_order:
                            effective_cp = max(current_checkpoint, highest_cp)
                            self.state.set_trailing_stop(
                                stop_order_id=stop_order["id"],
                                stop_price=target_stop_price,
                                checkpoint_level=effective_cp,
                            )
                            result["action"] = "progressive_lock"
                            result["checkpoint"] = effective_cp
                            result["stop_price"] = target_stop_price
                            logger.info(
                                f"  ✅ TIME-PROGRESSIVE STOP RATIFIED: Stop locked @ {target_stop_price} (+{target_stop_pct}%)"
                            )
                            return result
                        else:
                            logger.error("  ❌ Gagal pasang progressive stop order!")

        # 5. Time-Delayed BEP (Grace Period Protection)
        # Jika belum tembus checkpoint 1 (+2.0%) tapi sudah berjalan > 45m dan sempat profit >= +0.8%
        if current_checkpoint == 0 and getattr(config, "TIME_DELAYED_BEP_ENABLED", True):
            entry_time_str = pos.get("entry_time")
            if entry_time_str:
                try:
                    entry_dt = datetime.fromisoformat(entry_time_str)
                    elapsed_minutes = (datetime.now() - entry_dt).total_seconds() / 60.0
                except Exception:
                    elapsed_minutes = 0.0
                
                req_minutes = getattr(config, "TIME_DELAYED_BEP_MINUTES", 45)
                req_profit = getattr(config, "TIME_DELAYED_BEP_MIN_PROFIT_PERCENT", 0.8)
                highest_p = pos.get("highest_profit_pct", 0.0)
                
                if elapsed_minutes >= req_minutes and (highest_p >= req_profit or profit_pct >= req_profit):
                    bep_stop_level = getattr(config, "TIME_DELAYED_BEP_STOP_PERCENT", 0.12)
                    bep_stop_price = self.calculate_stop_price(entry_price, bep_stop_level, side)
                    
                    should_lock_bep = False
                    if not old_stop or not old_stop.get("stop_price"):
                        should_lock_bep = True
                    else:
                        if side == "long" and old_stop["stop_price"] < bep_stop_price:
                            should_lock_bep = True
                        elif side == "short" and old_stop["stop_price"] > bep_stop_price:
                            should_lock_bep = True
                    
                    if should_lock_bep:
                        logger.info(
                            f"🛡️ TIME-DELAYED BEP ACTIVATED! Trade age: {elapsed_minutes:.1f}m >= {req_minutes}m | "
                            f"Peak profit: +{highest_p:.2f}% (Now: {profit_pct:+.2f}%) | "
                            f"Locking Stop Level: +{bep_stop_level}% (BEP Price: {bep_stop_price})"
                        )
                        if old_stop and old_stop.get("order_id"):
                            cancel_result = self.order_mgr.cancel_stop_order(
                                symbol, old_stop["order_id"]
                            )
                            if cancel_result == "triggered":
                                logger.warning("⚠️ Old stop already triggered during BEP lock!")
                                result["action"] = "stop_triggered"
                                return result
                        
                        stop_order = self.order_mgr.place_stop_order(
                            symbol=symbol,
                            side=side,
                            amount=amount,
                            stop_price=bep_stop_price,
                        )
                        if stop_order:
                            self.state.set_trailing_stop(
                                stop_order_id=stop_order["id"],
                                stop_price=bep_stop_price,
                                checkpoint_level=0.5,
                            )
                            result["action"] = "bep_locked"
                            result["checkpoint"] = 0.5
                            result["stop_price"] = bep_stop_price
                            logger.info(
                                f"  ✅ BEP STOP RATIFIED: Stop locked @ {bep_stop_price} (+{bep_stop_level}%)"
                            )
                        else:
                            logger.error("  ❌ Gagal pasang BEP stop order!")
        
        return result
    
    def _verify_stop_order(self, symbol, order_id):
        """Verifikasi apakah stop order masih aktif di Binance (mendukung Algo Orders)."""
        if not order_id:
            return "not_found"

        # 1. Cek via Binance Algo Order API
        try:
            algo_info = self.order_mgr.exchange.fapiPrivateGetAlgoOrder({"algoId": int(order_id)})
            if algo_info:
                status = algo_info.get("algoStatus", "").upper()
                if status in ("FINISHED", "TRIGGERED"):
                    return "triggered"
                elif status in ("NEW", "ACTIVE"):
                    return "active"
                elif status in ("CANCELLED", "EXPIRED", "REJECTED"):
                    return "canceled"
        except Exception:
            pass

        # 2. Fallback regular order API
        try:
            order = self.order_mgr.exchange.fetch_order(order_id, symbol)
            status = order.get("status", "unknown")
            
            if status == "closed":
                return "triggered"
            elif status == "open":
                return "active"
            elif status in ("canceled", "expired"):
                return "canceled"
            else:
                return status
        except Exception:
            return "active"
    
    def remove_stop(self, symbol):
        """Remove trailing stop order dari Binance saat manual / reversal exit."""
        stop_info = self.state.get_trailing_stop()
        if not stop_info or not stop_info.get("order_id"):
            return "not_found"
        
        result = self.order_mgr.cancel_stop_order(symbol, stop_info["order_id"])
        logger.info(f"🗑️ Trailing stop removal result: {result}")
        return result

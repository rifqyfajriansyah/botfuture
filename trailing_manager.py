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

import time
from datetime import datetime
import config
from logger_setup import logger


class TrailingManager:
    """Mengelola pro stepped trailing stop berdasarkan checkpoint profit."""
    
    def __init__(self, order_manager, state_manager):
        self.order_mgr = order_manager
        self.state = state_manager
        self._cached_btcdom_time = 0
        self._cached_btcdom_change = 0.0
    
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
            
    def _get_btcdom_momentum(self):
        """
        Ambil momentum perubahan BTCDOM di timeframe 15m.
        Cached selama 30 detik untuk efisiensi API.
        """
        now = time.time()
        if now - getattr(self, "_cached_btcdom_time", 0) < 30:
            return getattr(self, "_cached_btcdom_change", 0.0)
            
        try:
            dom_sym = getattr(config, "DOM_SYMBOL", "BTCDOM/USDT")
            candles = self.order_mgr.exchange.fetch_ohlcv(dom_sym, "15m", limit=2)
            if candles and len(candles) >= 1:
                last_c = candles[-1]
                chg = ((last_c[4] - last_c[1]) / last_c[1]) * 100.0
                self._cached_btcdom_change = chg
                self._cached_btcdom_time = now
                return chg
        except Exception as e:
            logger.debug(f"Gagal fetch BTCDOM momentum: {e}")
            
        return 0.0
    
    def _get_symbol_atr_pct(self, symbol):
        """
        Ambil volatilitas ATR 14 (timeframe 15m) koin saat ini dalam satuan persen (%).
        Cached selama 60 detik untuk efisiensi API.
        Fallback default: 0.85% jika gagal fetch.
        """
        now = time.time()
        if not hasattr(self, "_cached_atr"):
            self._cached_atr = {}
            
        cached = self._cached_atr.get(symbol)
        if cached and (now - cached["time"] < 60):
            return cached["atr_pct"]
            
        try:
            tf = getattr(config, "TRADING_TIMEFRAME", "15m")
            candles = self.order_mgr.exchange.fetch_ohlcv(symbol, tf, limit=16)
            if candles and len(candles) >= 14:
                tr_list = []
                for i in range(1, len(candles)):
                    h = candles[i][2]
                    l = candles[i][3]
                    prev_c = candles[i-1][4]
                    tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
                    tr_list.append(tr)
                atr_val = sum(tr_list[-14:]) / 14.0
                last_close = candles[-1][4]
                atr_pct = (atr_val / last_close) * 100.0 if last_close > 0 else 0.85
                self._cached_atr[symbol] = {"atr_pct": atr_pct, "time": now}
                return atr_pct
        except Exception as e:
            logger.debug(f"Gagal hitung ATR live {symbol}: {e}")
            
        return 0.85
    
    def get_dynamic_tp_target(self, symbol):
        """Hitung target partial TP dinamis berdasarkan ATR koin."""
        if not getattr(config, "DYNAMIC_TP_ENABLED", True):
            return getattr(config, "PARTIAL_TP_PERCENT", 2.42)
            
        atr_pct = self._get_symbol_atr_pct(symbol)
        mult = getattr(config, "DYNAMIC_TP_ATR_MULTIPLIER", 2.2)
        min_p = getattr(config, "DYNAMIC_TP_MIN_PERCENT", 1.75)
        max_p = getattr(config, "DYNAMIC_TP_MAX_PERCENT", 3.60)
        
        calc_tp = atr_pct * mult
        return round(max(min_p, min(max_p, calc_tp)), 2)
    
    def get_dynamic_trailing_params(self, symbol):
        """Hitung checkpoint 1, stop level 1, dan offset pengawalan dinamis berdasarkan ATR koin."""
        atr_pct = self._get_symbol_atr_pct(symbol)
        
        # 1. Checkpoint 1
        cp1_ratio = getattr(config, "TRAILING_FIRST_CHECKPOINT_ATR_RATIO", 1.8)
        cp1_min = getattr(config, "TRAILING_FIRST_CHECKPOINT_MIN_PERCENT", 1.45)
        first_cp = round(max(cp1_min, atr_pct * cp1_ratio), 2)
        
        # 2. Stop Level 1
        stop1_ratio = getattr(config, "TRAILING_FIRST_STOP_ATR_RATIO", 0.85)
        stop1_min = getattr(config, "TRAILING_FIRST_STOP_MIN_PERCENT", 0.70)
        first_stop = round(max(stop1_min, atr_pct * stop1_ratio), 2)
        
        # 3. Trailing Offset (Ruang napas)
        offset_ratio = getattr(config, "TRAILING_STOP_OFFSET_ATR_RATIO", 0.85)
        offset_min = getattr(config, "TRAILING_STOP_OFFSET_MIN", 0.70)
        offset_max = getattr(config, "TRAILING_STOP_OFFSET_MAX", 1.20)
        offset = round(max(offset_min, min(offset_max, atr_pct * offset_ratio)), 2)
        
        step = getattr(config, "TRAILING_CHECKPOINT_STEP", 0.50)
        
        return {
            "first_cp": first_cp,
            "first_stop": first_stop,
            "offset": offset,
            "step": step,
            "atr_pct": round(atr_pct, 2)
        }
    
    def get_stop_level_for_checkpoint(self, checkpoint, symbol=None):
        """
        Tentukan level stop profit berdasarkan checkpoint (Dinamis Adaptif ATR).
        """
        if symbol:
            p = self.get_dynamic_trailing_params(symbol)
            first_cp = p["first_cp"]
            first_stop = p["first_stop"]
            offset = p["offset"]
        else:
            first_cp = getattr(config, "TRAILING_FIRST_CHECKPOINT_PERCENT", 1.65)
            first_stop = getattr(config, "TRAILING_FIRST_STOP_PERCENT", 0.80)
            offset = getattr(config, "TRAILING_STOP_OFFSET", 0.85)
        
        if checkpoint <= first_cp:
            return first_stop
        else:
            return round(checkpoint - offset, 2)
    
    def get_highest_reached_checkpoint(self, profit_pct, symbol=None):
        """
        Hitung checkpoint tertinggi yang sudah tercapai oleh profit saat ini (Dinamis Adaptif ATR).
        """
        if symbol:
            p = self.get_dynamic_trailing_params(symbol)
            first_cp = p["first_cp"]
            step = p["step"]
        else:
            first_cp = getattr(config, "TRAILING_FIRST_CHECKPOINT_PERCENT", 1.65)
            step = getattr(config, "TRAILING_CHECKPOINT_STEP", 0.50)
        
        if profit_pct < first_cp:
            return 0
            
        steps = int((profit_pct - first_cp) // step)
        return round(first_cp + (steps * step), 2)
    
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
        
        # 2b. PARTIAL TAKE PROFIT (Target Dinamis ATR ATAU Stall Guard "Bensin Habis" di Tengah Jalan)
        if getattr(config, "PARTIAL_TP_ENABLED", True) and not pos.get("partial_tp_done", False):
            # Target TP Dinamis Adaptif ATR koin
            tp_target_pct = self.get_dynamic_tp_target(symbol)
            hit_main_target = profit_pct >= tp_target_pct
            
            # Cek Stall Guard ("Bensin Habis di Tengah Jalan")
            hit_stall_guard = False
            stall_reason = ""
            if not hit_main_target and getattr(config, "STALL_GUARD_ENABLED", True):
                # Ambang aktif dinamis: 60% perjalanan menuju Target TP Dinamis
                trigger_ratio = getattr(config, "STALL_GUARD_TRIGGER_RATIO", 0.60)
                floor_min = getattr(config, "STALL_GUARD_MIN_PROFIT_FLOOR", 1.10)
                stall_min = round(max(floor_min, tp_target_pct * trigger_ratio), 2)
                stall_max = round(tp_target_pct - 0.05, 2)
                
                # Toleransi melorot dinamis adaptif ATR koin
                atr_pct = self._get_symbol_atr_pct(symbol)
                pullback_ratio = getattr(config, "STALL_GUARD_DYNAMIC_PULLBACK_RATIO", 0.40)
                min_pb = getattr(config, "STALL_GUARD_MIN_PULLBACK_PERCENT", 0.32)
                max_pb = getattr(config, "STALL_GUARD_MAX_PULLBACK_PERCENT", 0.60)
                pullback_thresh = round(max(min_pb, min(max_pb, atr_pct * pullback_ratio)), 2)
                min_exit_profit = getattr(config, "STALL_GUARD_MIN_EXIT_PROFIT", 0.75)
                
                # Cek umur trade untuk Stall Guard koin matang / berumur (>= 120 menit)
                entry_time_str = pos.get("entry_time")
                if entry_time_str:
                    try:
                        entry_dt = datetime.fromisoformat(entry_time_str)
                        elapsed_minutes = (datetime.now() - entry_dt).total_seconds() / 60.0
                        aged_minutes = getattr(config, "TIME_PROGRESSIVE_MINUTES", 120)
                        if elapsed_minutes >= aged_minutes:
                            stall_min = getattr(config, "STALL_GUARD_AGED_MIN_PROFIT_PERCENT", 1.05)
                            pullback_thresh = getattr(config, "STALL_GUARD_AGED_PULLBACK_PERCENT", 0.32)
                            min_exit_profit = getattr(config, "STALL_GUARD_AGED_MIN_EXIT_PROFIT", 0.60)
                    except Exception:
                        pass
                
                highest_p = float(pos.get("highest_profit_pct", 0.0) or 0.0)
                if highest_p >= stall_min and profit_pct < stall_max and profit_pct >= min_exit_profit:
                    # Skenario A: Melorot >= pullback_thresh dari puncak profit yang pernah dicapai
                    if (highest_p - profit_pct) >= pullback_thresh:
                        hit_stall_guard = True
                        stall_reason = f"stall_pullback (Peak +{highest_p:.2f}% -> Now +{profit_pct:.2f}% | Thresh: {pullback_thresh}%)"
                    else:
                        # Skenario B: Terbentuk jarum penolakan (rejection wick >= 30%) pada lilin 15m
                        try:
                            tf = getattr(config, "TRADING_TIMEFRAME", "15m")
                            candles = self.order_mgr.exchange.fetch_ohlcv(symbol, tf, limit=2)
                            if candles and len(candles) >= 1:
                                l_c = candles[-1]
                                o_p = float(l_c[1])
                                h_p = float(l_c[2])
                                l_p = float(l_c[3])
                                c_p = float(l_c[4])
                                c_range = h_p - l_p
                                if c_range > 0:
                                    wick_thresh = getattr(config, "STALL_GUARD_WICK_PERCENT", 30.0)
                                    if side == "long":
                                        upper_wick = (h_p - max(o_p, c_p)) / c_range * 100.0
                                        if upper_wick >= wick_thresh and (highest_p - profit_pct) >= 0.22:
                                            hit_stall_guard = True
                                            stall_reason = f"stall_upper_wick_{upper_wick:.1f}%"
                                    else:
                                        lower_wick = (min(o_p, c_p) - l_p) / c_range * 100.0
                                        if lower_wick >= wick_thresh and (highest_p - profit_pct) >= 0.22:
                                            hit_stall_guard = True
                                            stall_reason = f"stall_lower_wick_{lower_wick:.1f}%"
                        except Exception as e:
                            logger.debug(f"Stall guard wick check error: {e}")
            
            # 2a. STALL GUARD FULL CLOSE (Hanya jika disetel True eksplisit, default: False agar 50% jadi Moonbag)
            if hit_stall_guard and getattr(config, "STALL_GUARD_CLOSE_FULL", False):
                logger.info(
                    f"🛑 STALL GUARD FULL CLOSE TRIGGERED! ({stall_reason}) | "
                    f"Momentum habis di tengah jalan (+{profit_pct:.2f}%). "
                    f"Closing 100% position ({amount} {symbol}) to lock full profit in cash..."
                )
                close_order = self.order_mgr.close_position(
                    symbol=symbol,
                    side=side,
                    amount=amount,
                    reason=f"stall_guard_full_{profit_pct:.2f}%"
                )
                if close_order:
                    result["action"] = "stall_guard_full_close"
                    return result

            # 2b. PARTIAL TP (Main Target Dinamis ATAU Stall Guard 50% Moonbag)
            if hit_main_target or hit_stall_guard:
                ratio = getattr(config, "PARTIAL_TP_RATIO", 0.5)
                raw_tp_amount = amount * ratio
                try:
                    tp_amount = float(self.order_mgr.exchange.amount_to_precision(symbol, raw_tp_amount))
                except Exception:
                    tp_amount = raw_tp_amount
                    
                if tp_amount > 0 and tp_amount < amount:
                    trigger_desc = f"DYNAMIC TARGET (+{profit_pct:.2f}% >= +{tp_target_pct}%)" if hit_main_target else f"STALL GUARD ({stall_reason})"
                    logger.info(
                        f"🎉 PARTIAL TP TRIGGERED! {trigger_desc} | "
                        f"Executing 50% TP ({tp_amount} {symbol}) to lock cash in pocket..."
                    )
                    reason_str = f"partial_tp_main_{profit_pct:.2f}%" if hit_main_target else f"partial_tp_stall_{profit_pct:.2f}%"
                    close_order = self.order_mgr.close_partial(
                        symbol=symbol,
                        side=side,
                        amount=tp_amount,
                        reason=reason_str
                    )
                    if close_order:
                        close_order_id = close_order.get("id")
                        time.sleep(1.0)  # Beri waktu Binance memproses fills
                        partial_pnl = self.order_mgr.get_realized_pnl(
                            symbol=symbol,
                            side=side,
                            entry_price=entry_price,
                            amount=tp_amount,
                            fallback_close_price=current_price,
                            close_order_id=close_order_id
                        )
                        logger.info(f"💰 Realized Partial TP PnL: {partial_pnl:+.4f} USDT")
                        
                        try:
                            remaining_amount = float(self.order_mgr.exchange.amount_to_precision(symbol, amount - tp_amount))
                        except Exception:
                            remaining_amount = amount - tp_amount
                            
                        # Update state
                        pos["amount"] = remaining_amount
                        pos["partial_tp_done"] = True
                        pos["partial_tp_price"] = current_price
                        pos["partial_tp_pct"] = profit_pct
                        pos["partial_realized_pnl"] = partial_pnl
                        pos["partial_tp_time"] = datetime.now().isoformat()
                        self.state.save()
                        amount = remaining_amount
                        
                        # Kunci stop sisa 50% posisi:
                        # Jika Main Target -> Kunci stop di level stop Checkpoint 1 dinamis
                        # Jika Stall Guard -> Kunci stop di BEP (+0.22% cover fee)
                        if hit_main_target:
                            dyn_params = self.get_dynamic_trailing_params(symbol)
                            bep_pct = dyn_params["first_stop"]
                        else:
                            bep_pct = 0.22  # BEP murni cover fee
                        bep_stop_price = self.calculate_stop_price(entry_price, bep_pct, side)
                        
                        if old_stop and old_stop.get("order_id"):
                            self.order_mgr.cancel_stop_order(symbol, old_stop["order_id"])
                            
                        new_stop = self.order_mgr.place_stop_order(
                            symbol=symbol,
                            side=side,
                            amount=remaining_amount,
                            stop_price=bep_stop_price
                        )
                        if new_stop:
                            dyn_params = self.get_dynamic_trailing_params(symbol)
                            self.state.set_trailing_stop(
                                stop_order_id=new_stop["id"],
                                stop_price=bep_stop_price,
                                checkpoint_level=dyn_params["first_cp"]
                            )
                            logger.info(
                                f"🛡️ PARTIAL TP COMPLETED! Remaining {remaining_amount} {symbol} stop "
                                f"locked @ {bep_stop_price} (+{bep_pct}%). Free ride to the peak (Moonbag)!"
                            )
                            result["action"] = "partial_tp"
                            result["stop_price"] = bep_stop_price
                            return result

        # 3. Hitung checkpoint tertinggi yang sudah tercapai (Dinamis Adaptif ATR)
        current_checkpoint = self.state.get_current_checkpoint() or 0
        highest_cp = self.get_highest_reached_checkpoint(profit_pct, symbol=symbol)
        
        if highest_cp > current_checkpoint:
            # Loncat langsung ke checkpoint tertinggi yang tercapai
            stop_profit_level = self.get_stop_level_for_checkpoint(highest_cp, symbol=symbol)
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
        
        # 4. Time-Progressive BEP Lock (OPSI A: SATPAM KOIN LEMOT)
        # Filosofi Opsi A:
        # - Jika koin sudah tembus Checkpoint 1 (>= +1.5%), Trailing Harga & TP Parsial yang mengawal penuh.
        # - Trailing Waktu HANYA MENGAWAL koin yang sudah berjalan lama (>= 120m / 2 jam) dan profitnya loyo (< 1.2%),
        #   memasang stop di BEP murni (+0.18% cover fee) agar modal tidak tersandera koin lelet selamanya.
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
                first_cp = getattr(config, "TRAILING_FIRST_CHECKPOINT_PERCENT", 1.5)
                
                # Jika koin sudah tembus checkpoint 1 (+1.5%), jangan ganggu dengan stop waktu!
                if eff_profit < first_cp:
                    req_minutes = getattr(config, "TIME_PROGRESSIVE_MINUTES", 120)
                    stagnant_max = getattr(config, "TIME_PROGRESSIVE_STAGNANT_MAX_PROFIT", 1.2)
                    
                    if elapsed_minutes >= req_minutes and eff_profit <= stagnant_max and eff_profit >= 0.2:
                        bep_stop_pct = getattr(config, "TIME_PROGRESSIVE_BEP_STOP", 0.18)
                        target_stop_price = self.calculate_stop_price(entry_price, bep_stop_pct, side)
                        
                        # Buffer napas minimal 1.0% dari live price
                        min_buffer_pct = getattr(config, "TIME_PROGRESSIVE_MIN_BREATHING_ROOM_PERCENT", 1.0)
                        if side == "long":
                            max_allowed_stop = current_price * (1.0 - min_buffer_pct / 100.0)
                            target_stop_price = min(target_stop_price, max_allowed_stop)
                            if target_stop_price <= entry_price:
                                target_stop_price = entry_price * 1.0018
                        else:
                            min_allowed_stop = current_price * (1.0 + min_buffer_pct / 100.0)
                            target_stop_price = max(target_stop_price, min_allowed_stop)
                            if target_stop_price >= entry_price:
                                target_stop_price = entry_price * 0.9982
                        
                        # Validasi ke bursa
                        is_stop_valid = (side == "long" and target_stop_price < current_price and target_stop_price > entry_price) or \
                                        (side == "short" and target_stop_price > current_price and target_stop_price < entry_price)
                        
                        if is_stop_valid:
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
                                    f"⏰ TIME-PROGRESSIVE BEP LOCK (OPSI A: SATPAM KOIN LEMOT)! "
                                    f"Trade age: {elapsed_minutes:.1f}m >= {req_minutes}m | "
                                    f"Profit loyo: +{eff_profit:.2f}% | "
                                    f"Locking BEP Stop @ {target_stop_price} (+{bep_stop_pct}%)"
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
                                    self.state.set_trailing_stop(
                                        stop_order_id=stop_order["id"],
                                        stop_price=target_stop_price,
                                        checkpoint_level=0.5,
                                    )
                                    result["action"] = "progressive_lock"
                                    result["checkpoint"] = 0.5
                                    result["stop_price"] = target_stop_price
                                    logger.info(
                                        f"  ✅ BEP STOP RATIFIED (SATPAM KOIN LEMOT): Stop locked @ {target_stop_price} (+{bep_stop_pct}%)"
                                    )
                                    return result
                                else:
                                    logger.error("  ❌ Gagal pasang progressive stop order!")

        # 4b. BTCDOM-Adaptive BEP Lock (Pengaman Angin Sakal Likuiditas)
        # Filosofi:
        # - Jika posisi sudah cuan minimal DOM_MIN_PROFIT_TRIGGER (>= +0.80%), dan
        # - Terdeteksi lonjakan BTCDOM melawan arah posisi kita (Long: DOM naik >= 0.15% | Short: DOM turun <= -0.15%),
        # - Bot otomatis memajukan stop ke BEP (+0.18%) detik itu juga agar modal & profit aman dari pembalikan likuiditas!
        if getattr(config, "DOM_ADAPTIVE_LOCK_ENABLED", True) and not pos.get("dom_adaptive_locked", False):
            eff_profit = max(pos.get("highest_profit_pct", 0.0), profit_pct)
            min_trigger = getattr(config, "DOM_MIN_PROFIT_TRIGGER", 0.80)
            first_cp = getattr(config, "TRAILING_FIRST_CHECKPOINT_PERCENT", 1.5)
            
            # Hanya aktif jika sudah cuan >= 0.8% dan belum tembus checkpoint 1 (+1.5%)
            if eff_profit >= min_trigger and eff_profit < first_cp:
                dom_chg = self._get_btcdom_momentum()
                threshold = getattr(config, "DOM_SHOCK_THRESHOLD_PERCENT", 0.15)
                
                # Cek apakah arah DOM adalah "Angin Sakal" (melawan posisi kita)
                is_adverse_dom = False
                if side == "long" and dom_chg >= threshold:
                    is_adverse_dom = True
                elif side == "short" and dom_chg <= -threshold:
                    is_adverse_dom = True
                    
                if is_adverse_dom:
                    bep_pct = getattr(config, "DOM_BEP_STOP_PERCENT", 0.18)
                    target_stop_price = self.calculate_stop_price(entry_price, bep_pct, side)
                    
                    # Validasi stop price
                    is_stop_valid = (side == "long" and target_stop_price < current_price and target_stop_price > entry_price) or \
                                    (side == "short" and target_stop_price > current_price and target_stop_price < entry_price)
                                    
                    if is_stop_valid:
                        # Cek apakah stop baru ini lebih baik dari stop yang aktif
                        should_replace = True
                        if old_stop and old_stop.get("stop_price"):
                            old_sp = old_stop["stop_price"]
                            if side == "long" and old_sp >= target_stop_price:
                                should_replace = False
                            elif side == "short" and old_sp <= target_stop_price:
                                should_replace = False
                                
                        if should_replace:
                            if old_stop and old_stop.get("order_id"):
                                cancel_res = self.order_mgr.cancel_stop_order(symbol, old_stop["order_id"])
                                if cancel_res == "triggered":
                                    logger.warning("⚠️ Old stop already triggered during DOM lock!")
                                    result["action"] = "stop_triggered"
                                    return result
                                
                            new_stop = self.order_mgr.place_stop_order(
                                symbol=symbol,
                                side=side,
                                amount=amount,
                                stop_price=target_stop_price
                            )
                            if new_stop:
                                self.state.set_trailing_stop(
                                    stop_order_id=new_stop["id"],
                                    stop_price=target_stop_price,
                                    checkpoint_level=0.5
                                )
                                pos["dom_adaptive_locked"] = True
                                self.state.save()
                                logger.info(
                                    f"🌊 BTCDOM SHOCK DETECTED ({dom_chg:+.2f}%)! "
                                    f"Posisi {side.upper()} {symbol} (Profit: +{profit_pct:.2f}%) "
                                    f"diamankan ke BEP @ {target_stop_price} (+{bep_pct}%). "
                                    f"Modal terlindungi dari pembalikan likuiditas!"
                                )
                                result["action"] = "dom_bep_locked"
                                result["checkpoint"] = 0.5
                                result["stop_price"] = target_stop_price
                                return result

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
                    
                    # VALIDASI KE BURSA: Stop order HARUS di bawah harga live (untuk LONG) atau di atas harga live (untuk SHORT)
                    is_bep_valid = (side == "long" and bep_stop_price < current_price) or (side == "short" and bep_stop_price > current_price)
                    
                    if is_bep_valid:
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

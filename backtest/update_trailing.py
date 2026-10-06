import os

path = '/Users/macpro/Documents/Aplikasiku/Binance Bot/trailing_manager.py'
with open(path, 'r') as f:
    c = f.read()

target = """        # 2b. CHOPPY AUTO-BEP LOCK (Logika Cerdas User: Jika Choppy & Sempat Cuan >= +0.55%, Otomatis Gembok BEP)
        if getattr(config, "CHOPPY_AUTO_BEP_ENABLED", True):
            adx_info = self._get_symbol_adx_info(symbol)
            is_adx_choppy = adx_info.get("is_choppy", False)
            
            p_di = adx_info.get("plus_di", 20.0)
            m_di = adx_info.get("minus_di", 20.0)
            if side == "long":
                di_misaligned = (m_di > p_di * 1.15)
            else:
                di_misaligned = (p_di > m_di * 1.15)
                
            is_choppy_regime = is_adx_choppy or di_misaligned
            bep_trigger = getattr(config, "CHOPPY_BEP_TRIGGER_PERCENT", 0.55)
            bep_lock = getattr(config, "CHOPPY_BEP_LOCK_PERCENT", 0.12)
            
            if is_choppy_regime and profit_pct >= bep_trigger and not pos.get("choppy_bep_locked", False):
                current_cp = self.state.get_current_checkpoint()
                if current_cp is None or current_cp < bep_trigger:
                    bep_stop_price = self.calculate_stop_price(entry_price, bep_lock, side)
                    if old_stop and old_stop.get("order_id"):
                        self.order_mgr.cancel_stop_order(symbol, old_stop["order_id"])
                        
                    new_stop = self.order_mgr.place_stop_order(
                        symbol=symbol,
                        side=side,
                        amount=pos.get("amount", amount),
                        stop_price=bep_stop_price
                    )
                    if new_stop:
                        self.state.set_trailing_stop(
                            stop_order_id=new_stop["id"],
                            stop_price=bep_stop_price,
                            checkpoint_level=bep_trigger
                        )
                        pos["choppy_bep_locked"] = True
                        self.state.save()
                        logger.info(
                            f"🛡️ CHOPPY AUTO-BEP ACTIVATED for {symbol}! "
                            f"Profit: +{profit_pct:.2f}% >= +{bep_trigger}% | ADX: {adx_info['adx']:.1f} (+DI: {p_di:.1f}, -DI: {m_di:.1f}) | "
                            f"Physical Stop Locked @ {bep_stop_price} (+{bep_lock}%). MODAL 100% UTUH BEBAS RESIKO!"
                        )"""

replacement = """        # 2b. CHOPPY STEPPED RATCHET & TEBAS CUAN (Logika Cerdas Disiplin User)
        # Jika koin dalam mode Choppy (ADX < 22 atau DI misaligned):
        # Selama Target Cuan Harian 10% Modal belum tercapai:
        # Kawal ketat mulai dari +0.50% dengan jarak 0.20%!
        # (Misal peak 0.60% -> kunci 0.40%, peak 0.80% -> kunci 0.60%, dst).
        # Binance physical stop order langsung digeser naik mengawal koin!
        if getattr(config, "CHOPPY_AUTO_BEP_ENABLED", True):
            adx_info = self._get_symbol_adx_info(symbol)
            is_adx_choppy = adx_info.get("is_choppy", False)
            
            p_di = adx_info.get("plus_di", 20.0)
            m_di = adx_info.get("minus_di", 20.0)
            if side == "long":
                di_misaligned = (m_di > p_di * 1.15)
            else:
                di_misaligned = (p_di > m_di * 1.15)
                
            is_choppy_regime = is_adx_choppy or di_misaligned
            
            if is_choppy_regime:
                # 1. Evaluasi Target Cuan Harian (Compounding Snowball)
                daily_pnl = self.state.get_daily_pnl()
                available_bal = self.order_mgr.get_available_balance()
                target_pct = getattr(config, "DAILY_TARGET_PROFIT_PERCENT", 10.0)
                daily_target_usd = available_bal * (target_pct / 100.0)
                
                # Mode kawal ketat aktif HANYA jika target harian belum tercapai
                if daily_pnl < daily_target_usd:
                    ratchet_trigger = getattr(config, "CHOPPY_RATCHET_TRIGGER_PERCENT", 0.50)
                    ratchet_trail = getattr(config, "CHOPPY_RATCHET_TRAIL_PERCENT", 0.20)
                    highest_p = max(pos.get("highest_profit_pct", 0.0), profit_pct)
                    
                    if highest_p >= ratchet_trigger:
                        # Kunci level stop di (highest_p - ratchet_trail), minimal cover fee di +0.12%
                        desired_lock_pct = round(max(0.12, highest_p - ratchet_trail), 2)
                        current_locked_pct = float(pos.get("choppy_ratchet_locked_pct", 0.0))
                        
                        # Kerek stop order naik jika level baru lebih tinggi minimal 0.04%
                        if desired_lock_pct > current_locked_pct + 0.04:
                            ratchet_stop_price = self.calculate_stop_price(entry_price, desired_lock_pct, side)
                            if old_stop and old_stop.get("order_id"):
                                self.order_mgr.cancel_stop_order(symbol, old_stop["order_id"])
                                
                            new_stop = self.order_mgr.place_stop_order(
                                symbol=symbol,
                                side=side,
                                amount=pos.get("amount", amount),
                                stop_price=ratchet_stop_price
                            )
                            if new_stop:
                                self.state.set_trailing_stop(
                                    stop_order_id=new_stop["id"],
                                    stop_price=ratchet_stop_price,
                                    checkpoint_level=desired_lock_pct
                                )
                                pos["choppy_ratchet_locked_pct"] = desired_lock_pct
                                pos["choppy_bep_locked"] = True
                                self.state.save()
                                logger.info(
                                    f"🪜 CHOPPY STEPPED RATCHET LOCKED for {symbol}! "
                                    f"Peak: +{highest_p:.2f}% (trailed -{ratchet_trail:.2f}%) ➔ Stop Locked @ {ratchet_stop_price} (+{desired_lock_pct}%). "
                                    f"Target Harian: ${daily_pnl:.2f}/${daily_target_usd:.2f} USDT!"
                                )

                # 2. Pengaman BEP Dasar (jika belum kena ratchet tapi sudah >= bep_trigger)
                bep_trigger = getattr(config, "CHOPPY_BEP_TRIGGER_PERCENT", 0.55)
                bep_lock = getattr(config, "CHOPPY_BEP_LOCK_PERCENT", 0.12)
                if profit_pct >= bep_trigger and not pos.get("choppy_bep_locked", False):
                    current_cp = self.state.get_current_checkpoint()
                    if current_cp is None or current_cp < bep_trigger:
                        bep_stop_price = self.calculate_stop_price(entry_price, bep_lock, side)
                        if old_stop and old_stop.get("order_id"):
                            self.order_mgr.cancel_stop_order(symbol, old_stop["order_id"])
                            
                        new_stop = self.order_mgr.place_stop_order(
                            symbol=symbol,
                            side=side,
                            amount=pos.get("amount", amount),
                            stop_price=bep_stop_price
                        )
                        if new_stop:
                            self.state.set_trailing_stop(
                                stop_order_id=new_stop["id"],
                                stop_price=bep_stop_price,
                                checkpoint_level=bep_trigger
                            )
                            pos["choppy_bep_locked"] = True
                            self.state.save()
                            logger.info(
                                f"🛡️ CHOPPY AUTO-BEP ACTIVATED for {symbol}! "
                                f"Profit: +{profit_pct:.2f}% >= +{bep_trigger}% | ADX: {adx_info['adx']:.1f} | "
                                f"Physical Stop Locked @ {bep_stop_price} (+{bep_lock}%). MODAL 100% UTUH BEBAS RESIKO!"
                            )"""

if target in c:
    c = c.replace(target, replacement)
    with open(path, 'w') as f:
        f.write(c)
    print("SUCCESS updating trailing_manager.py")
else:
    print("Target not found!")

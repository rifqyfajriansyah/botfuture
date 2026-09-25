"""
State Manager
=============
Menyimpan dan memulihkan state bot ke/dari JSON file.
Memungkinkan recovery setelah restart tanpa kehilangan informasi posisi.
"""

import os
import json
import time
from datetime import datetime, timedelta
from logger_setup import logger
import config


class StateManager:
    """Mengelola state persistence bot ke file JSON."""
    
    def __init__(self, state_file=None):
        self.state_file = state_file or config.STATE_FILE
        self.state = self._load_state()
    
    def _default_state(self):
        """State default saat pertama kali dijalankan."""
        return {
            "bot_status": "idle",               # idle, scanning, trading, monitoring, cooldown
            "active_position": None,             # Info posisi aktif
            "pending_order": None,               # Info pending limit order
            "trailing_stop": None,               # Info trailing stop aktif
            "current_checkpoint": 0,             # Checkpoint trailing saat ini
            "last_signal": None,                 # Signal terakhir yang terdeteksi
            "last_scan_time": None,              # Waktu scan terakhir
            "trade_history": [],                 # Riwayat trade
            "total_trades": 0,
            "total_profit": 0.0,
            "consecutive_losses": 0,             # Jumlah loss beruntun
            "cooldown_until": 0,                 # Timestamp berakhirnya cooldown global
            "symbol_cooldowns": {},              # Timestamp cooldown per simbol {symbol: timestamp}
            "start_time": datetime.now().isoformat(),
        }
    
    def _load_state(self):
        """Load state dari file JSON."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)
                
                # Pastikan key baru ada (backward compatibility)
                default = self._default_state()
                for k, v in default.items():
                    if k not in state:
                        state[k] = v
                
                logger.info(f"📂 State loaded dari {self.state_file}")
                return state
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"⚠️ Gagal load state: {e}. Menggunakan default.")
        
        return self._default_state()
    
    def save(self):
        """Simpan state ke file JSON."""
        try:
            with open(self.state_file, "w") as f:
                json.dump(self.state, f, indent=2, default=str)
        except IOError as e:
            logger.error(f"❌ Gagal simpan state: {e}")
    
    # =========================================================================
    # Cooldown & Protection Management
    # =========================================================================
    
    def set_cooldown(self, symbol=None, minutes=None, reason="", sym_minutes=None, ignore_loss_multiplier=False):
        """
        Aktifkan cooldown global dan/atau per-symbol.
        
        Args:
            symbol: (Opsional) Symbol spesifik yang di-cooldown
            minutes: Durasi global dalam menit (default: config.SIGNAL_COOLDOWN_MINUTES)
            reason: Alasan cooldown
            sym_minutes: (Opsional) Durasi khusus symbol dalam menit (default: config.SYMBOL_COOLDOWN_MINUTES)
            ignore_loss_multiplier: Abaikan pengali consecutive loss (misal untuk timeout order biasa)
        """
        now = time.time()
        
        # Hitung durasi cooldown global (cek consecutive loss)
        losses = self.state.get("consecutive_losses", 0)
        base_minutes = minutes if minutes is not None else config.SIGNAL_COOLDOWN_MINUTES
        fixed_cooldown = getattr(config, "FIXED_COOLDOWN_ENABLED", False)
        
        if fixed_cooldown or ignore_loss_multiplier:
            actual_minutes = base_minutes
        elif losses >= config.MAX_CONSECUTIVE_LOSSES:
            actual_minutes = getattr(config, "CONSECUTIVE_LOSS_PAUSE_MINUTES", 120)
            logger.warning(
                f"🛑 Max Consecutive Losses ({losses}) tercapai! "
                f"Cooldown panjang diaktifkan: {actual_minutes} menit sebelum auto-resume."
            )
        elif losses >= config.DOUBLE_COOLDOWN_AFTER_LOSSES:
            actual_minutes = base_minutes * 2
            logger.warning(
                f"⚠️ Consecutive losses = {losses}! "
                f"Double cooldown diaktifkan: {actual_minutes} menit."
            )
        else:
            actual_minutes = base_minutes
            
        expire_time = now + (actual_minutes * 60)
        self.state["cooldown_until"] = expire_time
        
        # Set cooldown spesifik symbol jika ada
        if symbol:
            actual_sym_minutes = sym_minutes if sym_minutes is not None else getattr(config, "SYMBOL_COOLDOWN_MINUTES", 60)
            self.state["symbol_cooldowns"][symbol] = now + (actual_sym_minutes * 60)
            logger.info(
                f"⏳ Cooldown {symbol} aktif selama {actual_sym_minutes}m. Reason: {reason}"
            )
            
        logger.info(
            f"⏳ Global cooldown aktif selama {actual_minutes}m "
            f"(hingga {datetime.fromtimestamp(expire_time).strftime('%H:%M:%S')}). Reason: {reason}"
        )
        self.save()

    def is_cooldown_active(self, symbol=None):
        """
        Cek apakah saat ini sedang dalam masa cooldown.
        
        Returns:
            tuple: (is_active: bool, remaining_seconds: float, reason: str)
        """
        now = time.time()
        
        # 1. Cek Global Cooldown (termasuk pause 2 jam losestreak)
        global_until = self.state.get("cooldown_until", 0)
        if now < global_until:
            rem = global_until - now
            losses = self.state.get("consecutive_losses", 0)
            if losses >= config.MAX_CONSECUTIVE_LOSSES:
                return True, rem, f"Losestreak pause ({int(rem/60)}m tersisa dari 2 jam)"
            return True, rem, f"Global cooldown ({int(rem)}s tersisa)"
        else:
            # Jika masa cooldown 2 jam sudah lewat, auto-reset consecutive losses
            if self.state.get("consecutive_losses", 0) >= config.MAX_CONSECUTIVE_LOSSES:
                logger.info("🔄 Cooldown losestreak 2 jam selesai. Auto-reset consecutive losses ke 0.")
                self.state["consecutive_losses"] = 0
                self.save()
            
        # 2. Cek Symbol Cooldown
        if symbol:
            sym_until = self.state.get("symbol_cooldowns", {}).get(symbol, 0)
            if now < sym_until:
                rem = sym_until - now
                return True, rem, f"Symbol cooldown untuk {symbol} ({int(rem)}s tersisa)"
                
        return False, 0, ""

    def reset_consecutive_losses(self):
        """Reset hitungan loss beruntun (misal setelah win atau manual reset)."""
        self.state["consecutive_losses"] = 0
        self.save()
        logger.info("🔄 Consecutive losses counter di-reset ke 0.")

    # =========================================================================
    # Position Management
    # =========================================================================
    
    def set_position(self, symbol, side, entry_price, amount, order_id):
        """Simpan info posisi aktif."""
        self.state["active_position"] = {
            "symbol": symbol,
            "side": side,                    # 'long' atau 'short'
            "entry_price": entry_price,
            "amount": amount,
            "order_id": order_id,
            "entry_time": datetime.now().isoformat(),
            "highest_profit_pct": 0.0,
        }
        self.state["bot_status"] = "monitoring"
        self.save()
        logger.info(f"📊 Position saved: {side.upper()} {symbol} @ {entry_price}")
    
    def clear_position(self, pnl=0.0, reason="", start_cooldown=True):
        """Hapus posisi aktif, catat ke history, dan update statistik."""
        pos = self.state["active_position"]
        symbol = pos["symbol"] if pos else None
        
        if pos:
            # Akumulasikan PnL dari Partial TP jika ada
            partial_pnl = float(pos.get("partial_realized_pnl", 0.0))
            total_pnl = round(pnl + partial_pnl, 4)
            
            trade_record = {
                **pos,
                "close_time": datetime.now().isoformat(),
                "final_leg_pnl": pnl,
                "partial_pnl": partial_pnl,
                "pnl": total_pnl,
                "close_reason": reason,
            }
            self.state["trade_history"].append(trade_record)
            self.state["total_trades"] += 1
            self.state["total_profit"] += total_pnl
            
            # Update consecutive losses
            if pnl < 0:
                self.state["consecutive_losses"] = self.state.get("consecutive_losses", 0) + 1
                logger.warning(
                    f"🔻 Trade Loss recorded: {pnl:.2f} USDT | "
                    f"Consecutive Losses: {self.state['consecutive_losses']}"
                )
            else:
                self.state["consecutive_losses"] = 0
                logger.info(f"✨ Trade Win/Breakeven recorded: {pnl:.2f} USDT")
        
        self.state["active_position"] = None
        self.state["trailing_stop"] = None
        self.state["current_checkpoint"] = 0
        self.state["bot_status"] = "idle"
        self.save()
        logger.info(f"🔄 Position cleared. Reason: {reason}, PnL: {pnl:+.2f} USDT")
        
        if start_cooldown:
            self.set_cooldown(symbol=symbol, reason=f"Position closed ({reason})")
    
    def get_position(self):
        """Ambil info posisi aktif."""
        return self.state["active_position"]
    
    def has_position(self):
        """Cek apakah ada posisi aktif."""
        return self.state["active_position"] is not None
    
    # =========================================================================
    # Pending Order Management
    # =========================================================================
    
    def set_pending_order(self, symbol, side, price, amount, order_id, timeout_minutes=None):
        """Simpan info pending limit order."""
        if timeout_minutes is None:
            timeout_minutes = config.ORDER_TIMEOUT_MINUTES

        self.state["pending_order"] = {
            "symbol": symbol,
            "side": side,
            "price": price,
            "amount": amount,
            "order_id": order_id,
            "placed_time": time.time(),
            "placed_time_str": datetime.now().isoformat(),
            "timeout_minutes": timeout_minutes,
        }
        self.state["bot_status"] = "waiting_fill"
        self.save()
        logger.info(
            f"📝 Pending order saved: {side.upper()} {symbol} @ {price} "
            f"(Timeout: {timeout_minutes}m)"
        )
    
    def clear_pending_order(self, start_cooldown=False, symbol=None):
        """Hapus pending order."""
        self.state["pending_order"] = None
        self.state["bot_status"] = "idle"
        self.save()
        if start_cooldown:
            # Cooldown ringan jika order timeout/cancel (hanya jeda singkat sebelum scan koin lain)
            timeout_cooldown = getattr(config, "TIMEOUT_COOLDOWN_MINUTES", 1)
            timeout_sym_cooldown = getattr(config, "TIMEOUT_SYMBOL_COOLDOWN_MINUTES", 15)
            self.set_cooldown(
                symbol=symbol,
                minutes=timeout_cooldown,
                sym_minutes=timeout_sym_cooldown,
                reason="Pending order cancelled/timeout",
                ignore_loss_multiplier=True
            )
    
    def get_pending_order(self):
        """Ambil info pending order."""
        return self.state["pending_order"]
    
    def has_pending_order(self):
        """Cek apakah ada pending order."""
        return self.state["pending_order"] is not None
    
    def is_order_expired(self):
        """Cek apakah pending order sudah expired (timeout)."""
        order = self.state["pending_order"]
        if not order:
            return False
        timeout_min = order.get("timeout_minutes", config.ORDER_TIMEOUT_MINUTES)
        elapsed = time.time() - order["placed_time"]
        return elapsed > (timeout_min * 60)
    
    # =========================================================================
    # Trailing Stop Management
    # =========================================================================
    
    def set_trailing_stop(self, stop_order_id, stop_price, checkpoint_level):
        """Simpan info trailing stop aktif."""
        self.state["trailing_stop"] = {
            "order_id": stop_order_id,
            "stop_price": stop_price,
            "checkpoint_level": checkpoint_level,
            "set_time": datetime.now().isoformat(),
        }
        self.state["current_checkpoint"] = checkpoint_level
        self.save()
        logger.info(
            f"🛡️ Trailing stop saved: checkpoint {checkpoint_level}%, "
            f"stop @ {stop_price}"
        )
    
    def get_trailing_stop(self):
        """Ambil info trailing stop aktif."""
        return self.state["trailing_stop"]
    
    def get_current_checkpoint(self):
        """Ambil level checkpoint saat ini."""
        return self.state["current_checkpoint"]
    
    # =========================================================================
    # Signal & Misc
    # =========================================================================
    
    def set_last_signal(self, signal_data):
        """Simpan signal terakhir."""
        self.state["last_signal"] = {
            **signal_data,
            "time": datetime.now().isoformat(),
        }
        self.save()
    
    def set_status(self, status):
        """Update status bot."""
        self.state["bot_status"] = status
        self.save()
    
    def get_state(self):
        """Ambil seluruh state (untuk dashboard)."""
        return self.state.copy()
    
    def update_highest_profit(self, profit_pct):
        """Update highest profit yang pernah dicapai posisi ini."""
        pos = self.state["active_position"]
        if pos and profit_pct > pos.get("highest_profit_pct", 0):
            pos["highest_profit_pct"] = profit_pct
            self.save()

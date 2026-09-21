"""
Logger Setup
============
Konfigurasi logging untuk bot - file + console output.
"""

import os
import logging
from datetime import datetime
import config


def setup_logger(name="BinanceBot"):
    """Setup logger dengan file handler dan console handler."""
    
    # Buat directory logs jika belum ada
    os.makedirs(config.LOG_DIR, exist_ok=True)
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, config.LOG_LEVEL, logging.INFO))
    
    # Hindari duplicate handlers
    if logger.handlers:
        return logger
    
    # Format
    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)
    
    # File handler - general log
    today = datetime.now().strftime("%Y-%m-%d")
    file_handler = logging.FileHandler(
        os.path.join(config.LOG_DIR, f"bot_{today}.log"),
        encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    
    # File handler - trade log (hanya INFO+)
    trade_handler = logging.FileHandler(
        os.path.join(config.LOG_DIR, f"trades_{today}.log"),
        encoding="utf-8"
    )
    trade_handler.setFormatter(fmt)
    trade_handler.setLevel(logging.INFO)
    trade_handler.addFilter(TradeFilter())
    logger.addHandler(trade_handler)
    
    return logger


class TradeFilter(logging.Filter):
    """Filter untuk hanya log pesan yang berhubungan dengan trade."""
    
    TRADE_KEYWORDS = [
        "ORDER", "TRADE", "POSITION", "TRAILING", "STOP",
        "SIGNAL", "ENTRY", "EXIT", "CLOSE", "CANCEL",
        "PROFIT", "LOSS", "PNL", "REVERSAL", "FILL"
    ]
    
    def filter(self, record):
        msg = record.getMessage().upper()
        return any(kw in msg for kw in self.TRADE_KEYWORDS)


# Global logger instance
logger = setup_logger()

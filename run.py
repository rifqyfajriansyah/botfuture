"""
Binance Futures Trading Bot - Entry Point
==========================================
Jalankan file ini untuk memulai bot.

Usage:
    python run.py              # Jalankan bot saja
    python run.py --dashboard  # Jalankan bot + dashboard
    python run.py --dash-only  # Jalankan dashboard saja
"""

import sys
import threading
from bot import TradingBot
from dashboard import run_dashboard
from logger_setup import logger


def main():
    args = sys.argv[1:]
    
    if "--dash-only" in args:
        # Jalankan dashboard saja
        logger.info("🌐 Starting dashboard only mode...")
        run_dashboard()
    
    elif "--dashboard" in args:
        # Jalankan bot + dashboard di thread terpisah
        logger.info("🚀 Starting bot + dashboard...")
        
        # Dashboard di background thread
        dash_thread = threading.Thread(target=run_dashboard, daemon=True)
        dash_thread.start()
        
        # Bot di main thread
        bot = TradingBot()
        bot.run()
    
    else:
        # Jalankan bot saja
        bot = TradingBot()
        bot.run()


if __name__ == "__main__":
    main()

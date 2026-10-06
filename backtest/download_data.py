import os
import sys
import time
from datetime import datetime, timedelta
import ccxt
import pandas as pd

# Setup paths
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Initialize Binance Futures public exchange
exchange = ccxt.binance({
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

def get_top_120_symbols():
    print("🔍 Mengambil daftar Top 120 Koin Futures berdasarkan Volume 24 Jam...")
    tickers = exchange.fetch_tickers()
    usdt_futures = []
    
    for symbol, ticker in tickers.items():
        if symbol.endswith("/USDT:USDT") or symbol.endswith("/USDT"):
            quote_vol = ticker.get('quoteVolume') or 0.0
            usdt_futures.append((symbol, quote_vol))
            
    # Sort descending by quote volume
    usdt_futures.sort(key=lambda x: x[1], reverse=True)
    
    top_symbols = [x[0] for x in usdt_futures[:120]]
    if "BTC/USDT:USDT" not in top_symbols and "BTC/USDT" not in top_symbols:
        top_symbols.insert(0, "BTC/USDT:USDT")
        
    print(f"✅ Berhasil memilih {len(top_symbols)} koin futures teratas!")
    return top_symbols

def download_ohlcv_range(symbol, timeframe, days=90):
    clean_sym = symbol.replace("/", "_").replace(":", "_")
    csv_file = os.path.join(DATA_DIR, f"{clean_sym}_{timeframe}.csv")
    
    # Check if already downloaded
    if os.path.exists(csv_file):
        try:
            df_existing = pd.read_csv(csv_file)
            if len(df_existing) >= (days * 24 * (4 if timeframe == "15m" else 1) * 0.85):
                return True
        except Exception:
            pass

    since_dt = datetime.now() - timedelta(days=days)
    since_ms = int(since_dt.timestamp() * 1000)
    now_ms = int(datetime.now().timestamp() * 1000)
    
    all_candles = []
    curr_since = since_ms
    
    while curr_since < now_ms:
        try:
            candles = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=curr_since, limit=1000)
            if not candles:
                break
            all_candles.extend(candles)
            last_ts = candles[-1][0]
            if last_ts <= curr_since:
                break
            curr_since = last_ts + 1
            if len(candles) < 1000:
                break
            time.sleep(0.08) # Respect rate limits smoothly
        except Exception as e:
            # If coin is newer or rate limit hit, handle gracefully
            time.sleep(1.0)
            break
            
    if not all_candles:
        return False
        
    df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df.drop_duplicates(subset=['timestamp'], inplace=True)
    df.sort_values('timestamp', inplace=True)
    df.to_csv(csv_file, index=False)
    return True

def main():
    days = 90
    print(f"🚀 MEMULAI DOWNLOAD DATA HISTORIS {days} HARI (Juli - Oktober 2026)")
    print("💡 Download berjalan 100% lokal di Mac, TANPA membebani VPS!")
    symbols = get_top_120_symbols()
    
    total = len(symbols)
    success_15m = 0
    success_1h = 0
    
    start_t = time.time()
    for idx, sym in enumerate(symbols, 1):
        clean_sym = sym.split(":")[0]
        # Download 15m
        ok_15m = download_ohlcv_range(sym, "15m", days=days)
        if ok_15m:
            success_15m += 1
            
        # Download 1h
        ok_1h = download_ohlcv_range(sym, "1h", days=days)
        if ok_1h:
            success_1h += 1
            
        pct = (idx / total) * 100
        print(f"[{idx:3d}/{total:3d}] ({pct:5.1f}%) {clean_sym:12} -> 15m: {'✅' if ok_15m else '❌'} | 1h: {'✅' if ok_1h else '❌'}")
        
    duration = time.time() - start_t
    print("\n" + "=" * 60)
    print(f"🎉 SELESAI DALAM {duration:.1f} DETIK!")
    print(f"Total koin terdownload: 15m ({success_15m}/{total}) | 1h ({success_1h}/{total})")
    print(f"Semua file tersimpan rapi di: {DATA_DIR}")
    print("=" * 60)

if __name__ == "__main__":
    main()

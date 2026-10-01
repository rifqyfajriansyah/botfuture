"""
Market Scanner
==============
Mencari koin-koin dengan trend terbaik dari Binance Futures.
Multi-layer filtering: volume → volatilitas → spread → blacklist.
"""

import time
import urllib.request
import json
import ccxt
import config
from logger_setup import logger


class MarketScanner:
    """Scanner pasar untuk menemukan koin trending."""
    
    def __init__(self, exchange):
        self.exchange = exchange
        self._monitoring_coins_cache = set()
        self._last_monitoring_fetch = 0
    
    def _get_binance_monitoring_coins(self) -> set:
        """
        Ambil daftar koin berstatus 'Monitoring' (Tag Pemantauan / Isu Delisting)
        langsung dari asset service resmi Binance. Cache selama 4 jam.
        """
        now = time.time()
        if self._monitoring_coins_cache and (now - self._last_monitoring_fetch < 14400):
            return self._monitoring_coins_cache
            
        try:
            req = urllib.request.Request(
                "https://www.binance.com/bapi/asset/v2/public/asset-service/product/get-products?includeEtf=false",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())["data"]
            monitoring = set()
            for item in data:
                if "Monitoring" in item.get("tags", []):
                    b = item.get("b")
                    if b:
                        monitoring.add(b.upper())
            if monitoring:
                self._monitoring_coins_cache = monitoring
                self._last_monitoring_fetch = now
                logger.info(f"🛡️ Binance Monitoring Tag updated: {len(monitoring)} koin berisiko delisting diblokir otomatis.")
                return self._monitoring_coins_cache
        except Exception as e:
            logger.warning(f"⚠️ Gagal fetch Binance monitoring tags: {e}. Menggunakan fallback cache.")
            
        return self._monitoring_coins_cache

    def scan(self):
        """
        Scan market dan return list koin terbaik untuk trading.
        
        Returns:
            list[dict]: List koin yang lolos filter, sorted by score.
        """
        logger.debug("🔍 Scanning market untuk koin trending...")
        
        try:
            # Dapatkan list koin yang diawasi delisting oleh Binance
            monitoring_delist_coins = self._get_binance_monitoring_coins()
            
            # Layer 1: Ambil semua USDT perpetual futures yang aktif & aman dari delisting
            markets = self.exchange.load_markets()
            usdt_perps = []
            for s, m in markets.items():
                if not s.endswith(":USDT") or m.get("type") != "swap":
                    continue
                if m.get("active") is not True:
                    continue
                
                info = m.get("info", {})
                # Filter 1: Cek status trading (blokir SETTLING, PENDING_TRADING)
                if info.get("status") != "TRADING":
                    continue
                
                # Filter 2: Cek tanggal settlement delisting
                delivery_date = int(info.get("deliveryDate", 4133404800000))
                if delivery_date < 4100000000000:
                    continue
                    
                # Filter 3: Blokir semua saham TradFi, Equity, Pre-market perps (AAOI, SOXS, ARM, DELL, dll)
                c_type = str(info.get("contractType", "")).upper()
                u_type = str(info.get("underlyingType", "")).upper()
                u_sub = str(info.get("underlyingSubType", []))
                if "TRADIFI" in c_type or "EQUITY" in u_type or "TRADFI" in u_sub.upper() or "PREMARKET" in u_type:
                    continue
                    
                usdt_perps.append(s)
            
            # Layer 2: Fetch tickers dan filter by volume
            tickers = self.exchange.fetch_tickers(usdt_perps)
            
            sorted_tickers = sorted(
                tickers.values(),
                key=lambda t: t.get("quoteVolume") or 0,
                reverse=True
            )
            
            top_tickers = sorted_tickers[:config.SCANNER_TOP_N]
            
            # Layer 3: Multi-filter
            candidates = []
            
            for ticker in top_tickers:
                symbol = ticker["symbol"]
                base_symbol = symbol.replace(":USDT", "").split("/")[0].upper()
                
                # Skip blacklisted coins
                if base_symbol in config.BLACKLIST_COINS:
                    continue
                
                # Skip koin dengan Monitoring Tag (Isu / Risiko Delisting Binance)
                if base_symbol in monitoring_delist_coins:
                    logger.debug(f"⚠️ Skip {symbol}: Koin memiliki Monitoring Tag (Risiko Delisting Binance)")
                    continue
                
                # Filter: minimum price change 24h (volatilitas)
                change_pct = abs(ticker.get("percentage") or 0)
                if change_pct < config.MIN_24H_CHANGE_PERCENT:
                    continue
                
                # Filter: spread check
                bid = ticker.get("bid") or 0
                ask = ticker.get("ask") or 0
                spread_pct = 0
                if bid > 0 and ask > 0:
                    spread_pct = ((ask - bid) / bid) * 100
                    if spread_pct > config.MAX_SPREAD_PERCENT:
                        continue
                
                # Hitung skor berdasarkan kombinasi volume & volatilitas
                volume_score = min(ticker.get("quoteVolume", 0) / 1e9, 1.0) * 50
                volatility_score = min(change_pct / 10.0, 1.0) * 30
                spread_score = 20 if spread_pct == 0 else max(0, (config.MAX_SPREAD_PERCENT - spread_pct) / config.MAX_SPREAD_PERCENT) * 20
                
                total_score = volume_score + volatility_score + spread_score
                
                candidates.append({
                    "symbol": symbol,
                    "price": ticker.get("last", 0),
                    "quote_volume": ticker.get("quoteVolume", 0),
                    "change_24h": ticker.get("percentage", 0),
                    "spread_pct": round(spread_pct, 4),
                    "bid": bid,
                    "ask": ask,
                    "scan_score": round(total_score, 2),
                })
            
            candidates.sort(key=lambda x: x["scan_score"], reverse=True)
            logger.debug(f"Scan selesai: {len(candidates)} koin lolos filter.")
            return candidates
            
        except Exception as e:
            logger.error(f"❌ Error scanning market: {e}")
            return []

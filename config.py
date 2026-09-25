"""
Binance Futures Trading Bot - Configuration
============================================
Semua konfigurasi utama bot ada di sini.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# API CONFIGURATION
# =============================================================================
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
TRADING_MODE = os.getenv("TRADING_MODE", "testnet")  # 'live' atau 'testnet'

# =============================================================================
# TRADING PARAMETERS
# =============================================================================
LEVERAGE = 3                    # Leverage 3x
MARGIN_MODE = "isolated"        # Isolated margin (lebih aman per posisi)
BALANCE_USAGE = 0.90            # Gunakan 90% balance (maksimalisasi profit dengan entry terfilter ketat)
MAX_POSITIONS = 1               # Hanya 1 posisi aktif
MIN_WALLET_BALANCE_USDT = 5.0   # Saldo minimum untuk bot mulai trading

# =============================================================================
# COOLDOWN & ANTI-REENTRY SETTINGS
# =============================================================================
SIGNAL_COOLDOWN_MINUTES = 5             # Cooldown global 5 menit setelah trade selesai (cepat siap cari peluang baru)
FIXED_COOLDOWN_ENABLED = True           # Kalah maupun menang delay tetap fixed 5 menit (tidak ada penalti jeda lama)
SYMBOL_COOLDOWN_MINUTES = 60            # Cooldown khusus koin yang sama jika trade selesai (60 menit anti-revenge koin serupa)
TIMEOUT_COOLDOWN_MINUTES = 1            # Cooldown global jika limit order cancel/timeout (hanya 1m sebelum scan koin lain)
TIMEOUT_SYMBOL_COOLDOWN_MINUTES = 15     # Cooldown khusus simbol jika limit order cancel/timeout (hanya 15m / 1 candle)
MAX_CONSECUTIVE_LOSSES = 5              # Cadangan safety threshold
DOUBLE_COOLDOWN_AFTER_LOSSES = 5
CONSECUTIVE_LOSS_PAUSE_MINUTES = 60

# =============================================================================
# ENTRY RISK GATEKEEPER (Anti-Pucuk & Filter Kualitas Sinyal)
# =============================================================================
MIN_ENTRY_REJECTION_WICK_PERCENT = 22.0     # Wajib ada jarum penolakan minimal 22% (momentum kuat seringkali wick 20-25%)
MAX_ENTRY_RISK_EMA55_PERCENT = 1.35         # Maksimal jarak harga entry ke support EMA 55 hanya 1.35% (anti resiko tebal)
ANTI_CLIMAX_LOOKBACK_CANDLES = 8            # Pantau 8 candle terakhir (2 jam)
ANTI_CLIMAX_MAX_RSI = 70.0                  # Dilarang masuk LONG jika dalam 2 jam terakhir baru saja overbought > 70
ANTI_CLIMAX_MIN_RSI = 30.0                  # Dilarang masuk SHORT jika dalam 2 jam terakhir baru saja oversold < 30
BTC_FILTER_ENABLED = True                   # Pantau arah Bitcoin sebelum trading altcoin (anti-melawan induk pasar)
BTC_SYMBOL = "BTC/USDT"                     # Benchmark koin induk
BTC_FLASH_DUMP_THRESHOLD_PERCENT = 0.55     # BTC flash dump aktif jika lilin 15m drop >= -0.55% (nyata, bukan goyangan $200)
BTC_FLASH_LOCK_MINUTES = 15                 # Kunci proteksi flash dump/pump selama 15m (anti-whipsaw / kedipan micro)
BTC_FILTER_MODE = "smart"                   # 'smart': Izinkan altcoin kuat (HTF selaras) saat BTC tenang/sideways, blokir mutlak saat BTC flash dump/pump aktif
STRICT_HTF_REQUIRED = False                 # Izinkan koin decoupling yang punya tren 1H kuat
REVERSAL_SOLID_BREAKDOWN_PERCENT = 1.08      # Ruang napas normal 1.08% di bawah/atas EMA 55 (bukan 1.4% kegedean, non-round number)
REVERSAL_DUMP_FAST_CUT_THRESHOLD_PERCENT = 0.56 # Tebas instan saat BTC dump jika harga >= 0.56% di bawah EMA 55 (anti-kejilat goyangan 0.2%)
REVERSAL_EMA_BREAKDOWN_BUFFER_PERCENT = 0.58 # Toleransi candle closed wajib minimal 0.58% di bawah/atas EMA 55
REVERSAL_GRACE_PERIOD_MINUTES = 15          # Ruang napas 15 menit pertama (anti tebas lilin lampau sebelum entry)
REVERSAL_DUMP_FAST_CUT_ENABLED = True       # Jika di bawah EMA 55 >= 0.56% (LONG) dan terjadi BTC/Market dump, tebas instan!


# =============================================================================
# ORDER SETTINGS (TIERED HYBRID LIMIT ORDER)
# =============================================================================
# Level 1: Sinyal Kuat (High Conviction - Score >= 80)
HIGH_CONVICTION_SCORE = 80              # Ambang batas sinyal super kuat
HIGH_CONVICTION_OFFSET_PERCENT = 0.1    # Limit order sangat rapat (0.1%) agar cepat fill
HIGH_CONVICTION_TIMEOUT_MINUTES = 5     # Timeout 5 menit (cepat alihkan modal jika tidak dijemput)

# Level 2: Sinyal Standar (Normal Conviction - Score 70-79)
NORMAL_CONVICTION_OFFSET_PERCENT = 0.35 # Limit order tawar sehat (0.35%)
NORMAL_CONVICTION_TIMEOUT_MINUTES = 7   # Timeout 7 menit (tidak sandera modal lama-lama)

# Default fallback / backward compatibility
ENTRY_OFFSET_PERCENT = 0.35             # Default limit offset
ORDER_TIMEOUT_MINUTES = 7               # Default timeout 7 menit
ORDER_CHECK_INTERVAL = 10               # Cek order setiap 10 detik

# =============================================================================
# PRO TRAILING STOP & PARTIAL TAKE PROFIT (Realistic Cash Growth)
# =============================================================================
# Checkpoint 1: Profit +1.48% (ROE +4.4%) → Kunci stop di +0.72% (Garansi cuan ~$3.30 bersih)
# Checkpoint 2: Profit +1.90% (ROE +5.7%) → Geser stop ke +1.26% (Garansi cuan ~$5.80 bersih)
# Checkpoint 3: Profit +2.32% (ROE +7.0%) → Geser stop ke +1.68% (Garansi cuan ~$7.70 bersih)
# Checkpoint 4: Profit +2.74% (ROE +8.2%) → Geser stop ke +2.10% (Garansi cuan ~$9.65 bersih)
TRAILING_FIRST_CHECKPOINT_PERCENT = 1.48     # Checkpoint pertama di +1.48% (ROE +4.4% di 3x)
TRAILING_FIRST_STOP_PERCENT = 0.72           # Kunci profit bersih di +0.72% (+$3.30 USDT bersih)
TRAILING_CHECKPOINT_STEP = 0.42              # Step checkpoint berikutnya (+1.90%, +2.32%, +2.74%, dst)
TRAILING_STOP_OFFSET = 0.58                  # Jarak kawal stop 0.58% di bawah checkpoint (rapat & aman)

# PARTIAL TAKE PROFIT UTAMA (Target Dinaikkan ke +2.42%)
PARTIAL_TP_ENABLED = True                   # Aktifkan TP parsial 50%
PARTIAL_TP_PERCENT = 2.42                   # Target Utama di +2.42% (cuan ~$11.5 s/d ~$12 USDT sebelum tembok 2.50%)
PARTIAL_TP_RATIO = 0.5                      # Jual 50% muatan, sisa 50% dibiarkan berburu pucuk

# STALL GUARD (Deteksi Bensin Habis di Tengah Jalan)
STALL_GUARD_ENABLED = True                  # Aktifkan eksekusi partial TP jika bensin habis sebelum target utama 2.42%
STALL_GUARD_MIN_PROFIT_PERCENT = 1.26       # Aktif jika posisi sudah floating profit minimal +1.26%
STALL_GUARD_MAX_PROFIT_PERCENT = 2.38       # Beroperasi di rentang cuan sebelum target 2.42%
STALL_GUARD_PULLBACK_PERCENT = 0.42         # Bensin habis jika melorot >= 0.42% dari profit tertinggi (peak)
STALL_GUARD_WICK_PERCENT = 28.0             # Atau terbentuk jarum atas rejection wick >= 28% di lilin 15m

# =============================================================================
# TIME-PROGRESSIVE BEP (OPSI A: SATPAM KOIN LEMOT / SIDEWAYS)
# =============================================================================
# Filosofi Opsi A:
# - Koin yang lari kencang (>= +1.5%) TIDAK DIGANGGU oleh waktu, bebas berburu swing pucuk.
# - Trailing Waktu HANYA MENGAWAL koin loyo yang sudah jalan >= 2 jam (120m) dan profit < 1.2%,
#   dengan memasang stop di BEP murni (+0.18% cover fee) agar modal tidak tersandera selamanya.
TIME_PROGRESSIVE_LOCK_ENABLED = True
TIME_PROGRESSIVE_MINUTES = 120              # 2 Jam: waktu matang untuk mengecek koin loyo
TIME_PROGRESSIVE_STAGNANT_MAX_PROFIT = 1.2  # Koin yang stagnan/loyo di bawah +1.2%
TIME_PROGRESSIVE_MIN_BREATHING_ROOM_PERCENT = 1.0 # Buffer napas minimal 1.0% dari harga live

# =============================================================================
# BTCDOM-ADAPTIVE BEP & PROFIT LOCK (PENGAMAN ANGIN SAKAL LIKUIDITAS)
# =============================================================================
# Filosofi:
# - Saat likuiditas tenang, koin diberi ruang napas normal untuk mengejar TP besar (+1.5% s/d +2.0%+).
# - Jika posisi sudah cuan minimal DOM_MIN_PROFIT_TRIGGER (>= +0.80%), dan
# - Terdeteksi lonjakan BTCDOM melawan arah posisi (Angin Sakal >= 0.15% di 15m),
# - Bot otomatis memajukan stop ke BEP (+0.18%) detik itu juga agar modal & profit aman dari pembalikan likuiditas!
DOM_ADAPTIVE_LOCK_ENABLED = True           # Aktifkan Trailing BEP adaptif berbasis BTCDOM
DOM_SYMBOL = "BTCDOM/USDT"                  # Simbol kontrak dominansi di Binance Futures
DOM_MIN_PROFIT_TRIGGER = 0.80              # Minimal posisi sudah floating profit +0.80% untuk aktifkan radar DOM
DOM_SHOCK_THRESHOLD_PERCENT = 0.15          # Pergeseran DOM melawan posisi minimal 0.15% (15m momentum)
DOM_BEP_STOP_PERCENT = 0.18                 # Geser stop ke BEP +0.18% jika terdeteksi angin sakal DOM

# Backward compatibility & legacy time BEP
TIME_DELAYED_BEP_ENABLED = False            # Digantikan oleh Time-Progressive Opsi A yang lebih cerdas
TIME_DELAYED_BEP_MINUTES = 120
TIME_DELAYED_BEP_MIN_PROFIT_PERCENT = 0.8
TIME_DELAYED_BEP_STOP_PERCENT = 0.22

# Stagnation Force Close
STAGNATION_EXIT_ENABLED = False
MAX_STAGNANT_HOURS = 3.0
MAX_STAGNANT_MIN_PROFIT_PERCENT = 0.2

# =============================================================================
# DYNAMIC CONFLUENCE ENTRY (EMA 21 & ATR Pullback)
# =============================================================================
DYNAMIC_PULLBACK_ENTRY_ENABLED = True       # Entry di level support/resistance dinamis
ATR_PULLBACK_MULTIPLIER = 0.35              # Jarak pullback berbasis ATR (0.35x ATR)
ESTIMATED_ROUNDTRIP_FEE_PERCENT = 0.08      # Estimasi total fee round-trip Binance (Maker 0.02% + Taker 0.05% + buffer)

# Backward compatibility
TRAILING_CHECKPOINT_PERCENT = 2.0

# =============================================================================
# EMERGENCY STOP LOSS (Safety Net - Anti Likuidasi)
# =============================================================================
EMERGENCY_SL_ENABLED = True         # Safety net aktif (jauh agar tidak kejilat wick)
EMERGENCY_SL_PERCENT = 25.0         # Pasang di -25% (sebelum likuidasi leverage 3x ~33%)

# =============================================================================
# SIGNAL ENGINE SETTINGS (Institutional TPLR)
# =============================================================================
SIGNAL_MIN_SCORE = 70           # Skor minimum sinyal untuk entry (Grade A & A- masuk)

# EMA Parameters
EMA_FAST = 21
EMA_SLOW = 55
EMA_TREND = 200

# MACD Parameters
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# RSI Parameters
RSI_PERIOD = 14
RSI_OVERBOUGHT = 65
RSI_OVERSOLD = 35
RSI_REVERSAL_HIGH = 75
RSI_REVERSAL_LOW = 25

# ADX Parameters
ADX_PERIOD = 14
ADX_THRESHOLD = 25

# Volume
VOLUME_SMA_PERIOD = 20
MIN_VOLUME_RATIO = 0.8          # Minimal volume 0.8x dari average 20 SMA

# Timeframes & Confirmation
TRADING_TIMEFRAME = "15m"       # Timeframe utama (15m cepat & responsif)
HIGHER_TIMEFRAME = "1h"         # Timeframe konfirmasi trend makro (1h)
CANDLE_HISTORY_CONFIRMATION_COUNT = 3

# =============================================================================
# SCANNER SETTINGS
# =============================================================================
SCANNER_TOP_N = 80              # Scan top 80 koin berdasarkan volume (universe lebih luas ~45-50 koin aktif)
MIN_24H_CHANGE_PERCENT = 1.0    # Minimum perubahan harga 24h (absolute)
MAX_SPREAD_PERCENT = 0.05       # Maximum spread yang diperbolehkan

# Blacklist koin (stablecoins, TradFi perps, slow-moving heavyweights, low liquidity, dll)
BLACKLIST_COINS = [
    # Slow-moving Heavyweights (fokus ke altcoin yang lincah & berbobot volatilitas bagus)
    "BTC/USDT", "BTC",
    "ETH/USDT", "ETH",
    # Stablecoins
    "USDC/USDT", "BUSD/USDT", "TUSD/USDT", "DAI/USDT",
    "USDP/USDT", "FDUSD/USDT", "USDD/USDT",
    # TradFi Perpetuals (butuh agreement terpisah)
    "XAU/USDT", "XAU", "XAG/USDT", "XAG", "XPT/USDT", "XPT", "XPD/USDT", "XPD",
    "SAMSUNG/USDT", "SNDK/USDT", "CL/USDT", "SKHYNIX/USDT",
    "SOXL/USDT", "MU/USDT", "AKE/USDT", "MSTR/USDT",
    "AIN/USDT", "KORU/USDT", "SPCX/USDT",
    "SKHY/USDT", "SNXX/USDT", "POWER/USDT", "PONS/USDT",
    "CRCL/USDT", "BR/USDT", "BZ/USDT", "INTC/USDT",
    "NVDA/USDT", "TSLA/USDT", "AAPL/USDT", "MSFT/USDT",
    "AMD/USDT", "AMZN/USDT", "GOOG/USDT", "COIN/USDT",
    "PLTR/USDT", "BABA/USDT",
]

# =============================================================================
# SMART EXHAUSTION / CLIMAX EXIT (Puncak & Lembah Guard)
# =============================================================================
EXHAUSTION_EXIT_ENABLED = True             # Aktifkan deteksi titik pucuk / klimaks
EXHAUSTION_MIN_PROFIT_PERCENT = 1.8        # Minimal profit +1.8% (ROE ~5.4% di 3x | ~$8.1 USDT) untuk aktifkan radar pucuk jarum
EXHAUSTION_RSI_OVERBOUGHT = 73.0           # RSI overbought ekstrem untuk LONG
EXHAUSTION_RSI_OVERSOLD = 27.0             # RSI oversold ekstrem untuk SHORT
EXHAUSTION_WICK_PERCENT = 32.0             # Rejection wick minimal 32% (standar 1/3 candle)
EXHAUSTION_EMA_DIST_PERCENT = 2.0          # Jarak harga dari EMA 21 minimal 2.0% (overextended)
EXHAUSTION_PULLBACK_PERCENT = 0.4          # Penurunan dari high candle minimal 0.4% (tanda mulai melorot)
EXHAUSTION_VOLUME_RATIO = 1.8              # Volume minimal 1.8x dari SMA 20
EXHAUSTION_MIN_CONFLUENCE = 2              # Minimal 2 dari kriteria exhaustion terpenuhi

# =============================================================================
# REVERSAL GUARD
# =============================================================================
REVERSAL_CHECK_INTERVAL = 15    # Cek reversal & exhaustion setiap 15 detik (lebih responsif di pucuk)

# =============================================================================
# DASHBOARD
# =============================================================================
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "5000"))
DASHBOARD_HOST = "0.0.0.0"

# =============================================================================
# LOGGING
# =============================================================================
LOG_DIR = "logs"
LOG_LEVEL = "INFO"

# =============================================================================
# STATE PERSISTENCE
# =============================================================================
STATE_FILE = "bot_state.json"

# =============================================================================
# MAIN LOOP
# =============================================================================
MAIN_LOOP_INTERVAL = 10         # Sleep 10 detik antar iterasi
CANDLE_FETCH_LIMIT = 250        # Jumlah candle yang di-fetch untuk analisis

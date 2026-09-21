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
BALANCE_USAGE = 0.90            # Gunakan 90% balance (sisakan 10% buffer)
MAX_POSITIONS = 1               # Hanya 1 posisi aktif
MIN_WALLET_BALANCE_USDT = 5.0   # Saldo minimum untuk bot mulai trading

# =============================================================================
# COOLDOWN & ANTI-REENTRY SETTINGS
# =============================================================================
SIGNAL_COOLDOWN_MINUTES = 30            # Cooldown global 30 menit setelah trade selesai
SYMBOL_COOLDOWN_MINUTES = 60            # Cooldown khusus koin yang sama (60 menit)
TIMEOUT_COOLDOWN_MINUTES = 1            # Cooldown global jika limit order cancel/timeout (hanya 1m sebelum scan koin lain)
MAX_CONSECUTIVE_LOSSES = 3              # Max loss berturut-turut sebelum cooldown panjang
DOUBLE_COOLDOWN_AFTER_LOSSES = 2        # Double cooldown (60m) jika kena 2 loss berturut-turut
CONSECUTIVE_LOSS_PAUSE_MINUTES = 120    # Cooldown maksimal losestreak 2 jam (auto-resume setelah 2 jam)

# =============================================================================
# ORDER SETTINGS (TIERED HYBRID LIMIT ORDER)
# =============================================================================
# Level 1: Sinyal Kuat (High Conviction - Score >= 80)
HIGH_CONVICTION_SCORE = 80              # Ambang batas sinyal super kuat
HIGH_CONVICTION_OFFSET_PERCENT = 0.1    # Limit order sangat rapat (0.1%) agar cepat fill
HIGH_CONVICTION_TIMEOUT_MINUTES = 10    # Timeout 10 menit

# Level 2: Sinyal Standar (Normal Conviction - Score 70-79)
NORMAL_CONVICTION_OFFSET_PERCENT = 0.35 # Limit order tawar sehat (0.35%)
NORMAL_CONVICTION_TIMEOUT_MINUTES = 15  # Timeout 15 menit

# Default fallback / backward compatibility
ENTRY_OFFSET_PERCENT = 0.35             # Default limit offset
ORDER_TIMEOUT_MINUTES = 15              # Default timeout
ORDER_CHECK_INTERVAL = 10               # Cek order setiap 10 detik

# =============================================================================
# PRO TRAILING STOP CONFIGURATION (Sweet Spot Breathing Room Ratchet)
# =============================================================================
# Checkpoint 1: Profit +2.0% (ROE +6%) → Kunci BEP di +0.3% (Ruang napas 1.7% anti-kejilat)
# Checkpoint 2: Profit +3.5% (ROE +10.5%) → Geser stop ke +1.5% (Kunci bersih ~$4.5)
# Checkpoint 3: Profit +5.0% (ROE +15%) → Geser stop ke +3.0% (Kunci bersih ~$9.0)
TRAILING_FIRST_CHECKPOINT_PERCENT = 2.0 # Checkpoint pertama di +2.0% (ROE +6.0% di 3x)
TRAILING_FIRST_STOP_PERCENT = 0.3       # Kunci BEP + fee (+0.3%)
TRAILING_CHECKPOINT_STEP = 1.5          # Step checkpoint berikutnya (+3.5%, +5.0%, +6.5%, dst)
TRAILING_STOP_OFFSET = 2.0              # Jarak kawal stop 2% di bawah checkpoint (ruang bernapas ideal)

# =============================================================================
# TIME-DELAYED BEP & STAGNATION TIME-STOP (Anti-Sideways Protection)
# =============================================================================
TIME_DELAYED_BEP_ENABLED = True             # Aktifkan gembok BEP otomatis setelah waktu tertentu
TIME_DELAYED_BEP_MINUTES = 120              # Aktif setelah posisi berjalan 2 jam (8 candle 15m) agar tidak kejilat retest
TIME_DELAYED_BEP_MIN_PROFIT_PERCENT = 0.8   # Syarat: Pernah/sedang profit >= +0.8% (ROE +2.4% di 3x)
TIME_DELAYED_BEP_STOP_PERCENT = 0.22        # Kunci stop loss di +0.22% (Cover fee Binance 0.08% + Net Profit Bersih)

# Dynamic Time-Progressive Ratchet: Semakin lama posisi berjalan, kerek stop semakin naik
# agar tidak terjebak menunggu lama hanya untuk keluar di 0 koma sekian persen.
TIME_PROGRESSIVE_LOCK_ENABLED = True
TIME_PROGRESSIVE_TIERS = [
    # (elapsed_minutes, min_profit_req_pct, lock_stop_pct)
    (90,  1.4, 0.8),   # 1.5 Jam: Jika pernah/sedang profit >= +1.4%, kunci stop minimal +0.8% (ROE +2.4% -> ~$2.0-$2.5)
    (120, 1.7, 1.2),   # 2.0 Jam: Jika pernah/sedang profit >= +1.7%, kunci stop minimal +1.2% (ROE +3.6% -> ~$3.0-$3.5)
    (150, 2.0, 1.6),   # 2.5 Jam: Jika pernah/sedang profit >= +2.0%, kunci stop minimal +1.6% (ROE +4.8% -> ~$4.0-$4.5)
    (180, 2.2, 1.9),   # 3.0 Jam: Jika pernah/sedang profit >= +2.2%, kunci stop minimal +1.9% (ROE +5.7% -> ~$5.0+)
]

# Stagnation Force Close: Dinonaktifkan agar tidak memotong tren yang sedang bagus.
# Posisi dibiarkan berjalan (let winners run) sepenuhnya dikawal oleh Trailing Stop (by Price & by Time).
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
SIGNAL_MIN_SCORE = 75           # Skor minimum sinyal untuk entry (0-100)

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
SCANNER_TOP_N = 50              # Scan top 50 koin berdasarkan volume
MIN_24H_CHANGE_PERCENT = 1.0    # Minimum perubahan harga 24h (absolute)
MAX_SPREAD_PERCENT = 0.05       # Maximum spread yang diperbolehkan

# Blacklist koin (stablecoins, TradFi perps, low liquidity, dll)
BLACKLIST_COINS = [
    # Stablecoins
    "USDC/USDT", "BUSD/USDT", "TUSD/USDT", "DAI/USDT",
    "USDP/USDT", "FDUSD/USDT", "USDD/USDT",
    # TradFi Perpetuals (butuh agreement terpisah)
    "SAMSUNG/USDT", "SNDK/USDT", "CL/USDT", "SKHYNIX/USDT",
    "SOXL/USDT", "MU/USDT", "AKE/USDT", "MSTR/USDT",
    "XAU/USDT", "AIN/USDT", "KORU/USDT", "SPCX/USDT",
    "SKHY/USDT", "SNXX/USDT", "POWER/USDT", "PONS/USDT",
    "CRCL/USDT", "BR/USDT", "BZ/USDT",
]

# =============================================================================
# REVERSAL GUARD
# =============================================================================
REVERSAL_CHECK_INTERVAL = 30    # Cek reversal setiap 30 detik

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

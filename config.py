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
SIGNAL_COOLDOWN_MINUTES = 10             # Cooldown global 5 menit setelah trade selesai (cepat siap cari peluang baru)
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
MAX_ENTRY_RISK_EMA55_PERCENT = 1.35         # Maksimal jarak harga entry ke support EMA 55 hanya 0.88% (anti resiko tebal, cutloss kecil)
ANTI_CLIMAX_LOOKBACK_CANDLES = 8            # Pantau 8 candle terakhir (2 jam)
ANTI_CLIMAX_MAX_RSI = 70.0                  # Dilarang masuk LONG jika dalam 2 jam terakhir baru saja overbought > 70
ANTI_CLIMAX_MIN_RSI = 30.0                  # Dilarang masuk SHORT jika dalam 2 jam terakhir baru saja oversold < 30
BTC_FILTER_ENABLED = True                   # Pantau arah Bitcoin sebelum trading altcoin (anti-melawan induk pasar)
BTC_SYMBOL = "BTC/USDT"                     # Benchmark koin induk
BTC_FLASH_DUMP_THRESHOLD_PERCENT = 0.55     # BTC flash dump aktif jika lilin 15m drop >= -0.55% (nyata, bukan goyangan $200)
BTC_FLASH_LOCK_MINUTES = 15                 # Kunci proteksi flash dump/pump selama 15m (anti-whipsaw / kedipan micro)
BTC_FILTER_MODE = "smart"                   # 'smart': Izinkan altcoin kuat (HTF selaras) saat BTC tenang/sideways, blokir mutlak saat BTC flash dump/pump aktif
STRICT_HTF_REQUIRED = False                 # Izinkan koin decoupling yang punya tren 1H kuat

# ENTRY 2.0 (BTC TRAFFIC LIGHT & REGIME CONFLUENCE - ANTI-GOJEK KETAT)
BTC_CHOP_RSI_OVERSOLD = 42.0                # Jangan buka SHORT jika RSI 15m BTC < 42 (zona bawah rawan rebound dead-cat bounce)
BTC_CHOP_RSI_CRASH_FLOOR = 40.0             # DILARANG KERAS BUKA LONG jika RSI 15m BTC < 40 (pasar dingin/sedang dump parah)
BTC_CHOP_RSI_OVERBOUGHT = 65.0              # Jangan buka LONG jika RSI 15m BTC > 65 (pucuk jenuh, rawan profit-taking)
ANOMALY_MIN_SCORE = 90                      # Skor sinyal wajib >= 90 (Grade S) untuk boleh decoupling lawan arus BTC
ANOMALY_MIN_VOL_RATIO = 1.60                # Volume wajib >= 1.60x SMA 20 (Smart Money nyata) untuk boleh lawan arus BTC
ENTRY_MIN_VOLUME_RATIO = 0.80               # Volume standar minimal lilin entry >= 1.20x SMA 20 (hanya candle bervolume kuat)

REVERSAL_SOLID_BREAKDOWN_PERCENT = 1.50      # Batas darurat solid mutlak dirapatkan ke 0.78% (dari 1.08%, non-round number) agar minus mini
REVERSAL_DUMP_FAST_CUT_THRESHOLD_PERCENT = 0.54 # Tebas cepat jika harga >= 0.54% di bawah EMA 55 saat ada sinyal dump
REVERSAL_EMA_BREAKDOWN_BUFFER_PERCENT = 0.52 # Toleransi candle closed wajib minimal 0.52% di bawah/atas EMA 55
REVERSAL_GRACE_PERIOD_MINUTES = 12           # Ruang napas normal 7 menit (dari 15m, lilin 15m matang di menit ke-7)
REVERSAL_DUMP_FAST_CUT_ENABLED = True       # Jika di bawah EMA 55 >= 0.54% (LONG) dan terjadi BTC/Market dump, tebas instan!

# MACRO PRESSURE FAST CUT (BTC & BTCDOM ADVERSE SHIELD - OPSI A)
MACRO_PRESSURE_CUT_ENABLED = True             # Bypass Grace Period jika terjadi tekanan makro dari BTC atau BTCDOM
MACRO_BTC_PRESSURE_DROP_PERCENT = 0.32        # Tekanan BTC jika lilin 15m drop >= -0.32% (terhadap open lilin 15m)
MACRO_DOM_PRESSURE_SURGE_PERCENT = 0.12       # Tekanan BTCDOM jika lilin 15m melonjak melawan posisi >= 0.12%
MACRO_PRESSURE_EMA_CUT_PERCENT = 0.54         # Batas tembus EMA 55 (0.54%) untuk eksekusi tebas instan tanpa Grace Period
MACRO_WICK_RECOVERY_PROTECT_PERCENT = 28.0    # Jangan tebas jika koin membentuk jarum pantulan bawah >= 28% (anti-kejilat wick kagetan)


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
# FLEXIBLE & DYNAMIC ATR TRAILING STOP & PARTIAL TAKE PROFIT
# =============================================================================
# 1. DYNAMIC TAKE PROFIT UTAMA (Target Adaptif Volatilitas Koin)
DYNAMIC_TP_ENABLED = True
DYNAMIC_TP_ATR_MULTIPLIER = 2.2      # Target TP dihitung 2.2x ATR 15m koin saat entry
DYNAMIC_TP_MIN_PERCENT = 1.75        # Target minimal +1.75% (koin tenang tetap cuan tebal ~$6 bersih)
DYNAMIC_TP_MAX_PERCENT = 3.60        # Target maksimal +3.60% (koin roket dipanen di ~$13+ bersih)
PARTIAL_TP_ENABLED = True            # Aktifkan eksekusi TP parsial
PARTIAL_TP_RATIO = 0.50              # Jual 50% muatan saat target kena, sisa 50% jadi Moonbag
PARTIAL_TP_PERCENT = 2.42            # Fallback statis jika data ATR tidak tersedia

# 2. FLEXIBLE TRAILING PROFIT RATCHET (Tangga Pengawalan Adaptif)
DYNAMIC_TRAILING_ENABLED = True
TRAILING_FIRST_CHECKPOINT_ATR_RATIO = 1.4  # Checkpoint 1 aktif lebih cepat (1.4x ATR koin)
TRAILING_FIRST_CHECKPOINT_MIN_PERCENT = 1.30 # Minimal Checkpoint 1 aktif di +1.30%
TRAILING_FIRST_CHECKPOINT_MAX_PERCENT = 1.65 # PLAFON MAKSIMAL: Koin seliar apapun WAJIB aktif di +1.65%!
TRAILING_FIRST_STOP_ATR_RATIO = 0.80       # Kunci stop loss pertama di 0.80x ATR
TRAILING_FIRST_STOP_MIN_PERCENT = 0.65     # Minimal stop loss terkunci di +0.65%
TRAILING_FIRST_STOP_MAX_PERCENT = 0.90     # Plafon stop 1 di +0.90%
TRAILING_STOP_OFFSET_ATR_RATIO = 0.80      # Jarak kawal stop 0.80x ATR koin (ruang napas lega)
TRAILING_STOP_OFFSET_MIN = 0.65            # Minimal jarak stop 0.65% (anti kejilat spread)
TRAILING_STOP_OFFSET_MAX = 1.00            # Maksimal jarak stop 1.00% (agar cuan terjaga)
TRAILING_CHECKPOINT_STEP = 0.40            # Step checkpoint bertingkat berikutnya (+0.40% cepat naik)

# Fallback statis trailing (jika ATR tidak tersedia)
TRAILING_FIRST_CHECKPOINT_PERCENT = 1.65    # Checkpoint 1 fallback di +1.65%
TRAILING_FIRST_STOP_PERCENT = 0.80          # Stop 1 fallback di +0.80%
TRAILING_STOP_OFFSET = 0.85                 # Offset fallback di 0.85%

# 3. FLEXIBLE STALL GUARD (Deteksi Bensin Habis & Moonbag Protector)
STALL_GUARD_ENABLED = True           # Aktifkan deteksi bensin habis
STALL_GUARD_CLOSE_FULL = False       # REVOLUSI: Jual 50% saja, jangan 100%! Sisa 50% jadi Moonbag
STALL_GUARD_TRIGGER_RATIO = 0.60     # Aktif di 60% perjalanan menuju Target TP Dinamis
STALL_GUARD_MIN_PROFIT_FLOOR = 1.10  # Paling cepat aktif di profit +1.10% (di atas radar BEP 0.80%)
STALL_GUARD_DYNAMIC_PULLBACK_RATIO = 0.40 # Toleransi melorot 0.40x ATR koin dari peak
STALL_GUARD_MIN_PULLBACK_PERCENT = 0.32   # Minimal melorot 0.32% (koin tenang)
STALL_GUARD_MAX_PULLBACK_PERCENT = 0.60   # Maksimal melorot 0.60% (koin roket)
STALL_GUARD_WICK_PERCENT = 30.0           # Ekor jarum atas rejection wick >= 30% lilin 15m
STALL_GUARD_MIN_EXIT_PROFIT = 0.75        # Menjamin eksekusi stall guard tetap cuan bersih ~$5+

# STALL GUARD KHUSUS KOIN MATANG / BERUMUR (>= 120 Menit)
STALL_GUARD_AGED_MIN_PROFIT_PERCENT = 1.05
STALL_GUARD_AGED_PULLBACK_PERCENT = 0.32
STALL_GUARD_AGED_MIN_EXIT_PROFIT = 0.60

# =============================================================================
# 3b. MID-RANGE PROFIT GUARD (PENGAMAN AREA 0.0% s/d +0.80%)
# =============================================================================
# Filosofi:
# - Di bawah +0.50%: Koin bebas bergerak dan bernapas tanpa diganggu.
# - Jika sudah terbang masuk zona menengah (>= +0.55% s/d +0.60% / cuan ~$4):
#   Koin terbukti punya momentum, tapi belum sampai ke radar BEP statis (+0.80%).
# - Jika dari puncak tersebut koin melorot kembali ke pintu modal (profit <= +0.10% / BEP cover fee):
#   Bot mengamankan posisi agar modal selamat dan tidak berbalik menjadi kerugian tekor!
MID_RANGE_GUARD_ENABLED = True
MID_RANGE_TRIGGER_PROFIT = 0.55             # Aktif HANYA jika koin sudah pernah naik minimal +0.55% (cuan ~$3.8+)
MID_RANGE_LOCK_PROFIT = 0.08                # Batas aman di BEP tipis (+0.08% cover fee Binance, modal utuh)

# =============================================================================
# CHOPPY AUTO-BEP & ADAPTIVE REGIME EXIT (PENGAMAN PASAR CHOPPY VS GACOR)
# =============================================================================
# Filosofi:
# 1. Pintu Masuk (Entry): Tetap bebas tanpa dicekik agar tidak ketinggalan kereta.
# 2. Pasca-Entry (Setelah Masuk):
#    - Bot mengecek nilai ADX 15m & arah kekuatan (+DI vs -DI) koin.
#    - Jika ADX < 22 (Pasar Choppy/Sideways) ATAU Arah DI melawan posisi (+DI vs -DI misaligned):
#      * Koin berada di Mode Choppy:
#        a. AUTO-BEP LOCK: Begitu floating profit >= CHOPPY_BEP_TRIGGER_PERCENT (+0.55%),
#           bot OTOMATIS langsung mengunci Stop Loss ke level BEP (+0.12% cover fee).
#           Modal terlindungi 100%, anti-loss dari pembalikan arah!
#        b. CHOPPY PARTIAL TP: Target Partial TP 1 (CP1) diturunkan ke +0.95% agar lekas
#           mengamankan 50% uang dapur di dompet sebelum koin kehilangan bensin.
#    - Jika ADX >= 25 dan DI searah (Pasar Gacor / Strong Trend):
#      * Mode Gacor: Target CP1 normal (+1.45% s/d +1.80%) dengan Trailing Ratchet lega
#        mengejar Target Puncak Moonbag ($15 s/d $20 USD | +2.70%).
CHOPPY_AUTO_BEP_ENABLED = True
CHOPPY_ADX_THRESHOLD = 22.0                  # Batas ADX 15m koin: di bawah 22.0 diklasifikasikan sebagai Choppy/Lemas
CHOPPY_BEP_TRIGGER_PERCENT = 0.55            # Floating profit minimal +0.55% untuk langsung kunci stop ke BEP
CHOPPY_BEP_LOCK_PERCENT = 0.12               # Level stop BEP yang dikunci (+0.12% untuk menutup biaya trading fee)
CHOPPY_CP1_PERCENT = 0.95                    # Target Partial TP 1 koin choppy (+0.95%) agar cepat bungkus profit

# =============================================================================
# TARGET DISIPLIN HARIAN (COMPOUNDING SNOWBALL) & STEPPED RATCHET CHOPPY
# =============================================================================
DAILY_TARGET_PROFIT_PERCENT = 10.0            # Target cuan harian dinamis (10% dari modal akun)
CHOPPY_RATCHET_TRIGGER_PERCENT = 0.50         # Mulai aktif mengawal ketat saat koin choppy naik >= +0.50%
CHOPPY_RATCHET_TRAIL_PERCENT = 0.20           # Jarak kawal rapat mepet (0.20% di belakang harga pucuk)
MOONBAG_TARGET_USD = 20.0                    # Target puncak profit satu trade ($20 USD | ~+2.72% harga)

# =============================================================================
# MOONBAG TIMEOUT (PENGAMAN KOIN STAGNAN PASCA-PARTIAL TP)
# =============================================================================
# Filosofi:
# - Koin yang mau meledak liar (MON, NMR, PENGU, AAVE, DASH) 96% selesai dalam < 2.5 jam.
# - Jika koin sudah ambil Partial TP (Moonbag), tapi setelah MOONBAG_TIMEOUT_HOURS (3.5 jam)
#   belum tembus Checkpoint 2 (stagnan di bawah MOONBAG_TIMEOUT_MAX_PROFIT 1.5%),
#   bot otomatis menutup sisa posisi 100% via Market Order untuk mengunci sisa profit ke kas!
# - Modal margin $245 langsung cair dan bebas berputar mencari setup baru.
MOONBAG_TIMEOUT_ENABLED = True
MOONBAG_TIMEOUT_HOURS = 3.5                   # Maksimal 3.5 jam setelah entry jika sudah Partial TP
MOONBAG_TIMEOUT_MAX_PROFIT = 1.5              # Hanya aktif jika profit masih loyo/stagnan di bawah +1.5%

# =============================================================================
# TIME-PROGRESSIVE BEP (OPSI A: SATPAM KOIN LEMOT / SIDEWAYS)
# =============================================================================
# Filosofi Opsi A:
# - Koin yang lari kencang (>= +1.5%) TIDAK DIGANGGU oleh waktu, bebas berburu swing pucuk.
# - Trailing Waktu HANYA MENGAWAL koin loyo yang sudah jalan >= 2 jam (120m) dan profit < 1.2%,
#   dengan memasang stop di BEP murni (+0.18% cover fee) agar modal tidak tersandera selamanya.
TIME_PROGRESSIVE_LOCK_ENABLED = True
TIME_PROGRESSIVE_MINUTES = 75              # 75 Menit (5 lilin 15m): batas waktu koin matang / loyo
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
# BOUNCE FAILURE GUARD (Dead-Cat Bounce Rejection Cut)
# =============================================================================
# Filosofi:
# - Saat koin sempat drop (dip) lalu MANTUL naik, kita amati kekuatannya.
# - Jika setelah mantul harga gagal tembus entry (tertahan resisten) dan mulai melorot kembali,
#   bot langsung tebas potong rugi saat itu juga sebelum minusnya membengkak kembali ke dasar jurang!
BOUNCE_FAILURE_GUARD_ENABLED = True
BOUNCE_FAILURE_REQUIRE_EMA55_TEST = True     # Rem hanya aktif jika harga sudah menguji/menusuk ke batas lantai EMA 55 (Safe Pocket)
BOUNCE_FAILURE_EMA_BUFFER_PERCENT = 0.52     # Toleransi buffer lantai EMA 55 (0.52% di bawah/atas EMA 55)
BOUNCE_FAILURE_MIN_DRAWDOWN_PERCENT = -0.75  # Drawdown minimal terhadap entry untuk konfirmasi dip nyata
BOUNCE_FAILURE_MIN_REBOUND_PERCENT = 0.35    # Sempat berhasil mantul naik minimal +0.35% harga dari dasar jurang
BOUNCE_FAILURE_SLIPPAGE_TOLERANCE = 0.25     # Jika setelah mantul harga melorot kembali >= 0.25% dari puncak pantulan -> TEBAS!
BOUNCE_FAILURE_MAX_LOSS_PERCENT = -1.15      # Batas minus harga maksimal (-1.15% harga | ~ -3.45% ROE di 3x) setelah tembus batas EMA 55
MAX_LOSS_USDT_CAP = -8.80                    # Batas kerugian dolar nominal maksimal (-$8.80 USDT) setelah tembus batas EMA 55

# =============================================================================
# PANIC VOLUME DUMP CUT (Deteksi Air Terjun vs Gojekan Jarum di Lilin 1m)
# =============================================================================
# Filosofi:
# - Jika harga jebol di bawah EMA 55 saat drawdown >= -0.75%:
#   Bot mengecek volume lilin 1 menit terakhir.
# - Jika Volume >= 2.5x rata-rata 1m (Smart Money air terjun nyata) -> TEBAS INSTAN tanpa nunggu 15m!
# - Jika Volume kecil/biasa (< 2.5x) -> TAHAN! Ini gojekan jarum likuidasi, beri ruang mantul!
PANIC_VOLUME_CUT_ENABLED = True
PANIC_VOLUME_CUT_MIN_DRAWDOWN = -0.75        # Hanya aktif jika drawdown sudah menyentuh -0.75% harga
PANIC_VOLUME_CUT_RATIO = 3.8                 # Volume ledakan 1m >= 2.5x rata-rata SMA 10 lilin 1m

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
SIGNAL_MIN_SCORE = 70           # Skor minimum sinyal untuk entry (Hanya Grade A & A+ super kuat yang boleh masuk!)

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
ADX_THRESHOLD = 20.0            # Wajib ADX >= 20 jika volume normal (< 1.5x)
ADX_BREAKOUT_THRESHOLD = 14.0   # Toleransi ADX >= 14 jika ada volume ledakan raksasa (>= 1.5x)
ADX_BREAKOUT_VOL_RATIO = 1.50   # Batas volume ledakan untuk aktivasi toleransi awal

# Volume
VOLUME_SMA_PERIOD = 20
MIN_VOLUME_RATIO = 0.80         # Minimal volume 1.15x dari average 20 SMA (Smart Money validasi)

# Timeframes & Confirmation
TRADING_TIMEFRAME = "15m"       # Timeframe utama (15m cepat & responsif)
HIGHER_TIMEFRAME = "1h"         # Timeframe konfirmasi trend makro (1h)
CANDLE_HISTORY_CONFIRMATION_COUNT = 3

# =============================================================================
# SCANNER SETTINGS
# =============================================================================
SCANNER_TOP_N = 120             # Scan top 120 koin berdasarkan volume (universe luas, banyak peluang Grade A+)
MIN_24H_CHANGE_PERCENT = 1.0    # Minimum perubahan harga 24h (absolute)
MAX_SPREAD_PERCENT = 0.05       # Maximum spread yang diperbolehkan

# Blacklist koin (delisting risk, monitoring tag, stablecoins, TradFi perps, slow-moving heavyweights, anomali liar)
BLACKLIST_COINS = [
    # Slow-moving Heavyweights (fokus ke altcoin yang lincah & berbobot volatilitas bagus)
    "BTC/USDT", "BTC",
    "ETH/USDT", "ETH",

    # Stablecoins
    "USDC/USDT", "BUSD/USDT", "TUSD/USDT", "DAI/USDT",
    "USDP/USDT", "FDUSD/USDT", "USDD/USDT",

    # Official Binance Monitoring Tag (Tag Pemantauan / Koin Berisiko Delisting)
    "ACT", "ARK", "AVA", "AWE", "BLUR", "COOKIE", "DODO", "EPIC",
    "FTT", "GLMR", "GNS", "GTC", "HEI", "JASMY", "LSK", "MOVE",
    "MOVR", "NOM", "PORTAL", "QI", "QKC", "QUICK", "RARE", "RESOLV",
    "SCR", "SOPH", "STX", "SYN", "TLM", "TOWNS", "VELODROME", "WIF",

    # High-volatility political memecoins / High-risk wicks
    "TRUMP/USDT", "TRUMP",

    # TradFi Perpetuals & Gold/Commodity Perps (Emas / Bukan Crypto Asli)
    "PAXG/USDT", "PAXG",
    "XAUT/USDT", "XAUT",
    "AAOI/USDT", "AAOI",
    "SOXS/USDT", "SOXS",
    "DRAM/USDT", "DRAM",
    "GOOGL/USDT", "GOOGL",
    "XAU/USDT", "XAU", "XAG/USDT", "XAG", "XPT/USDT", "XPT", "XPD/USDT", "XPD",
    "SAMSUNG/USDT", "SNDK/USDT", "CL/USDT", "SKHYNIX/USDT",
    "SOXL/USDT", "MU/USDT", "AKE/USDT", "MSTR/USDT",
    "AIN/USDT", "KORU/USDT", "SPCX/USDT",
    "SKHY/USDT", "SNXX/USDT", "POWER/USDT", "PONS/USDT",
    "CRCL/USDT", "BR/USDT", "BZ/USDT", "INTC/USDT",
    "NVDA/USDT", "TSLA/USDT", "AAPL/USDT", "MSFT/USDT",
    "AMD/USDT", "AMZN/USDT", "GOOG/USDT", "COIN/USDT",
    "PLTR/USDT", "BABA/USDT", "DELL/USDT", "DELL",
    "ARM/USDT", "ARM", "RKLB/USDT", "RKLB", "MARSCOIN/USDT", "MARSCOIN",
]

# =============================================================================
# SMART EXHAUSTION / CLIMAX EXIT (Puncak & Lembah Guard - Super Climax)
# =============================================================================
EXHAUSTION_EXIT_ENABLED = True             # Aktifkan deteksi titik pucuk / klimaks
EXHAUSTION_MIN_PROFIT_PERCENT = 3.2        # Minimal profit +3.2% (ROE ~9.6% di 3x | ~$14.4 USDT) baru boleh cari pucuk!
EXHAUSTION_RSI_OVERBOUGHT = 76.0           # RSI overbought ekstrem untuk LONG
EXHAUSTION_RSI_OVERSOLD = 24.0             # RSI oversold ekstrem untuk SHORT
EXHAUSTION_WICK_PERCENT = 35.0             # Rejection wick minimal 35% (jarum pembalikan nyata)
EXHAUSTION_EMA_DIST_PERCENT = 2.2          # Jarak harga dari EMA 21 minimal 2.2% (overextended)
EXHAUSTION_PULLBACK_PERCENT = 0.65         # Penurunan/pantulan minimal 0.65% (bukan nafas tipis)
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

# =============================================================================
# PRE-FILL WATCHDOG (Auto-Abort Antrian Limit Order jika Pasar Berbalik)
# =============================================================================
PRE_FILL_WATCHDOG_ENABLED = True
PRE_FILL_MAX_ADVERSE_DRIFT_PERCENT = 0.35   # Batalkan jika harga market lari >= 0.35% melawan arah order saat antri
PRE_FILL_CHECK_BTC_REVERSAL = True          # Batalkan jika arah BTC mendadak berbalik arah saat antri

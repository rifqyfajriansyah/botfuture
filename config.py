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
LEVERAGE = 3                    # Leverage 3x (Aman & terkontrol)
MARGIN_MODE = "isolated"        # Isolated margin (lebih aman per posisi)
BALANCE_USAGE = 0.95            # Gunakan 95% balance (Maksimalisasi compounding & capital efficiency sesuai arahan user)
MAX_POSITIONS = 1               # Hanya 1 posisi aktif
# =============================================================================
# CAPITAL FLOOR GUARD (PENGAMAN MODAL POKOK 5 JUTA RUPIAH)
# =============================================================================
# Jika sewaktu-waktu saldo dompet turun ke batas ini (~Rp 5.000.000),
# bot OTOMATIS BERHENTI membuka posisi baru untuk mengunci modal pokok 100% aman!
MIN_WALLET_BALANCE_USDT = 280.0   # $280 USDT setara Rp 5.000.000 IDR (Kurs ~Rp 17.850 / USDT)

# =============================================================================
# COOLDOWN & ANTI-REENTRY SETTINGS
# =============================================================================
SIGNAL_COOLDOWN_MINUTES = 10             # Cooldown global 10 menit setelah trade selesai (cepat siap cari peluang baru)
FIXED_COOLDOWN_ENABLED = True           # Kalah maupun menang delay global tetap fixed 10 menit (tidak ada penalti jeda berjam-jam)
SYMBOL_COOLDOWN_MINUTES = 45            # Cooldown khusus koin yang sama jika trade MENANG/BEP (45 menit jeda sehat)
SYMBOL_LOSS_COOLDOWN_MINUTES = 240      # COOLDOWN 4 JAM (240 Menit) jika trade KALAH/CUTLOSS (Kunci anti-revenge koin jebakan)
TIMEOUT_COOLDOWN_MINUTES = 1            # Cooldown global jika limit order cancel/timeout (hanya 1m sebelum scan koin lain)
TIMEOUT_SYMBOL_COOLDOWN_MINUTES = 15     # Cooldown khusus simbol jika limit order cancel/timeout (hanya 15m / 1 candle)
MAX_CONSECUTIVE_LOSSES = 999            # Dinonaktifkan: gas terus tanpa jeda/pause losestreak
DOUBLE_COOLDOWN_AFTER_LOSSES = 999      # Dinonaktifkan
CONSECUTIVE_LOSS_PAUSE_MINUTES = 0      # Dinonaktifkan

# =============================================================================
# COMBAT MODE / HIGH-FREQUENCY MONITORING (Anti-Flash Slippage Guard)
# =============================================================================
COMBAT_LOOP_INTERVAL = 2.5              # Interval cepat 2.5 detik saat posisi floating minus (tangkap lonjakan kilat 4x lebih cepat)
COMBAT_TRIGGER_DRAWDOWN = -0.40         # Masuk mode siaga cepat jika drawdown <= -0.40% harga

# =============================================================================
# ASYMMETRIC LONG & SHORT DYNAMICS & BTC TREND FILTER (VALIDASI HISTORIS OKTOBER)
# =============================================================================
TRADING_ALLOWED_SIDES = "BOTH"                   # Opsi Arah Trading: "BOTH" (Long & Short terfilter) | "LONG_ONLY" (Fokus Long)
ALLOW_COUNTER_TREND_SHORT = False                # DILARANG KERAS SHORT lawan arus saat BTC Bullish! (Anti-suicide short squeeze)
LONG_MAX_RSI = 52.0                             # Anti-Pucuk Sejati: Dilarang LONG jika RSI > 52.0 (wajib beli diskon)
SHORT_MIN_RSI = 48.0                            # Anti-Dasar Sejati: Dilarang SHORT jika RSI < 48.0 (wajib retest resisten)
MIN_ENTRY_REJECTION_WICK_PERCENT = 25.0         # Wick minimal 25% (ekor penolakan nyata, menolak lilin botak)
CHOP_MIN_REJECTION_WICK_PERCENT = 35.0          # Saat Sideways/Chop, Upper Wick SHORT wajib >= 35% (ekor penolakan tebal resisten)
SHORT_TP1_PERCENT = 0.60                        # TP1 khusus SHORT lebih cepat di +0.60% (kunci cuan anti bounce-back)
SHORT_SIDEWAYS_FULL_TEBAS = True                # Khusus SHORT di Sideways: Tebas 100% langsung di +0.60% via Market Order!
COUNTER_TREND_ALLOWED = True                     # Boleh trade lawan arah BTC asal TER-CONFIRM
COUNTER_TREND_MIN_SCORE = 90                     # Skor sinyal wajib Grade S (>= 90)
COUNTER_TREND_MIN_WICK = 35.0                    # Wick rejection ekor penolakan wajib tebal >= 35%
COUNTER_TREND_MIN_VOL_RATIO = 1.35               # Volume aliran dana nyata >= 1.35x
COUNTER_TREND_MAX_LONG_RSI = 52.0                # LONG saat BTC Bearish: RSI koin dilarang di pucuk (maks 52.0)
COUNTER_TREND_MIN_SHORT_RSI = 48.0               # SHORT saat BTC Bullish: RSI koin dilarang di dasar (min 48.0)
WHALE_RESCUE_VOLUME_RATIO = 1.80             # Pintu VIP Paus: Ledakan volume >= 1.80x
SUPER_WICK_RESCUE_RATIO = 50.0               # Pintu VIP Super-Wick: Ekor monster >= 50%
SUPER_WICK_MIN_VOL = 0.50                    # Toleransi volume minimum untuk Super-Wick (0.50x)
MAX_ENTRY_RISK_EMA55_PERCENT = 1.35         # Maksimal jarak harga entry ke support EMA 55 hanya 0.88% (anti resiko tebal, cutloss kecil)
ANTI_CLIMAX_LOOKBACK_CANDLES = 8            # Pantau 8 candle terakhir (2 jam)
ANTI_CLIMAX_MAX_RSI = 70.0                  # Dilarang masuk LONG jika dalam 2 jam terakhir baru saja overbought > 70
ANTI_CLIMAX_MIN_RSI = 30.0                  # Dilarang masuk SHORT jika dalam 2 jam terakhir baru saja oversold < 30
BTC_FILTER_ENABLED = True                   # Pantau arah Bitcoin sebelum trading altcoin (anti-melawan induk pasar)
BTC_SYMBOL = "BTC/USDT"                     # Benchmark koin induk
BTC_FLASH_DUMP_THRESHOLD_PERCENT = 0.55     # BTC flash dump aktif jika lilin 15m drop >= -0.55% (nyata, bukan goyangan $200)
BTC_FLASH_LOCK_MINUTES = 15                 # Kunci proteksi flash dump/pump selama 15m (anti-whipsaw / kedipan micro)
BTC_FILTER_MODE = "smart"                    # 'smart': Izinkan altcoin kuat (HTF selaras) saat BTC tenang/sideways, blokir mutlak saat BTC flash dump/pump aktif
STRICT_HTF_REQUIRED = True                 # Izinkan koin decoupling yang punya tren 1H kuat

# BTC 1H CHOP / SIDEWAYS REGIME DETECTION (VALIDASI 218 HISTORICAL TRADES: +$168.73 USDT NET GAIN)
BTC_CHOP_1H_RANGE_MAX = 0.80               # Maksimum rentang lilin 1H BTC (High - Low)/Close (%) untuk Chop Zone
BTC_CHOP_3H_DISP_MAX = 0.80                # Maksimum perpindahan harga net 3 jam terakhir (%) untuk Chop Zone
CHOP_MIN_VOLUME_RATIO = 1.15               # Saat BTC Sideways/Chop, altcoin WAJIB punya volume >= 1.15x (validasi Smart Money nyata)

# ENTRY 2.0 (BTC MICRO-REBOUND & MICRO-SLIP GUARD - ZONA EMAS BACKTEST 0.14%)
BTC_REBOUND_MAX_15M_PCT = 0.14              # Dilarang SHORT jika lilin 15m BTC sedang memantul naik >= +0.14% (anti keseret pantulan)
BTC_SLIP_MAX_15M_PCT = 0.14                 # Dilarang LONG jika lilin 15m BTC sedang longsor turun <= -0.14% (anti pisau jatuh)
BTC_CHOP_MAX_LONG_RSI = 60.0               # [Adaptive Chop Gate] Di pasar Sideways, dilarang LONG jika BTC 15m RSI >= 60.0 (atap resisten kotak)
BTC_CHOP_MIN_SHORT_RSI = 50.0              # [Adaptive Chop Gate] Di pasar Sideways, dilarang SHORT jika BTC 15m RSI >= 50.0 (BTC di separuh atas kotak)
BTC_MIN_SHORT_RSI = 32.0                    # Dilarang buka SHORT jika RSI 15m BTC < 32 (jenuh jual di dasar support rawan memantul untuk koin standar)
BTC_MIN_SHORT_RSI_ROCKET = 26.0             # [Opsi B] Lantai dasar SHORT dilonggarkan ke 26.0 khusus koin Grade-S Rocket Dump
BTC_OPSI_B_MIN_SCORE = 90                   # [Opsi B] Skor wajib >= 90 (Grade S) untuk lolos di zona RSI 26 - 32
BTC_OPSI_B_MIN_VOL_RATIO = 1.40             # [Opsi B] Volume ledakan wajib >= 1.40x SMA 20
BTC_OPSI_B_MIN_WICK_PERCENT = 20.0          # [Opsi B] Ekor atas penolakan (upper wick) wajib >= 20%
BTC_OPSI_B_MAX_BUYER_WICK_PERCENT = 20.0    # [Opsi B] Maksimum ekor bawah (perlawanan buyer) agar tidak kena short squeeze (< 20%)
BTC_MAX_LONG_RSI = 80.0                     # Dilarang buka LONG jika RSI 15m BTC >= 80 (jenuh beli ekstrem di pucuk rawan dump kilat, hemat -$33.69 USDT)
BTC_CHOP_RSI_CRASH_FLOOR = 40.0             # DILARANG KERAS BUKA LONG jika RSI 15m BTC < 40 (pasar dingin/sedang dump parah)
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
HIGH_CONVICTION_OFFSET_PERCENT = 0.08   # Limit order sangat rapat (0.08%) agar cepat fill & anti-ketinggalan
HIGH_CONVICTION_TIMEOUT_MINUTES = 3     # Timeout cepat 3 menit (segera alihkan modal jika tidak dijemput)

# Level 2: Sinyal Standar (Normal Conviction - Score 70-79)
NORMAL_CONVICTION_OFFSET_PERCENT = 0.10 # Limit order rapat (0.10% - Golden Sweet Spot)
NORMAL_CONVICTION_TIMEOUT_MINUTES = 5   # Timeout 5 menit (tidak sandera modal lama-lama)

# Default fallback / backward compatibility
ENTRY_OFFSET_PERCENT = 0.10             # Default limit offset (0.10%)
ORDER_TIMEOUT_MINUTES = 5               # Default timeout 5 menit
ORDER_CHECK_INTERVAL = 10               # Cek order setiap 10 detik

# =============================================================================
# PARTIAL FILL SWEEP (Anti-Ketinggalan Kereta)
# =============================================================================
PARTIAL_FILL_SWEEP_ENABLED = True       # Jika order terisi sebagian saat timeout, sapu sisanya pakai market
MIN_PARTIAL_FILL_RATIO = 0.20           # Minimal 20% sudah terisi untuk memicu sweep
MAX_PARTIAL_FILL_RATIO = 0.95           # Di atas 95% dianggap sudah full
MAX_SWEEP_SLIPPAGE_PERCENT = 0.35       # Maksimal toleransi selisih harga dari entry awal (0.35%) agar tidak beli di pucuk

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
TRAILING_FIRST_CHECKPOINT_MIN_PERCENT = 0.95 # Checkpoint 1 aktif di +0.95% (Napas lega, anti kejilat kocokan awal)
TRAILING_FIRST_CHECKPOINT_MAX_PERCENT = 1.30 # Plafon maksimal CP1 aktif di +1.30%
TRAILING_FIRST_STOP_ATR_RATIO = 0.80       # Kunci stop loss pertama di 0.80x ATR
TRAILING_FIRST_STOP_MIN_PERCENT = 0.45     # Stop 1 terkunci di +0.45% (Jarak napas 0.50% lega! Cuan ~$6 aman di atas fee)
TRAILING_FIRST_STOP_MAX_PERCENT = 0.70     # Plafon stop 1 di +0.70%
TRAILING_STOP_OFFSET_ATR_RATIO = 0.80      # Jarak kawal stop 0.80x ATR koin (ruang napas lega)
TRAILING_STOP_OFFSET_MIN = 0.50            # Minimal jarak stop 0.50% (lega, anti kejilat noise lilin)
TRAILING_STOP_OFFSET_MAX = 1.00            # Maksimal jarak stop 1.00% (agar cuan terjaga)
TRAILING_CHECKPOINT_STEP = 0.45            # Step checkpoint bertingkat (+0.45% per level)

# Fallback statis trailing (jika ATR tidak tersedia)
TRAILING_FIRST_CHECKPOINT_PERCENT = 1.65    # Checkpoint 1 fallback di +1.65%
TRAILING_FIRST_STOP_PERCENT = 0.80          # Stop 1 fallback di +0.80%
TRAILING_STOP_OFFSET = 0.85                 # Offset fallback di 0.85%

# 3. FLEXIBLE STALL GUARD (Deteksi Bensin Habis & Moonbag Protector)
STALL_GUARD_ENABLED = True           # Aktifkan deteksi bensin habis
STALL_GUARD_CLOSE_FULL = True        # TEBAS 100%: Kunci cuan utuh saat bensin habis / rejection wick! (Koin roket tanpa wick tetap aman moonbag via Dynamic TP)
STALL_GUARD_TRIGGER_RATIO = 0.60     # Aktif di 60% perjalanan menuju Target TP Dinamis
STALL_GUARD_MIN_PROFIT_FLOOR = 1.10  # Paling cepat aktif di profit +1.10% (di atas radar BEP 0.80%)
STALL_GUARD_DYNAMIC_PULLBACK_RATIO = 0.40 # Toleransi melorot 0.40x ATR koin dari peak
STALL_GUARD_MIN_PULLBACK_PERCENT = 0.32   # Minimal melorot 0.32% (koin tenang)
STALL_GUARD_MAX_PULLBACK_PERCENT = 0.60   # Maksimal melorot 0.60% (koin roket)
STALL_GUARD_WICK_PERCENT = 30.0           # Ekor jarum atas rejection wick >= 30% lilin 15m
STALL_GUARD_MIN_EXIT_PROFIT = 0.75        # Menjamin eksekusi stall guard tetap cuan bersih ~$5+

# =============================================================================
# SMART DUAL-MODE ENTRY (JALUR ROKET VS JALUR NAWAR)
# =============================================================================
# Jalur 1: Super Breakout / Koin Roket (JANGAN NAWAR JAUH - ANTI KETINGGALAN KERETA)
ROCKET_MIN_SCORE = 85                   # Skor minimum sinyal super kuat (Grade A)
ROCKET_MIN_VOL_RATIO = 1.50             # Volume ledakan minimal 1.50x SMA 20
ROCKET_MIN_WICK_PERCENT = 30.0          # Ekor penolakan kokoh minimal 30% (mantul nyata dari support)
ROCKET_ENTRY_OFFSET_PERCENT = 0.05      # Offset mikro sangat tipis (0.05%) agar langsung auto-fill di retest awal
ROCKET_TIMEOUT_MINUTES = 3              # Timeout cepat 3 menit (koin roket langsung jalan)

# =============================================================================
# ADAPTIVE PRESSURE BIDDING (GOLDEN SWEET SPOT 0.10% - ANTI KETINGGALAN KERETA)
# =============================================================================
# Filosofi Disiplin Sniper:
# Saat sinyal muncul, jika ada indikasi tekanan berlawanan arah (penjual mengguyur di pucuk):
# - LONG: Ada jarum atas (upper wick) / lilin 1m merah / BTC goyang -> Tawar di diskon sweet spot 0.10%!
# - SHORT: Ada jarum bawah (lower wick) / lilin 1m hijau / BTC membal -> Jual di premium sweet spot +0.10%!
# - Jika tekanan ekstrem (ekor panjang >= 35%) -> Tawar lebih dalam di 0.18%!
# Jika kondisi roket bersih murni tanpa hambatan seller/buyer -> Masuk via Jalur Roket (0.05%) agar instan fill!
ADAPTIVE_PRESSURE_ENTRY_ENABLED = True
PRESSURE_OPPOSING_WICK_THRESHOLD = 20.0       # Batas ekor lawan (>= 20%) indikasi tekanan seller/buyer
PRESSURE_SWEET_SPOT_OFFSET_PERCENT = 0.10     # Golden Sweet Spot diskon/premium rapat (0.10% - fill rate 80%+)
PRESSURE_EXTREME_WICK_THRESHOLD = 35.0        # Jika ekor lawan sangat panjang (>= 35%), seller ekstra brutal
PRESSURE_EXTREME_OFFSET_PERCENT = 0.18        # Diskon/premium saat tekanan ekstrem (0.18%)
CHECK_MICRO_1M_PRESSURE = True                # Cek konfirmasi lilin 1m terakhir

# =============================================================================
# BTC-GUIDED ADAPTIVE SNIPER CALIBRATION
# =============================================================================
# Menyesuaikan mode sniper berdasarkan nakhoda pasar (BTC):
# 1. BTC Overbought Ekstrem (RSI >= 70) / Retracing (15m Chg <= -0.10%): Mode Defensive Deep Discount (0.45%)
# 2. BTC Sideways / Chop Zone / Altcoin ada penolakan: Mode Sweet Spot Discount (0.35%)
# 3. BTC Bullish Sehat (50 <= RSI <= 68 & Chg >= 0%) + Altcoin Bersih: Mode Rocket Fast-Fill (0.05%)
BTC_SNIPER_CALIBRATION_ENABLED = True
BTC_SNIPER_OVERBOUGHT_RSI = 70.0              # Area overbought ekstrem BTC (rawan koreksi mendadak)
BTC_SNIPER_OVERSOLD_RSI = 30.0                # Area oversold ekstrem BTC (rawan short squeeze)
BTC_SNIPER_RETRACE_DROP_PCT = -0.10           # Lilin 15m BTC sedang merah/turun
BTC_SNIPER_HEALTHY_MIN_RSI = 50.0             # Batas bawah RSI BTC momentum sehat
BTC_SNIPER_HEALTHY_MAX_RSI = 68.0             # Batas atas RSI BTC momentum sehat (sebelum pucuk overbought)


# Jalur Ekstra: Zero-Fill Momentum Chase on Timeout (Dinonaktifkan sesuai instruksi user)
ZERO_FILL_CHASE_ENABLED = False         # Dinonaktifkan: jika order tawar belum keisi saat timeout, cancel murni tanpa kejar pasar!
ZERO_FILL_CHASE_MIN_GAIN_PERCENT = 0.08 # Koin sudah mulai bergerak ke arah sinyal minimal +0.08%
ZERO_FILL_CHASE_MAX_SLIPPAGE_PERCENT = 0.35 # Maksimal toleransi selisih harga dari sinyal (0.35%)

# STALL GUARD KHUSUS KOIN MATANG / BERUMUR (>= 120 Menit)
STALL_GUARD_AGED_MIN_PROFIT_PERCENT = 1.05
STALL_GUARD_AGED_PULLBACK_PERCENT = 0.32
STALL_GUARD_AGED_MIN_EXIT_PROFIT = 0.60

# =============================================================================
# 3b. CHOPPY & SIDEWAYS EXHAUSTION TEBAS ("MENTOK $7 - $11 USD GAKUAT TEBAS")
# =============================================================================
# Filosofi Disiplin User:
# =============================================================================
# CHOPPY SIDEWAYS TEBAS BERJENJANG (FLEXIBLE ADAPTIVE & VOLUME SMART)
# =============================================================================
# Filosofi:
# 1. Koin baru mulai cuan (+0.50% s/d +1.10% / ~$7 s/d $15.4 USD):
#    - Diberi ruang napas LONGGAR (Pullback 0.24%, Wick 38%).
#    - Lilin doji semut tipis (< 0.20%) diabaikan agar tidak kaget/prematur.
# 2. Kondisi Khusus Volume (Whale Climax Alert):
#    - Jika volume meledak >= 1.6x + jarum reject >= 24%: TEBAS SEKETIKA (CLIMAX_VOL_TEBAS)!
# 3. Pucuk Matang (>= +1.10% / ~$15.4 USD):
#    - Disiplin ketat tebas pucuk (Pullback 0.18%, Wick 26%) mengunci profit tertinggi!
CHOPPY_SIDEWAYS_TEBAS_ENABLED = True          # Tebas koin gakuat khusus saat pasar choppy/sideways
CHOPPY_TEBAS_MIN_PEAK_PERCENT = 0.50          # Mulai aktif saat peak >= +0.50% (~$7 USD)
CHOPPY_TEBAS_MATURE_PERCENT = 1.10            # Target pucuk matang (+1.10% / ~$15.4 USD) -> REKOR TERTINGGI!

# Fase 1: Ruang Napas Awal (+0.50% s/d +1.10% / ~$7 s/d $15.4 USD) -> ANTI PREMATUR
CHOPPY_TEBAS_EARLY_PULLBACK = 0.24            # Napas longgar 0.24% dari peak
CHOPPY_TEBAS_EARLY_WICK = 38.0                # Hanya tebas jika wick reject ekstrem >= 38%
CHOPPY_TEBAS_MIN_CANDLE_RANGE = 0.20          # Abaikan wick jika range lilin < 0.20% (anti false rejection doji tipis)

# Fase 2: Pucuk Matang Disiplin (>= +1.10% / ~$15.4 USD) -> AMANKAN CUAN PUNCAK
CHOPPY_TEBAS_MATURE_PULLBACK = 0.18           # Disiplin ketat melorot >= 0.18%
CHOPPY_TEBAS_MATURE_WICK = 26.0               # Disiplin tebas jika ada wick reject >= 26%

# Kondisi Khusus Volume: Whale Climax Dump Alert
CHOPPY_TEBAS_CLIMAX_VOL_RATIO = 1.6           # Volume meledak >= 1.6x rata-rata
CHOPPY_TEBAS_CLIMAX_WICK = 24.0               # Rejection wick >= 24% saat volume meledak = bandar dumping masif!
CHOPPY_TEBAS_MIN_EXIT_PROFIT_USD = 4.0        # Menjamin saat tebas minimal tetap cuan bersih ~$4+ USD


# =============================================================================
# CHOPPY AUTO-BEP & ADAPTIVE REGIME EXIT (PENGAMAN PASAR CHOPPY VS GACOR)
# =============================================================================
# Filosofi:
# 1. Pintu Masuk (Entry): Tetap bebas tanpa dicekik agar tidak ketinggalan kereta.
# 2. Pasca-Entry (Setelah Masuk):
#    - Bot mengecek nilai ADX 15m & arah kekuatan (+DI vs -DI) koin.
#    - Jika ADX < 22 (Pasar Choppy/Sideways) ATAU BTC Sideways/Chop:
#      * Koin berada di Mode Choppy:
#        a. AUTO-BEP LOCK: Begitu floating profit >= +0.50%, bot OTOMATIS mengunci
#           Stop Loss ke level BEP Murni (+0.08% cover fee). Memberi ruang napas
#           longgar tanpa mencekik koin prematur, modal terlindungi 100%!
#        b. CHOPPY PARTIAL TP: Target Partial TP 1 (CP1) di +0.85% untuk langsung
#           mengunci 50% muatan kas ke dompet (cuan pasti ~$1.65 - $1.80 USDT).
#        c. Sisa 50% (Moonbag) dikawal trailing berjarak -0.22% mengejar +1.5% s/d +2.0%+.
#    - Jika ADX >= 25 dan DI searah (Pasar Gacor / Strong Trend):
#      * Mode Gacor: Target CP1 normal (+1.45% s/d +1.80%) dengan Trailing Ratchet lega.
CHOPPY_AUTO_BEP_ENABLED = True
CHOPPY_ADX_THRESHOLD = 22.0                  # Batas ADX 15m koin: di bawah 22.0 diklasifikasikan sebagai Choppy/Lemas
CHOPPY_BEP_TRIGGER_PERCENT = 0.50            # Floating profit minimal +0.50% untuk langsung kunci stop ke BEP
CHOPPY_BEP_LOCK_PERCENT = 0.08               # Level stop BEP murni (+0.08% untuk menutup biaya trading fee tanpa mencekik)
CHOPPY_CP1_PERCENT = 0.85                    # Target Partial TP 1 koin choppy (+0.85%) agar lekas bungkus cuan pasti
CHOPPY_TP1_PERCENT = 0.85                    # Alias TP1 koin choppy (+0.85%)

# =============================================================================
# TARGET DISIPLIN HARIAN (COMPOUNDING SNOWBALL) & STEPPED RATCHET CHOPPY
# =============================================================================
DAILY_TARGET_PROFIT_PERCENT = 10.0            # Target cuan harian dinamis (10% dari modal akun)
CHOPPY_RATCHET_TRIGGER_PERCENT = 0.50         # Stepped ratchet mulai trailing di pasar choppy mulai +0.50%
CHOPPY_RATCHET_TRAIL_PERCENT = 0.38           # Jarak kawal lega 0.38% dari peak (napas aman, anti kejilat kocokan!)
MOONBAG_TARGET_USD = 20.0                    # Target puncak profit satu trade ($20 USD | ~+2.72% harga)

# =============================================================================
# STAGNATION & TIME-STOP LOSS GUARDS (PENGAMAN KALAH SEMUA REGIME)
# =============================================================================
# Lapis 1: Stagnant Early Cut (Fleksibel Smart Invalidation Cut)
# =============================================================================
STAGNANT_EARLY_CUT_ENABLED = True             # Potong dini koin lemas mandul (Fleksibel Smart Cut)
STAGNANT_EARLY_CUT_MINUTES = 20               # Jika sudah berjalan 20 menit (> 1.3 lilin 15m)
STAGNANT_EARLY_CUT_MAX_HP = 0.20              # Dan tidak pernah naik sama sekali (highest profit < +0.20%)
STAGNANT_EARLY_CUT_LOSS_THRESHOLD = -0.58     # Dan floating minus <= -0.58% -> Potong dini koin lemas sebelum kena hard stop -0.75% (rugi mentok ~$7.50 s/d ~$7.80)

# Lapis 2: Absolute Stagnation Time-Stop (> 80 Menit / > 5 Lilin 15m)
# CATATAN AUDIT 312 TRADES: 39 trade cuan butuh 50-90m (+120 USDT). Dilonggarkan ke 80m
# dan hanya tebas jika profit <= -0.55% (koin konsolidasi minus tipis -0.10% spt XLM/TAO aman!).
STAGNANT_TIMESTOP_ENABLED = True              # Tutup posisi jika koin tersandera > 80 menit
STAGNANT_TIMESTOP_MINUTES = 80                # Jika posisi mengambang > 80 menit (> 5 lilin 15m)
STAGNANT_TIMESTOP_MAX_LOSS = -0.55            # Hanya jika minus lebih dalam dari -0.55% (bukan 0.0%)
STAGNANT_TIMESTOP_MAX_HP = 0.35               # Dan tak ada daya dorong momentum (highest profit < +0.35%)

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
TIME_PROGRESSIVE_BEP_STOP = 0.18               # Stop BEP murni (+0.18% cover fee exchange)

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
# - DEAD-CAT BOUNCE TEBAS PREMATUR:
#   Hasil bedah 228 trade membuktikan bahwa tebas pasar prematur pada goyangan jarum -0.7% s/d -0.9%
#   menyebabkan kekalahan 30 trade beruntun (-$229.66 USDT), dan koin-koin juara (NIGHT, MANA, CTSI, STRK)
#   langsung meledak cuan +2% s/d +15% tepat setelah dipotong!
#   Maka DEAD_CAT_BOUNCE_CUT_ENABLED dimatikan agar koin bernafas membuktikan arahnya.
BOUNCE_FAILURE_GUARD_ENABLED = True
DEAD_CAT_BOUNCE_CUT_ENABLED = False              # Nonaktifkan tebas prematur saat wick goyang biasa!
BOUNCE_FAILURE_REQUIRE_EMA55_TEST = True     # Rem hanya aktif jika harga sudah menguji/menusuk ke batas lantai EMA 55 (Safe Pocket)
BOUNCE_FAILURE_EMA_BUFFER_PERCENT = 0.52     # Toleransi buffer lantai EMA 55 (0.52% di bawah/atas EMA 55)
BOUNCE_FAILURE_MIN_DRAWDOWN_PERCENT = -0.50  # Drawdown minimal terhadap entry untuk konfirmasi dip nyata (sebelum kena batas keras -0.75%)
BOUNCE_FAILURE_MIN_REBOUND_PERCENT = 0.35    # Sempat berhasil mantul naik minimal +0.35% harga dari dasar jurang
BOUNCE_FAILURE_SLIPPAGE_TOLERANCE = 0.25     # Jika setelah mantul harga melorot kembali >= 0.25% dari puncak pantulan -> TEBAS!
BOUNCE_FAILURE_MAX_LOSS_PERCENT = -0.75      # Batas minus harga maksimal keras (-0.75% harga | Sweet Spot terbaik, rugi mentok ~$9.80)
MAX_LOSS_USDT_CAP = -4.20                    # Batas kerugian dolar nominal maksimal (-$4.20 USDT) mutlak!

# =============================================================================
# FLEXIBLE MACRO LIQUIDITY GATE (BTC + BTCDOM ADAPTIVE)
# =============================================================================
FLEXIBLE_MACRO_ENABLED = True                    # Aktifkan perisai makro likuiditas adaptif
DOM_SYMBOL = "BTCDOM/USDT"                       # Simbol dominansi BTC
MACRO_ADVERSE_MIN_SCORE = 90                     # Syarat score minimal jika melawan arah makro
MACRO_ADVERSE_MIN_VOL_RATIO = 1.35               # Syarat lonjakan volume minimal jika melawan makro
MACRO_ADVERSE_EXTRA_OFFSET = 0.05                # Tambahan diskon limit order (+0.05%) saat lawan arah makro

# =============================================================================
# PANIC VOLUME DUMP CUT (Deteksi Air Terjun vs Gojekan Jarum di Lilin 1m)
# =============================================================================
# Filosofi:
# - Jika harga jebol di bawah EMA 55 saat drawdown >= -0.75%:
#   Bot mengecek volume lilin 1 menit terakhir.
# - Jika Volume >= 2.5x rata-rata 1m (Smart Money air terjun nyata) -> TEBAS INSTAN tanpa nunggu 15m!
# - Jika Volume kecil/biasa (< 2.5x) -> TAHAN! Ini gojekan jarum likuidasi, beri ruang mantul!
# CATATAN AUDIT 312 TRADES: Dinonaktifkan (False) karena jarum likuidasi 1m sering memotong koin prematur (seperti SUI).
# Pengaman batas bawah sepenuhnya dipegang oleh Hard Loss Cap (-1.05% / mentok -$3.90).
PANIC_VOLUME_CUT_ENABLED = False
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
EMERGENCY_SL_PERCENT = 18.0         # Pasang di -25% (sebelum likuidasi leverage 3x ~33%)

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
MIN_VOLUME_RATIO = 0.80         # Minimal volume 0.80x dari average 20 SMA (Smart Money validasi)
MAX_PULLBACK_VOLUME_RATIO = 3.20 # Batas atas volume lilin entry (mencegah buying/selling climax trap & whale dump)

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
    "龙虾/USDT", "龙虾",  # High-spread volatile meme

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

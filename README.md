# 🤖 Binance Futures Trading Bot

Bot trading otomatis untuk Binance Futures dengan strategi single-position, confluence signal, dan stepped trailing stop.

## ✨ Fitur Utama

| Fitur | Deskripsi |
|-------|-----------|
| **Single Position** | Hanya 1 posisi aktif pada satu waktu |
| **3x Leverage** | Leverage fixed 3x dengan isolated margin |
| **Smart Scanner** | Otomatis cari koin trending (top 50 volume, filter volatilitas & spread) |
| **Confluence Signal** | Multi-indikator: EMA + MACD + RSI + ADX + Volume dengan scoring system |
| **Multi-Timeframe** | 4H trend filter + 1H entry signal |
| **Limit Order Entry** | Antri di -1% (LONG) / +1% (SHORT) dari harga — bukan market price |
| **Order Timeout** | Cancel limit order jika tidak terisi dalam 30 menit |
| **Stepped Trailing Stop** | Checkpoint 3% → stop 1%, 6% → 3%, 9% → 6%, dst |
| **Signal Reversal Guard** | Auto close jika signal berbalik arah |
| **Emergency Stop Loss** | Safety net di -25% (sebelum likuidasi) |
| **Web Dashboard** | Monitoring real-time via browser |
| **State Recovery** | Bot bisa restart tanpa kehilangan state |

## 📦 Instalasi

```bash
# 1. Clone/masuk ke directory
cd "Binance Bot"

# 2. Buat virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Setup API keys
cp .env.example .env
# Edit .env dan masukkan API key Binance kamu
```

## ⚙️ Konfigurasi

Edit file `.env`:

```env
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
TRADING_MODE=testnet    # Ganti ke 'live' untuk real trading
DASHBOARD_PORT=5000
```

Konfigurasi detail lainnya ada di `config.py`.

## 🚀 Menjalankan Bot

```bash
# Bot saja
python run.py

# Bot + Dashboard
python run.py --dashboard

# Dashboard saja (monitoring)
python run.py --dash-only
```

Dashboard bisa diakses di: `http://localhost:5000`

## 📊 Strategi Trading

### Signal Engine (Confluence)

Bot menggunakan sistem scoring 0-100 dengan minimum score 70 untuk entry:

| Indikator | Bobot | Kondisi LONG |
|-----------|-------|-------------|
| EMA 21/55/200 | 25 poin | Fast > Slow > Trend |
| MACD (12,26,9) | 20 poin | MACD > Signal line |
| RSI (14) | 20 poin | 35 < RSI < 65 |
| ADX (14) | 20 poin | ADX > 25 (trending) |
| Volume | 15 poin | Volume > SMA(20) |
| Higher TF (4H) | ±10 bonus | Konfirmasi arah |

### Trailing Stop (Stepped)

```
Profit 3%  → Stop di 1%  (lock profit 1%)
Profit 6%  → Stop di 3%  (lock profit 3%)
Profit 9%  → Stop di 6%  (lock profit 6%)
Profit 12% → Stop di 9%  (lock profit 9%)
... dst setiap kelipatan 3%
```

### Reversal Guard

Jika signal berubah ke arah berlawanan (butuh 2 dari 3 kondisi):
1. EMA death/golden cross
2. MACD cross
3. RSI extreme reversal

Bot akan **close market** posisi dan cari signal baru.

## 📁 Struktur File

```
├── .env.example          # Template API keys
├── .env                  # API keys (gitignored)
├── requirements.txt      # Dependencies
├── README.md             # Dokumentasi ini
├── run.py                # Entry point
├── config.py             # Konfigurasi
├── bot.py                # Main loop orchestrator
├── scanner.py            # Market scanner
├── signal_engine.py      # Signal analysis
├── order_manager.py      # Order lifecycle
├── trailing_manager.py   # Trailing stop logic
├── reversal_guard.py     # Auto close on reversal
├── state_manager.py      # State persistence
├── logger_setup.py       # Logging setup
├── dashboard.py          # Web dashboard
└── logs/                 # Log files
```

## ⚠️ Disclaimer

> **Bot trading otomatis memiliki risiko kehilangan modal.**
> Leverage 3x memperbesar risiko. Gunakan hanya modal yang siap untuk kehilangan.
> Selalu test di **testnet** terlebih dahulu sebelum menggunakan dana riil.
> Past performance does not guarantee future results.

## 🔒 Keamanan

- API keys disimpan di `.env` (jangan commit ke git!)
- Gunakan API key dengan permission **Futures only** + **IP whitelist**
- Jangan berikan permission **Withdraw**

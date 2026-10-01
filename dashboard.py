"""
Web Dashboard
=============
Simple Flask dashboard untuk monitoring bot secara real-time.
Menampilkan: status, posisi, orders, trailing stop, trade history.
"""

import os
import json
import time
from datetime import datetime, timezone
import ccxt
from flask import Flask, render_template_string, jsonify
import config
from state_manager import StateManager


app = Flask(__name__)
state_manager = StateManager()

# =============================================================================
# HTML Template
# =============================================================================
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Binance Futures Bot Dashboard</title>
    <meta name="description" content="Real-time monitoring dashboard for Binance Futures Trading Bot">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', sans-serif;
            background: #0a0e17;
            color: #e2e8f0;
            min-height: 100vh;
        }
        
        .header {
            background: linear-gradient(135deg, #1a1f2e 0%, #0f1420 100%);
            border-bottom: 1px solid rgba(255,255,255,0.05);
            padding: 20px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header h1 {
            font-size: 1.4rem;
            font-weight: 700;
            background: linear-gradient(135deg, #f0b90b, #fcd535);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .header .status-badge {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        
        .status-running .status-dot { background: #22c55e; box-shadow: 0 0 10px rgba(34,197,94,0.5); }
        .status-running { background: rgba(34,197,94,0.1); border: 1px solid rgba(34,197,94,0.3); color: #22c55e; }
        
        .status-idle .status-dot { background: #eab308; box-shadow: 0 0 10px rgba(234,179,8,0.5); }
        .status-idle { background: rgba(234,179,8,0.1); border: 1px solid rgba(234,179,8,0.3); color: #eab308; }
        
        .status-stopped .status-dot { background: #ef4444; }
        .status-stopped { background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3); color: #ef4444; }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
        }
        
        .card {
            background: linear-gradient(145deg, #151a28, #111827);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 16px;
            padding: 24px;
            transition: all 0.3s ease;
        }
        
        .card:hover {
            border-color: rgba(240,185,11,0.2);
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }
        
        .card-title {
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #64748b;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .card-title .icon {
            font-size: 1.1rem;
        }
        
        .stat-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 16px;
        }
        
        .stat-item {
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
            padding: 16px;
        }
        
        .stat-label {
            font-size: 0.75rem;
            color: #64748b;
            margin-bottom: 4px;
        }
        
        .stat-value {
            font-size: 1.3rem;
            font-weight: 700;
        }
        
        .stat-value.positive { color: #22c55e; }
        .stat-value.negative { color: #ef4444; }
        .stat-value.neutral { color: #f0b90b; }
        
        .position-card {
            grid-column: span 2;
        }
        
        .position-info {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 12px;
        }
        
        .trade-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
        }
        
        .trade-table th {
            text-align: left;
            padding: 10px 12px;
            color: #64748b;
            font-weight: 600;
            border-bottom: 1px solid rgba(255,255,255,0.06);
        }
        
        .trade-table td {
            padding: 10px 12px;
            border-bottom: 1px solid rgba(255,255,255,0.03);
        }
        
        .badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        
        .badge-long { background: rgba(34,197,94,0.15); color: #22c55e; }
        .badge-short { background: rgba(239,68,68,0.15); color: #ef4444; }
        
        .no-data {
            text-align: center;
            padding: 30px;
            color: #475569;
            font-style: italic;
        }
        
        .trailing-progress {
            margin-top: 12px;
        }
        
        .progress-bar {
            width: 100%;
            height: 8px;
            background: rgba(255,255,255,0.05);
            border-radius: 4px;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            border-radius: 4px;
            background: linear-gradient(90deg, #f0b90b, #22c55e);
            transition: width 0.5s ease;
        }
        
        .checkpoint-labels {
            display: flex;
            justify-content: space-between;
            margin-top: 6px;
            font-size: 0.7rem;
            color: #64748b;
        }
        
        .full-width { grid-column: 1 / -1; }
        
        .refresh-info {
            text-align: center;
            padding: 10px;
            color: #475569;
            font-size: 0.75rem;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 Binance Futures Bot</h1>
        <div id="statusBadge" class="status-badge status-idle">
            <div class="status-dot"></div>
            <span id="statusText">Loading...</span>
        </div>
    </div>
    
    <div class="container">
        <!-- Summary Card -->
        <div class="card">
            <div class="card-title"><span class="icon">📊</span> Binance Wallet & Performance</div>
            <div class="stat-grid">
                <div class="stat-item">
                    <div class="stat-label">Wallet Balance (Binance)</div>
                    <div class="stat-value neutral" id="walletBalance" style="color: #f0b90b; font-weight: 700;">-</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Today Net Profit (Real)</div>
                    <div class="stat-value" id="todayNetProfit">-</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Total Trades / Win Rate</div>
                    <div class="stat-value neutral" id="totalTrades">-</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">All-Time Recorded PnL</div>
                    <div class="stat-value" id="totalProfit">-</div>
                </div>
            </div>
        </div>
        
        <!-- Config Card -->
        <div class="card">
            <div class="card-title"><span class="icon">⚙️</span> Configuration</div>
            <div class="stat-grid">
                <div class="stat-item">
                    <div class="stat-label">Leverage</div>
                    <div class="stat-value neutral" id="leverage">-</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Entry Offset</div>
                    <div class="stat-value neutral" id="entryOffset">-</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Checkpoint</div>
                    <div class="stat-value neutral" id="checkpoint">-</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Emergency SL</div>
                    <div class="stat-value" id="emergencySL">-</div>
                </div>
            </div>
        </div>
        
        <!-- Active Position Card -->
        <div class="card full-width">
            <div class="card-title"><span class="icon">📈</span> Active Position</div>
            <div id="positionContent">
                <div class="no-data">No active position</div>
            </div>
        </div>
        
        <!-- Trailing Stop Card -->
        <div class="card">
            <div class="card-title"><span class="icon">🛡️</span> Trailing Stop</div>
            <div id="trailingContent">
                <div class="no-data">No trailing stop active</div>
            </div>
        </div>
        
        <!-- Last Signal Card -->
        <div class="card">
            <div class="card-title"><span class="icon">📡</span> Last Signal</div>
            <div id="signalContent">
                <div class="no-data">No signal detected yet</div>
            </div>
        </div>
        
        <!-- Trade History Card -->
        <div class="card full-width">
            <div class="card-title"><span class="icon">📜</span> Trade History</div>
            <div id="historyContent">
                <div class="no-data">No trades yet</div>
            </div>
        </div>
    </div>
    
    <div class="refresh-info">Auto-refresh every 5 seconds</div>
    
    <script>
        async function fetchState() {
            try {
                const res = await fetch('/api/state');
                const data = await res.json();
                updateDashboard(data);
            } catch (err) {
                console.error('Fetch error:', err);
            }
        }
        
        function updateDashboard(state) {
            // Status
            const badge = document.getElementById('statusBadge');
            const statusText = document.getElementById('statusText');
            const status = state.bot_status || 'idle';
            statusText.textContent = status.toUpperCase();
            badge.className = 'status-badge ' + 
                (status === 'idle' ? 'status-idle' : 
                 status === 'stopped' ? 'status-stopped' : 'status-running');
            
            // Summary & Binance Reality
            const walletBal = state.binance_wallet_balance !== undefined ? state.binance_wallet_balance : (state.available_usdt || 0);
            document.getElementById('walletBalance').textContent = '$' + Number(walletBal).toFixed(2) + ' USDT';
            
            const todayNet = state.today_net_pnl !== undefined ? state.today_net_pnl : 0;
            const todayEl = document.getElementById('todayNetProfit');
            todayEl.textContent = (todayNet >= 0 ? '+' : '') + Number(todayNet).toFixed(2) + ' USDT';
            todayEl.className = 'stat-value ' + (todayNet >= 0 ? 'positive' : 'negative');
            
            const wins = state.win_count || 0;
            const total = state.total_trades || 0;
            const winRate = total > 0 ? ((wins / total) * 100).toFixed(1) : '0';
            document.getElementById('totalTrades').textContent = `${total} (${winRate}% Win)`;
            
            const profit = state.total_profit || 0;
            const profitEl = document.getElementById('totalProfit');
            profitEl.textContent = (profit >= 0 ? '+' : '') + Number(profit).toFixed(2) + ' USDT';
            profitEl.className = 'stat-value ' + (profit >= 0 ? 'positive' : 'negative');
            
            // Config
            document.getElementById('leverage').textContent = '{{ leverage }}x';
            document.getElementById('entryOffset').textContent = '{{ entry_offset }}';
            document.getElementById('checkpoint').textContent = '{{ checkpoint }}%';
            document.getElementById('emergencySL').textContent = '{{ emergency_sl }}';
            
            // Position
            const posContent = document.getElementById('positionContent');
            if (state.active_position) {
                const pos = state.active_position;
                posContent.innerHTML = `
                    <div class="position-info">
                        <div class="stat-item">
                            <div class="stat-label">Symbol</div>
                            <div class="stat-value neutral">${pos.symbol}</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-label">Side</div>
                            <div class="stat-value">
                                <span class="badge ${pos.side === 'long' ? 'badge-long' : 'badge-short'}">
                                    ${pos.side.toUpperCase()}
                                </span>
                            </div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-label">Entry Price</div>
                            <div class="stat-value neutral">${pos.entry_price}</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-label">Amount</div>
                            <div class="stat-value neutral">${pos.amount}</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-label">Highest Profit</div>
                            <div class="stat-value positive">${(pos.highest_profit_pct || 0).toFixed(2)}%</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-label">Entry Time</div>
                            <div class="stat-value neutral" style="font-size:0.9rem">${new Date(pos.entry_time).toLocaleString()}</div>
                        </div>
                    </div>
                `;
            } else {
                posContent.innerHTML = '<div class="no-data">No active position</div>';
            }
            
            // Trailing Stop
            const trailContent = document.getElementById('trailingContent');
            if (state.trailing_stop) {
                const trail = state.trailing_stop;
                const cp = state.current_checkpoint || 0;
                const progress = Math.min(cp / 15 * 100, 100);
                trailContent.innerHTML = `
                    <div class="stat-grid">
                        <div class="stat-item">
                            <div class="stat-label">Checkpoint</div>
                            <div class="stat-value positive">${cp}%</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-label">Stop Price</div>
                            <div class="stat-value neutral">${trail.stop_price}</div>
                        </div>
                    </div>
                    <div class="trailing-progress">
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${progress}%"></div>
                        </div>
                        <div class="checkpoint-labels">
                            <span>0%</span><span>3%</span><span>6%</span><span>9%</span><span>12%</span><span>15%+</span>
                        </div>
                    </div>
                `;
            } else {
                trailContent.innerHTML = '<div class="no-data">No trailing stop active</div>';
            }
            
            // Last Signal
            const sigContent = document.getElementById('signalContent');
            if (state.last_signal) {
                const sig = state.last_signal;
                sigContent.innerHTML = `
                    <div class="stat-grid">
                        <div class="stat-item">
                            <div class="stat-label">Symbol</div>
                            <div class="stat-value neutral">${sig.symbol || '-'}</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-label">Signal</div>
                            <div class="stat-value">
                                <span class="badge ${sig.signal === 'LONG' ? 'badge-long' : 'badge-short'}">
                                    ${sig.signal || '-'}
                                </span>
                            </div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-label">Score</div>
                            <div class="stat-value neutral">${sig.score || '-'}/100</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-label">Time</div>
                            <div class="stat-value neutral" style="font-size:0.85rem">${sig.time ? new Date(sig.time).toLocaleString() : '-'}</div>
                        </div>
                    </div>
                `;
            } else {
                sigContent.innerHTML = '<div class="no-data">No signal detected yet</div>';
            }
            
            // Trade History
            const histContent = document.getElementById('historyContent');
            if (state.trade_history && state.trade_history.length > 0) {
                const recent = state.trade_history.slice(-10).reverse();
                let html = `<table class="trade-table">
                    <thead><tr>
                        <th>Time</th><th>Symbol</th><th>Side</th>
                        <th>Entry</th><th>PnL</th><th>Reason</th>
                    </tr></thead><tbody>`;
                recent.forEach(t => {
                    const pnl = t.pnl || 0;
                    html += `<tr>
                        <td>${t.close_time ? new Date(t.close_time).toLocaleString() : '-'}</td>
                        <td>${t.symbol}</td>
                        <td><span class="badge ${t.side === 'long' ? 'badge-long' : 'badge-short'}">${t.side.toUpperCase()}</span></td>
                        <td>${t.entry_price}</td>
                        <td style="color:${pnl >= 0 ? '#22c55e' : '#ef4444'}">${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}</td>
                        <td>${t.close_reason || '-'}</td>
                    </tr>`;
                });
                html += '</tbody></table>';
                histContent.innerHTML = html;
            } else {
                histContent.innerHTML = '<div class="no-data">No trades yet</div>';
            }
        }
        
        // Initial fetch & auto-refresh
        fetchState();
        setInterval(fetchState, 5000);
    </script>
</body>
</html>
"""


# =============================================================================
# Routes
# =============================================================================

@app.route("/")
def index():
    """Render dashboard page."""
    return render_template_string(
        DASHBOARD_HTML,
        mode=config.TRADING_MODE.upper(),
        leverage=config.LEVERAGE,
        entry_offset=f"{config.HIGH_CONVICTION_OFFSET_PERCENT}% / {config.NORMAL_CONVICTION_OFFSET_PERCENT}%",
        checkpoint=config.TRAILING_CHECKPOINT_PERCENT,
        emergency_sl=f"-{config.EMERGENCY_SL_PERCENT}%" if config.EMERGENCY_SL_ENABLED else "OFF",
    )


_binance_cache = {
    "last_check": 0,
    "wallet_balance": 0.0,
    "today_net_pnl": 0.0,
    "exchange": None
}

def get_live_binance_metrics():
    """Fetch live wallet balance & today net PnL directly from Binance (cached 10s)."""
    global _binance_cache
    now = time.time()
    if now - _binance_cache["last_check"] < 10:
        return _binance_cache["wallet_balance"], _binance_cache["today_net_pnl"]
        
    try:
        if _binance_cache["exchange"] is None:
            _binance_cache["exchange"] = ccxt.binance({
                "apiKey": config.BINANCE_API_KEY,
                "secret": config.BINANCE_API_SECRET,
                "options": {"defaultType": "future"}
            })
        ex = _binance_cache["exchange"]
        bal = ex.fetch_balance()
        wallet_bal = float(bal.get("USDT", {}).get("total", 0.0))
        
        # Hitung Net PnL hari ini (sejak 00:00 UTC)
        now_dt = datetime.now(timezone.utc)
        midnight_utc = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        start_time = int(midnight_utc.timestamp() * 1000)
        
        income_res = ex.fapiPrivateGetIncome({"startTime": start_time, "limit": 1000})
        today_pnl = sum(float(x.get("income", 0)) for x in income_res if x.get("incomeType") == "REALIZED_PNL")
        today_comm = sum(float(x.get("income", 0)) for x in income_res if x.get("incomeType") == "COMMISSION")
        today_net = today_pnl + today_comm
        
        _binance_cache["wallet_balance"] = round(wallet_bal, 2)
        _binance_cache["today_net_pnl"] = round(today_net, 2)
        _binance_cache["last_check"] = now
    except Exception as e:
        pass
        
    return _binance_cache["wallet_balance"], _binance_cache["today_net_pnl"]


@app.route("/api/state")
def api_state():
    """API endpoint untuk state bot."""
    # Reload state dari file (karena bot dan dashboard proses terpisah)
    state_manager.state = state_manager._load_state()
    res = state_manager.get_state()
    
    # Enrich dengan live Binance metrics (saldo kas & cuan riil hari ini)
    w_bal, today_pnl = get_live_binance_metrics()
    res["binance_wallet_balance"] = w_bal
    res["today_net_pnl"] = today_pnl
    
    # Hitung win/loss count
    th = res.get("trade_history", [])
    wins = sum(1 for t in th if float(t.get("pnl", 0)) > 0)
    losses = sum(1 for t in th if float(t.get("pnl", 0)) < 0)
    res["win_count"] = wins
    res["loss_count"] = losses
    res["total_trades"] = len(th)
    
    return jsonify(res)


def run_dashboard():
    """Run dashboard server."""
    print(f"🌐 Dashboard running at http://localhost:{config.DASHBOARD_PORT}")
    app.run(
        host=config.DASHBOARD_HOST,
        port=config.DASHBOARD_PORT,
        debug=False,
        use_reloader=False,
    )


if __name__ == "__main__":
    run_dashboard()

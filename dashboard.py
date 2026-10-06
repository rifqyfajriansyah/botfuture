"""
Web Dashboard (Institutional Cyber Edition)
===========================================
Flask dashboard ultra-modern untuk monitoring Binance Futures Trading Bot secara real-time.
Fitur Unggulan:
- Glassmorphism Dark UI dengan typography Outfit & Inter
- Cuan Harian & Default Target 10% Modal Otomatis (Compounding Snowball)
- Privacy Mode (Eye toggle 👁️ / 🙈) untuk sensor saldo & cuan jadi bintang-bintang (••••••)
- Deteksi Pasar Real-Time: Choppy (Sideways 🦀) vs Trending (Kuat 🌊) berbasis ADX
- Live Unrealized PnL & ROE untuk posisi aktif
- Real-time Trailing Ratchet visual progress
- Responsive untuk mobile & desktop
"""

import os
import json
import time
from datetime import datetime, timezone
import pandas as pd
import numpy as np
import ccxt
from flask import Flask, render_template_string, jsonify
import config
from state_manager import StateManager


app = Flask(__name__)
state_manager = StateManager()

# =============================================================================
# HTML & UI TEMPLATE
# =============================================================================
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Binance Futures Bot - Terminal</title>
    <meta name="description" content="Institutional Real-Time Trading Terminal & Dashboard for Binance Futures Bot">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-base: #070a12;
            --bg-card: rgba(15, 22, 36, 0.75);
            --bg-card-hover: rgba(22, 32, 52, 0.85);
            --border-card: rgba(255, 255, 255, 0.07);
            --border-highlight: rgba(240, 185, 11, 0.25);
            --gold: #f0b90b;
            --gold-gradient: linear-gradient(135deg, #f0b90b 0%, #fcd535 100%);
            --emerald: #10b981;
            --emerald-glow: rgba(16, 185, 129, 0.25);
            --crimson: #f43f5e;
            --crimson-glow: rgba(244, 63, 94, 0.25);
            --cyan: #38bdf8;
            --purple: #a855f7;
            --amber: #f59e0b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --text-dim: #64748b;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', -apple-system, sans-serif;
            background: var(--bg-base);
            background-image: 
                radial-gradient(at 0% 0%, rgba(240, 185, 11, 0.05) 0px, transparent 50%),
                radial-gradient(at 100% 0%, rgba(56, 189, 248, 0.05) 0px, transparent 50%),
                radial-gradient(at 50% 100%, rgba(168, 85, 247, 0.03) 0px, transparent 50%);
            background-attachment: fixed;
            color: var(--text-main);
            min-height: 100vh;
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
        }

        /* Top Navigation Header */
        .header {
            background: rgba(10, 15, 26, 0.85);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-bottom: 1px solid var(--border-card);
            padding: 16px 28px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .header-brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .brand-icon {
            font-size: 1.5rem;
            background: rgba(240, 185, 11, 0.12);
            border: 1px solid rgba(240, 185, 11, 0.3);
            width: 42px;
            height: 42px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .brand-title {
            font-family: 'Outfit', sans-serif;
            font-size: 1.25rem;
            font-weight: 700;
            letter-spacing: -0.3px;
            background: var(--gold-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .brand-subtitle {
            font-size: 0.72rem;
            color: var(--text-muted);
            letter-spacing: 0.8px;
            text-transform: uppercase;
            font-weight: 600;
        }

        .header-controls {
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }

        /* Chop Live Indicator Badge */
        .chop-indicator-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 14px;
            border-radius: 12px;
            font-size: 0.8rem;
            font-weight: 700;
            font-family: 'Outfit', sans-serif;
            letter-spacing: 0.4px;
            transition: all 0.3s ease;
        }

        .badge-trending {
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.35);
            color: #34d399;
            box-shadow: 0 0 12px rgba(16, 185, 129, 0.15);
        }

        .badge-choppy {
            background: rgba(245, 158, 11, 0.12);
            border: 1px solid rgba(245, 158, 11, 0.4);
            color: #fbbf24;
            box-shadow: 0 0 12px rgba(245, 158, 11, 0.15);
        }

        /* Privacy Eye Toggle */
        .privacy-btn {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--border-card);
            color: var(--text-muted);
            padding: 8px 14px;
            border-radius: 12px;
            font-size: 0.82rem;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.25s ease;
        }

        .privacy-btn:hover {
            background: rgba(255, 255, 255, 0.08);
            border-color: rgba(255, 255, 255, 0.2);
            color: var(--text-main);
            transform: translateY(-1px);
        }

        .privacy-btn.active {
            background: rgba(240, 185, 11, 0.1);
            border-color: rgba(240, 185, 11, 0.4);
            color: var(--gold);
        }

        /* Status Badge */
        .status-badge {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.82rem;
            font-weight: 700;
            font-family: 'Outfit', sans-serif;
            letter-spacing: 0.5px;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            animation: pulse-dot 2s infinite ease-in-out;
        }

        .status-running {
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: #34d399;
        }
        .status-running .status-dot { background: #10b981; box-shadow: 0 0 10px #10b981; }

        .status-monitoring {
            background: rgba(56, 189, 248, 0.12);
            border: 1px solid rgba(56, 189, 248, 0.3);
            color: #38bdf8;
        }
        .status-monitoring .status-dot { background: #38bdf8; box-shadow: 0 0 10px #38bdf8; }

        .status-idle {
            background: rgba(234, 179, 8, 0.12);
            border: 1px solid rgba(234, 179, 8, 0.3);
            color: #facc15;
        }
        .status-idle .status-dot { background: #eab308; box-shadow: 0 0 10px #eab308; }

        @keyframes pulse-dot {
            0%, 100% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.3); opacity: 0.5; }
        }

        /* Container Layout */
        .container {
            max-width: 1440px;
            margin: 0 auto;
            padding: 24px;
            display: grid;
            grid-template-columns: repeat(12, 1fr);
            gap: 20px;
        }

        /* Glass Cards */
        .card {
            background: var(--bg-card);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--border-card);
            border-radius: 20px;
            padding: 24px;
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
            position: relative;
            overflow: hidden;
        }

        .card:hover {
            border-color: var(--border-highlight);
            box-shadow: 0 14px 40px rgba(0, 0, 0, 0.35);
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }

        .card-title {
            font-family: 'Outfit', sans-serif;
            font-size: 0.88rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .card-icon {
            font-size: 1.1rem;
        }

        /* Grid Spans */
        .col-4 { grid-column: span 4; }
        .col-6 { grid-column: span 6; }
        .col-8 { grid-column: span 8; }
        .col-12 { grid-column: span 12; }

        @media (max-width: 1100px) {
            .col-4, .col-6, .col-8 { grid-column: span 12; }
        }

        /* Stats Component */
        .stat-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 14px;
        }

        .stat-item {
            background: rgba(255, 255, 255, 0.025);
            border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 14px;
            padding: 16px;
            transition: background 0.2s;
        }

        .stat-item:hover {
            background: rgba(255, 255, 255, 0.04);
        }

        .stat-label {
            font-size: 0.72rem;
            color: var(--text-dim);
            text-transform: uppercase;
            letter-spacing: 0.6px;
            font-weight: 600;
            margin-bottom: 6px;
        }

        .stat-value {
            font-family: 'Outfit', sans-serif;
            font-size: 1.35rem;
            font-weight: 700;
            letter-spacing: -0.3px;
        }

        .stat-value.gold { color: var(--gold); }
        .stat-value.emerald { color: #34d399; }
        .stat-value.crimson { color: #f43f5e; }
        .stat-value.cyan { color: #38bdf8; }
        .stat-value.purple { color: #c084fc; }
        .stat-value.amber { color: #fbbf24; }

        .stat-sub {
            font-size: 0.75rem;
            color: var(--text-dim);
            margin-top: 4px;
            font-weight: 500;
        }

        /* Daily Target Tracker Card */
        .target-card {
            background: linear-gradient(145deg, rgba(16, 26, 44, 0.8), rgba(12, 18, 30, 0.8));
            border: 1px solid rgba(240, 185, 11, 0.15);
        }

        .target-header-action {
            display: flex;
            align-items: center;
            gap: 6px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            padding: 4px 10px;
            font-size: 0.75rem;
            color: var(--text-muted);
            cursor: pointer;
            transition: all 0.2s;
        }

        .target-header-action:hover {
            background: rgba(240, 185, 11, 0.1);
            color: var(--gold);
            border-color: rgba(240, 185, 11, 0.3);
        }

        .target-main-display {
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            margin-bottom: 16px;
        }

        .target-profit-box .amount {
            font-family: 'Outfit', sans-serif;
            font-size: 2.1rem;
            font-weight: 800;
            line-height: 1.1;
        }

        .target-profit-box .label {
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-top: 4px;
        }

        .target-goal-box {
            text-align: right;
        }

        .target-goal-box .goal-val {
            font-family: 'Outfit', sans-serif;
            font-size: 1.1rem;
            font-weight: 700;
            color: var(--gold);
        }

        .target-goal-box .goal-sub {
            font-size: 0.72rem;
            color: var(--text-dim);
        }

        /* Target Progress Bar */
        .target-progress-wrapper {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            height: 14px;
            padding: 2px;
            position: relative;
            overflow: hidden;
            margin-bottom: 12px;
        }

        .target-progress-fill {
            height: 100%;
            border-radius: 10px;
            transition: width 0.8s cubic-bezier(0.16, 1, 0.3, 1), background 0.5s ease;
            position: relative;
        }

        .progress-green {
            background: linear-gradient(90deg, #10b981 0%, #34d399 100%);
            box-shadow: 0 0 12px rgba(16, 185, 129, 0.5);
        }

        .progress-gold {
            background: linear-gradient(90deg, #f0b90b 0%, #fcd535 100%);
            box-shadow: 0 0 12px rgba(240, 185, 11, 0.5);
        }

        .progress-red {
            background: linear-gradient(90deg, #f43f5e 0%, #fb7185 100%);
            box-shadow: 0 0 12px rgba(244, 63, 94, 0.5);
        }

        .target-status-line {
            display: flex;
            justify-content: space-between;
            font-size: 0.75rem;
            font-weight: 600;
        }

        /* Active Position Card */
        .active-position-card {
            border: 1px solid rgba(56, 189, 248, 0.2);
            background: linear-gradient(160deg, rgba(14, 28, 48, 0.85) 0%, rgba(10, 16, 28, 0.9) 100%);
            box-shadow: 0 12px 35px rgba(0, 0, 0, 0.35);
        }

        .pos-header-badges {
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }

        .badge {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            padding: 4px 12px;
            border-radius: 8px;
            font-size: 0.75rem;
            font-weight: 700;
            font-family: 'Outfit', sans-serif;
            letter-spacing: 0.5px;
        }

        .badge-long {
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid rgba(16, 185, 129, 0.4);
            color: #34d399;
        }

        .badge-short {
            background: rgba(244, 63, 94, 0.15);
            border: 1px solid rgba(244, 63, 94, 0.4);
            color: #fb7185;
        }

        .badge-leverage {
            background: rgba(168, 85, 247, 0.15);
            border: 1px solid rgba(168, 85, 247, 0.4);
            color: #c084fc;
        }

        .badge-combat {
            background: rgba(240, 185, 11, 0.15);
            border: 1px solid rgba(240, 185, 11, 0.4);
            color: var(--gold);
        }

        .pos-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 14px;
            margin-top: 16px;
        }

        .pos-pnl-banner {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.07);
            border-radius: 14px;
            padding: 18px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }

        .pnl-big {
            font-family: 'Outfit', sans-serif;
            font-size: 2.2rem;
            font-weight: 800;
            letter-spacing: -0.5px;
        }

        .pnl-roe {
            font-family: 'Outfit', sans-serif;
            font-size: 1.1rem;
            font-weight: 700;
            padding: 4px 12px;
            border-radius: 10px;
        }

        .pnl-roe.positive {
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .pnl-roe.negative {
            background: rgba(244, 63, 94, 0.15);
            color: #fb7185;
            border: 1px solid rgba(244, 63, 94, 0.3);
        }

        /* Trailing Ratchet Visual Step Bar */
        .ratchet-box {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 16px;
            margin-top: 16px;
        }

        .ratchet-header {
            display: flex;
            justify-content: space-between;
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-bottom: 8px;
            font-weight: 600;
        }

        .ratchet-progress {
            width: 100%;
            height: 8px;
            background: rgba(255, 255, 255, 0.06);
            border-radius: 6px;
            overflow: hidden;
            margin-bottom: 8px;
        }

        .ratchet-fill {
            height: 100%;
            border-radius: 6px;
            background: linear-gradient(90deg, #38bdf8 0%, #10b981 100%);
            transition: width 0.5s ease;
        }

        .ratchet-milestones {
            display: flex;
            justify-content: space-between;
            font-size: 0.7rem;
            color: var(--text-dim);
            font-family: 'JetBrains Mono', monospace;
        }

        /* Radar Scanning Empty State */
        .radar-box {
            text-align: center;
            padding: 45px 20px;
            color: var(--text-muted);
        }

        .radar-spinner {
            width: 48px;
            height: 48px;
            border: 2px solid rgba(240, 185, 11, 0.15);
            border-top: 2px solid var(--gold);
            border-radius: 50%;
            margin: 0 auto 16px auto;
            animation: spin 1.2s cubic-bezier(0.5, 0.1, 0.5, 0.9) infinite;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        /* Trade History Table */
        .table-responsive {
            overflow-x: auto;
            margin-top: 6px;
        }

        .history-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.83rem;
            text-align: left;
        }

        .history-table th {
            padding: 12px 14px;
            font-weight: 600;
            color: var(--text-dim);
            text-transform: uppercase;
            font-size: 0.7rem;
            letter-spacing: 0.8px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        }

        .history-table td {
            padding: 12px 14px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.03);
            color: var(--text-main);
            font-family: 'Inter', sans-serif;
        }

        .history-table tr:hover td {
            background: rgba(255, 255, 255, 0.02);
        }

        .font-mono {
            font-family: 'JetBrains Mono', monospace !important;
        }

        /* Footer Info */
        .footer-info {
            text-align: center;
            padding: 24px;
            font-size: 0.75rem;
            color: var(--text-dim);
            display: flex;
            justify-content: center;
            gap: 20px;
            align-items: center;
        }

        .footer-dot {
            width: 4px;
            height: 4px;
            border-radius: 50%;
            background: var(--text-dim);
        }

        /* Modal Edit Target */
        .modal-overlay {
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.75);
            backdrop-filter: blur(8px);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 999;
        }

        .modal-card {
            background: #0f172a;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 18px;
            padding: 24px;
            width: 90%;
            max-width: 400px;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
        }

        .modal-title {
            font-family: 'Outfit', sans-serif;
            font-size: 1.15rem;
            font-weight: 700;
            margin-bottom: 8px;
            color: var(--text-main);
        }

        .modal-hint {
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-bottom: 16px;
            line-height: 1.4;
        }

        .modal-input {
            width: 100%;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 10px;
            padding: 10px 14px;
            color: var(--gold);
            font-family: 'Outfit', sans-serif;
            font-size: 1.25rem;
            font-weight: 700;
            margin-bottom: 14px;
            outline: none;
        }

        .modal-input:focus {
            border-color: var(--gold);
        }

        .modal-buttons {
            display: flex;
            gap: 10px;
            justify-content: flex-end;
            flex-wrap: wrap;
        }

        .btn-cancel {
            background: transparent;
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: var(--text-muted);
            padding: 8px 14px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            font-size: 0.8rem;
        }

        .btn-default-10 {
            background: rgba(240, 185, 11, 0.12);
            border: 1px solid rgba(240, 185, 11, 0.4);
            color: var(--gold);
            padding: 8px 14px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 700;
            font-size: 0.8rem;
        }

        .btn-save {
            background: var(--gold);
            border: none;
            color: #000;
            padding: 8px 18px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 700;
            font-size: 0.85rem;
        }
    </style>
</head>
<body>

    <!-- Top Sticky Header -->
    <header class="header">
        <div class="header-brand">
            <div class="brand-icon">⚡</div>
            <div>
                <div class="brand-title">BINANCE FUTURES TERMINAL</div>
                <div class="brand-subtitle">Institutional TPLR Engine • {{ leverage }}x Isolated</div>
            </div>
        </div>

        <div class="header-controls">
            <!-- Choppy vs Trending Live Badge -->
            <div id="chopBadge" class="chop-indicator-badge badge-trending">
                <span id="chopIcon">🌊</span>
                <span id="chopText">TRENDING (ADX 67.4)</span>
            </div>

            <!-- Privacy Toggle Button -->
            <button class="privacy-btn" id="privacyBtn" onclick="togglePrivacyMode()" title="Sembunyikan/Tampilkan Saldo & Angka Dolar">
                <span id="privacyIcon">👁️</span>
                <span id="privacyText">Saldo Tampil</span>
            </button>

            <!-- Status Indicator -->
            <div id="statusBadge" class="status-badge status-idle">
                <div class="status-dot"></div>
                <span id="statusText">LOADING...</span>
            </div>
        </div>
    </header>

    <!-- Main Content Grid -->
    <main class="container">

        <!-- 1. WALLET BALANCE & EQUITY CARD -->
        <section class="card col-4">
            <div class="card-header">
                <div class="card-title">
                    <span class="card-icon">💰</span> Binance Futures Wallet
                </div>
                <span class="badge badge-leverage">{{ leverage }}x Leverage</span>
            </div>
            
            <div class="stat-item" style="margin-bottom: 14px; padding: 18px;">
                <div class="stat-label">Total Saldo Dompet (USDT)</div>
                <div class="stat-value gold font-mono" id="walletBalance" style="font-size: 1.9rem;">-</div>
                <div class="stat-sub">Saldo terverifikasi langsung dari bursa Binance</div>
            </div>

            <div class="stat-grid">
                <div class="stat-item">
                    <div class="stat-label">Status Margin</div>
                    <div class="stat-value cyan" style="font-size: 1.05rem;">ISOLATED</div>
                    <div class="stat-sub">Anti-liquidate saldo luar</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Alokasi Trade</div>
                    <div class="stat-value purple" style="font-size: 1.05rem;">90% Modal</div>
                    <div class="stat-sub">Maksimalisasi profit</div>
                </div>
            </div>
        </section>

        <!-- 2. DAILY PROFIT & TARGET TRACKER (10% MODAL DEFAULT) -->
        <section class="card col-4 target-card">
            <div class="card-header">
                <div class="card-title">
                    <span class="card-icon">🎯</span> Target Cuan Harian
                </div>
                <button class="target-header-action" onclick="openTargetModal()">
                    <span>✏️ Ubah Target</span>
                </button>
            </div>

            <div class="target-main-display">
                <div class="target-profit-box">
                    <div class="amount font-mono" id="todayNetProfit">-</div>
                    <div class="label">Net Cuan Hari Ini (UTC Realized)</div>
                </div>
                <div class="target-goal-box">
                    <div class="goal-val font-mono" id="targetGoalDisplay">$26.50 USDT</div>
                    <div class="goal-sub" id="targetGoalSub">Target Harian (10% Modal)</div>
                </div>
            </div>

            <!-- Animated Progress Bar -->
            <div class="target-progress-wrapper">
                <div class="target-progress-fill progress-gold" id="targetProgressFill" style="width: 0%;"></div>
            </div>

            <div class="target-status-line">
                <span id="targetStatusText" style="color: var(--text-muted);">Menghitung progres...</span>
                <span id="targetPercentText" class="font-mono" style="color: var(--gold);">0%</span>
            </div>
        </section>

        <!-- 3. PERFORMANCE STATS & CHOPPY / TREND CONDITION -->
        <section class="card col-4">
            <div class="card-header">
                <div class="card-title">
                    <span class="card-icon">📊</span> Performa & Regime Pasar
                </div>
                <span class="badge badge-long" id="winRateBadge">0% Win Rate</span>
            </div>

            <div class="stat-grid">
                <div class="stat-item">
                    <div class="stat-label">Kondisi Pasar (Trend vs Chop)</div>
                    <div class="stat-value" id="marketChopVal" style="font-size: 1.05rem;">-</div>
                    <div class="stat-sub" id="marketChopSub">Menghitung ADX 15m...</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Total Trade Selesai</div>
                    <div class="stat-value" id="totalTradesCount">-</div>
                    <div class="stat-sub" id="winLossDetail">0 Menang / 0 Kalah</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">All-Time Bot PnL</div>
                    <div class="stat-value font-mono" id="allTimeProfit">-</div>
                    <div class="stat-sub">Sejak awal aktivasi</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Monitoring Loop</div>
                    <div class="stat-value gold" style="font-size: 1.05rem;" id="combatLoopText">Combat 2.5s</div>
                    <div class="stat-sub">Anti-slippage guard</div>
                </div>
            </div>
        </section>

        <!-- 4. ACTIVE POSITION (FULL WIDTH HERO) -->
        <section class="card col-12 active-position-card" id="activePositionCard">
            <div class="card-header">
                <div class="card-title">
                    <span class="card-icon">⚡</span> Posisi Aktif Saat Ini
                </div>
                <div class="pos-header-badges" id="posHeaderBadges">
                    <span class="badge badge-leverage">{{ leverage }}x Isolated</span>
                </div>
            </div>

            <div id="positionContent">
                <div class="radar-box">
                    <div class="radar-spinner"></div>
                    <div style="font-weight: 600; color: var(--text-main); font-size: 0.95rem;">Sedang Memindai Pasar...</div>
                    <div style="font-size: 0.8rem; margin-top: 4px;">Scanner siap menangkap setup Grade A+ pullback di Binance Futures</div>
                </div>
            </div>
        </section>

        <!-- 5. ENGINE CONFIGURATION -->
        <section class="card col-6">
            <div class="card-header">
                <div class="card-title">
                    <span class="card-icon">🛡️</span> Sistem Proteksi & Parameter
                </div>
            </div>
            <div class="stat-grid">
                <div class="stat-item">
                    <div class="stat-label">Cutloss Threshold</div>
                    <div class="stat-value crimson">Murni -1.15%</div>
                    <div class="stat-sub">Persentase harga koin</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Mode Siaga Tempur</div>
                    <div class="stat-value gold">Loop 2.5s</div>
                    <div class="stat-sub">Aktif saat floating minus</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Trailing Ratchet</div>
                    <div class="stat-value emerald">Dynamic ATR</div>
                    <div class="stat-sub">Kawal cuan sampai pucuk</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Emergency SL Bursa</div>
                    <div class="stat-value cyan">{{ emergency_sl }}</div>
                    <div class="stat-sub">Jauh di atas likuidasi</div>
                </div>
            </div>
        </section>

        <!-- 6. LAST DETECTED SIGNAL -->
        <section class="card col-6">
            <div class="card-header">
                <div class="card-title">
                    <span class="card-icon">📡</span> Sinyal Terakhir Terdeteksi
                </div>
            </div>
            <div id="signalContent">
                <div style="color: var(--text-dim); text-align: center; padding: 25px;">Belum ada sinyal terdeteksi</div>
            </div>
        </section>

        <!-- 7. RECENT TRADE HISTORY -->
        <section class="card col-12">
            <div class="card-header">
                <div class="card-title">
                    <span class="card-icon">📜</span> Riwayat Trade Terakhir
                </div>
                <span style="font-size: 0.75rem; color: var(--text-dim);">10 Trade Terakhir</span>
            </div>
            <div class="table-responsive">
                <div id="historyContent">
                    <div style="color: var(--text-dim); text-align: center; padding: 30px;">Belum ada trade</div>
                </div>
            </div>
        </section>

    </main>

    <!-- Footer -->
    <footer class="footer-info">
        <span>Binance Institutional TPLR Bot</span>
        <div class="footer-dot"></div>
        <span>Auto-sync setiap 3 detik</span>
        <div class="footer-dot"></div>
        <span>Mode: <strong style="color: var(--gold);">{{ mode }}</strong></span>
    </footer>

    <!-- Modal Edit Target Harian -->
    <div class="modal-overlay" id="targetModal">
        <div class="modal-card">
            <div class="modal-title">🎯 Tentukan Target Cuan Harian</div>
            <div class="modal-hint" id="dynTargetHint">
                Target bawaan adalah <strong>{{ target_pct }}% dari modal akun</strong>. Kamu juga bisa memasukkan target kustom dalam USDT di bawah ini:
            </div>
            <input type="number" step="0.5" min="1" max="1000" id="customTargetInput" class="modal-input" placeholder="Misal: 26.50">
            <div class="modal-buttons">
                <button class="btn-cancel" onclick="closeTargetModal()">Tutup</button>
                <button class="btn-default-10" onclick="setDynamicTenPercent()">🔄 Default 10% Modal</button>
                <button class="btn-save" onclick="saveTargetModal()">Simpan Kustom</button>
            </div>
        </div>
    </div>

    <!-- JAVASCRIPT LOGIC -->
    <script>
        // State Global & Privacy Mode
        let isPrivacyMode = localStorage.getItem('binance_bot_privacy') === '1';
        const DEFAULT_TARGET_PCT = {{ target_pct }}; // 10.0%
        let useDynamicPercent = localStorage.getItem('binance_bot_use_dynamic_target') !== 'false'; // default true (10% modal)
        let customTargetUSDT = parseFloat(localStorage.getItem('binance_bot_daily_goal') || '0');
        let currentWalletBal = 265.0;

        // Apply visual button state on load
        function updatePrivacyBtnUI() {
            const btn = document.getElementById('privacyBtn');
            const icon = document.getElementById('privacyIcon');
            const text = document.getElementById('privacyText');
            if (isPrivacyMode) {
                btn.classList.add('active');
                icon.textContent = '🙈';
                text.textContent = 'Saldo Sensor';
            } else {
                btn.classList.remove('active');
                icon.textContent = '👁️';
                text.textContent = 'Saldo Tampil';
            }
        }
        updatePrivacyBtnUI();

        function togglePrivacyMode() {
            isPrivacyMode = !isPrivacyMode;
            localStorage.setItem('binance_bot_privacy', isPrivacyMode ? '1' : '0');
            updatePrivacyBtnUI();
            fetchState(); // Re-render values
        }

        function maskMoney(val, prefix = '$', suffix = ' USDT') {
            if (isPrivacyMode) {
                return '••••••••';
            }
            if (val === undefined || val === null || isNaN(val)) return '-';
            const num = Number(val);
            const sign = num > 0 && prefix === '+' ? '+' : (num < 0 ? '-' : '');
            const cleanPrefix = (prefix === '+' || prefix === '-') ? '' : prefix;
            return `${sign}${cleanPrefix}${Math.abs(num).toFixed(2)}${suffix}`;
        }

        // Modal Target Logic
        function openTargetModal() {
            const dynTarget = (currentWalletBal * (DEFAULT_TARGET_PCT / 100.0)).toFixed(2);
            document.getElementById('dynTargetHint').innerHTML = 
                `Target default: <strong>10% dari modal ($${currentWalletBal.toFixed(2)}) = $${dynTarget} USDT</strong>.<br>Ketik angka jika ingin nominal kustom:`;
            document.getElementById('customTargetInput').value = useDynamicPercent ? dynTarget : (customTargetUSDT || dynTarget);
            document.getElementById('targetModal').style.display = 'flex';
        }
        function closeTargetModal() {
            document.getElementById('targetModal').style.display = 'none';
        }
        function saveTargetModal() {
            const val = parseFloat(document.getElementById('customTargetInput').value);
            if (!isNaN(val) && val > 0) {
                customTargetUSDT = val;
                useDynamicPercent = false;
                localStorage.setItem('binance_bot_daily_goal', val.toString());
                localStorage.setItem('binance_bot_use_dynamic_target', 'false');
            }
            closeTargetModal();
            fetchState();
        }
        function setDynamicTenPercent() {
            useDynamicPercent = true;
            localStorage.setItem('binance_bot_use_dynamic_target', 'true');
            localStorage.removeItem('binance_bot_daily_goal');
            closeTargetModal();
            fetchState();
        }

        // Main Fetch & Render Loop
        async function fetchState() {
            try {
                const res = await fetch('/api/state');
                const data = await res.json();
                renderDashboard(data);
            } catch (err) {
                console.error('Fetch error:', err);
            }
        }

        function renderDashboard(state) {
            // 1. Choppy vs Trending Live Indicator
            const chopBadge = document.getElementById('chopBadge');
            const chopIcon = document.getElementById('chopIcon');
            const chopText = document.getElementById('chopText');
            const chopValEl = document.getElementById('marketChopVal');
            const chopSubEl = document.getElementById('marketChopSub');

            const mc = state.market_condition || {};
            const isChoppy = mc.is_choppy === true;
            const btcAdx = mc.btc_adx !== undefined ? mc.btc_adx : 25.0;
            const symAdx = mc.symbol_adx;

            if (isChoppy) {
                chopBadge.className = 'chop-indicator-badge badge-choppy';
                chopIcon.textContent = '🦀';
                chopText.textContent = `CHOPPY (ADX ${symAdx || btcAdx})`;
                
                chopValEl.innerHTML = '<span style="color:#fbbf24">CHOPPY / SIDEWAYS 🦀</span>';
                chopSubEl.textContent = `ADX ${symAdx || btcAdx} < 22 (Pasar menyempit / rawan whipsaw)`;
            } else {
                chopBadge.className = 'chop-indicator-badge badge-trending';
                chopIcon.textContent = '🌊';
                chopText.textContent = `TRENDING (ADX ${symAdx || btcAdx})`;
                
                chopValEl.innerHTML = '<span style="color:#34d399">TRENDING KUAT 🌊</span>';
                chopSubEl.textContent = `ADX ${symAdx || btcAdx} >= 22 (Arah tren kuat searah)`;
            }

            // 2. Status Badge
            const badge = document.getElementById('statusBadge');
            const statusText = document.getElementById('statusText');
            const rawStatus = (state.bot_status || state.status || 'idle').toLowerCase();
            
            if (state.active_position) {
                statusText.textContent = 'MONITORING POSISI';
                badge.className = 'status-badge status-monitoring';
            } else if (rawStatus === 'running' || rawStatus === 'scanning') {
                statusText.textContent = 'RUNNING (SCANNING)';
                badge.className = 'status-badge status-running';
            } else if (rawStatus === 'stopped') {
                statusText.textContent = 'STOPPED';
                badge.className = 'status-badge status-idle';
            } else {
                statusText.textContent = 'SIAP / SCANNING';
                badge.className = 'status-badge status-running';
            }

            // 3. Wallet Balance
            const walletBal = state.binance_wallet_balance !== undefined ? state.binance_wallet_balance : (state.available_usdt || 0);
            currentWalletBal = walletBal > 0 ? walletBal : currentWalletBal;
            document.getElementById('walletBalance').textContent = maskMoney(walletBal, '$', ' USDT');

            // 4. Daily Target Tracker (Default 10% dari Modal Akun)
            let dailyGoalUSDT;
            if (useDynamicPercent || !customTargetUSDT || customTargetUSDT <= 0) {
                dailyGoalUSDT = Math.max(1.0, currentWalletBal * (DEFAULT_TARGET_PCT / 100.0));
                document.getElementById('targetGoalDisplay').textContent = maskMoney(dailyGoalUSDT, '$', ' USDT');
                document.getElementById('targetGoalSub').textContent = `Target Harian (${DEFAULT_TARGET_PCT}% Modal)`;
            } else {
                dailyGoalUSDT = customTargetUSDT;
                document.getElementById('targetGoalDisplay').textContent = maskMoney(dailyGoalUSDT, '$', ' USDT');
                document.getElementById('targetGoalSub').textContent = `Target Kustom`;
            }

            const todayNet = state.today_net_pnl !== undefined ? Number(state.today_net_pnl) : 0;
            const todayEl = document.getElementById('todayNetProfit');
            todayEl.textContent = maskMoney(todayNet, todayNet >= 0 ? '+' : '', ' USDT');
            todayEl.style.color = todayNet >= 0 ? '#34d399' : '#f43f5e';

            const fill = document.getElementById('targetProgressFill');
            const statusLine = document.getElementById('targetStatusText');
            const pctLine = document.getElementById('targetPercentText');

            if (todayNet >= 0) {
                const pct = Math.min((todayNet / dailyGoalUSDT) * 100, 100);
                fill.style.width = `${Math.max(pct, 2)}%`;
                pctLine.textContent = `${pct.toFixed(0)}%`;
                
                if (todayNet >= dailyGoalUSDT) {
                    fill.className = 'target-progress-fill progress-green';
                    statusLine.innerHTML = '🎉 <strong>TARGET TERCAPAI!</strong> Luar biasa!';
                    statusLine.style.color = '#34d399';
                    pctLine.style.color = '#34d399';
                } else {
                    fill.className = 'target-progress-fill progress-gold';
                    const remaining = dailyGoalUSDT - todayNet;
                    statusLine.textContent = isPrivacyMode ? 'Mengejar target hari ini...' : `Sisa $${remaining.toFixed(2)} USDT menuju target`;
                    statusLine.style.color = 'var(--text-muted)';
                    pctLine.style.color = 'var(--gold)';
                }
            } else {
                // Posisi defisit
                fill.style.width = '10%';
                fill.className = 'target-progress-fill progress-red';
                statusLine.innerHTML = '🛡️ Mode Pemulihan (Fokus eksekusi disiplin)';
                statusLine.style.color = '#f43f5e';
                pctLine.textContent = 'Defisit';
                pctLine.style.color = '#f43f5e';
            }

            // 5. Performa
            const wins = state.win_count || 0;
            const losses = state.loss_count || 0;
            const total = state.total_trades || 0;
            const winRate = total > 0 ? ((wins / total) * 100).toFixed(1) : '0';
            
            document.getElementById('totalTradesCount').textContent = total;
            document.getElementById('winLossDetail').textContent = `${wins} Menang / ${losses} Kalah`;
            document.getElementById('winRateBadge').textContent = `${winRate}% Win Rate`;

            const totalProfit = state.total_profit || 0;
            const allTimeEl = document.getElementById('allTimeProfit');
            allTimeEl.textContent = maskMoney(totalProfit, totalProfit >= 0 ? '+' : '', ' USDT');
            allTimeEl.className = 'stat-value font-mono ' + (totalProfit >= 0 ? 'emerald' : 'crimson');

            // 6. Active Position
            const posCard = document.getElementById('activePositionCard');
            const posContent = document.getElementById('positionContent');
            const posBadges = document.getElementById('posHeaderBadges');

            if (state.active_position) {
                const pos = state.active_position;
                const sideUpper = (pos.side || 'long').toUpperCase();
                const isLong = pos.side === 'long';
                
                const posChopLabel = isChoppy ? '🦀 Choppy Guard' : '🌊 Trending Strong';
                const posChopClass = isChoppy ? 'badge-choppy' : 'badge-trending';

                posBadges.innerHTML = `
                    <span class="badge ${isLong ? 'badge-long' : 'badge-short'}">${sideUpper}</span>
                    <span class="badge badge-leverage">{{ leverage }}x Isolated</span>
                    <span class="badge ${posChopClass}">${posChopLabel}</span>
                    <span class="badge badge-combat">Combat Active</span>
                `;

                const unrealizedPnl = pos.unrealized_pnl !== undefined ? pos.unrealized_pnl : 0;
                const roePct = pos.roe_pct !== undefined ? pos.roe_pct : (pos.current_profit_pct ? pos.current_profit_pct * {{ leverage }} : 0);
                const isProfit = roePct >= 0;

                const currPrice = pos.current_price || pos.entry_price;
                const highestPct = (pos.highest_profit_pct || 0).toFixed(2);
                const cp = state.current_checkpoint || 0;
                const cpProgress = Math.min((cp / 5.0) * 100, 100);

                posContent.innerHTML = `
                    <div class="pos-pnl-banner">
                        <div>
                            <div class="stat-label">Live Unrealized PnL</div>
                            <div class="pnl-big font-mono" style="color: ${isProfit ? '#34d399' : '#f43f5e'}">
                                ${maskMoney(unrealizedPnl, isProfit ? '+' : '', ' USDT')}
                            </div>
                        </div>
                        <div class="pnl-roe ${isProfit ? 'positive' : 'negative'}">
                            ${isProfit ? '+' : ''}${Number(roePct).toFixed(2)}% ROE ({{ leverage }}x)
                        </div>
                    </div>

                    <div class="pos-grid">
                        <div class="stat-item">
                            <div class="stat-label">Simbol Pasangan</div>
                            <div class="stat-value gold">${pos.symbol}</div>
                            <div class="stat-sub">Binance USDⓈ-M Perps</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-label">Harga Entry vs Sekarang</div>
                            <div class="stat-value font-mono" style="font-size: 1.15rem;">
                                ${pos.entry_price} <span style="color:var(--text-dim)">➔</span> ${currPrice}
                            </div>
                            <div class="stat-sub">Slippage dijaga rapat</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-label">Kondisi Koin (ADX)</div>
                            <div class="stat-value ${isChoppy ? 'amber' : 'emerald'}" style="font-size: 1.15rem;">
                                ${isChoppy ? '🦀 CHOPPY' : '🌊 TRENDING'} (${symAdx || btcAdx})
                            </div>
                            <div class="stat-sub">${isChoppy ? 'BEP Cepat Siaga' : 'Let Winners Run'}</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-label">Puncak Tertinggi</div>
                            <div class="stat-value emerald">+${highestPct}%</div>
                            <div class="stat-sub">Peak trailing tracking</div>
                        </div>
                    </div>

                    <div class="ratchet-box">
                        <div class="ratchet-header">
                            <span>Pengawalan Trailing Ratchet: <strong>Checkpoint ${cp}%</strong></span>
                            <span>Target Minimum TP: +1.65%</span>
                        </div>
                        <div class="ratchet-progress">
                            <div class="ratchet-fill" style="width: ${Math.max(cpProgress, 5)}%"></div>
                        </div>
                        <div class="ratchet-milestones">
                            <span>0% (Entry)</span>
                            <span>+1.3% (CP1)</span>
                            <span>+1.7% (CP2)</span>
                            <span>+2.5% (Panen)</span>
                            <span>+4.0%+ (Moonbag)</span>
                        </div>
                    </div>
                `;
            } else {
                posBadges.innerHTML = `<span class="badge badge-leverage">{{ leverage }}x Isolated</span>`;
                posContent.innerHTML = `
                    <div class="radar-box">
                        <div class="radar-spinner"></div>
                        <div style="font-weight: 600; color: var(--text-main); font-size: 1rem;">Radar Aktif Memindai Koin...</div>
                        <div style="font-size: 0.82rem; margin-top: 6px; color: var(--text-dim);">
                            Menunggu sinyal Grade A+ (skor >= 70, wick rejection > 22%, volume breakout)
                        </div>
                    </div>
                `;
            }

            // 7. Last Signal
            const sigContent = document.getElementById('signalContent');
            if (state.last_signal) {
                const sig = state.last_signal;
                const sigScore = sig.score || 0;
                sigContent.innerHTML = `
                    <div class="stat-grid">
                        <div class="stat-item">
                            <div class="stat-label">Koin Terdeteksi</div>
                            <div class="stat-value gold">${sig.symbol || '-'}</div>
                            <div class="stat-sub">Sinyal: <strong style="color:#34d399">${sig.signal || '-'}</strong></div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-label">Skor Kualitas TPLR</div>
                            <div class="stat-value emerald font-mono">${sigScore}/100</div>
                            <div class="stat-sub">Grade A+ Setup</div>
                        </div>
                    </div>
                `;
            } else {
                sigContent.innerHTML = `<div style="color: var(--text-dim); text-align: center; padding: 25px;">Belum ada sinyal terbaru</div>`;
            }

            // 8. Trade History Table
            const histContent = document.getElementById('historyContent');
            if (state.trade_history && state.trade_history.length > 0) {
                const recent = state.trade_history.slice(-10).reverse();
                let html = `
                    <table class="history-table">
                        <thead>
                            <tr>
                                <th>Waktu</th>
                                <th>Pasangan Koin</th>
                                <th>Arah</th>
                                <th>Harga Entry</th>
                                <th>Hasil PnL</th>
                                <th>Alasan Penutupan</th>
                            </tr>
                        </thead>
                        <tbody>
                `;

                recent.forEach(t => {
                    const pnl = Number(t.pnl || 0);
                    const isWin = pnl >= 0;
                    const dateStr = t.close_time ? new Date(t.close_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : '-';
                    html += `
                        <tr>
                            <td class="font-mono" style="color: var(--text-dim);">${dateStr}</td>
                            <td style="font-weight: 600;">${t.symbol}</td>
                            <td>
                                <span class="badge ${t.side === 'long' ? 'badge-long' : 'badge-short'}" style="padding: 2px 8px; font-size: 0.7rem;">
                                    ${(t.side || '').toUpperCase()}
                                </span>
                            </td>
                            <td class="font-mono">${t.entry_price || '-'}</td>
                            <td class="font-mono" style="font-weight: 700; color: ${isWin ? '#34d399' : '#f43f5e'};">
                                ${maskMoney(pnl, isWin ? '+' : '', ' USDT')}
                            </td>
                            <td style="font-size: 0.78rem; color: var(--text-muted);">${t.close_reason || '-'}</td>
                        </tr>
                    `;
                });

                html += `</tbody></table>`;
                histContent.innerHTML = html;
            } else {
                histContent.innerHTML = `<div style="color: var(--text-dim); text-align: center; padding: 30px;">Belum ada riwayat trade</div>`;
            }
        }

        // Jalankan polling live setiap 3 detik
        fetchState();
        setInterval(fetchState, 3000);
    </script>
</body>
</html>
"""

# =============================================================================
# FLASK ROUTES & BACKEND DATA FETCHER
# =============================================================================

@app.route("/")
def index():
    """Render modern terminal dashboard."""
    return render_template_string(
        DASHBOARD_HTML,
        mode=config.TRADING_MODE.upper(),
        leverage=config.LEVERAGE,
        target_pct=getattr(config, "DAILY_TARGET_PROFIT_PERCENT", 10.0),
        emergency_sl=f"-{config.EMERGENCY_SL_PERCENT}%" if config.EMERGENCY_SL_ENABLED else "OFF",
    )


_binance_cache = {
    "last_check": 0,
    "wallet_balance": 0.0,
    "today_net_pnl": 0.0,
    "exchange": None
}

def get_live_binance_metrics():
    """Fetch live wallet balance & today net PnL directly from Binance (cached 5s)."""
    global _binance_cache
    now = time.time()
    if now - _binance_cache["last_check"] < 5 and _binance_cache["wallet_balance"] > 0:
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


_chop_cache = {
    "last_check": 0,
    "data": {
        "btc_adx": 65.0,
        "symbol_adx": None,
        "is_choppy": False,
        "status_label": "TRENDING KUAT"
    }
}

def get_market_choppiness(active_symbol=None):
    """Hitung ADX 15m untuk deteksi Choppy vs Trending (cached 15s)."""
    global _chop_cache
    now = time.time()
    if now - _chop_cache["last_check"] < 15 and _chop_cache["data"]["btc_adx"] > 0:
        return _chop_cache["data"]

    try:
        ex = _binance_cache.get("exchange")
        if not ex:
            return _chop_cache["data"]

        def _calc_adx(sym):
            ohlcv = ex.fetch_ohlcv(sym, "15m", limit=32)
            if not ohlcv or len(ohlcv) < 20:
                return 25.0
            df = pd.DataFrame(ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
            df['up'] = df['high'] - df['high'].shift(1)
            df['down'] = df['low'].shift(1) - df['low']
            df['plus_dm'] = np.where((df['up'] > df['down']) & (df['up'] > 0), df['up'], 0.0)
            df['minus_dm'] = np.where((df['down'] > df['up']) & (df['down'] > 0), df['down'], 0.0)
            df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
            tr_s = df['tr'].rolling(14).sum()
            p_di = 100 * (df['plus_dm'].rolling(14).sum() / tr_s)
            m_di = 100 * (df['minus_dm'].rolling(14).sum() / tr_s)
            dx = 100 * abs(p_di - m_di) / (p_di + m_di)
            return round(float(dx.rolling(14).mean().iloc[-1]), 1)

        btc_adx = _calc_adx("BTC/USDT:USDT")
        
        sym_adx = None
        if active_symbol and "BTC" not in active_symbol:
            try:
                sym_adx = _calc_adx(active_symbol)
            except Exception:
                pass

        # Threshold Choppy: ADX < 22.0
        is_choppy = (sym_adx < 22.0) if sym_adx is not None else (btc_adx < 22.0)
        status_label = "CHOPPY (SIDEWAYS)" if is_choppy else "TRENDING (KUAT)"

        data = {
            "btc_adx": btc_adx,
            "symbol_adx": sym_adx,
            "is_choppy": is_choppy,
            "status_label": status_label
        }
        _chop_cache["last_check"] = now
        _chop_cache["data"] = data
        return data
    except Exception as e:
        return _chop_cache["data"]


@app.route("/api/state")
def api_state():
    """API endpoint untuk status bot real-time."""
    state_manager.state = state_manager._load_state()
    res = state_manager.get_state()
    
    # Enrich dengan live Binance metrics
    w_bal, today_pnl = get_live_binance_metrics()
    res["binance_wallet_balance"] = w_bal
    res["today_net_pnl"] = today_pnl
    
    # Enrich active position dengan live price & unrealized PnL
    active_sym = None
    if res.get("active_position") and _binance_cache.get("exchange"):
        try:
            pos = res["active_position"]
            symbol = pos.get("symbol")
            active_sym = symbol
            if symbol:
                ticker = _binance_cache["exchange"].fetch_ticker(symbol)
                curr_price = float(ticker.get("last", 0) or ticker.get("close", 0))
                entry_price = float(pos.get("entry_price", 0))
                amount = float(pos.get("amount", 0))
                side = str(pos.get("side", "long")).lower()
                
                if curr_price > 0 and entry_price > 0:
                    pos["current_price"] = curr_price
                    if side == "long":
                        pct = ((curr_price - entry_price) / entry_price) * 100.0
                        u_pnl = (curr_price - entry_price) * amount
                    else:
                        pct = ((entry_price - curr_price) / entry_price) * 100.0
                        u_pnl = (entry_price - curr_price) * amount
                    pos["current_profit_pct"] = round(pct, 2)
                    pos["unrealized_pnl"] = round(u_pnl, 2)
                    pos["roe_pct"] = round(pct * config.LEVERAGE, 2)
        except Exception:
            pass
            
    # Enrich dengan market condition (Choppy vs Trending)
    res["market_condition"] = get_market_choppiness(active_sym)

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

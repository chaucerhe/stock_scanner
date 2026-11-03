from flask import Flask, request, jsonify, render_template_string
import requests
import concurrent.futures
import os
import json
import re
import subprocess
import threading
from datetime import datetime

app = Flask(__name__)

# 全局复用 Session 连接池
http_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(max_retries=3, pool_connections=100, pool_maxsize=100)
http_session.mount('http://', adapter)
http_session.mount('https://', adapter)

TENCENT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://stockapp.finance.qq.com/',
}


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>伏击圈：精准缩量回踩猎杀系统（东财高频版）</title>
    <script src="/static/vue.global.prod.js"></script>
    <style>
        :root {
            --bg-deep: #0f172a;
            --bg-surface: #1e293b;
            --bg-elevated: #334155;
            --border-subtle: #475569;
            --text-primary: #f8fafc;
            --text-secondary: #cbd5e1;
            --text-muted: #94a3b8;
            --accent-cyan: #06b6d4;
            --accent-cyan-dim: rgba(6, 182, 212, 0.18);
            --accent-indigo: #4f46e5;
            --accent-purple: #9333ea;
            --accent-red: #ef4444;
            --accent-green: #10b981;
            --shadow-glow: 0 0 40px rgba(6, 182, 212, 0.15);
            --shadow-card: 0 10px 30px rgba(0, 0, 0, 0.4);
        }
        * { box-sizing: border-box; }
        body {
            background: var(--bg-deep);
            background-image:
                radial-gradient(circle at 15% 20%, rgba(79, 70, 229, 0.12), transparent 40%),
                radial-gradient(circle at 85% 80%, rgba(6, 182, 212, 0.10), transparent 45%);
            background-attachment: fixed;
            color: var(--text-primary);
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
            -webkit-font-smoothing: antialiased;
            min-height: 100vh;
            padding: 1rem;
            margin: 0;
        }
        @media (min-width: 768px) {
            body { padding: 2rem; }
        }
        .glass-card {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.85) 0%, rgba(15, 23, 42, 0.75) 100%);
            backdrop-filter: blur(14px);
            -webkit-backdrop-filter: blur(14px);
            border: 1px solid var(--border-subtle);
            box-shadow: var(--shadow-card);
        }
        .hero-title {
            background: linear-gradient(120deg, #22d3ee 0%, #818cf8 50%, #c084fc 100%);
            background-clip: text;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 0 40px rgba(99, 102, 241, 0.4);
            letter-spacing: -0.02em;
            line-height: 1.1;
        }
        .hero-title-icon {
            filter: drop-shadow(0 0 16px rgba(6, 182, 212, 0.6));
        }
        .btn-primary {
            transition: all 0.2s ease-out;
            position: relative;
            overflow: hidden;
            font-weight: 600;
            letter-spacing: 0.01em;
        }
        .btn-primary::before {
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(180deg, rgba(255,255,255,0.12) 0%, transparent 50%);
            pointer-events: none;
        }
        .btn-primary:hover:not(:disabled) {
            transform: translateY(-1px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4), 0 0 24px rgba(6, 182, 212, 0.25);
        }
        .btn-primary:active:not(:disabled) { transform: translateY(0); }
        .btn-primary:disabled { cursor: not-allowed; opacity: 0.6; }
        .btn-cyan { background: linear-gradient(135deg, #0891b2 0%, #06b6d4 100%); color: #ecfeff; }
        .btn-indigo { background: linear-gradient(135deg, #4338ca 0%, #6366f1 100%); color: #eef2ff; }
        .btn-purple { background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%); color: #faf5ff; }
        .btn-slate { background: linear-gradient(135deg, #334155 0%, #475569 100%); color: #e2e8f0; }

        textarea {
            transition: all 0.2s ease-out;
        }
        textarea:focus {
            border-color: var(--accent-cyan);
            box-shadow: 0 0 0 3px rgba(6, 182, 212, 0.18);
            outline: none;
        }

        .stat-card {
            background: linear-gradient(135deg, rgba(51, 65, 85, 0.6) 0%, rgba(30, 41, 59, 0.6) 100%);
            border: 1px solid var(--border-subtle);
            position: relative;
            overflow: hidden;
        }
        .stat-card::after {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--accent-cyan), transparent);
            opacity: 0.6;
        }
        .stat-value {
            background: linear-gradient(180deg, #f8fafc 0%, #94a3b8 100%);
            background-clip: text;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-variant-numeric: tabular-nums;
        }

        .strategy-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.3rem 0.8rem;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            border: 1px solid;
        }
        .badge-manual { color: #67e8f9; border-color: rgba(6, 182, 212, 0.4); background: rgba(6, 182, 212, 0.1); }
        .badge-hot { color: #a5b4fc; border-color: rgba(99, 102, 241, 0.4); background: rgba(99, 102, 241, 0.1); }
        .badge-rebound { color: #d8b4fe; border-color: rgba(168, 85, 247, 0.4); background: rgba(168, 85, 247, 0.1); }

        .result-table { width: 100%; border-collapse: separate; border-spacing: 0; }
        .result-table thead th {
            background: rgba(15, 23, 42, 0.9);
            backdrop-filter: blur(8px);
            position: sticky;
            top: 0;
            z-index: 10;
            text-transform: uppercase;
            font-size: 0.68rem;
            letter-spacing: 0.08em;
            color: var(--text-muted);
            font-weight: 600;
            border-bottom: 1px solid var(--border-subtle);
            padding: 0.85rem 1rem;
            text-align: left;
        }
        /* 修复：th 上 text-right/text-center 工具类被上方 text-align:left 覆盖的优先级问题 */
        .result-table thead th.text-right { text-align: right; }
        .result-table thead th.text-center { text-align: center; }
        .result-table tbody td {
            padding: 0.9rem 1rem;
            border-bottom: 1px solid rgba(71, 85, 105, 0.4);
            font-size: 0.875rem;
            vertical-align: middle;
        }
        .result-table tbody tr {
            transition: background 0.15s ease-out;
        }
        /* 左侧高亮条：用 inset box-shadow 实现，避免 tr::before 在表格中生成匿名单元格导致整行错位 */
        .result-table tbody tr td:first-child {
            box-shadow: inset 0 0 0 0 transparent;
            transition: box-shadow 0.2s ease-out;
        }
        .result-table tbody tr.row-pass {
            background: rgba(6, 182, 212, 0.06);
        }
        .result-table tbody tr.row-pass:hover {
            background: rgba(6, 182, 212, 0.12);
        }
        .result-table tbody tr.row-pass:hover td:first-child {
            box-shadow: inset 3px 0 0 0 var(--accent-cyan);
        }
        .result-table tbody tr.row-fail {
            opacity: 0.55;
        }
        .result-table tbody tr.row-fail:hover { opacity: 0.85; }

        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.3rem;
            padding: 0.25rem 0.7rem;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 700;
            white-space: nowrap;
        }
        .status-pass {
            color: #67e8f9;
            background: rgba(6, 182, 212, 0.15);
            border: 1px solid rgba(6, 182, 212, 0.35);
        }
        .status-watch {
            color: var(--text-muted);
            background: rgba(100, 116, 139, 0.18);
            border: 1px solid rgba(100, 116, 139, 0.4);
        }

        .price-up { color: #f87171; font-weight: 600; font-variant-numeric: tabular-nums; }
        .price-down { color: #4ade80; font-weight: 600; font-variant-numeric: tabular-nums; }
        .price-flat { color: var(--text-secondary); font-variant-numeric: tabular-nums; }
        .metric-highlight { color: var(--accent-cyan); font-weight: 700; }

        .toast {
            position: fixed;
            top: 1.5rem;
            right: 1.5rem;
            z-index: 1000;
            padding: 0.85rem 1.25rem;
            border-radius: 0.5rem;
            backdrop-filter: blur(12px);
            font-size: 0.875rem;
            font-weight: 500;
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.5);
            border: 1px solid;
            min-width: 220px;
            animation: slideIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        }
        .toast-error { color: #fca5a5; background: rgba(127, 29, 29, 0.85); border-color: rgba(239, 68, 68, 0.4); }
        .toast-success { color: #86efac; background: rgba(20, 83, 45, 0.85); border-color: rgba(34, 197, 94, 0.4); }
        .toast-info { color: #7dd3fc; background: rgba(12, 74, 110, 0.85); border-color: rgba(6, 182, 212, 0.4); }
        /* ===== 财务报告弹窗 ===== */
        .modal-mask {
            position: fixed; inset: 0; z-index: 60;
            background: rgba(2, 6, 23, 0.72);
            backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
            display: flex; align-items: center; justify-content: center; padding: 1rem;
        }
        .modal-panel {
            width: 100%; max-width: 560px; max-height: 86vh; overflow-y: auto;
            border-radius: 14px; padding: 1.5rem;
        }
        .stock-check-list {
            margin: 0.75rem 0; border: 1px solid var(--border-subtle); border-radius: 10px;
            max-height: 260px; overflow-y: auto;
        }
        .stock-check-item {
            display: flex; align-items: center; gap: 0.6rem;
            padding: 0.55rem 0.85rem; cursor: pointer; font-size: 0.85rem;
            border-bottom: 1px solid rgba(71, 85, 105, 0.35); transition: background 0.15s;
        }
        .stock-check-item:last-child { border-bottom: none; }
        .stock-check-item:hover { background: rgba(6, 182, 212, 0.08); }
        .stock-check-item input { accent-color: #06b6d4; width: 15px; height: 15px; }
        .stock-check-item em { font-style: normal; color: var(--text-muted); font-family: monospace; font-size: 0.75rem; }
        .modal-input {
            width: 100%; background: #0b1220; border: 1px solid var(--border-subtle);
            border-radius: 8px; padding: 0.6rem 0.75rem; color: var(--text-primary);
            font-size: 0.8rem; font-family: monospace; outline: none;
        }
        .modal-input:focus { border-color: var(--accent-cyan); }
        .job-status-row { display: flex; align-items: center; gap: 0.5rem; font-size: 0.78rem; padding: 0.3rem 0; }
        .job-status-row .mono { font-family: monospace; color: var(--text-muted); }

        @keyframes slideIn {
            from { transform: translateX(110%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .spin { animation: spin 0.8s linear infinite; display: inline-block; }

        .empty-state {
            text-align: center;
            padding: 4rem 2rem;
            color: var(--text-muted);
        }
        .empty-icon {
            font-size: 3rem;
            opacity: 0.4;
            margin-bottom: 1rem;
            display: block;
        }

        .loading-pulse {
            background: linear-gradient(90deg, rgba(51,65,85,0.4) 0%, rgba(99,102,241,0.3) 50%, rgba(51,65,85,0.4) 100%);
            background-size: 200% 100%;
            animation: shimmer 1.6s ease-in-out infinite;
        }
        @keyframes shimmer {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
        }

        .progress-bar {
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--accent-cyan), var(--accent-indigo), transparent);
            background-size: 200% 100%;
            animation: shimmer 1.4s ease-in-out infinite;
        }

        @media (max-width: 768px) {
            .hide-mobile { display: none; }
        }

        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: var(--border-subtle); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--accent-cyan); }

        /* ========== Tailwind-like utility classes (offline) ========== */
        .p-4 { padding: 1rem; }
        .p-3 { padding: 0.75rem; }
        .p-6 { padding: 1.5rem; }
        .px-3 { padding-left: 0.75rem; padding-right: 0.75rem; }
        .px-5 { padding-left: 1.25rem; padding-right: 1.25rem; }
        .py-1\\.5 { padding-top: 0.375rem; padding-bottom: 0.375rem; }
        .py-2\\.5 { padding-top: 0.625rem; padding-bottom: 0.625rem; }
        .mb-1 { margin-bottom: 0.25rem; }
        .mb-2 { margin-bottom: 0.5rem; }
        .mb-3 { margin-bottom: 0.75rem; }
        .mb-5 { margin-bottom: 1.25rem; }
        .mb-6 { margin-bottom: 1.5rem; }
        .mb-8 { margin-bottom: 2rem; }
        .mt-2 { margin-top: 0.5rem; }
        .mt-5 { margin-top: 1.25rem; }
        .mr-2 { margin-right: 0.5rem; }
        .gap-1\\.5 { gap: 0.375rem; }
        .gap-2 { gap: 0.5rem; }
        .gap-3 { gap: 0.75rem; }
        .gap-4 { gap: 1rem; }
        .gap-5 { gap: 1.25rem; }

        .block { display: block; }
        .flex { display: flex; }
        .inline-flex { display: inline-flex; }
        .grid { display: grid; }
        .hidden { display: none; }
        .items-center { align-items: center; }
        .justify-between { justify-content: space-between; }
        .flex-wrap { flex-wrap: wrap; }
        .flex-1 { flex: 1 1 0%; }
        .mx-auto { margin-left: auto; margin-right: auto; }
        .w-full { width: 100%; }
        .max-w-7xl { max-width: 80rem; }
        .max-w-3xl { max-width: 48rem; }
        .max-w-md { max-width: 28rem; }
        .max-w-xs { max-width: 20rem; }
        .min-h-screen { min-height: 100vh; }
        .overflow-hidden { overflow: hidden; }
        .overflow-x-auto { overflow-x: auto; }
        .rounded-lg { border-radius: 0.5rem; }
        .rounded-xl { border-radius: 0.75rem; }
        .rounded-md { border-radius: 0.375rem; }
        .rounded-full { border-radius: 9999px; }
        .border { border-width: 1px; border-style: solid; }
        .border-b { border-bottom-width: 1px; border-bottom-style: solid; }
        .border-slate-600 { border-color: #475569; }
        .border-slate-700 { border-color: #334155; }
        .border-slate-700\/60 { border-color: rgba(51, 65, 85, 0.6); }
        .bg-slate-800 { background-color: #1e293b; }
        .bg-slate-900\/60 { background-color: rgba(15, 23, 42, 0.6); }
        .hover\:bg-slate-700:hover { background-color: #334155; }
        .text-left { text-align: left; }
        .text-right { text-align: right; }
        .text-center { text-align: center; }
        .text-xs { font-size: 0.75rem; line-height: 1rem; }
        .text-sm { font-size: 0.875rem; line-height: 1.25rem; }
        .text-base { font-size: 1rem; line-height: 1.5rem; }
        .text-lg { font-size: 1.125rem; line-height: 1.75rem; }
        .text-xl { font-size: 1.25rem; line-height: 1.75rem; }
        .text-2xl { font-size: 1.5rem; line-height: 2rem; }
        .text-3xl { font-size: 1.875rem; line-height: 2.25rem; }
        .text-5xl { font-size: 3rem; line-height: 1; }
        .font-mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
        .font-semibold { font-weight: 600; }
        .font-bold { font-weight: 700; }
        .uppercase { text-transform: uppercase; }
        .tracking-wider { letter-spacing: 0.05em; }
        .leading-relaxed { line-height: 1.625; }
        .text-slate-100 { color: #f1f5f9; }
        .text-slate-200 { color: #e2e8f0; }
        .text-slate-300 { color: #cbd5e1; }
        .text-slate-400 { color: #94a3b8; }
        .text-slate-500 { color: #64748b; }
        .text-cyan-400 { color: #22d3ee; }
        .text-indigo-400 { color: #818cf8; }
        .text-purple-400 { color: #c084fc; }
        .transition-colors { transition: color 0.2s, background-color 0.2s, border-color 0.2s; }
        .grid-cols-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
        .md\:grid-cols-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .resize-none { resize: none; }

        @media (min-width: 768px) {
            .md\:p-8 { padding: 2rem; }
            .md\:p-5 { padding: 1.25rem; }
            .md\:p-4 { padding: 1rem; }
            .md\:text-5xl { font-size: 3rem; line-height: 1; }
            .md\:text-3xl { font-size: 1.875rem; line-height: 2.25rem; }
            .md\:text-xl { font-size: 1.25rem; line-height: 1.75rem; }
            .md\:text-base { font-size: 1rem; line-height: 1.5rem; }
            .md\:gap-4 { gap: 1rem; }
            .md\:grid-cols-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }
    </style>
</head>
<body class="p-4 md:p-8">
    <div id="app"></div>
    <script type="text/x-template" id="app-template">
        <!-- Hero -->
        <header class="mb-8">
            <h1 class="hero-title text-3xl md:text-5xl font-bold mb-3 flex items-center flex-wrap gap-3">
                <span class="hero-title-icon">🎯</span>
                <span>伏击圈：精准缩量回踩猎杀系统</span>
                <span class="text-base md:text-xl text-slate-500 font-mono">(东财高频版)</span>
            </h1>
            <p class="text-slate-400 text-sm md:text-base max-w-3xl leading-relaxed">
                核心纪律：<span class="text-cyan-400 font-semibold">不追高</span> · 
                <span class="text-indigo-400 font-semibold">等缩量</span> · 
                <span class="text-purple-400 font-semibold">踩均线</span>。
                专治手痒，只做右侧确定性低吸。
            </p>
        </header>

        <!-- Input Panel -->
        <section class="glass-card rounded-xl p-6 md:p-8 mb-8">
            <div class="grid md:grid-cols-2 gap-5 mb-6">
                <div>
                    <label class="block text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">
                        手动输入代码 · 逗号分隔
                    </label>
                    <textarea v-model="stockCodes" rows="2"
                        class="w-full bg-slate-900/60 border border-slate-700 rounded-lg p-3 text-slate-100 font-mono text-sm"
                        placeholder="sh600023,sz000027,sz000899,sh605020"></textarea>
                </div>
                <div>
                    <label class="block text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">
                        排除代码 · 全市场扫描时生效
                    </label>
                    <textarea v-model="excludeCodes" rows="2"
                        class="w-full bg-slate-900/60 border border-slate-700 rounded-lg p-3 text-slate-100 font-mono text-sm"
                        placeholder="sz000899"></textarea>
                </div>
            </div>

            <div class="flex flex-wrap gap-3">
                <button @click="scanStocks" :disabled="loading"
                    class="btn-primary btn-cyan px-5 py-2.5 rounded-lg flex items-center gap-2">
                    <span v-if="loading && scanType==='manual'" class="spin">↻</span>
                    [[ (loading && scanType==='manual') ? '深度测算中...' : '开始手动扫描' ]]
                </button>
                <button @click="scanHotSectors" :disabled="loading"
                    class="btn-primary btn-indigo px-5 py-2.5 rounded-lg flex items-center gap-2">
                    <span v-if="loading && scanType==='hot'" class="spin">↻</span>
                    [[ (loading && scanType==='hot') ? '全市场地雷阵铺设中...' : '一键扫描全市场黄金坑' ]]
                </button>
                <button @click="scanRebound" :disabled="loading"
                    class="btn-primary btn-purple px-5 py-2.5 rounded-lg flex items-center gap-2">
                    <span v-if="loading && scanType==='rebound'" class="spin">↻</span>
                    [[ (loading && scanType==='rebound') ? '测算底部拐点...' : '捕捉底部企稳信号' ]]
                </button>
                <button @click="fillHotStocks" :disabled="loading"
                    class="btn-primary btn-slate px-5 py-2.5 rounded-lg flex items-center gap-2">
                    填入自选股观察池
                </button>
            </div>

            <div v-if="loading" class="mt-5">
                <div class="progress-bar rounded-full"></div>
                <p class="text-xs text-slate-500 mt-2 font-mono">[ RUNTIME ] 并发拉取K线 · 多数据源容错 · 17道过滤阀门校验中</p>
            </div>
        </section>

        <!-- Stats Row -->
        <section v-if="results.length > 0" class="grid grid-cols-3 gap-3 md:gap-4 mb-6">
            <div class="stat-card rounded-lg p-4 md:p-5">
                <div class="text-xs text-slate-400 uppercase tracking-wider mb-1">扫描数</div>
                <div class="stat-value text-2xl md:text-3xl font-bold">[[ totalScanned || results.length ]]</div>
            </div>
            <div class="stat-card rounded-lg p-4 md:p-5">
                <div class="text-xs text-slate-400 uppercase tracking-wider mb-1">命中数</div>
                <div class="stat-value text-2xl md:text-3xl font-bold">[[ passedCount ]]</div>
            </div>
            <div class="stat-card rounded-lg p-4 md:p-5">
                <div class="text-xs text-slate-400 uppercase tracking-wider mb-1">命中率</div>
                <div class="stat-value text-2xl md:text-3xl font-bold">[[ hitRate ]]%</div>
            </div>
        </section>

        <!-- Results Table -->
        <section v-if="results.length > 0" class="glass-card rounded-xl overflow-hidden">
            <div class="p-4 md:p-5 border-b border-slate-700/60 flex flex-wrap justify-between items-center gap-3">
                <div class="flex items-center gap-3">
                    <h2 class="text-lg md:text-xl font-bold text-slate-100">扫描结果</h2>
                    <span class="strategy-badge" :class="strategyBadgeClass">[[ strategyLabel ]]</span>
                </div>
                <div class="flex items-center gap-2">
                    <button @click="openReportModal" :disabled="results.length === 0"
                        :class="results.length === 0 ? 'opacity-40 cursor-not-allowed' : 'hover:bg-cyan-500/20'"
                        class="text-xs px-3 py-1.5 rounded-md bg-cyan-500/10 border border-cyan-500/40 text-cyan-300 transition-colors flex items-center gap-1.5">
                        📊 生成财务报告
                    </button>
                    <button @click="copyResults"
                        class="text-xs px-3 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 border border-slate-600 text-slate-200 transition-colors flex items-center gap-1.5">
                        📋 复制结果
                    </button>
                </div>
            </div>
            <div class="overflow-x-auto">
                <table class="result-table">
                    <thead>
                        <tr>
                            <th class="hide-mobile">代码</th>
                            <th>名称</th>
                            <th class="text-right">最新价</th>
                            <th class="text-right hide-mobile">MA20防线</th>
                            <th class="text-right">乖离率</th>
                            <th class="text-right hide-mobile">量比</th>
                            <th class="text-center">状态</th>
                            <th>系统判定</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="stock in sortedResults" :key="stock.code"
                            :class="stock.is_rejected ? 'row-fail' : 'row-pass'">
                            <td class="hide-mobile font-mono text-slate-400 text-xs">[[ stock.code ]]</td>
                            <td class="font-semibold text-slate-100">[[ stock.name ]]</td>
                            <td class="text-right">
                                <span :class="priceClass(stock)">[[ stock.price.toFixed(2) ]]</span>
                            </td>
                            <td class="text-right hide-mobile text-slate-300 font-mono">[[ stock.ma20.toFixed(2) ]]</td>
                            <td class="text-right">
                                <span :class="highlightBias(stock.bias_20)">
                                    [[ stock.bias_20 > 0 ? '+' : '' ]][[ stock.bias_20.toFixed(2) ]]%
                                </span>
                            </td>
                            <td class="text-right hide-mobile">
                                <span :class="highlightVolRatio(stock.vol_ratio)">[[ stock.vol_ratio.toFixed(2) ]]</span>
                            </td>
                            <td class="text-center">
                                <span v-if="!stock.is_rejected" class="status-pill status-pass">⚡ 进入伏击圈</span>
                                <span v-else class="status-pill status-watch">○ 观望</span>
                            </td>
                            <td class="text-xs text-slate-400 max-w-xs">[[ stock.reject_reason || '形态完美 · 进入伏击圈' ]]</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </section>

        <!-- Empty State -->
        <section v-if="results.length === 0 && !loading" class="glass-card rounded-xl">
            <div class="empty-state">
                <span class="empty-icon">🎯</span>
                <h3 class="text-lg font-semibold text-slate-300 mb-1">等待伏击指令</h3>
                <p class="text-sm text-slate-500 max-w-md mx-auto">
                    输入股票代码手动扫描，或一键扫描全市场黄金坑。系统将通过17道过滤阀门筛选缩量回踩形态。
                </p>
            </div>
        </section>

        <!-- 财务报告弹窗 -->
        <div v-if="reportModal.show" class="modal-mask" @click.self="closeReportModal">
            <div class="modal-panel glass-card">
                <div class="flex items-center justify-between mb-1">
                    <h3 class="text-base font-bold text-slate-100">📊 生成财务报告</h3>
                    <button @click="closeReportModal" class="text-slate-400 hover:text-slate-200 text-lg leading-none">×</button>
                </div>
                <p class="text-xs text-slate-400">勾选需要分析的股票（每只约 5 分钟 / 10 万 tokens，3 路并发生成，单次最多 20 只）</p>

                <div class="flex gap-2 mt-3">
                    <button @click="selectPassedOnly" class="text-xs px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 border border-slate-600 text-slate-300">全选非观望</button>
                    <button @click="selectedCodes = []" class="text-xs px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 border border-slate-600 text-slate-300">清空</button>
                    <span class="ml-auto text-xs text-slate-400 self-center">已选 [[ selectedCodes.length ]] 只</span>
                </div>

                <div class="stock-check-list">
                    <label v-for="s in sortedResults" :key="s.code" class="stock-check-item">
                        <input type="checkbox" :value="s.code" v-model="selectedCodes" :disabled="reportJobRunning">
                        <span class="flex-1">[[ s.name ]] <em>[[ s.code ]]</em></span>
                        <span v-if="!s.is_rejected" class="status-pill status-pass">✅ 伏击圈</span>
                        <span v-else class="status-pill status-watch">🟡 观望</span>
                    </label>
                </div>

                <label class="block text-xs text-slate-400 mb-1">报告保存位置</label>
                <div class="flex items-center gap-2">
                    <div class="modal-input flex-1 truncate" :class="reportSaveDir ? '' : 'text-slate-500'">
                        [[ reportSaveDir || '默认 ~/Documents/财经/当天日期文件夹' ]]
                    </div>
                    <button @click="pickReportDir" :disabled="reportJobRunning || pickingDir"
                        class="shrink-0 text-xs px-3 py-2 rounded-md bg-slate-800 hover:bg-slate-700 border border-slate-600 text-slate-200 transition-colors flex items-center gap-1">
                        📁 [[ pickingDir ? '选择中...' : '选择文件夹' ]]
                    </button>
                </div>

                <!-- 任务进度 -->
                <div v-if="reportJob" class="mt-3 pt-3 border-t border-slate-700/50">
                    <div class="text-xs text-slate-400 mb-1">任务进度（[[ reportJob.statusText ]]）</div>
                    <div v-for="(r, code) in reportJob.results" :key="code" class="job-status-row">
                        <span v-if="r.status === 'done'">✅</span>
                        <span v-else-if="r.status === 'running'">⏳</span>
                        <span v-else-if="r.status === 'failed'">❌</span>
                        <span v-else>🕐</span>
                        <span class="mono">[[ code ]]</span>
                        <span class="text-slate-300">[[ r.name || '' ]]</span>
                        <span v-if="r.docx" class="text-cyan-300 truncate">→ [[ r.docx ]]</span>
                    </div>
                </div>

                <div class="flex justify-end gap-2 mt-4">
                    <button @click="closeReportModal" class="text-xs px-4 py-2 rounded-md bg-slate-800 hover:bg-slate-700 border border-slate-600 text-slate-200">关闭</button>
                    <button @click="submitReportJob"
                        :disabled="selectedCodes.length === 0 || selectedCodes.length > 20 || reportJobRunning"
                        :class="(selectedCodes.length === 0 || selectedCodes.length > 20 || reportJobRunning) ? 'opacity-40 cursor-not-allowed' : 'hover:bg-cyan-500/30'"
                        class="text-xs px-4 py-2 rounded-md bg-cyan-500/20 border border-cyan-500/50 text-cyan-200 font-medium">
                        [[ reportJobRunning ? '生成中...' : '生成 ' + selectedCodes.length + ' 只报告' ]]
                    </button>
                </div>
            </div>
        </div>

        <!-- Toast -->
        <transition>
            <div v-if="toast.show" class="toast" :class="'toast-' + toast.type">
                [[ toast.message ]]
            </div>
        </transition>
</script>
    <script>
        const { createApp } = Vue;

        const app = createApp({
            template: '#app-template',
            compilerOptions: {
                delimiters: ['[[', ']]']
            },
            data() {
                return {
                    stockCodes: 'sh600023,sz000027,sz000899,sh605020',
                    excludeCodes: 'sz000899',
                    results: [],
                    totalScanned: 0, // 真实扫描总数（后端返回，避免与命中数混淆）
                    loading: false,
                    scanType: 'manual',
                    currentStrategy: 'manual', // 精准记录当前的业务策略状态（manual代表回踩，rebound代表企稳）
                    toast: { show: false, message: '', type: 'error' },
                    toastTimer: null,
                    // ===== 财务报告 =====
                    reportModal: { show: false },
                    selectedCodes: [],
                    reportSaveDir: '',
                    reportJob: null,        // { id, status, statusText, results: {code: {status, name, docx}} }
                    reportJobTimer: null,
                    pickingDir: false
                }
            },
            computed: {
                reportJobRunning() {
                    return !!(this.reportJob && (this.reportJob.status === 'pending' || this.reportJob.status === 'running'));
                },
                passedCount() {
                    return this.results.filter(r => !r.is_rejected).length;
                },
                hitRate() {
                    // 命中率 = 命中数 / 真实扫描总数（全市场模式）或 results.length（手动模式）
                    const denom = this.totalScanned > 0 ? this.totalScanned : this.results.length;
                    if (denom === 0) return '0.0';
                    return ((this.passedCount / denom) * 100).toFixed(1);
                },
                sortedResults() {
                    return [...this.results].sort((a, b) => {
                        if (a.is_rejected !== b.is_rejected) {
                            return a.is_rejected ? 1 : -1;
                        }
                        return Math.abs(a.bias_20) - Math.abs(b.bias_20);
                    });
                },
                strategyLabel() {
                    return this.currentStrategy === 'rebound' ? '底部企稳' : '回踩狙击';
                },
                strategyBadgeClass() {
                    return {
                        manual: 'badge-manual',
                        hot: 'badge-hot',
                        rebound: 'badge-rebound'
                    }[this.currentStrategy];
                }
            },
            methods: {
                abs(val) {
                    return Math.abs(Number(val) || 0);
                },
                showToast(message, type = 'error') {
                    if (this.toastTimer) clearTimeout(this.toastTimer);
                    this.toast = { show: true, message, type };
                    this.toastTimer = setTimeout(() => {
                        this.toast.show = false;
                    }, 3500);
                },
                priceClass(stock) {
                    if (stock.change_percent > 0) return 'price-up';
                    if (stock.change_percent < 0) return 'price-down';
                    return 'price-flat';
                },
                highlightBias(bias) {
                    if (Math.abs(bias) <= 2) return 'metric-highlight';
                    return 'text-slate-300 font-mono';
                },
                highlightVolRatio(vol) {
                    if (vol <= 0.8) return 'metric-highlight';
                    return 'text-slate-300 font-mono';
                },
                copyResults() {
                    if (this.sortedResults.length === 0) {
                        this.showToast('当前无结果可复制', 'info');
                        return;
                    }
                    const text = this.sortedResults.map(r => `${r.code} ${r.name}`).join('\\n');
                    if (navigator.clipboard && navigator.clipboard.writeText) {
                        navigator.clipboard.writeText(text).then(() => {
                            this.showToast(`已复制 ${this.sortedResults.length} 条结果`, 'success');
                        });
                    }
                },
                fillHotStocks() {
                    this.stockCodes = 'sh600023,sz000027,sz000899,sh605020,sh600900,sz000001,sh601318';
                    this.showToast('已填入自选股观察池', 'info');
                },
                // ===== 财务报告 =====
                async openReportModal() {
                    if (this.results.length === 0) return;
                    this.selectPassedOnly();
                    this.reportJob = null;
                    this.reportModal.show = true;
                    // 若后台仍有进行中的任务（如页面刷新后），恢复进度显示并继续轮询
                    try {
                        const resp = await fetch('/api/report_jobs_latest');
                        const data = await resp.json();
                        if (data && data.success && data.job &&
                            (data.job.status === 'pending' || data.job.status === 'running')) {
                            this.reportJob = data.job;
                            this.startReportPolling();
                        }
                    } catch (e) { /* 忽略，按无任务处理 */ }
                },
                closeReportModal() {
                    if (this.reportJobRunning) {
                        this.showToast('任务仍在后台生成中，可稍后重新打开查看', 'info');
                    }
                    this.reportModal.show = false;
                },
                selectPassedOnly() {
                    this.selectedCodes = this.results.filter(r => !r.is_rejected).map(r => r.code);
                },
                async pickReportDir() {
                    if (this.pickingDir) return;
                    this.pickingDir = true;
                    try {
                        const resp = await fetch('/api/pick_dir');
                        const data = await resp.json();
                        if (data && data.success) {
                            this.reportSaveDir = data.path;
                        } else if (data && data.error !== 'canceled') {
                            this.showToast('选择文件夹失败: ' + data.error, 'error');
                        }
                    } catch (e) {
                        this.showToast('选择文件夹失败: ' + e.message, 'error');
                    } finally {
                        this.pickingDir = false;
                    }
                },
                async submitReportJob() {
                    if (this.selectedCodes.length === 0 || this.selectedCodes.length > 20 || this.reportJobRunning) return;
                    const stocks = this.selectedCodes.map(code => {
                        const hit = this.results.find(r => r.code === code);
                        return { code, name: hit ? hit.name : '' };
                    });
                    try {
                        const resp = await fetch('/api/report_jobs', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ stocks, save_dir: this.reportSaveDir.trim() })
                        });
                        const data = await resp.json();
                        if (data && data.success) {
                            this.reportJob = data.job;
                            this.showToast('任务已创建，后台开始生成报告', 'success');
                            this.startReportPolling();
                        } else {
                            this.showToast((data && data.error) || '任务创建失败', 'error');
                        }
                    } catch (e) {
                        this.showToast('请求失败: ' + e.message, 'error');
                    }
                },
                startReportPolling() {
                    if (this.reportJobTimer) clearInterval(this.reportJobTimer);
                    this.reportJobTimer = setInterval(this.pollReportJob, 15000);
                    this.pollReportJob();
                },
                async pollReportJob() {
                    if (!this.reportJob) return;
                    try {
                        const resp = await fetch('/api/report_jobs/' + this.reportJob.id);
                        const data = await resp.json();
                        if (data && data.success) {
                            const prevRunning = this.reportJobRunning;
                            this.reportJob = data.job;
                            if (prevRunning && !this.reportJobRunning) {
                                clearInterval(this.reportJobTimer);
                                this.reportJobTimer = null;
                                const okCount = Object.values(this.reportJob.results).filter(r => r.status === 'done').length;
                                this.showToast(`财务报告生成完毕：成功 ${okCount} / ${Object.keys(this.reportJob.results).length} 只`, okCount > 0 ? 'success' : 'error');
                            }
                        }
                    } catch (e) { /* 轮询失败静默，下一轮重试 */ }
                },
                // ==========================================
                // 核心修正 1：手动扫描不再强制重置策略，而是沿用当前的 currentStrategy
                // ==========================================
                async scanStocks() {
                    if (!this.stockCodes.trim()) {
                        this.showToast('请输入股票代码', 'error');
                        return;
                    }
                    this.loading = true;
                    this.results = [];
                    this.totalScanned = 0;
                    try {
                        const codes = this.stockCodes.split(',').map(c => c.trim()).filter(c => c);
                        const response = await fetch('/api/scan', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                codes: codes,
                                strategy: this.currentStrategy // 👈 动态跟随你当前的选择（如果是企稳，就传 rebound）
                            })
                        });
                        const data = await response.json();
                        if (data.status === 'success') {
                            this.results = data.results;
                            this.totalScanned = data.total_scanned || data.results.length;
                            if (this.results.length === 0) {
                                this.showToast('扫描完成 · 无合规标的', 'info');
                            }
                        } else {
                            this.showToast('扫描出错: ' + (data.message || '未知错误'), 'error');
                        }
                    } catch (error) {
                        console.error(error);
                        this.showToast('网络请求失败: ' + error.message, 'error');
                    } finally {
                        this.loading = false;
                    }
                },
                // ==========================================
                // 核心修正 2：全市场扫描和企稳扫描按钮点击时，精准切换策略状态
                // ==========================================
                async scanHotSectors() {
                    this.currentStrategy = 'manual'; // 回踩业务模式
                    this.scanType = 'hot';
                    this.loading = true;
                    this.results = [];
                    this.totalScanned = 0;
                    try {
                        const excludes = this.excludeCodes.split(',').map(c => c.trim()).filter(c => c).map(c => c.replace(/^(sh|sz)/i, ''));
                        const response = await fetch('/api/scan_hot', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ exclude_codes: excludes })
                        });
                        const data = await response.json();
                        if (data.status === 'success') {
                            this.results = data.results;
                            this.totalScanned = data.total_scanned || 0;
                        } else {
                            this.showToast(data.message || '扫描失败', 'error');
                        }
                    } catch (error) { this.showToast('网络请求失败'); } finally { this.loading = false; }
                },
                async scanRebound() {
                    this.currentStrategy = 'rebound'; // 👈 明确切换为底部企稳业务模式！
                    this.scanType = 'rebound';
                    this.loading = true;
                    this.results = [];
                    this.totalScanned = 0;
                    try {
                        const excludes = this.excludeCodes.split(',').map(c => c.trim()).filter(c => c).map(c => c.replace(/^(sh|sz)/i, ''));
                        const response = await fetch('/api/scan_rebound', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ exclude_codes: excludes })
                        });
                        const data = await response.json();
                        if (data.status === 'success') {
                            this.results = data.results;
                            this.totalScanned = data.total_scanned || 0;
                        } else {
                            this.showToast(data.message || '扫描失败', 'error');
                        }
                    } catch (error) { this.showToast('网络请求失败'); } finally { this.loading = false; }
                }
            }
        });
        // Vue3 自定义分隔符：必须在使用 DOM 内模板时于 mount 前设置
        app.config.compilerOptions.delimiters = ['[[', ']]'];
        app.mount('#app');
    </script>
</body>
</html>
"""


@app.after_request
def add_no_cache_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


def get_em_secid(code):
    """将标准代码转东财 secid。沪市 6/9 开头用 1.，深市用 0."""
    clean = code.lower().replace('sh', '').replace('sz', '').replace('bj', '')
    if clean.startswith('6') or clean.startswith('9'):
        return '1.' + clean
    return '0.' + clean


def fetch_klines(code):
    """多数据源容错获取 K 线。返回最近 250 天的 K 线列表。"""
    sina_symbol = code.lower()
    em_secid = get_em_secid(code)

    # 数据源 1：腾讯财经
    try:
        tencent_url = (
            f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            f"?param={sina_symbol},day,,,250,qfq"
        )
        resp = http_session.get(tencent_url, timeout=8, headers=TENCENT_HEADERS)
        if resp.status_code == 200:
            payload = resp.json()
            stock_data = (payload.get('data') or {}).get(sina_symbol) or {}
            qfqday = stock_data.get('qfqday') or stock_data.get('day') or []
            if isinstance(qfqday, list) and len(qfqday) > 0:
                result = []
                for row in qfqday:
                    if not isinstance(row, (list, tuple)) or len(row) < 6:
                        continue
                    result.append([
                        str(row[0]),
                        str(row[1]),
                        str(row[2]),
                        str(row[3]),
                        str(row[4]),
                        str(row[5]),
                    ])
                if result:
                    return result
    except Exception as e:
        print(f"[tencent-fail] {code}: {e}")

    # 数据源 2：东方财富
    try:
        em_url = (
            f"http://push2his.eastmoney.com/api/qt/stock/kline/get"
            f"?secid={em_secid}"
            f"&fields1=f1,f2,f3,f4,f5,f6"
            f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
            f"&klt=101&fqt=1&end=20500000&lmt=250"
        )
        resp = http_session.get(em_url, timeout=8)
        if resp.status_code == 200:
            payload = resp.json()
            data = payload.get('data')
            if data and data.get('klines'):
                klines = data['klines']
                if isinstance(klines, list) and len(klines) > 0:
                    result = []
                    for line in klines:
                        parts = line.split(',')
                        if len(parts) >= 6:
                            result.append(parts)
                    if result:
                        return result
    except Exception as e:
        print(f"[em-fail] {code}: {e}")

    # 数据源 3：新浪财经
    try:
        sina_url = (
            f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
            f"CN_MarketData.getKLineData?symbol={sina_symbol}&scale=240&ma=no&datalen=250"
        )
        resp = http_session.get(sina_url, timeout=8)
        if resp.status_code == 200:
            text = resp.text.strip()
            if text and text.startswith('['):
                import json as _json
                arr = _json.loads(text)
                if isinstance(arr, list) and len(arr) > 0:
                    result = []
                    for item in arr:
                        if not isinstance(item, dict):
                            continue
                        day = item.get('day', '')
                        open_p = item.get('open', '')
                        high = item.get('high', '')
                        low = item.get('low', '')
                        close = item.get('close', '')
                        vol = item.get('volume', '')
                        result.append([day, open_p, close, high, low, vol])
                    if result:
                        return result
    except Exception as e:
        print(f"[sina-fail] {code}: {e}")

    return None


def get_stock_name(code):
    """用腾讯财经接口获取股票名称。"""
    sina_symbol = code.lower()
    try:
        url = f"http://qt.gtimg.cn/q={sina_symbol}"
        resp = http_session.get(url, timeout=5)
        if resp.status_code == 200:
            text = resp.text
            var_name = f'v_{sina_symbol}="'
            idx = text.find(var_name)
            if idx != -1:
                start = idx + len(var_name)
                end = text.find('"', start)
                if end != -1:
                    parts = text[start:end].split('~')
                    if len(parts) >= 2:
                        name = parts[1]
                        if name:
                            return name
            # 兜底：取首个中文片段
            import re
            m = re.search(r'"([^"]*[\u4e00-\u9fa5]+[^"]*)"', text)
            if m:
                parts = m.group(1).split('~')
                if len(parts) >= 2:
                    return parts[1]
    except Exception as e:
        print(f"[name-fail] {code}: {e}")
    return None


def get_profit_growth(code):
    """获取最近一期净利润同比增长率（%）。数据源：东方财富财务指标。
    返回 None 表示获取失败，调用方应视为业绩未知（不作为否决依据）。
    """
    clean = code.lower().replace('sh', '').replace('sz', '').replace('bj', '').strip()
    market = 'SH' if clean.startswith('6') else 'SZ'
    try:
        secucode = f"{clean}.{market}"
        dc_url = (
            "https://datacenter-web.eastmoney.com/api/data/v1/get?"
            "sortColumns=REPORT_DATE&sortTypes=-1&pageSize=1&pageNumber=1"
            f"&filter=(SECUCODE=\"{secucode}\")"
            "&reportName=RPT_F10_FINANCE_MAINFINADATA"
        )
        resp = http_session.get(dc_url, timeout=5)
        if resp.status_code == 200:
            payload = resp.json()
            if payload.get('result') and payload['result'].get('data'):
                row = payload['result']['data'][0]
                # 兼容多个东财可能的净利润同比增幅字段名
                for key in ['NETPROFIT_YOY_RATIO', 'YSTZ', 'NETPROFIT_GROWTH_RATE', 'PARENT_NETPROFIT_YOY']:
                    val = row.get(key)
                    if val is not None and str(val).strip() != '':
                        return float(val)
    except Exception as e:
        print(f"[profit-fail] {code}: {e}")
    return None


def analyze_stock_pullback(code, name=None):
    """回踩猎杀逻辑（参数已调优版 + 长线牛市防线）。"""
    try:
        clean_code = code.lower().replace('sh', '').replace('sz', '').replace('bj', '')

        klines = fetch_klines(code)
        if not klines or len(klines) < 120:
            return {"error": f"data insufficient for {code}"}

        today_kline = klines[-1]
        yesterday_kline = klines[-2]

        today_date = today_kline[0]
        today_open = float(today_kline[1])
        today_close = float(today_kline[2])
        today_high = float(today_kline[3])
        today_low = float(today_kline[4])
        today_vol = float(today_kline[5]) if today_kline[5] else 0.0

        yesterday_close = float(yesterday_kline[2])

        if len(today_kline) > 8 and today_kline[8]:
            try: change_percent = float(today_kline[8])
            except (ValueError, TypeError): change_percent = (today_close - yesterday_close) / yesterday_close * 100 if yesterday_close > 0 else 0.0
        else:
            change_percent = (today_close - yesterday_close) / yesterday_close * 100 if yesterday_close > 0 else 0.0

        if not name:
            name = get_stock_name(code) or clean_code

        if today_close >= 50:
            return {"code": code, "name": name, "price": today_close, "change_percent": change_percent, "ma20": 0.0, "bias_20": 0.0, "vol_ratio": 0.0, "is_rejected": True, "reject_reason": "价格过高"}
        if name and ('ST' in name.upper()):
            return {"code": code, "name": name, "price": today_close, "change_percent": change_percent, "ma20": 0.0, "bias_20": 0.0, "vol_ratio": 0.0, "is_rejected": True, "reject_reason": "风险警示股"}

        closes = [float(k[2]) for k in klines]
        vols = [float(k[5]) if k[5] else 0.0 for k in klines]

        def ma(arr, n):
            if len(arr) < n: return 0.0
            return sum(arr[-n:]) / n

        ma5 = ma(closes, 5)
        ma10 = ma(closes, 10)
        ma20 = ma(closes, 20)
        ma30 = ma(closes, 30)
        ma60 = ma(closes, 60)
        ma120 = ma(closes, 120)

        ma20_yesterday = sum(closes[-21:-1]) / 20 if len(closes) >= 21 else 0.0
        max_high_120 = max(float(k[3]) for k in klines[-120:])

        avg_vol_5 = sum(vols[-6:-1]) / 5 if len(vols) >= 6 else 1.0
        vol_ratio = today_vol / avg_vol_5 if avg_vol_5 > 0 else 0.0
        bias_20 = (today_close - ma20) / ma20 * 100 if ma20 > 0 else 0.0

        price = today_close

        def reject(reason):
            return {"code": code, "name": name, "price": price, "change_percent": change_percent, "ma20": ma20, "bias_20": bias_20, "vol_ratio": vol_ratio, "is_rejected": True, "reject_reason": reason}

        def pass_result():
            return {"code": code, "name": name, "price": price, "change_percent": change_percent, "ma20": ma20, "bias_20": bias_20, "vol_ratio": vol_ratio, "is_rejected": False, "reject_reason": ""}

        # ==========================================
        # 回踩刚性风控门禁
        # ==========================================
        # 0. 【大局观硬卡死】长线空头趋势绝不属于中线回踩黄金坑
        if ma20 < ma60:
            return reject("趋势走弱：MA20在MA60下方，不属于健康的上升通道回踩")
        if price < ma20:
            return reject("破位差生：现价跌破MA20生命线")
        if ma20 <= ma20_yesterday:
            return reject("趋势走弱：MA20斜率走平或向下")
        if today_low < ma20 * 0.96:
            return reject("日内重伤：盘中跌破MA20达4%以上")
        if price < max_high_120 * 0.70:
            return reject("超跌反弹：距半年高点跌幅超30%")

        ma_arr = [ma5, ma10, ma20, ma30]
        if min(ma_arr) > 0:
            ma_spread = (max(ma_arr) - min(ma_arr)) / min(ma_arr)
            if ma_spread < 0.03: return reject("均线死结")

        if ma5 < ma20:
            return reject("短线破位")
        if price < ma5 and price < ma10:
            return reject("泰山压顶：现价被MA5和MA10双重均线压制，不属于健康的回踩形态")
        if (ma5 - price) / ma5 > 0.04 if ma5 > 0 else False:
            return reject("高空坠物")
        if price < ma5 and price < ma10 and ((ma10 - price) / ma10 > 0.02 if ma10 > 0 else False):
            return reject("双线击穿")

        if vol_ratio > 1.2:
            return reject(f"洗盘量能不合规：量比{vol_ratio:.2f}，未见明显缩窄")

        # ==========================================================
        # 🔥 铁血加装：拒绝大阴线接飞刀（保护极致盈亏比的同时卡死下坠动能）
        # ==========================================================
        # 如果当天大跌（<-2.5%），且收盘价极度贴近全天最低价（下影线占比小于 25%），说明恐慌盘仍在宣泄
        kline_range = today_high - today_low
        if kline_range > 0 and change_percent < -2.5:
            lower_shadow = today_close - today_low
            # 如果下影线长度占整根 K 线振幅不足 25%，说明没有资金在尾盘抄底托盘，属于光头光脚杀跌
            if (lower_shadow / kline_range) < 0.25:
                return reject("飞刀倾泻：当天大阴线强力杀跌且无尾盘承接，拒绝接飞刀")

        if change_percent < -5.0: return reject("跌幅过大")
        if change_percent > 4.0: return reject("拉升中，脱离伏击点")
        if bias_20 > 3.0: return reject("悬在半空")

        return pass_result()

    except Exception as e:
        return {"error": f"analyze error for {code}: {str(e)}"}


def analyze_stock_rebound(code, name=None):
    """底部企稳反转逻辑（动态博弈升级版：兼顾纪律防御与逆市生机）。"""
    try:
        clean_code = code.lower().replace('sh', '').replace('sz', '').replace('bj', '')

        klines = fetch_klines(code)
        if not klines or len(klines) < 120:
            return {"error": f"data insufficient for {code}"}

        today_kline = klines[-1]
        yesterday_kline = klines[-2]

        today_open = float(today_kline[1])
        today_close = float(today_kline[2])
        today_high = float(today_kline[3])
        today_low = float(today_kline[4])
        today_vol = float(today_kline[5]) if today_kline[5] else 0.0

        yesterday_close = float(yesterday_kline[2])
        yesterday_low = float(yesterday_kline[4])

        if len(today_kline) > 8 and today_kline[8]:
            try: change_percent = float(today_kline[8])
            except (ValueError, TypeError): change_percent = (today_close - yesterday_close) / yesterday_close * 100 if yesterday_close > 0 else 0.0
        else:
            change_percent = (today_close - yesterday_close) / yesterday_close * 100 if yesterday_close > 0 else 0.0

        if not name:
            name = get_stock_name(code) or clean_code

        price = today_close

        if price >= 50:
            return {"code": code, "name": name, "price": price, "change_percent": change_percent, "ma20": 0.0, "bias_20": 0.0, "vol_ratio": 0.0, "is_rejected": True, "reject_reason": "价格过高"}
        if name and ('ST' in name.upper()):
            return {"code": code, "name": name, "price": price, "change_percent": change_percent, "ma20": 0.0, "bias_20": 0.0, "vol_ratio": 0.0, "is_rejected": True, "reject_reason": "风险警示股"}

        closes = [float(k[2]) for k in klines]
        vols = [float(k[5]) if k[5] else 0.0 for k in klines]

        def ma(arr, n):
            if len(arr) < n: return 0.0
            return sum(arr[-n:]) / n

        ma5 = ma(closes, 5)
        ma10 = ma(closes, 10)
        ma20 = ma(closes, 20)
        ma24 = ma(closes, 24)
        ma60 = ma(closes, 60)

        ma5_yesterday = sum(closes[-6:-1]) / 5 if len(closes) >= 6 else 0.0
        ma10_yesterday = sum(closes[-11:-1]) / 10 if len(closes) >= 11 else 0.0

        avg_vol_5 = sum(vols[-6:-1]) / 5 if len(vols) >= 6 else 1.0
        vol_ratio = today_vol / avg_vol_5 if avg_vol_5 > 0 else 0.0
        bias_20 = (today_close - ma20) / ma20 * 100 if ma20 > 0 else 0.0
        bias_24 = (today_close - ma24) / ma24 * 100 if ma24 > 0 else 0.0

        # 换手率（东财K线第11个字段 f61；新浪源无此字段则置 0 跳过该阀门）
        turnover_rate = 0.0
        try:
            if len(today_kline) > 10 and today_kline[10]:
                turnover_rate = float(today_kline[10])
        except (ValueError, TypeError):
            turnover_rate = 0.0

        # 日内冲高幅度：(今日最高 - 昨收) / 昨收 * 100
        high_percent = (today_high - yesterday_close) / yesterday_close * 100 if yesterday_close > 0 else 0.0

        def reject(reason):
            return {"code": code, "name": name, "price": price, "change_percent": change_percent, "ma20": ma20, "bias_20": bias_20, "vol_ratio": vol_ratio, "is_rejected": True, "reject_reason": reason}

        def pass_result():
            return {"code": code, "name": name, "price": price, "change_percent": change_percent, "ma20": ma20, "bias_20": bias_20, "vol_ratio": vol_ratio, "is_rejected": False, "reject_reason": ""}

        # ==========================================================
        # � 全局死刑阀门（一票否决！优先级最高，绿卡也无法豁免）
        # ==========================================================
        # 否决1: 换手率爆量出货 (> 15.0%) —— 仅在有换手率数据时生效
        if turnover_rate > 0 and turnover_rate > 15.0:
            return reject("【死刑】换手率过于剧烈(>15%)，筹码极度松动，存在主力对倒/甩货风险")

        # 否决2: 高位长上影线/冲高回落 (上影线长度 > 实体长度的 1.5 倍 且 冲高幅度>8%)
        upper_shadow = today_high - max(today_open, today_close)
        body = abs(today_close - today_open)
        if body > 0 and upper_shadow > 1.5 * body and high_percent > 8.0:
            return reject("【死刑】高位炸板/长上影线砸盘，上方抛压巨大")

        # 否决3: 20日线偏离过大 —— 常规模式严格 ≤5.0%；强攻绿卡放宽至 ≤6.5%（由 change_percent 锁死）
        is_hero_candidate = (
            change_percent >= 3.0
            and vol_ratio >= 2.0
            and today_vol > (avg_vol_5 * 1.5)
            and price >= ma5
        )
        bias_limit = 6.5 if is_hero_candidate else 5.0
        if bias_20 > bias_limit:
            return reject(f"【死刑】偏离20日生命线过远(>{bias_limit:.1f}%)，防守空间过大，严禁追高")

        # ==========================================================
        # � 跑道 A：右侧企稳/主升浪跟进（国泰海通、洛阳钼业模式）
        # ==========================================================
        # 在 20日线附近或上方（>= MA20*0.98），且满足放量强攻即放行
        if price >= ma20 * 0.98:
            if is_hero_candidate:
                # 强攻英雄只需通过最底层的硬性破位和跌幅限制
                if change_percent > 6.5: return reject("爆发过头：日内涨幅过大不宜追高")
                if price < ma5: return reject("英雄气短：价格未能稳在5日线上方")
                return pass_result()

        # ==========================================================
        # 🛫 跑道 B：左侧超跌反弹（专门抓暴跌深坑神单）
        # ==========================================================
        # 股价确实在 20日线下方，符合超跌定义
        elif price < ma20:
            # 1. 超跌硬指标：乖离率必须足够深 (BIAS_24 < -15%)
            is_oversold = bias_24 < -15.0
            # 2. 瞬间爆发力：必须是极度暴量 (量比 > 2.5 且 涨幅 > 4%)
            is_rebound_force = (vol_ratio >= 2.5 and change_percent >= 4.0)
            # 3. 过滤器：业绩不能滑坡（获取失败视为未知，不否决）
            profit_growth = get_profit_growth(code)
            is_fundamental_good = (profit_growth is None) or (profit_growth > 0)
            if is_oversold and is_rebound_force and is_fundamental_good:
                return pass_result()

        # ==========================================================
        # 🛑 常规模式下的冷血过滤（非爆量强攻个股，继续严密监控）
        # ==========================================================
        # 1. 均线拧麻花拦截
        ma_arr = [ma5, ma10, ma20]
        if min(ma_arr) > 0:
            ma_spread = (max(ma_arr) - min(ma_arr)) / min(ma_arr)
            if ma_spread < 0.02:
                return reject("均线拧麻花：短期均线高度粘合，主力装死无斜率")

        # 2. 无量撞墙拦截
        if ma60 > 0 and (ma60 - price) / ma60 < 0.025 and price < ma60:
            if vol_ratio < 1.5:
                return reject("无量撞墙：逼近60日线筹码密集区但兵力匮乏")

        # 3. 基础趋势拦截
        if ma20 < ma60 and ma5 < ma20: return reject("无底深渊：中期空头加速通道中")
        if ma10 >= ma20: return reject("尚未超跌：均线仍是多头排列")
        if today_low <= yesterday_low: return reject("重心下移：最低价仍在探底")
        if ma5 <= ma5_yesterday: return reject("均线未扭转：MA5斜率依然向下")
        if price < ma5 or price < ma10: return reject("多头较弱：收盘价未同时站上5日和10日线")
        if price <= today_open or change_percent < 1.0: return reject("反击无力：非实体红阳线")
        if change_percent > 5.0: return reject("拉升过猛：常规反弹幅度过大")
        if vol_ratio < 1.1: return reject("缩量反抽：无量反弹多为诱多")
        if vol_ratio > 3.0: return reject("爆量滞涨：底部筹码松动过大")

        return pass_result()

    except Exception as e:
        return {"error": f"analyze error for {code}: {str(e)}"}


def _is_excluded_board(code):
    """排除创业板、科创板、北交所。"""
    return (
        code.startswith('300') or code.startswith('301')
        or code.startswith('688') or code.startswith('689')
        or code.startswith('8') or code.startswith('4')
    )


def _append_stock_item(result, seen, blacklist, symbol, name):
    """将单只股票加入结果列表，统一做去重与板块过滤。"""
    symbol = str(symbol).strip().lower()
    name = str(name).strip()
    if not symbol:
        return False
    clean = symbol.replace('sh', '').replace('sz', '').replace('bj', '')
    if not clean or len(clean) != 6:
        return False
    if _is_excluded_board(clean):
        return False
    if clean in blacklist or clean in seen:
        return False
    seen.add(clean)
    result.append({"symbol": symbol, "name": name})
    return True


def fetch_all_stocks(exclude_codes):
    """腾讯财经全市场主板股票列表高频拉取（多并发 + 分页容错版）。
    exclude_codes: 不带 sh/sz 前缀的代码列表。
    """
    blacklist = {c.strip().lower().replace('sh', '').replace('sz', '').replace('bj', '') for c in exclude_codes if c.strip()}
    result = []
    seen = set()

    # 腾讯财经板块排行榜单接口 (每页 100 条)
    page_size = 100
    # A股主板股票总量约 3200+，分 35 页拉取足够覆盖全市场
    total_pages = 35

    def fetch_page(page_idx):
        offset = page_idx * page_size
        # 腾讯财经全市场排序接口 (按价格排序，全覆盖；sort_type 仅支持 price 等枚举，不支持 amount)
        tencent_url = (
            "https://proxy.finance.qq.com/cgi/cgi-bin/rank/hs/getBoardRankList"
            f"?board_code=aStock&sort_type=price&direct=down&offset={offset}&count={page_size}"
        )
        for attempt in range(3):  # 失败自动重试 3 次
            try:
                resp = http_session.get(tencent_url, timeout=6, headers=TENCENT_HEADERS)
                if resp.status_code == 200:
                    payload = resp.json()
                    if payload.get('code') == 0:
                        rank_list = (payload.get('data') or {}).get('rank_list') or []
                        return rank_list
            except Exception:
                pass
        return []

    # 使用线程池并发并行拉取 35 个分页（2秒内拉完全市场 3500+ 只股票清单）
    page_items = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_page, p) for p in range(total_pages)]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                page_items.extend(res)

    # 统一过滤、去重与剔除非主板（创业板/科创板/北交所/黑名单）
    for item in page_items:
        code = str(item.get('code', '')).strip()
        name = str(item.get('name', '')).strip()
        _append_stock_item(result, seen, blacklist, code, name)

    print(f"[tencent-all-success] 腾讯财经接口成功拉取到 {len(result)} 只主板股票！")
    return result


@app.route('/api/scan', methods=['POST'])
def scan():
    """手动扫描接口（动态适配回踩与企稳双策略，彻底丢弃不合规数据）。"""
    data = request.json
    codes = data.get('codes', [])
    strategy = data.get('strategy', 'manual')

    if not codes:
        return jsonify({"status": "error", "message": "No codes provided"})

    target_function = analyze_stock_rebound if strategy == 'rebound' else analyze_stock_pullback

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(target_function, code): code for code in codes}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if "error" in res:
                # 保持错误数据的兜底显示
                code = futures[future]
                results.append({
                    "code": code,
                    "name": get_stock_name(code) or code,
                    "price": 0.0,
                    "change_percent": 0.0,
                    "ma20": 0.0,
                    "bias_20": 0.0,
                    "vol_ratio": 0.0,
                    "is_rejected": True,
                    "reject_reason": res["error"],
                })
            else:
                # 👈 核心修复：手动扫描必须保留完整结果（包括被拒绝的个股及其原因）
                results.append(res)

    return jsonify({"status": "success", "results": results, "total_scanned": len(codes)})


@app.route('/api/scan_hot', methods=['POST'])
def scan_hot():
    data = request.json or {}
    exclude_codes = data.get('exclude_codes', [])

    stocks = fetch_all_stocks(exclude_codes)

    # 核心安全校验：如果腾讯接口返回少于 1000 只主板股票，说明网络波动，弹出提示而不假装扫描
    if not stocks or len(stocks) < 1000:
        return jsonify({
            "status": "error",
            "message": f"腾讯财经接口响应异常（仅获取到 {len(stocks)} 只标的），请重新点击扫描！"
        })

    results = []
    # 使用 30 线程并发抓取 K 线并做 17 道冷血过滤
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        futures = {
            executor.submit(analyze_stock_pullback, s['symbol'], s.get('name')): s['symbol']
            for s in stocks
        }
        for future in concurrent.futures.as_completed(futures):
            try:
                res = future.result()
                if "error" not in res and not res.get('is_rejected'):
                    results.append(res)
            except Exception:
                continue

    # 按乖离率 abs(bias_20) 升序排序，精选前 20 只完美形态进入伏击圈
    passed_results = sorted(results, key=lambda x: abs(x.get('bias_20', 0)))[:20]
    return jsonify({"status": "success", "results": passed_results})


@app.route('/api/scan_rebound', methods=['POST'])
def scan_rebound():
    data = request.json or {}
    exclude_codes = data.get('exclude_codes', [])

    stocks = fetch_all_stocks(exclude_codes)
    if not stocks or len(stocks) < 1000:
        return jsonify({
            "status": "error",
            "message": f"腾讯财经接口响应异常（仅获取到 {len(stocks)} 只标的），请重新点击扫描！"
        })

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        futures = {
            executor.submit(analyze_stock_rebound, s['symbol'], s.get('name')): s['symbol']
            for s in stocks
        }
        for future in concurrent.futures.as_completed(futures):
            try:
                res = future.result()
                if "error" not in res and not res.get('is_rejected'):
                    results.append(res)
            except Exception:
                continue

    passed_results = sorted(results, key=lambda x: abs(x.get('price', 0) - x.get('ma20', 0)))[:20]
    return jsonify({"status": "success", "results": passed_results, "total_scanned": len(stocks)})


# ============================================================
# 财务报告生成（通过 traecli exec 驱动 AI agent，逐只生成 docx）
# ============================================================
REPORT_JOBS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'report_jobs')
os.makedirs(REPORT_JOBS_DIR, exist_ok=True)
REPORT_WORKDIR = '/Users/bytedance/Documents/财经'
REPORT_SKILL_PATH = '/Users/bytedance/.trae-cn/skills/stock-finance-analysis/SKILL.md'


def _report_job_path(job_id):
    return os.path.join(REPORT_JOBS_DIR, f'{job_id}.json')


def _save_report_job(job):
    with open(_report_job_path(job['id']), 'w', encoding='utf-8') as f:
        json.dump(job, f, ensure_ascii=False, indent=2)


def _build_report_prompt(stock, save_dir):
    """组装给 traecli agent 的自包含 prompt（冒烟测试验证版本）"""
    code = stock['code'].lower()          # 形如 sh601098
    sec = f"{code[2:]}.{ 'SH' if code.startswith('sh') else 'SZ' }"
    name = stock.get('name') or code
    return (
        f"为A股 {name}({sec}) 生成财务分析报告 Word 文档。要求："
        f"1) 先 Read {REPORT_SKILL_PATH}，严格遵循其输出模板章节结构与投资决策三维判别框架（5条红线/4项健康特征/击球区）。"
        f"2) 本环境无 datapro/tdx MCP，数据一律用公开 HTTP 接口获取："
        f"K线用 https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,60,qfq ；"
        f"现价用 http://qt.gtimg.cn/q={code} （字段[3]现价[4]昨收）；"
        f"财务指标/三大报表/杜邦/盈利/偿债/营运/成长用东财 "
        f"https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_F10_FINANCE_MAINFINADATA"
        f"&filter=(SECUCODE=\"{sec}\")&sortColumns=REPORT_DATE&sortTypes=-1&pageSize=4"
        f"（自行探索该域名其他 reportName 接口补齐维度）；业绩预告/每股指标同理用东财 F10 接口。"
        f"3) 数据缺失字段填 —，不得编造。"
        f"4) 组装 JSON 后执行 python3 gen_stock_doc.py --outdir=\"{save_dir}\" <临时JSON>，"
        f"临时 JSON 以 .tmp_ 开头且生成成功后删除。"
        f"5) 最后只输出：最终结论（坚决剔除/保留入池）+ 一句依据 + docx 保存路径。"
    )


def _run_report_job(job_id):
    """后台线程：3 路并发调用 traecli exec 生成报告，实时更新任务 JSON"""
    path = _report_job_path(job_id)
    with open(path, encoding='utf-8') as f:
        job = json.load(f)
    job['status'] = 'running'
    _save_report_job(job)
    lock = threading.Lock()

    def worker(s):
        code = s['code']
        with lock:
            job['results'][code] = {'status': 'running', 'name': s.get('name', '')}
            _save_report_job(job)
        try:
            proc = subprocess.run(
                ['traecli', 'exec', '--skip-git-repo-check', '--ephemeral',
                 _build_report_prompt(s, job['save_dir'])],
                cwd=REPORT_WORKDIR, capture_output=True, text=True, timeout=1800
            )
            out = (proc.stdout or '') + (proc.stderr or '')
            m = re.findall(r'(/\S+?\.docx)', out)
            docx = m[-1] if m else ''
            ok = proc.returncode == 0 and bool(docx)
            result = {
                'status': 'done' if ok else 'failed',
                'name': s.get('name', ''),
                'docx': docx,
                'output_tail': out[-800:]
            }
        except Exception as e:
            result = {'status': 'failed', 'name': s.get('name', ''), 'error': str(e)}
        with lock:
            job['results'][code] = result
            _save_report_job(job)

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(worker, job['stocks']))

    results = job['results'].values()
    done_n = sum(1 for r in results if r['status'] == 'done')
    job['status'] = 'done' if done_n == len(job['stocks']) else ('partial' if done_n > 0 else 'failed')
    _save_report_job(job)


def _job_status_text(job):
    mapping = {'pending': '排队中', 'running': '生成中', 'done': '全部完成',
               'partial': '部分成功', 'failed': '全部失败'}
    return mapping.get(job.get('status'), job.get('status', ''))


@app.route('/api/pick_dir')
def pick_dir():
    """调起 macOS 原生文件夹选择框，返回所选绝对路径"""
    try:
        proc = subprocess.run(
            ['osascript', '-e',
             'POSIX path of (choose folder with prompt "选择财务报告保存位置")'],
            capture_output=True, text=True, timeout=120
        )
        if proc.returncode != 0:
            # 用户点了取消
            return jsonify({"success": False, "error": "canceled"})
        path = proc.stdout.strip().rstrip('/')
        if not path:
            return jsonify({"success": False, "error": "canceled"})
        return jsonify({"success": True, "path": path})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/report_jobs', methods=['POST'])
def create_report_job():
    data = request.json or {}
    stocks = data.get('stocks', [])
    save_dir = (data.get('save_dir') or '').strip()

    if not stocks:
        return jsonify({"success": False, "error": "未选择任何股票"}), 400
    if len(stocks) > 20:
        return jsonify({"success": False, "error": "单次最多 20 只（每只约 10 万 tokens）"}), 400
    for s in stocks:
        if not re.match(r'^(sh|sz)\d{6}$', str(s.get('code', '')).lower()):
            return jsonify({"success": False, "error": f"非法股票代码: {s.get('code')}"}), 400

    if not save_dir:
        save_dir = os.path.join(REPORT_WORKDIR, datetime.now().strftime('%m.%d').lstrip('0').replace('.0', '.'))
    save_dir = os.path.abspath(os.path.expanduser(save_dir))
    try:
        os.makedirs(save_dir, exist_ok=True)
    except Exception as e:
        return jsonify({"success": False, "error": f"保存目录不可用: {e}"}), 400

    job_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    job = {
        'id': job_id,
        'status': 'pending',
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'save_dir': save_dir,
        'stocks': [{'code': s['code'].lower(), 'name': s.get('name', '')} for s in stocks],
        'results': {s['code'].lower(): {'status': 'pending', 'name': s.get('name', '')} for s in stocks}
    }
    _save_report_job(job)
    threading.Thread(target=_run_report_job, args=(job_id,), daemon=True).start()

    resp = dict(job)
    resp['statusText'] = _job_status_text(job)
    return jsonify({"success": True, "job": resp})


@app.route('/api/report_jobs/<job_id>')
def get_report_job(job_id):
    if not re.match(r'^\d{8}_\d{6}$', job_id):
        return jsonify({"success": False, "error": "非法任务ID"}), 400
    path = _report_job_path(job_id)
    if not os.path.exists(path):
        return jsonify({"success": False, "error": "任务不存在"}), 404
    with open(path, encoding='utf-8') as f:
        job = json.load(f)
    job['statusText'] = _job_status_text(job)
    return jsonify({"success": True, "job": job})


@app.route('/api/report_jobs_latest')
def get_latest_report_job():
    """返回最近一次任务（用于页面刷新后恢复进度显示）"""
    if not os.path.isdir(REPORT_JOBS_DIR):
        return jsonify({"success": True, "job": None})
    files = sorted(f for f in os.listdir(REPORT_JOBS_DIR) if f.endswith('.json'))
    if not files:
        return jsonify({"success": True, "job": None})
    with open(os.path.join(REPORT_JOBS_DIR, files[-1]), encoding='utf-8') as f:
        job = json.load(f)
    job['statusText'] = _job_status_text(job)
    return jsonify({"success": True, "job": job})


if __name__ == '__main__':
    # 常驻模式（launchd）下 STOCK_DEBUG=0 关闭调试器；手动终端运行默认开 debug 方便开发
    app.run(host='0.0.0.0', port=5001, debug=os.environ.get('STOCK_DEBUG', '1') == '1')

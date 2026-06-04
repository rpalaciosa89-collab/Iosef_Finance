    
    /* ====================================================================
       IOSEF FINANCE TERMINAL – Hybrid Frontend
       HTTP for base data (FastAPI)  +  WebSocket for realtime (Go)
       ==================================================================== */

    const API = 'http://127.0.0.1:8000/api';
    const WS_URL = 'ws://localhost:8080/ws/market';

    let rawData = [];
    let filteredData = [];
    let sortCol = 'signal_strength_score';
    let sortAsc = false;
    let ws = null;
    let wsConnected = false;
    let lastPrices = {};  // For flash animations
    let dropdownsDone = false;
    let currentMarket = 'nasdaq100';
    const activeAlerts = new Map(); // deduplication memory
    
    // History State
    let historyData = [];
    let historyOffset = 0;
    const historyLimit = 50;

    // ── Market Status ─────────────────────────────────────────────────────
    function updateMarketStatus() {
        function getMarketState(tz, openHour, openMin, closeHour, closeMin) {
            const now = new Date();
            const formatter = new Intl.DateTimeFormat('en-US', { timeZone: tz, weekday: 'short', hour: 'numeric', minute: 'numeric', hour12: false });
            const parts = formatter.formatToParts(now);
            let weekday = '', hour = 0, minute = 0;
            parts.forEach(p => {
                if (p.type === 'weekday') weekday = p.value;
                if (p.type === 'hour') hour = parseInt(p.value, 10);
                if (p.type === 'minute') minute = parseInt(p.value, 10);
            });
            if (hour === 24) hour = 0;
            
            const isWeekend = weekday === 'Sat' || weekday === 'Sun';
            if (isWeekend) return { state: 'closed_weekend', desc: '❌ Cerrado' };
            
            const currentTime = hour * 60 + minute;
            const openTime = openHour * 60 + openMin;
            const closeTime = closeHour * 60 + closeMin;
            
            if (currentTime >= openTime && currentTime < closeTime) {
                return { state: 'open', desc: '🟢 Abierto' };
            } else if (currentTime < openTime && openTime - currentTime <= 120) {
                return { state: 'closed_soon', desc: '🔴 Cerrado (abre pronto)' };
            } else {
                return { state: 'closed', desc: '❌ Cerrado (fuera de horario)' };
            }
        }

        const eu = getMarketState('Europe/Paris', 9, 0, 17, 30);
        const us = getMarketState('America/New_York', 9, 30, 16, 0);

        document.getElementById('ms-eu').innerHTML = `<span>🇪🇺 Europa &rarr;</span> <span style="font-weight:500;">${eu.desc}</span>`;
        document.getElementById('ms-us').innerHTML = `<span>🇺🇸 Estados Unidos &rarr;</span> <span style="font-weight:500;">${us.desc}</span>`;

        const reasonEl = document.getElementById('ms-reason');
        if (eu.state === 'closed_weekend' || us.state === 'closed_weekend') {
            reasonEl.style.display = 'block';
            reasonEl.innerHTML = '📅 Motivo: Fin de semana';
        } else if (eu.state === 'closed' && us.state === 'closed') {
            reasonEl.style.display = 'block';
            reasonEl.innerHTML = '📅 Motivo: Fuera de horario';
        } else {
            reasonEl.style.display = 'none';
        }

        let summary = "🔴 Cerrados";
        if (eu.state === 'open' && us.state === 'open') summary = "🟢 Ambos Abiertos";
        else if (eu.state === 'open') summary = "🟢 Europa Abierto";
        else if (us.state === 'open') summary = "🟢 EE.UU. Abierto";
        else if (eu.state === 'closed_soon' || us.state === 'closed_soon') summary = "🟡 Abre pronto";

        document.getElementById('market-status-summary').textContent = summary;
    }

    // ── Tab Navigation ────────────────────────────────────────────────────
    function switchView(viewName) {
        document.getElementById('tab-scanner').classList.remove('active');
        document.getElementById('tab-activas').classList.remove('active');
        document.getElementById('tab-history').classList.remove('active');
        document.getElementById('tab-analytics').classList.remove('active');
        
        document.getElementById('view-scanner').style.display = 'none';
        document.getElementById('view-activas').style.display = 'none';
        document.getElementById('view-history').style.display = 'none';
        document.getElementById('view-analytics').style.display = 'none';
        
        document.getElementById('tab-' + viewName).classList.add('active');
        document.getElementById('view-' + viewName).style.display = 'flex';
        
        if (viewName === 'history') {
            fetchHistory(true);
        } else if (viewName === 'analytics') {
            fetchAnalytics();
        } else if (viewName === 'activas') {
            renderActivas();
        }
    }

    // ── Init ──────────────────────────────────────────────────────────────
    async function init() {
        showLoadingSkeleton();
        updateMarketStatus();
        setInterval(updateMarketStatus, 60000);
        await fetchInitialData();
        populateDropdowns();
        applyFilters();
        connectWS();
        attachListeners();
        checkSystemHealth();
    }

    function showLoadingSkeleton() {
        const tbody = document.getElementById('table-body');
        let html = '';
        for (let i = 0; i < 15; i++) {
            html += '<tr class="loading-row">' + '<td></td>'.repeat(12) + '</tr>';
        }
        tbody.innerHTML = html;
    }

    // ── HTTP: Initial data from FastAPI (one-time) ────────────────────────
    async function fetchInitialData() {
        try {
            const t0 = performance.now();
            const res = await fetch(`${API}/scan?market=${currentMarket}&_t=${Date.now()}`, { cache: 'no-store' });
            const json = await res.json();
            const latency = Math.round(performance.now() - t0);
            rawData = json.data || [];
            storePrices();
            updateStats(json.timestamp);
            document.getElementById('sb-backend').textContent = `Backend: OK (${latency}ms)`;
            document.getElementById('sb-latency').textContent = `Latency: ${latency}ms`;
        } catch (e) {
            document.getElementById('sb-backend').textContent = 'Backend: OFFLINE';
            console.error('Initial fetch failed', e);
        }
    }

    // ── HTTP: History data ───────────────────────────────────────────────
    async function fetchHistory(reset = false) {
        if (reset) {
            historyOffset = 0;
            historyData = [];
            document.getElementById('history-table-body').innerHTML = '<tr><td colspan="7" style="text-align:center; padding:20px;">Cargando historial...</td></tr>';
        }
        
        try {
            const res = await fetch(`${API}/history?limit=${historyLimit}&offset=${historyOffset}&_t=${Date.now()}`, { cache: 'no-store' });
            const json = await res.json();
            
            if (reset) {
                historyData = json.data || [];
            } else {
                historyData = historyData.concat(json.data || []);
            }
            
            renderHistoryTable();
            
            const btnMore = document.getElementById('btn-load-more');
            if (json.data && json.data.length < historyLimit) {
                btnMore.style.display = 'none';
            } else {
                btnMore.style.display = 'inline-flex';
            }
            
        } catch (e) {
            console.error('History fetch failed', e);
            document.getElementById('history-table-body').innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--red); padding:20px;">Error al cargar el historial.</td></tr>';
        }
    }

    // ── HTTP: Analytics data ─────────────────────────────────────────────
    async function fetchAnalytics() {
        const summaryList = document.getElementById('analytics-summary-list');
        const tbSignals = document.getElementById('analytics-top-signals');
        const tbAssets = document.getElementById('analytics-top-assets');
        const tbContexts = document.getElementById('analytics-contexts');
        const tbExpiry = document.getElementById('analytics-high-expiry');

        summaryList.innerHTML = '<li>Cargando analíticas...</li>';
        [tbSignals, tbAssets, tbContexts, tbExpiry].forEach(el => el.innerHTML = '<tr><td colspan="4" style="text-align:center;">Cargando...</td></tr>');

        try {
            const res = await fetch(`${API}/analytics?_t=${Date.now()}`, { cache: 'no-store' });
            const json = await res.json();
            const data = json.data;

            // 1. Resumen
            summaryList.innerHTML = '';
            if (data.summary_text && data.summary_text.length > 0) {
                data.summary_text.forEach(text => {
                    const li = document.createElement('li');
                    li.textContent = text;
                    li.style.marginBottom = '6px';
                    summaryList.appendChild(li);
                });
            } else {
                summaryList.innerHTML = '<li>Sin datos suficientes.</li>';
            }

            // Helpers for tables
            const renderRows = (items, colsFunc) => {
                if (!items || items.length === 0) return '<tr><td colspan="4" style="text-align:center; color:var(--text-secondary);">Datos insuficientes</td></tr>';
                return items.map(item => `<tr>${colsFunc(item)}</tr>`).join('');
            };

            const fmtVal = val => (val || 0).toFixed(2);
            const clr = val => (val > 0) ? 'color:var(--green);' : (val < 0 ? 'color:var(--red);' : '');

            // 2. Top Señales
            tbSignals.innerHTML = renderRows(data.rankings.top_signals_by_wr, item => `
                <td style="font-weight:600;">${item.name}</td>
                <td>${item.total_trades}</td>
                <td style="font-family:var(--font-mono);">${fmtVal(item.effective_win_rate)}%</td>
                <td style="font-family:var(--font-mono);${clr(item.avg_pnl)}">${fmtVal(item.avg_pnl)}%</td>
            `);

            // 3. Mejores Activos
            tbAssets.innerHTML = renderRows(data.rankings.top_assets_by_wr, item => `
                <td style="font-weight:600;">${item.name}</td>
                <td>${item.total_trades}</td>
                <td style="font-family:var(--font-mono);">${fmtVal(item.effective_win_rate)}%</td>
                <td style="font-family:var(--font-mono);${clr(item.avg_pnl)}">${fmtVal(item.avg_pnl)}%</td>
            `);

            // 4. Contextos
            const contextsArr = Object.entries(data.context_analytics || {}).map(([k,v]) => ({name:k, ...v})).sort((a,b) => b.total_trades - a.total_trades);
            tbContexts.innerHTML = renderRows(contextsArr, item => `
                <td style="font-weight:600;">${item.name.toUpperCase()}</td>
                <td>${item.total_trades}</td>
                <td style="font-family:var(--font-mono);">${fmtVal(item.effective_win_rate)}%</td>
                <td style="font-family:var(--font-mono);">${fmtVal(item.expiry_rate)}%</td>
            `);

            // 5. Altas Expiraciones
            tbExpiry.innerHTML = renderRows(data.rankings.high_expiry_signals, item => `
                <td style="font-weight:600;">${item.name}</td>
                <td>${item.total_trades}</td>
                <td style="font-family:var(--font-mono);color:var(--red);">${fmtVal(item.expiry_rate)}%</td>
                <td style="font-family:var(--font-mono);">${fmtVal(item.effective_win_rate)}%</td>
            `);

        } catch (e) {
            console.error('Analytics fetch failed', e);
            summaryList.innerHTML = '<li style="color:var(--red);">Error cargando analíticas</li>';
            [tbSignals, tbAssets, tbContexts, tbExpiry].forEach(el => el.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--red);">Error</td></tr>');
        }
    }    
    function loadMoreHistory() {
        historyOffset += historyLimit;
        fetchHistory(false);
    }
    
    function formatHistoryTime(val) {
        if (!val) return 'No disponible';
        let d = new Date(val);
        if (isNaN(d.getTime())) {
            if (!isNaN(val)) {
                const num = Number(val);
                const ms = num < 10000000000 ? num * 1000 : num;
                d = new Date(ms);
            }
        }
        if (isNaN(d.getTime())) return 'No disponible';
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function renderHistoryTable() {
        const tbody = document.getElementById('history-table-body');
        
        if (!historyData || historyData.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:20px; color:var(--text-secondary);">No hay operaciones cerradas registradas en el historial.</td></tr>';
            return;
        }
        
        let html = '';
        historyData.forEach((trade, idx) => {
            // PARTE 5: Frontend defensivo. Si falta algún campo crítico, no renderizar la fila.
            if (trade.entry_price == null || trade.stop_loss == null || trade.take_profit == null) {
                return; // Skip rendering
            }

            // Determine result display
            let resDisplay = '';
            let pnlColor = 'var(--text-primary)';
            
            if (trade.trade_result === 'win') {
                resDisplay = '<span class="status-badge" style="background:var(--green-dim);color:var(--green);border:1px solid rgba(0,200,150,0.3);"><span class="icon">✅</span> GANADOR</span>';
                pnlColor = 'var(--green)';
            } else if (trade.trade_result === 'loss') {
                resDisplay = '<span class="status-badge" style="background:var(--red-dim);color:var(--red);border:1px solid rgba(255,71,87,0.3);"><span class="icon">❌</span> PERDEDOR</span>';
                pnlColor = 'var(--red)';
            } else {
                resDisplay = '<span class="status-badge" style="background:var(--amber-dim);color:var(--amber);border:1px solid rgba(245,158,11,0.3);"><span class="icon">⏳</span> EXPIRADO</span>';
                pnlColor = 'var(--amber)';
            }
            
            const pnlStr = trade.pnl_percentage ? (trade.pnl_percentage > 0 ? '+' : '') + trade.pnl_percentage.toFixed(2) + '%' : '0.00%';
            
            const entry = trade.entry_price ? trade.entry_price.toFixed(2) : '—';
            const tp = trade.take_profit ? trade.take_profit.toFixed(2) : '—';
            const sl = trade.stop_loss ? trade.stop_loss.toFixed(2) : '—';
            
            let durationStr = '—';
            if (trade.trade_duration_seconds) {
                const mins = Math.floor(trade.trade_duration_seconds / 60);
                durationStr = mins > 0 ? `${mins}m` : `${trade.trade_duration_seconds}s`;
            }
            
            const detectedDate = formatHistoryTime(trade.signal_detected_at);
            const closedDate = formatHistoryTime(trade.trade_closed_at);
            
            html += `<tr onclick="openHistoryModal(${idx})">
                <td>
                    <div style="font-weight:600;font-size:13px;">${trade.ticker}</div>
                    <div style="font-size:10px;color:var(--text-secondary);">${trade.trade_direction || ''}</div>
                </td>
                <td>
                    <div style="font-weight:500;">${trade.human_signal || trade.signal_type || '—'}</div>
                    <div style="font-size:10px;color:var(--text-secondary);">Riesgo/Beneficio: ${trade.risk_reward_ratio || '—'}</div>
                </td>
                <td>${resDisplay}</td>
                <td style="font-family:var(--font-mono); font-weight:600; color:${pnlColor};">${pnlStr}</td>
                <td>
                    <div style="font-family:var(--font-mono);font-size:11px;">Ent: ${entry}</div>
                    <div style="font-family:var(--font-mono);font-size:10px;color:var(--text-secondary);">TP: ${tp} | SL: ${sl}</div>
                </td>
                <td style="font-family:var(--font-mono);">${durationStr}</td>
                <td>
                    <div style="font-size:11px;">Apertura: ${detectedDate}</div>
                    <div style="font-size:11px;color:var(--text-secondary);">Cierre: ${closedDate}</div>
                </td>
            </tr>`;
        });
        
        tbody.innerHTML = html;
    }

    // ── WebSocket: Realtime from Go ───────────────────────────────────────
    function connectWS() {
        setWsStatus('connecting');
        ws = new WebSocket(WS_URL);

        ws.onopen = () => {
            wsConnected = true;
            setWsStatus('live');
            document.getElementById('sb-ws').textContent = 'WebSocket: CONNECTED';
        };

        ws.onmessage = (evt) => {
            try {
                const payload = JSON.parse(evt.data);
                // Only process messages for the currently selected market
                if (payload.market && payload.market !== currentMarket) return;
                
                // Process Alerts
                if (payload.alerts && payload.alerts.length > 0) {
                    processAlerts(payload.alerts);
                }

                if (payload.tickers && payload.tickers.length > 0) {
                    rawData = payload.tickers;
                    if (!dropdownsDone) { populateDropdowns(); dropdownsDone = true; }
                    applyFilters();
                    updateStats(payload.timestamp);
                    updateMarketBar();
                }
            } catch (e) { console.error('WS parse error', e); }
        };

        ws.onclose = () => {
            wsConnected = false;
            setWsStatus('offline');
            document.getElementById('sb-ws').textContent = 'WebSocket: RECONNECTING…';
            setTimeout(connectWS, 3000);
        };

        ws.onerror = () => { ws.close(); };
    }

    function setWsStatus(state) {
        const dot = document.getElementById('ws-dot');
        const label = document.getElementById('ws-label');
        dot.className = 'status-dot ' + state;
        const labels = { live: 'LIVE', offline: 'OFFLINE', connecting: 'CONNECTING' };
        label.textContent = labels[state] || state;
    }

    // ── Live Alerts ───────────────────────────────────────────────────────
    function processAlerts(alerts) {
        const list = document.getElementById('alerts-list');
        if (!list) return;

        const now = Date.now();

        alerts.forEach(alert => {
            const id = `${alert.ticker}-${alert.type}`;
            const lastSeen = activeAlerts.get(id);

            // Deduplicate: Don't show the exact same alert within 15 minutes (900,000 ms)
            if (!lastSeen || (now - lastSeen > 900000)) {
                activeAlerts.set(id, now);

                const li = document.createElement('li');
                li.className = `alert-${alert.color}`;
                li.innerHTML = `
                    <div class="alert-top">
                        <span class="alert-ticker">${alert.ticker}</span>
                        <span class="alert-time">${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'})}</span>
                    </div>
                    <div class="alert-msg">${alert.message}</div>
                `;
                list.insertBefore(li, list.firstChild);
            }
        });

        // Limit to 20 visible alerts
        while (list.children.length > 20) {
            list.removeChild(list.lastChild);
        }
    }

    // ── System health check ──────────────────────────────────────────────
    async function checkSystemHealth() {
        try {
            const res = await fetch('http://localhost:8080/health');
            const data = await res.json();
            document.getElementById('sb-redis').textContent = `Redis: ${data.redis_status?.toUpperCase() || 'OK'}`;
            document.getElementById('system-info').innerHTML = `
                <div style="margin-bottom:4px;"><span style="color:var(--text-tertiary)">Go Server:</span> <span style="color:var(--green)">Online</span></div>
                <div style="margin-bottom:4px;"><span style="color:var(--text-tertiary)">Redis:</span> <span style="color:var(--green)">${data.redis_status}</span></div>
                <div style="margin-bottom:4px;"><span style="color:var(--text-tertiary)">WS Clients:</span> ${data.connected_clients}</div>
                <div><span style="color:var(--text-tertiary)">Uptime:</span> ${data.uptime}</div>
            `;
        } catch (e) {
            document.getElementById('sb-redis').textContent = 'Redis: —';
        }
    }
    setInterval(checkSystemHealth, 15000);

    // ── Stats ─────────────────────────────────────────────────────────────
    function updateStats(ts) {
        document.getElementById('stat-count').textContent = rawData.length;
        document.getElementById('stat-time').textContent = ts ? new Date(ts * 1000).toLocaleTimeString() : '—';
    }

    // ── Market Ticker Bar ────────────────────────────────────────────────
    function updateMarketBar() {
        const bar = document.getElementById('market-bar');
        const top = rawData.slice(0, 15);
        bar.innerHTML = top.map((t, i) => {
            const cls = t.change_pct >= 0 ? 'positive' : 'negative';
            const sign = t.change_pct >= 0 ? '+' : '';
            return `<div class="market-chip">
                <span class="sym">${t.ticker}</span>
                <span class="price">${t.price.toFixed(2)}</span>
                <span class="chg ${cls}">${sign}${t.change_pct.toFixed(2)}%</span>
                ${i < top.length - 1 ? '<span class="divider"></span>' : ''}
            </div>`;
        }).join('');
    }

    // ── Price tracking for flash ──────────────────────────────────────────
    function storePrices() {
        rawData.forEach(t => { lastPrices[t.ticker] = t.price; });
    }

    // ── Dropdowns ─────────────────────────────────────────────────────────
    function populateDropdowns() {
        const sectors = new Set();
        rawData.forEach(t => { if (t.sector) sectors.add(t.sector); });
        const sel = document.getElementById('f-sector');
        sel.innerHTML = '<option value="all">All</option>';
        [...sectors].sort().forEach(s => {
            sel.innerHTML += `<option value="${s}">${s}</option>`;
        });
    }

    // ── Attach listeners ──────────────────────────────────────────────────
    function attachListeners() {
        document.querySelectorAll('th[data-col]').forEach(th => {
            th.addEventListener('click', () => {
                const col = th.dataset.col;
                if (sortCol === col) sortAsc = !sortAsc;
                else { sortCol = col; sortAsc = false; }
                applyFilters();
            });
        });
        document.querySelectorAll('.filter-bar select, .filter-bar input').forEach(el => {
            el.addEventListener('input', applyFilters);
        });
        document.getElementById('market-selector').addEventListener('change', async (e) => {
            currentMarket = e.target.value;
            dropdownsDone = false;
            showLoadingSkeleton();
            await fetchInitialData();
            populateDropdowns();
            applyFilters();
        });
        document.getElementById('btn-signal-lab').addEventListener('click', openSignalLab);
        document.getElementById('btn-strategy-lab').addEventListener('click', () => {
            if (typeof openStrategyLab === 'function') openStrategyLab();
        });
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape') {
                closeModal();
                closeSignalLab();
                if (typeof closeStrategyLab === 'function') closeStrategyLab();
            }
        });
    }

    // ── Filters ───────────────────────────────────────────────────────────
    function applyFilters() {
        const tQ = document.getElementById('f-ticker').value.toUpperCase();
        const sQ = document.getElementById('f-sector').value;
        const rQ = document.getElementById('f-rsi').value;
        const vQ = document.getElementById('f-vol').value;
        const sigQ = document.getElementById('f-signal').value;

        filteredData = rawData.filter(t => {
            if (tQ && !t.ticker.includes(tQ)) return false;
            if (sQ !== 'all' && t.sector !== sQ) return false;
            if (rQ === 'oversold' && t.rsi >= 30) return false;
            if (rQ === 'overbought' && t.rsi <= 70) return false;
            if (rQ === 'neutral' && (t.rsi < 30 || t.rsi > 70)) return false;
            if (vQ === 'high' && t.relative_volume <= 1.5) return false;
            if (vQ === 'low' && t.relative_volume >= 0.8) return false;
            if (sigQ === 'bullish' && t.composite_score < 6) return false;
            if (sigQ === 'bearish' && t.composite_score > 2) return false;
            if (sigQ === 'breakout' && !t.ma_breakout_signal) return false;
            return true;
        });

        filteredData.sort((a, b) => {
            let va = a[sortCol], vb = b[sortCol];
            if (va == null) va = '';
            if (vb == null) vb = '';
            if (typeof va === 'string') return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
            if (typeof va === 'boolean') { va = va ? 1 : 0; vb = vb ? 1 : 0; }
            return sortAsc ? va - vb : vb - va;
        });

        renderTable();
        renderActivas();
        renderSidePanels();
        document.getElementById('filter-count').textContent = `${filteredData.length} / ${rawData.length}`;
    }

    // ── Table render ──────────────────────────────────────────────────────
    function renderTable() {
        const tbody = document.getElementById('table-body');

        // Update sort indicators
        document.querySelectorAll('th[data-col]').forEach(th => {
            th.classList.remove('sorted', 'sort-asc', 'sort-desc');
            if (th.dataset.col === sortCol) {
                th.classList.add('sorted', sortAsc ? 'sort-asc' : 'sort-desc');
            }
        });

        let displayData = filteredData;
        if (viewMode === 'simple') {
            displayData = filteredData.filter(t => {
                const pScore = t.signal_strength_score != null ? t.signal_strength_score : 0;
                const clarity = t.decision_clarity || 'baja';
                return pScore >= 60 && clarity !== 'baja';
            }).slice(0, 3);
        }

        const total_signals_detected = filteredData.length;
        const signals_passing_filter = displayData.length;

        if (signals_passing_filter === 0) {
            if (viewMode === 'simple') {
                if (total_signals_detected > 0) {
                    tbody.innerHTML = `
                        <tr>
                            <td colspan="20" style="padding: 60px 20px; text-align: center; border-bottom: none;">
                                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; max-width: 500px; margin: 0 auto; gap: 15px;">
                                    <div style="font-size: 3rem; margin-bottom: 5px; opacity: 0.9;">🧠</div>
                                    <div style="font-size: 1.25rem; font-weight: 600; color: var(--text-primary); letter-spacing: -0.01em;">Estado del sistema</div>
                                    <div style="color: var(--text-secondary); font-size: 1rem; line-height: 1.5; text-align: center;">
                                        Se detectaron <span style="font-weight: 600; color: var(--text-primary);">${total_signals_detected}</span> señales en este mercado.<br>
                                        Ninguna cumple los criterios de calidad actuales.
                                    </div>
                                    <div style="background: var(--bg-tertiary); padding: 15px 20px; border-radius: 8px; border: 1px solid var(--border); width: 100%; text-align: center; margin-top: 5px;">
                                        <div style="color: var(--text-primary); font-weight: 500; margin-bottom: 5px; font-size: 0.95rem;">El sistema está en modo observación.</div>
                                        <div style="color: var(--text-secondary); font-size: 0.85rem;">👉 Se prioriza no operar antes que tomar señales sin ventaja clara.</div>
                                    </div>
                                </div>
                            </td>
                        </tr>
                    `;
                } else {
                    tbody.innerHTML = `
                        <tr>
                            <td colspan="20" style="padding: 60px 20px; text-align: center; border-bottom: none;">
                                <div style="color: var(--text-secondary); font-size: 1.05rem;">
                                    No hay actividad relevante en este mercado en este momento.
                                </div>
                            </td>
                        </tr>
                    `;
                }
            } else {
                tbody.innerHTML = '<tr><td colspan="20" style="text-align:center; padding:40px 20px; color: var(--text-secondary);">No se encontraron resultados</td></tr>';
            }
            storePrices();
            return;
        }

        const rows = displayData.map(t => {
            const chgCls = t.change_pct >= 0 ? 'positive' : 'negative';
            const chgSign = t.change_pct >= 0 ? '+' : '';
            const momCls = t.momentum_1m >= 0 ? 'positive' : 'negative';
            const momSign = t.momentum_1m >= 0 ? '+' : '';

            // RSI coloring
            let rsiCls = '';
            let rsiBarColor = 'var(--text-tertiary)';
            if (t.rsi < 30) { rsiCls = 'positive'; rsiBarColor = 'var(--green)'; }
            else if (t.rsi > 70) { rsiCls = 'negative'; rsiBarColor = 'var(--red)'; }

            // Score badge
            let scoreCls = 'score-neutral';
            if (t.composite_score >= 6) scoreCls = 'score-bullish';
            else if (t.composite_score <= 2) scoreCls = 'score-bearish';

            // Priority badge
            const pScore = t.signal_strength_score != null ? t.signal_strength_score : 0;
            let priCls = 'priority-low';
            let priIcon = '🔴';
            if (pScore >= 75) { priCls = 'priority-high'; priIcon = '🔥'; }
            else if (pScore >= 40) { priCls = 'priority-medium'; priIcon = '🟡'; }
            const srcCls = t.signal_strength_source === 'optimized' ? 'source-optimized' : 'source-fallback';
            const srcLabel = t.signal_strength_source === 'optimized' ? 'OPT' : 'FB';
            // Simple-mode priority: icon + text label (no score number, no OPT/FB tag)
            const priSimpleLabel = pScore >= 75 ? '🔥 Alta' : pScore >= 40 ? '🟡 Media' : '⚪ Baja';

            // Breakout signal
            const signal = t.ma_breakout_signal ? '<span class="breakout-badge">BRK</span>' : '';

            // Flash detection
            const prev = lastPrices[t.ticker];
            let flashCls = '';
            if (prev !== undefined && prev !== t.price) {
                flashCls = t.price > prev ? 'flash-up' : 'flash-down';
            }

            // Indicator "En seguimiento"
            let trackingIndicator = '';
            if (t.trade_tracking && t.trade_tracking.trade_status === 'open') {
                trackingIndicator = '<span style="font-size: 0.65rem; background: var(--bg-tertiary); color: var(--text-secondary); padding: 2px 4px; border-radius: 4px; margin-left: 6px; border: 1px solid var(--border);" title="Esta oportunidad ya está en Operaciones Activas">👁️ En seguimiento</span>';
            }

            return `<tr onclick="openModal('${t.ticker}')" class="${flashCls}">
                <td class="ticker-cell" style="display:flex; align-items:center;">${t.ticker}${trackingIndicator}</td>
                <td class="sector-cell col-pro">${t.sector || '—'}</td>
                <td>${t.price.toFixed(2)}</td>
                <td class="${chgCls}">${chgSign}${t.change_pct.toFixed(2)}%</td>
                <td class="col-pro"><span class="rsi-bar"><span class="rsi-indicator" style="background:${rsiBarColor}"></span><span class="${rsiCls}">${t.rsi.toFixed(1)}</span></span></td>
                <td class="col-pro">${t.relative_volume.toFixed(2)}x</td>
                <td class="col-pro">${t.sma20.toFixed(2)}</td>
                <td class="col-pro">${t.sma50.toFixed(2)}</td>
                <td class="col-pro">${t.sma200.toFixed(2)}</td>
                <td class="col-pro ${momCls}">${momSign}${t.momentum_1m.toFixed(2)}%</td>
                <td class="col-pro"><span class="priority-badge ${priCls}">${priIcon} ${pScore.toFixed(0)} <span class="source-tag ${srcCls}">${srcLabel}</span></span></td>
                <td class="col-pro"><span class="score-badge ${scoreCls}">${t.composite_score}</span></td>
                <td class="col-pro">${signal}</td>
                <td class="col-simple"><span class="priority-badge ${priCls}">${priSimpleLabel}</span></td>
                <td class="col-simple">${humanSignalBadge(t)}</td>
                <td class="col-simple">${buildLifecyclePills(t)}</td>
                <td class="col-simple">${actionBadge(t.suggested_action)}</td>
                <td class="col-simple" style="color:var(--text-secondary);font-size:0.78rem">${t.holding_period || '—'}</td>
                <td class="col-simple">${riskBadge(t.risk_level)}</td>
                <td class="col-simple">${clarityBadge(t.decision_clarity)}</td>
            </tr>`;
        });

        tbody.innerHTML = rows.join('');
        storePrices();
    }

    // ── Activas render ────────────────────────────────────────────────────────
    function renderActivas() {
        const container = document.getElementById('activas-container');
        if (!rawData || rawData.length === 0) {
            container.innerHTML = '<div style="text-align:center; padding: 40px; color: var(--text-secondary);">Cargando operaciones activas...</div>';
            return;
        }

        const activeTrades = rawData.filter(t => t.trade_tracking && t.trade_tracking.trade_status === 'open');

        const selMkt = document.getElementById('market-selector').value;
        let marketName = '🇺🇸 NASDAQ 100';
        if (selMkt === 'sp500') marketName = '🇺🇸 S&P 500';
        else if (selMkt === 'europe') marketName = '🇪🇺 Europa';

        let html = `<div style="margin-bottom: 30px;">
            <h3 style="font-size: 14px; font-weight: 600; color: var(--text-primary); margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid var(--border);">${marketName}</h3>`;

        if (activeTrades.length === 0) {
            html += `<div style="background: var(--bg-2); border: 1px solid var(--border); border-radius: 6px; padding: 30px; text-align: center; color: var(--text-secondary);">
                Sin operaciones activas en este mercado
            </div>`;
        } else {
            html += `<table class="data-table">
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th>Señal</th>
                        <th>Estado</th>
                        <th>Tiempo Activo</th>
                        <th>PnL Flotante</th>
                    </tr>
                </thead>
                <tbody>`;
            
            activeTrades.forEach(t => {
                const tracking = t.trade_tracking;
                const pnl = tracking.pnl_percentage || 0;
                const pnlColor = pnl > 0 ? 'var(--green)' : (pnl < 0 ? 'var(--red)' : 'var(--text-secondary)');
                const pnlSign = pnl > 0 ? '+' : '';
                
                const durationStr = tracking.trade_duration_seconds ? 
                    (tracking.trade_duration_seconds < 3600 ? Math.floor(tracking.trade_duration_seconds / 60) + ' min' : Math.floor(tracking.trade_duration_seconds / 3600) + ' h') : '0 min';

                let statusBadge = '<span style="color: var(--green); font-size: 0.8rem;">🟢 Vigente</span>';
                if (t.signal_status === 'weakening') statusBadge = '<span style="color: var(--yellow); font-size: 0.8rem;">🟡 Debilitándose</span>';

                html += `<tr onclick="openModal('${t.ticker}')" style="cursor:pointer;">
                    <td style="font-weight: 600;">${t.ticker}</td>
                    <td>${humanSignalBadge(t)}</td>
                    <td>${statusBadge}</td>
                    <td style="color: var(--text-secondary);">${durationStr}</td>
                    <td style="font-weight: 600; color: ${pnlColor};">${pnlSign}${pnl.toFixed(1)}%</td>
                </tr>`;
            });
            
            html += `</tbody></table>`;
        }
        html += `</div>`;

        container.innerHTML = html;
    }

    // ── Human Layer helpers ──────────────────────────────────────────────────
    function humanSignalClass(sig) {
        if (!sig) return 'hs-none';
        const s = sig.toUpperCase();
        if (s.includes('REBOTE'))    return 'hs-rebote';
        if (s.includes('RUPTURA'))   return 'hs-ruptura';
        if (s.includes('TENDENCIA')) return 'hs-tendencia';
        if (s.includes('COMPRAS'))   return 'hs-compras';
        if (s.includes('EXCESIVA'))  return 'hs-excesiva';
        if (s.includes('VENTAS'))    return 'hs-ventas';
        if (s.includes('SOPORTE'))   return 'hs-soporte';
        if (s.includes('DÉBIL') || s.includes('DEBIL')) return 'hs-debil';
        return 'hs-none';
    }
    function humanSignalBadge(t) {
        const sig = t.human_signal || '— SIN SEÑAL';
        return `<span class="human-signal-badge ${humanSignalClass(sig)}">${sig}</span>`;
    }
    function actionClass(action) {
        if (!action) return 'action-esperar';
        const a = action.toLowerCase();
        if (a.includes('evitar') || a.includes('vender') || a.includes('reducir')) return 'action-evitar';
        if (a.includes('tomar'))   return 'action-tomar';
        if (a.includes('comprar con') || a.includes('precauci') || a.includes('vigilar antes')) return 'action-precaucion';
        if (a.includes('comprar')) return 'action-comprar';
        if (a.includes('vigilar')) return 'action-vigilar';
        return 'action-esperar';
    }
    function actionBadge(action) {
        return `<span class="action-pill ${actionClass(action)}">${action || 'Esperar'}</span>`;
    }
    function riskClass(risk) {
        if (!risk) return 'risk-alto';
        const r = risk.toLowerCase();
        if (r.startsWith('medio-alto') || r.startsWith('medio alto')) return 'risk-medio-alto';
        if (r.startsWith('medio')) return 'risk-medio';
        return 'risk-alto';
    }
    function riskBadge(risk) {
        return `<span class="risk-pill ${riskClass(risk)}">${risk || 'Alto'}</span>`;
    }
    function clarityClass(clarity) {
        if (clarity === 'alta')  return 'clarity-alta';
        if (clarity === 'media') return 'clarity-media';
        return 'clarity-baja';
    }
    function clarityBadge(clarity) {
        return `<span class="clarity-badge ${clarityClass(clarity)}">${clarity || 'baja'}</span>`;
    }

    // ── Mode Toggle ──────────────────────────────────────────────────────────
    let viewMode = localStorage.getItem('iosef_view_mode') || 'pro';
    function toggleMode(mode) {
        viewMode = mode;
        localStorage.setItem('iosef_view_mode', mode);
        document.body.classList.toggle('mode-simple', mode === 'simple');
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === mode);
        });
        // Update Signal Lab button label per mode
        const sigLabBtn = document.getElementById('btn-signal-lab');
        if (sigLabBtn) {
            sigLabBtn.innerHTML = mode === 'simple' ? '📊 VER ANÁLISIS' : '🔬 SIGNAL LAB';
        }
        renderTable();
    }
    (function applyInitialMode() {
        if (viewMode === 'simple') {
            document.body.classList.add('mode-simple');
            document.querySelectorAll('.mode-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.mode === 'simple');
            });
            const sigLabBtn = document.getElementById('btn-signal-lab');
            if (sigLabBtn) sigLabBtn.innerHTML = '📊 VER ANÁLISIS';
        }
    })();



    // ── Side panels ───────────────────────────────────────────────────────
    function renderSidePanels() {
        const valid = rawData.filter(t => t.change_pct != null);

        // Gainers
        const gainers = [...valid].sort((a, b) => b.change_pct - a.change_pct).slice(0, 8);
        document.getElementById('gainers-list').innerHTML = gainers.map(t =>
            `<li class="side-item" onclick="openModal('${t.ticker}')">
                <span class="sym">${t.ticker}</span>
                <span class="price-col">${t.price.toFixed(2)}</span>
                <span class="chg-col positive">+${t.change_pct.toFixed(2)}%</span>
            </li>`
        ).join('');

        // Losers
        const losers = [...valid].sort((a, b) => a.change_pct - b.change_pct).slice(0, 8);
        document.getElementById('losers-list').innerHTML = losers.map(t =>
            `<li class="side-item" onclick="openModal('${t.ticker}')">
                <span class="sym">${t.ticker}</span>
                <span class="price-col">${t.price.toFixed(2)}</span>
                <span class="chg-col negative">${t.change_pct.toFixed(2)}%</span>
            </li>`
        ).join('');

        // Breakouts
        const brk = valid.filter(t => t.ma_breakout_signal).sort((a, b) => (b.signal_strength_score||0) - (a.signal_strength_score||0)).slice(0, 8);
        document.getElementById('breakouts-list').innerHTML = brk.length > 0
            ? brk.map(t => {
                const ps = t.signal_strength_score != null ? t.signal_strength_score : 0;
                const pIcon = ps >= 75 ? '🔥' : ps >= 40 ? '🟡' : '🔴';
                return `<li class="side-item" onclick="openModal('${t.ticker}')">
                    <span class="sym">${t.ticker}</span>
                    <span class="price-col">${pIcon} ${ps.toFixed(0)}</span>
                    <span class="chg-col" style="color:var(--blue)">⚡ BRK</span>
                </li>`;
            }).join('')
            : '<li class="side-item"><span style="color:var(--text-tertiary)">No breakouts detected</span></li>';
    }

    // ── Modal ─────────────────────────────────────────────────────────────
    async function openModal(ticker) {
        const overlay = document.getElementById('modal-overlay');
        const body = document.getElementById('modal-body');
        overlay.classList.add('active');
        document.getElementById('modal-ticker').textContent = ticker;

        const scanItem = rawData.find(t => t.ticker === ticker);
        document.getElementById('modal-subtitle').textContent = scanItem
            ? `${scanItem.sector || ''} · ${scanItem.industry || ''}`
            : '';

        body.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-tertiary)">Loading…</div>';

        try {
            const [dRes, fRes] = await Promise.all([
                fetch(`${API}/ticker/${ticker}?_t=${Date.now()}`, { cache: 'no-store' }),
                fetch(`${API}/ticker/${ticker}/financials?_t=${Date.now()}`, { cache: 'no-store' })
            ]);
            const dData = await dRes.json();
            const fData = await fRes.json();
            const info = dData.data || {};
            const fins = fData.data || {};
            let html = '<div class="modal-layout">';

            // ── Human Summary (always visible: Pro + Simple) ─────────────────
            if (scanItem && scanItem.human_signal) {
                const sigCls  = humanSignalClass(scanItem.human_signal);
                const actCls  = actionClass(scanItem.suggested_action);
                const rskCls  = riskClass(scanItem.risk_level);
                const clrCls  = clarityClass(scanItem.decision_clarity);
                html += `<div class="human-summary-card" style="grid-column:1/-1">
                    <div class="human-summary-header">
                        <span class="human-signal-big human-signal-badge ${sigCls}">${scanItem.human_signal}</span>
                        <span class="clarity-badge ${clrCls}">Claridad: ${scanItem.decision_clarity || 'baja'}</span>
                    </div>
                    <p class="human-explanation-text">${scanItem.explanation || ''}</p>
                    <div class="human-meta-row">
                        <div class="human-meta-item">
                            <span class="human-meta-label">Acción</span>
                            <span class="action-pill ${actCls}">${scanItem.suggested_action || 'Esperar'}</span>
                        </div>
                        <div class="human-meta-item">
                            <span class="human-meta-label">Horizonte</span>
                            <span style="font-size:12px;color:var(--text-secondary)">⏱️ ${scanItem.holding_period || '—'}</span>
                        </div>
                        <div class="human-meta-item">
                            <span class="human-meta-label">Riesgo</span>
                            <span class="risk-pill ${rskCls}">${scanItem.risk_level || '—'}</span>
                        </div>
                        <div class="human-meta-item" style="margin-left:auto">
                            <span class="human-meta-label">Confianza</span>
                            <span style="font-size:11px;color:var(--text-tertiary)">${scanItem.confidence_text || '—'}</span>
                        </div>
                    </div>
                </div>`;
            }

            // Signal Lifecycle Block (both modes)
            if (scanItem && scanItem.signal_status) {
                html += buildEstadoSenal(scanItem);
                
                // Trade Plan Block
                if (scanItem.trade_plan && Object.keys(scanItem.trade_plan).length > 0) {
                    html += buildTradePlan(scanItem.trade_plan);
                }

                // Trade Tracking Block
                if (scanItem.trade_tracking && Object.keys(scanItem.trade_tracking).length > 0) {
                    html += buildTradeTracking(scanItem.trade_tracking);
                }
            }

            // Chart Section (Full Width)
            html += '<div class="chart-section" style="width:100%;">';
            html += `
            <div class="tf-bar">
                <button class="tf-btn active" data-period="1d" data-interval="1m" onclick="changeTimeframe(this, '${ticker}')">1D</button>
                <button class="tf-btn" data-period="5d" data-interval="5m" onclick="changeTimeframe(this, '${ticker}')">5D</button>
                <button class="tf-btn" data-period="1mo" data-interval="30m" onclick="changeTimeframe(this, '${ticker}')">1M</button>
                <button class="tf-btn" data-period="3mo" data-interval="1d" onclick="changeTimeframe(this, '${ticker}')">3M</button>
                <button class="tf-btn" data-period="1y" data-interval="1d" onclick="changeTimeframe(this, '${ticker}')">1Y</button>
            </div>
            <div id="chart-container" style="width:100%; min-width:100%; max-width:100%;"></div>
            `;
            html += '</div>';

            // Pro Only Section (Technical Data + Financials)
            html += '<div class="pro-only-block" style="width:100%; display:flex; flex-direction:column; gap:24px;">';
            
            // Detail Grid
            html += '<div class="detail-grid">';
            
            if (scanItem) {
                const sCls = scanItem.composite_score >= 6 ? 'score-bullish' : scanItem.composite_score <= 2 ? 'score-bearish' : 'score-neutral';
                const chgCls = scanItem.change_pct >= 0 ? 'positive' : 'negative';
                const chgSign = scanItem.change_pct >= 0 ? '+' : '';
                const momCls = scanItem.momentum_1m >= 0 ? 'positive' : 'negative';
                const momSign = scanItem.momentum_1m >= 0 ? '+' : '';
                let rsiCls = '';
                if (scanItem.rsi < 30) rsiCls = 'positive';
                else if (scanItem.rsi > 70) rsiCls = 'negative';

                const breakoutHtml = scanItem.ma_breakout_signal ? '<span class="breakout-badge">BRK</span>' : '<span style="color:var(--text-tertiary)">None</span>';

                html += detailCard('Ticker', scanItem.ticker);
                html += detailCard('Sector', scanItem.sector || '—');
                html += detailCard('Industry', scanItem.industry || '—');
                html += detailCard('Last Price', `$${scanItem.price.toFixed(2)}`);
                html += detailCard('Change %', `<span class="${chgCls}">${chgSign}${scanItem.change_pct.toFixed(2)}%</span>`);
                html += detailCard('RSI', `<span class="${rsiCls}">${scanItem.rsi.toFixed(2)}</span>`);
                html += detailCard('Relative Vol', `${scanItem.relative_volume.toFixed(2)}x`);
                html += detailCard('Composite Score', `<span class="score-badge ${sCls}">${scanItem.composite_score}</span>`);

                // Priority Score
                const pSc = scanItem.signal_strength_score != null ? scanItem.signal_strength_score : 0;
                let pCls = 'priority-low';
                let pIcn = '🔴';
                if (pSc >= 75) { pCls = 'priority-high'; pIcn = '🔥'; }
                else if (pSc >= 40) { pCls = 'priority-medium'; pIcn = '🟡'; }
                const pSrcCls = scanItem.signal_strength_source === 'optimized' ? 'source-optimized' : 'source-fallback';
                const pSrcLbl = scanItem.signal_strength_source === 'optimized' ? 'Optimized' : 'Fallback';
                html += detailCard('Prioridad', `<span class="priority-badge ${pCls}">${pIcn} ${pSc.toFixed(1)}</span>`);
                html += detailCard('Score Source', `<span class="source-tag ${pSrcCls}" style="font-size:0.75rem;padding:2px 8px">${pSrcLbl}</span>`);

                html += detailCard('Breakout', breakoutHtml);
                html += detailCard('SMA20', `$${scanItem.sma20.toFixed(2)}`);
                html += detailCard('SMA50', `$${scanItem.sma50.toFixed(2)}`);
                html += detailCard('SMA200', `$${scanItem.sma200.toFixed(2)}`);
                html += detailCard('Momentum 1M', `<span class="${momCls}">${momSign}${scanItem.momentum_1m.toFixed(2)}%</span>`);
            } else {
                html += detailCard('Last Price', info.lastPrice ? '$' + info.lastPrice.toFixed(2) : '—');
                html += detailCard('Market Cap', info.marketCap ? '$' + (info.marketCap / 1e9).toFixed(2) + 'B' : '—');
                html += detailCard('Day Range', info.dayLow && info.dayHigh ? `$${info.dayLow.toFixed(2)} – $${info.dayHigh.toFixed(2)}` : '—');
                html += detailCard('52W Range', info.yearLow && info.yearHigh ? `$${info.yearLow.toFixed(2)} – $${info.yearHigh.toFixed(2)}` : '—');
                html += detailCard('50D Avg', info.fiftyDayAverage ? '$' + info.fiftyDayAverage.toFixed(2) : '—');
                html += detailCard('200D Avg', info.twoHundredDayAverage ? '$' + info.twoHundredDayAverage.toFixed(2) : '—');
            }
            html += '</div>'; // end detail-grid

            // Technical Reading
            if (scanItem) {
                html += generateTechReading(scanItem);
            }

            // Financials Table
            if (Object.keys(fins).length > 0) {
                html += '<div class="financials-section" style="margin-top: 10px;">';
                html += '<h3 style="margin-bottom:10px;font-size:13px;color:var(--text-secondary)">Quarterly Financials</h3>';
                const dates = Object.keys(fins).sort((a, b) => new Date(b) - new Date(a));
                const metrics = Object.keys(fins[dates[0]]);
                html += '<div style="width:100%;overflow-x:auto;"><table class="fin-table"><thead><tr><th>Metric</th>';
                dates.forEach(d => html += `<th>${d.substring(0, 10)}</th>`);
                html += '</tr></thead><tbody>';
                metrics.forEach(m => {
                    html += `<tr><td style="text-align:left;font-weight:500">${m}</td>`;
                    dates.forEach(d => {
                        let v = fins[d][m];
                        if (v != null) {
                            let val = Number(v);
                            let absVal = Math.abs(val);
                            if (absVal >= 1e9) v = (val/1e9).toFixed(2) + 'B';
                            else if (absVal >= 1e6) v = (val/1e6).toFixed(2) + 'M';
                            else v = val.toLocaleString(undefined, {maximumFractionDigits: 2});
                        } else {
                            v = '—';
                        }
                        html += `<td>${v}</td>`;
                    });
                    html += '</tr>';
                });
                html += '</tbody></table></div>';
                html += '</div>';
            }

            html += '</div>'; // End Pro Only Section
            html += '</div>'; // End Modal Layout

            body.innerHTML = html;
            setTimeout(() => initChart(ticker), 0);
        } catch (e) {
            body.innerHTML = '<p style="color:var(--red)">Error loading details.</p>';
        }
    }

    // ── Signal Lifecycle Helpers ─────────────────────────────────────────────

    function formatAge(isoStr) {
        if (!isoStr) return null;
        const secs = Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000);
        if (secs < 60) return `hace ${secs} s`;
        const mins = Math.floor(secs / 60);
        if (mins < 60) return `hace ${mins} min`;
        const hrs = Math.floor(mins / 60);
        return `hace ${hrs} h`;
    }

    function formatTime(isoStr) {
        if (!isoStr) return '—';
        const d = new Date(isoStr);
        return d.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }

    function lcStatusMeta(status) {
        const MAP = {
            new:       { emoji: '🆕', label: 'Nueva',         cssStatus: 'status-new' },
            active:    { emoji: '✅', label: 'Vigente',        cssStatus: 'status-active' },
            weakening: { emoji: '⚠️', label: 'Debilitándose', cssStatus: 'status-weakening' },
            expired:   { emoji: '❌', label: 'Expirada',       cssStatus: 'status-expired' },
        };
        return MAP[status] || { emoji: '—', label: '—', cssStatus: 'status-none' };
    }

    function lcEntryMeta(entry) {
        const MAP = {
            open:      { emoji: '🎯', label: 'Abierta',           cssEntry: 'entry-open' },
            narrowing: { emoji: '⏳', label: 'Reduciendo calidad', cssEntry: 'entry-narrowing' },
            late:      { emoji: '🔶', label: 'Entrada tardía',     cssEntry: 'entry-late' },
            closed:    { emoji: '🚫', label: 'Cerrada',            cssEntry: 'entry-closed' },
        };
        return MAP[entry] || null;
    }

    /** Compact pills for table rows in Simple Mode */
    function buildLifecyclePills(item) {
        const status = item.signal_status || '';
        const entry  = item.entry_window_status || '';
        if (!status) return '<span class="lc-pill status-none">—</span>';

        const sm = lcStatusMeta(status);
        const em = lcEntryMeta(entry);

        const detectedAge = formatAge(item.signal_detected_at);
        const validatedAge = formatAge(item.signal_last_validated_at);

        let html = '<div class="lifecycle-pills">';
        html += `<span class="lc-pill ${sm.cssStatus}">${sm.emoji} ${sm.label}</span>`;
        if (em) html += `<span class="lc-pill ${em.cssEntry}">${em.emoji} Entrada: ${em.label}</span>`;
        if (detectedAge) html += `<span class="lc-pill status-none">🕐 ${detectedAge}</span>`;
        if (validatedAge) html += `<span class="lc-pill status-none">🔄 ${validatedAge}</span>`;
        html += '</div>';
        return html;
    }

    /** Detailed block for modal — appears below human card */
    function buildEstadoSenal(item) {
        const status = item.signal_status || '';
        if (!status) return ''; // No lifecycle for this ticker

        const sm = lcStatusMeta(status);
        const em = lcEntryMeta(item.entry_window_status || '');
        const detectedTime  = formatTime(item.signal_detected_at);
        const validatedAge  = formatAge(item.signal_last_validated_at);
        const age = item.signal_age_seconds > 0
            ? (() => {
                const s = item.signal_age_seconds;
                if (s < 60) return `${s}s`;
                const m = Math.floor(s/60); if (m < 60) return `${m} min`;
                return `${Math.floor(m/60)} h ${m%60} min`;
            })() : '—';

        const reval = item.signal_revalidation_note || '';
        const reason = item.signal_invalid_reason || '';
        const noteText = item.signal_expired ? reason || reval : reval;
        const noteClass = item.signal_expired ? 'expired'
                        : status === 'weakening' ? 'weakening'
                        : status === 'active' ? 'active' : '';

        let html = `<div class="estado-senal">
            <div class="estado-senal-title">⚡ Estado de la señal</div>
            <div class="estado-senal-grid">
                <div class="estado-senal-item">
                    <span class="estado-senal-label">Estado</span>
                    <span class="estado-senal-value">${sm.emoji} ${sm.label}</span>
                </div>
                <div class="estado-senal-item">
                    <span class="estado-senal-label">Detectada a las</span>
                    <span class="estado-senal-value">${detectedTime}</span>
                </div>
                <div class="estado-senal-item">
                    <span class="estado-senal-label">Última validación</span>
                    <span class="estado-senal-value">${validatedAge || '—'}</span>
                </div>
                <div class="estado-senal-item">
                    <span class="estado-senal-label">Tiempo activa</span>
                    <span class="estado-senal-value">${age}</span>
                </div>`;

        if (em) {
            html += `<div class="estado-senal-item">
                <span class="estado-senal-label">Ventana de entrada</span>
                <span class="estado-senal-value">${em.emoji} ${em.label}</span>
            </div>`;
        }
        html += `</div>`;

        if (noteText) {
            html += `<div class="estado-senal-note ${noteClass}">${noteText}</div>`;
        }
        html += `</div>`;
        return html;
    }

    /** Detailed block for modal — appears below estado de la señal if there is a plan */
    function buildTradePlan(plan) {
        if (!plan.entry_price) return '';

        const dirStr = plan.direction === 'LONG' ? 'Comprar' : 'Vender Corto';
        const dirCls = plan.direction === 'LONG' ? 'status-active' : 'status-expired';
        const tpStr = plan.tp_pct > 0 ? `+${plan.tp_pct.toFixed(1)}%` : `${plan.tp_pct.toFixed(1)}%`;
        const slStr = plan.sl_pct > 0 ? `+${plan.sl_pct.toFixed(1)}%` : `${plan.sl_pct.toFixed(1)}%`;

        let html = `<div class="estado-senal" style="margin-top:-8px;">
            <div class="estado-senal-title">🎯 ESTRATEGIA (SIMULACIÓN)</div>
            <div class="estado-senal-grid">
                <div class="estado-senal-item">
                    <span class="estado-senal-label">Operación</span>
                    <span class="estado-senal-value lc-pill ${dirCls}" style="width:fit-content; margin-top:2px;">${dirStr}</span>
                </div>
                <div class="estado-senal-item">
                    <span class="estado-senal-label">Entrada Teórica</span>
                    <span class="estado-senal-value">$${plan.entry_price.toFixed(2)}</span>
                </div>
                <div class="estado-senal-item">
                    <span class="estado-senal-label" style="color:var(--red);">Stop Loss</span>
                    <span class="estado-senal-value" style="color:var(--red);">$${plan.stop_loss.toFixed(2)} <span style="font-size:10px;">(${slStr})</span></span>
                </div>
                <div class="estado-senal-item">
                    <span class="estado-senal-label" style="color:var(--green);">Objetivo (TP)</span>
                    <span class="estado-senal-value" style="color:var(--green);">$${plan.take_profit.toFixed(2)} <span style="font-size:10px;">(${tpStr})</span></span>
                </div>
                <div class="estado-senal-item">
                    <span class="estado-senal-label">Ratio Riesgo/Beneficio</span>
                    <span class="estado-senal-value">${plan.risk_reward}</span>
                </div>
            </div>
        </div>`;
        return html;
    }

    /** Trade tracking block for modal */
    function buildTradeTracking(tracking) {
        if (!tracking.trade_status || tracking.trade_status === 'pending') return '';

        let emoji = '🟢';
        let label = 'EN CURSO';
        let borderColor = '#3b82f6'; // blue for open
        
        if (tracking.trade_status === 'closed_win') {
            emoji = '✅'; label = 'GANADOR'; borderColor = 'var(--green)';
        } else if (tracking.trade_status === 'closed_loss') {
            emoji = '❌'; label = 'PERDEDOR'; borderColor = 'var(--red)';
        } else if (tracking.trade_status === 'closed_expired') {
            emoji = '⏳'; label = 'EXPIRADO'; borderColor = '#eab308'; // yellow
        }

        let pnlColor = 'var(--text-main)';
        let pnlText = tracking.pnl_percentage > 0 ? `+${tracking.pnl_percentage.toFixed(2)}%` : `${tracking.pnl_percentage.toFixed(2)}%`;
        if (tracking.pnl_percentage > 0) pnlColor = 'var(--green)';
        else if (tracking.pnl_percentage < 0) pnlColor = 'var(--red)';

        // Translated reason
        let reasonTranslated = "";
        let contextTranslated = "";
        if (tracking.exit_reason === "target hit") {
            reasonTranslated = "Objetivo alcanzado";
            contextTranslated = "objetivo alcanzado";
        } else if (tracking.exit_reason === "stop loss hit") {
            reasonTranslated = "Stop Loss ejecutado";
            contextTranslated = "stop loss";
        } else if (tracking.exit_reason === "time expired") {
            reasonTranslated = "Tiempo expirado sin alcanzar niveles";
            contextTranslated = "expirado";
        } else if (tracking.exit_reason) {
            reasonTranslated = tracking.exit_reason;
            contextTranslated = tracking.exit_reason;
        }

        let resultLabel = tracking.trade_status === 'open' ? 'Resultado Actual' : 'Resultado Final';
        let pnlContext = contextTranslated ? ` <span style="font-size:12px; font-weight:normal; color:var(--text-muted)">(${contextTranslated})</span>` : '';

        const durMin = Math.floor(tracking.trade_duration_seconds / 60);
        const timeActive = durMin > 0 ? `${durMin} min` : `${tracking.trade_duration_seconds} s`;

        let html = `<div class="estado-senal" style="margin-top:-8px; border-left: 4px solid ${borderColor};">
            <div class="estado-senal-title" style="display:flex; justify-content:space-between; align-items:center;">
                <span>📊 SEGUIMIENTO EN VIVO</span>
                <span style="font-size: 1.1rem; font-weight: bold; color: ${borderColor};">${emoji} ${label}</span>
            </div>
            <div class="estado-senal-grid">
                <div class="estado-senal-item">
                    <span class="estado-senal-label">${resultLabel}</span>
                    <span class="estado-senal-value" style="color:${pnlColor}; font-weight:bold; font-size:1.15rem;">${pnlText}${pnlContext}</span>
                    <span class="estado-senal-value" style="font-size:11px; color:var(--text-muted); margin-top:2px;">Monto Absoluto: $${tracking.pnl_absolute.toFixed(2)}</span>
                </div>
                <div class="estado-senal-item">
                    <span class="estado-senal-label">Tiempo activo</span>
                    <span class="estado-senal-value">${timeActive}</span>
                </div>`;

        if (reasonTranslated) {
            html += `<div class="estado-senal-item" style="grid-column: 1 / -1; margin-top: 4px; padding-top: 8px; border-top: 1px dashed var(--border);">
                    <span class="estado-senal-label">Salida</span>
                    <span class="estado-senal-value" style="color:var(--text-main); font-weight:500;">${reasonTranslated}</span>
                </div>`;
        }

        html += `</div></div>`;
        return html;
    }

    // ────────────────────────────────────────────────────────────────────────

    function detailCard(label, value) {
        return `<div class="detail-card"><div class="label">${label}</div><div class="value">${value}</div></div>`;
    }


    function generateTechReading(s) {
        const bullets = [];

        // 1. Trend vs SMAs
        if (s.price != null && s.sma20 != null && s.sma50 != null) {
            if (s.price > s.sma20 && s.price > s.sma50) {
                bullets.push({ cls: 'bull', text: `Tendencia alcista de corto y medio plazo: el precio ($${s.price.toFixed(2)}) cotiza por encima de la SMA20 ($${s.sma20.toFixed(2)}) y la SMA50 ($${s.sma50.toFixed(2)}).` });
            } else if (s.price > s.sma20 && s.price <= s.sma50) {
                bullets.push({ cls: 'neut', text: `El precio ($${s.price.toFixed(2)}) está por encima de la SMA20 pero por debajo de la SMA50, sugiriendo consolidación.` });
            } else if (s.price <= s.sma20 && s.price > s.sma50) {
                bullets.push({ cls: 'neut', text: `El precio se sitúa por debajo de la SMA20 pero se sostiene sobre la SMA50 — posible pullback de corto plazo.` });
            } else {
                bullets.push({ cls: 'bear', text: `Tendencia bajista: el precio ($${s.price.toFixed(2)}) cotiza por debajo de la SMA20 y la SMA50.` });
            }
        }

        // 2. RSI
        if (s.rsi != null) {
            if (s.rsi < 30) {
                bullets.push({ cls: 'bull', text: `RSI en zona de sobreventa (${s.rsi.toFixed(1)}), lo que puede indicar un rebote potencial.` });
            } else if (s.rsi > 70) {
                bullets.push({ cls: 'bear', text: `RSI en zona de sobrecompra (${s.rsi.toFixed(1)}), precaución ante posible corrección.` });
            } else {
                bullets.push({ cls: 'neut', text: `RSI en zona neutral (${s.rsi.toFixed(1)}), sin señales extremas de sobrecompra o sobreventa.` });
            }
        }

        // 3. Volume + Momentum
        if (s.relative_volume != null && s.momentum_1m != null) {
            const momDir = s.momentum_1m >= 0 ? 'positivo' : 'negativo';
            const momCls = s.momentum_1m >= 0 ? 'bull' : 'bear';
            if (s.relative_volume > 1.5) {
                bullets.push({ cls: momCls, text: `Volumen relativo elevado (${s.relative_volume.toFixed(2)}x) con momentum mensual ${momDir} (${s.momentum_1m >= 0 ? '+' : ''}${s.momentum_1m.toFixed(2)}%).` });
            } else {
                bullets.push({ cls: 'neut', text: `Volumen dentro de la media (${s.relative_volume.toFixed(2)}x). Momentum mensual ${momDir} (${s.momentum_1m >= 0 ? '+' : ''}${s.momentum_1m.toFixed(2)}%).` });
            }
        }

        // 4. Breakout signal
        if (s.ma_breakout_signal) {
            bullets.push({ cls: 'signal', text: 'Señal de breakout detectada: el precio cruzó al alza una media móvil clave (SMA50 o SMA200).' });
        }

        // Determine overall bias for the header dot
        const bullCount = bullets.filter(b => b.cls === 'bull' || b.cls === 'signal').length;
        const bearCount = bullets.filter(b => b.cls === 'bear').length;
        let dotCls = 'dot-neut';
        if (bullCount > bearCount) dotCls = 'dot-bull';
        else if (bearCount > bullCount) dotCls = 'dot-bear';

        let html = '<div class="tech-reading">';
        html += `<div class="tech-reading-header"><span class="dot ${dotCls}"></span> Lectura Técnica</div>`;
        html += '<ul class="tech-bullets">';
        bullets.forEach(b => {
            html += `<li class="${b.cls}">${b.text}</li>`;
        });
        html += '</ul></div>';
        return html;
    }

    let currentChart = null;
    let currentChartRo = null;

    async function initChart(ticker, period = "1d", interval = "1m") {
        const container = document.getElementById('chart-container');
        if (!container) return;

        if (currentChart) {
            currentChart.remove();
            currentChart = null;
        }
        if (currentChartRo) {
            currentChartRo.disconnect();
            currentChartRo = null;
        }

        container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-tertiary)">Loading chart...</div>';

        try {
            const res = await fetch(`${API}/ticker/${ticker}/intraday?period=${period}&interval=${interval}&_t=${Date.now()}`, { cache: 'no-store' });
            const data = await res.json();
            const rawData = data.data || [];

            if (rawData.length === 0) {
                container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-tertiary)">No data available for this timeframe</div>';
                return;
            }

            container.innerHTML = ''; // clear loading

            const isDaily = interval === "1d";

            currentChart = LightweightCharts.createChart(container, {
                width: container.clientWidth,
                height: container.clientHeight,
                layout: {
                    background: { type: 'solid', color: 'transparent' },
                    textColor: '#8b8fa3',
                },
                grid: {
                    vertLines: { color: 'rgba(42, 46, 61, 0.5)' },
                    horzLines: { color: 'rgba(42, 46, 61, 0.5)' },
                },
                crosshair: {
                    mode: LightweightCharts.CrosshairMode.Normal,
                },
                rightPriceScale: {
                    borderColor: 'rgba(42, 46, 61, 0.5)',
                },
                timeScale: {
                    borderColor: 'rgba(42, 46, 61, 0.5)',
                    timeVisible: !isDaily,
                    secondsVisible: false,
                },
            });

            const candleSeries = currentChart.addCandlestickSeries({
                upColor: '#00c896',
                downColor: '#ff4757',
                borderDownColor: '#ff4757',
                borderUpColor: '#00c896',
                wickDownColor: '#ff4757',
                wickUpColor: '#00c896',
            });

            candleSeries.setData(rawData);

            // --- Volume ---
            const volumeSeries = currentChart.addHistogramSeries({
                priceFormat: {
                    type: 'volume',
                },
                priceScaleId: '', // Overlay so it doesn't squish the candlesticks
                scaleMargins: {
                    top: 0.7, // 30% height at the bottom
                    bottom: 0,
                },
            });

            const volumeData = rawData.map(d => ({
                time: d.time,
                value: d.volume,
                color: d.close >= d.open ? 'rgba(0, 200, 150, 0.5)' : 'rgba(255, 71, 87, 0.5)'
            }));

            volumeSeries.setData(volumeData);
            
            // --- SMAs ---
            function calcSMA(data, period) {
                const sma = [];
                let sum = 0;
                for (let i = 0; i < data.length; i++) {
                    sum += data[i].close;
                    if (i >= period) sum -= data[i - period].close;
                    if (i >= period - 1) {
                        sma.push({ time: data[i].time, value: sum / period });
                    }
                }
                return sma;
            }

            const sma20Data = calcSMA(rawData, 20);
            const sma50Data = calcSMA(rawData, 50);

            const sma20Series = currentChart.addLineSeries({
                color: '#00e5ff',
                lineWidth: 1.5,
                crosshairMarkerVisible: false,
                lastValueVisible: false,
                priceLineVisible: false,
            });
            sma20Series.setData(sma20Data);

            const sma50Series = currentChart.addLineSeries({
                color: '#f59e0b',
                lineWidth: 1.5,
                crosshairMarkerVisible: false,
                lastValueVisible: false,
                priceLineVisible: false,
            });
            sma50Series.setData(sma50Data);

            currentChart.timeScale().fitContent();

            // --- Legend ---
            const labelMap = {
                "1d": "1D · 1m",
                "5d": "5D · 5m",
                "1mo": "1M · 30m",
                "3mo": "3M · 1D",
                "1y": "1Y · 1D"
            };
            const label = labelMap[period] || `${period} · ${interval}`;

            const legend = document.createElement('div');
            legend.style.position = 'absolute';
            legend.style.top = '12px';
            legend.style.left = '12px';
            legend.style.zIndex = '10';
            legend.style.fontSize = '12px';
            legend.style.fontFamily = 'var(--font-sans)';
            legend.style.pointerEvents = 'none';
            legend.style.color = 'var(--text-primary)';
            legend.innerHTML = `
                <div style="font-weight:600;margin-bottom:4px;">${ticker} <span style="color:var(--text-tertiary);font-weight:400;font-size:11px;">${label}</span></div>
                <div style="font-size:11px;">
                    <span style="color:#00e5ff;margin-right:8px;">SMA20 <span id="leg-sma20">—</span></span>
                    <span style="color:#f59e0b;">SMA50 <span id="leg-sma50">—</span></span>
                </div>
            `;
            container.appendChild(legend);

            const legSma20 = document.getElementById('leg-sma20');
            const legSma50 = document.getElementById('leg-sma50');
            
            currentChart.subscribeCrosshairMove(param => {
                if (param.time && param.seriesData) {
                    const price20 = param.seriesData.get(sma20Series);
                    const price50 = param.seriesData.get(sma50Series);
                    legSma20.textContent = price20 ? price20.value.toFixed(2) : '—';
                    legSma50.textContent = price50 ? price50.value.toFixed(2) : '—';
                } else {
                    const last20 = sma20Data[sma20Data.length - 1];
                    const last50 = sma50Data[sma50Data.length - 1];
                    legSma20.textContent = last20 ? last20.value.toFixed(2) : '—';
                    legSma50.textContent = last50 ? last50.value.toFixed(2) : '—';
                }
            });

            // Init legend values
            const last20 = sma20Data[sma20Data.length - 1];
            const last50 = sma50Data[sma50Data.length - 1];
            legSma20.textContent = last20 ? last20.value.toFixed(2) : '—';
            legSma50.textContent = last50 ? last50.value.toFixed(2) : '—';

            // Handle resize
            currentChartRo = new ResizeObserver(entries => {
                const cr = entries[0].contentRect;
                currentChart.resize(cr.width, cr.height);
            });
            currentChartRo.observe(container);
            
        } catch (e) {
            console.error(e);
            container.innerHTML = `<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;color:var(--red);text-align:center;">
                <div>Failed to load chart</div>
                <div style="font-size:10px;margin-top:5px;opacity:0.8;">${e.message || e}</div>
            </div>`;
        }
    }

    async function changeTimeframe(btn, ticker) {
        const buttons = btn.parentElement.querySelectorAll('.tf-btn');
        buttons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        const period = btn.getAttribute('data-period');
        const interval = btn.getAttribute('data-interval');

        await initChart(ticker, period, interval);
    }

    function closeModal() {
        document.getElementById('modal-overlay').classList.remove('active');
        if (currentChart) {
            currentChart.remove();
            currentChart = null;
        }
        if (currentChartRo) {
            currentChartRo.disconnect();
            currentChartRo = null;
        }
    }

    function openHistoryModal(idx) {
        const item = historyData[idx];
        if (!item) return;
        
        const overlay = document.getElementById('modal-overlay');
        const body = document.getElementById('modal-body');
        overlay.classList.add('active');
        document.getElementById('modal-ticker').textContent = item.ticker;
        document.getElementById('modal-subtitle').textContent = "Historial Simulado";
        
        let html = '<div class="modal-layout">';
        
        // 1. Timeline Block
        const detectedTime = item.signal_detected_at ? formatTime(item.signal_detected_at) : '—';
        const openedTime = item.trade_opened_at ? formatTime(item.trade_opened_at) : '—';
        const closedTime = item.trade_closed_at ? formatTime(item.trade_closed_at) : '—';
        
        html += `<div class="estado-senal" style="grid-column:1/-1;">
            <div class="estado-senal-title">⏱️ Timeline</div>
            <div style="font-family:var(--font-mono); font-size:12px; line-height:1.8; color:var(--text-secondary); padding: 5px 0;">
                <div>${detectedTime} &rarr; Señal detectada (${item.human_signal || item.signal_type})</div>`;
        if (openedTime !== '—') {
            html += `<div>${openedTime} &rarr; Entrada simulada ($${item.entry_price ? item.entry_price.toFixed(2) : '—'})</div>`;
        }
        
        let exitStr = "Cierre";
        if (item.exit_reason === "target hit") exitStr = "Objetivo alcanzado";
        else if (item.exit_reason === "stop loss hit") exitStr = "Stop loss alcanzado";
        else if (item.exit_reason === "time expired") exitStr = "Tiempo expirado";
        else if (item.exit_reason) exitStr = item.exit_reason;
        
        if (closedTime !== '—') {
            html += `<div>${closedTime} &rarr; ${exitStr}</div>`;
        }
        html += `</div></div>`;
        
        // 2. Strategy Block (mocking trade_plan structure)
        const mockPlan = {
            entry_price: item.entry_price,
            direction: item.trade_direction,
            stop_loss: item.stop_loss,
            sl_pct: item.entry_price && item.stop_loss ? ((item.stop_loss - item.entry_price) / item.entry_price) * 100 : 0,
            take_profit: item.take_profit,
            tp_pct: item.entry_price && item.take_profit ? ((item.take_profit - item.entry_price) / item.entry_price) * 100 : 0,
            risk_reward: item.risk_reward_ratio
        };
        html += buildTradePlan(mockPlan);
        
        // 3. Result Block (mocking trade_tracking structure)
        const mockTracking = {
            trade_status: item.trade_status,
            pnl_percentage: item.pnl_percentage,
            pnl_absolute: item.pnl_absolute,
            trade_duration_seconds: item.trade_duration_seconds,
            exit_reason: item.exit_reason
        };
        html += buildTradeTracking(mockTracking);
        
        html += '</div>'; // end modal-layout
        body.innerHTML = html;
    }

    // ── Signal Intelligence Lab 2.0 ────────────────────────────────────
    async function openSignalLab() {
        const overlay = document.getElementById('signal-lab-overlay');
        overlay.classList.add('active');

        // Update header based on mode
        const titleEl = document.getElementById('signal-lab-title');
        if (titleEl) {
            titleEl.innerHTML = viewMode === 'simple'
                ? '<span class="icon">🔬</span> SIGNAL INTELLIGENCE LAB'
                : '<span class="icon">🔬</span> SIGNAL INTELLIGENCE LAB — EVIDENCE DASHBOARD';
        }

        const grid = document.getElementById('signal-lab-grid');
        grid.innerHTML = '<div style="padding:40px;color:var(--text-secondary);text-align:center;">Analizando señales históricas del universo seleccionado…</div>';

        try {
            const res = await fetch(`${API}/signal-evaluation?market=${currentMarket}&_t=${Date.now()}`, { cache: 'no-store' });
            const json = await res.json();
            renderSignalLab(json.data);
        } catch (e) {
            grid.innerHTML = `<div style="color:var(--red);padding:20px;">Error al cargar evaluación de señales: ${e}</div>`;
        }
    }

    function closeSignalLab() {
        document.getElementById('signal-lab-overlay').classList.remove('active');
    }

    function renderSignalLab(data) {
        const grid = document.getElementById('signal-lab-grid');
        const descEl = document.getElementById('signal-lab-desc');

        // Handle new structure: { universe: {...}, signals: {...} }
        const universe = data?.universe || {};
        const signals = data?.signals || data || {};

        if (!signals || Object.keys(signals).length === 0) {
            grid.innerHTML = '<div style="padding:20px;color:var(--text-secondary);">No hay datos de señales disponibles.</div>';
            return;
        }

        // ── Universe Metadata Header ─────────────────────────────────────
        const marketLabel = { nasdaq100: 'Nasdaq 100', sp500: 'S&P 500', europe: 'Europe Top' }[currentMarket] || currentMarket;
        if (descEl) {
            descEl.innerHTML = `
                <div class="sil-universe-header">
                    <div class="sil-universe-stat">
                        <span class="label">Universo</span>
                        <span class="value">${marketLabel}</span>
                    </div>
                    <div class="sil-universe-stat">
                        <span class="label">Activos analizados</span>
                        <span class="value">${universe.tickers || '—'}</span>
                    </div>
                    <div class="sil-universe-stat">
                        <span class="label">Periodo</span>
                        <span class="value">${universe.period || '2y'}</span>
                    </div>
                    <div class="sil-universe-stat">
                        <span class="label">Muestra mín. por ticker</span>
                        <span class="value">≥ ${universe.min_ticker_sample || 3} ocurrencias</span>
                    </div>
                    <div class="sil-universe-stat">
                        <span class="label">Muestra suficiente</span>
                        <span class="value">≥ ${universe.sample_sufficient_threshold || 40} señales</span>
                    </div>
                </div>
                <div style="padding: 10px 20px; font-size: 11px; color: var(--text-tertiary); line-height: 1.5;">
                    Probabilidades empíricas basadas en backtesting histórico. <strong>Contexto:</strong> Bullish = Breadth &gt; 60%, Bearish = Breadth &lt; 40%.
                    <em>El rendimiento pasado no garantiza resultados futuros.</em>
                </div>
            `;
        }

        // Human-readable signal names
        const SIGNAL_NAMES = {
            oversold:             '🔻 Rebote desde sobreventa',
            overbought:           '🔺 Caída tras subida excesiva',
            ma_breakout_signal:   '⚡ Ruptura de media móvil',
            breakout_up:          '📊 Cruce alcista SMA50',
            breakdown_down:       '📉 Cruce bajista SMA50',
            momentum_shift_up:    '📈 Impulso comprador fuerte',
            momentum_shift_down:  '🔻 Impulso vendedor fuerte',
            high_volume:          '🔊 Volumen inusualmente alto',
            breakout_vol_1_5:     '⚡📊 Cruce alcista + volumen',
            breakout_bullish:     '⚡🟢 Cruce alcista en mercado fuerte',
            high_vol_mom_2:       '🔊📈 Volumen alto + impulso',
            oversold_bullish:     '🔻🟢 Sobreventa en mercado fuerte',
        };

        const SIGNAL_DESCRIPTIONS = {
            oversold:             'RSI cruza por debajo de 30, indicando posible rebote técnico.',
            overbought:           'RSI cruza por encima de 70, indicando posible corrección.',
            ma_breakout_signal:   'Precio cruza por encima de SMA50 o SMA200.',
            breakout_up:          'Precio cruza al alza la SMA50.',
            breakdown_down:       'Precio cruza a la baja la SMA50.',
            momentum_shift_up:    'Movimiento diario superior al +3%.',
            momentum_shift_down:  'Movimiento diario inferior al -3%.',
            high_volume:          'Volumen supera 2x su media de 20 días.',
            breakout_vol_1_5:     'Cruce alcista de SMA50 con volumen >1.5x.',
            breakout_bullish:     'Cruce alcista de SMA50 cuando breadth > 60%.',
            high_vol_mom_2:       'Volumen alto combinado con movimiento >+2%.',
            oversold_bullish:     'Sobreventa (RSI<30) cuando breadth > 60%.',
        };

        // Sort by 5d win rate descending
        const sortedEntries = Object.entries(signals).sort((a, b) => b[1].win_rate_5d - a[1].win_rate_5d);

        let html = '';

        // ── Helper: render sample badge ──────────────────────────────────
        function sampleBadge(quality, count) {
            const labels = {
                sufficient:   '✅ Suficiente',
                limited:      '⚠️ Limitada',
                insufficient: '❌ Insuficiente'
            };
            return `<span class="sil-sample-badge sil-sample-${quality}">${count} señales · ${labels[quality] || quality}</span>`;
        }

        // ── Helper: render context rows ──────────────────────────────────
        function contextRows(ctx, bestCtx, worstCtx) {
            if (!ctx || Object.keys(ctx).length === 0) return '<div style="font-size:11px;color:var(--text-tertiary);">Sin datos de contexto disponibles</div>';
            const order = ['bullish', 'bearish', 'neutral'];
            let rows = '';
            order.forEach(k => {
                const c = ctx[k];
                if (!c) return;
                const wr = (c.win_rate * 100).toFixed(0);
                const barColor = wr >= 60 ? 'var(--green)' : wr < 45 ? 'var(--red)' : 'var(--amber)';
                let tag = '';
                if (k === bestCtx) tag = ' <span class="sil-best-tag">✅ MEJOR</span>';
                if (k === worstCtx) tag = ' <span class="sil-worst-tag">⚠️ PEOR</span>';
                const ctxLabel = k === 'bullish' ? 'Alcista' : k === 'bearish' ? 'Bajista' : 'Neutral';
                rows += `
                    <div class="sil-context-row">
                        <span class="ctx-label">${ctxLabel}${tag}</span>
                        <div class="ctx-bar-bg"><div class="ctx-bar-fill" style="width:${wr}%;background:${barColor}"></div></div>
                        <span class="ctx-val">${wr}%</span>
                        <span class="ctx-count">${c.count} ops</span>
                    </div>
                `;
            });
            return rows;
        }

        // ── Helper: render ticker chips ──────────────────────────────────
        function tickerChips(tickers, type) {
            if (!tickers || tickers.length === 0) return '<div style="font-size:11px;color:var(--text-tertiary);">Sin datos suficientes</div>';
            return '<div class="sil-ticker-chips">' + tickers.map(t => {
                const wr = (t.win_rate * 100).toFixed(0);
                const chipClass = type === 'good' ? 'sil-chip-good' : 'sil-chip-bad';
                const warn = t.sample_warning ? '<span class="t-warn">⚠️</span>' : '';
                return `<span class="sil-ticker-chip ${chipClass}">
                    <span class="t-name">${t.ticker}</span>
                    <span class="t-wr">${wr}%</span>
                    <span class="t-count">${t.count} ops</span>
                    ${warn}
                </span>`;
            }).join('') + '</div>';
        }

        // ── Build cards ──────────────────────────────────────────────────
        sortedEntries.forEach(([sigName, stats], index) => {
            const isTop = index < 3;
            const humanName = SIGNAL_NAMES[sigName] || sigName.replace(/_/g, ' ');
            const description = SIGNAL_DESCRIPTIONS[sigName] || '';
            const wr5 = (stats.win_rate_5d * 100).toFixed(0);
            const avg5 = stats.avg_return_5d;
            const quality = stats.sample_quality || 'insufficient';
            const bestHorizon = stats.win_rate_20d > stats.win_rate_5d ? '2-4 semanas' : '5-10 días';

            html += `<div class="sil-card ${isTop ? 'sil-top' : ''}">`;

            // ── Header ───────────────────────────────────────────────────
            html += `
                <div class="sil-card-header">
                    <div>
                        <div class="sil-signal-name">
                            ${isTop ? '<span title="Top Signal" style="margin-right:4px;">🏆</span>' : ''}
                            ${humanName}
                        </div>
                        ${description ? `<div style="font-size:11px;color:var(--text-tertiary);margin-top:3px;">${description}</div>` : ''}
                    </div>
                    ${sampleBadge(quality, stats.total_signals)}
                </div>
            `;

            // ── Core Metrics Grid ────────────────────────────────────────
            const avg5Cls = avg5 > 0 ? 'positive' : avg5 < 0 ? 'negative' : 'neutral';
            const avg5Sign = avg5 > 0 ? '+' : '';
            html += `
                <div class="sil-metrics">
                    <div class="sil-metric">
                        <div class="label">Win Rate 5D</div>
                        <div class="value ${wr5 >= 60 ? 'positive' : wr5 < 45 ? 'negative' : 'neutral'}">${wr5}%</div>
                    </div>
                    <div class="sil-metric">
                        <div class="label">PnL Medio 5D</div>
                        <div class="value ${avg5Cls}">${avg5Sign}${avg5.toFixed(2)}%</div>
                    </div>
                    <div class="sil-metric">
                        <div class="label">Horizonte Óptimo</div>
                        <div class="value neutral" style="font-size:12px;">${bestHorizon}</div>
                    </div>
            `;

            // Pro mode: add more metrics
            if (viewMode === 'pro') {
                const wr1 = (stats.win_rate_1d * 100).toFixed(0);
                const wr20 = (stats.win_rate_20d * 100).toFixed(0);
                const med5 = stats.median_return_5d || 0;
                html += `
                    <div class="sil-metric">
                        <div class="label">Win Rate 1D</div>
                        <div class="value ${wr1 >= 55 ? 'positive' : wr1 < 45 ? 'negative' : 'neutral'}">${wr1}%</div>
                    </div>
                    <div class="sil-metric">
                        <div class="label">Win Rate 20D</div>
                        <div class="value ${wr20 >= 55 ? 'positive' : wr20 < 45 ? 'negative' : 'neutral'}">${wr20}%</div>
                    </div>
                    <div class="sil-metric">
                        <div class="label">Mediana 5D</div>
                        <div class="value ${med5 >= 0 ? 'positive' : 'negative'}">${med5 > 0 ? '+' : ''}${med5.toFixed(2)}%</div>
                    </div>
                `;
            }
            html += '</div>'; // close sil-metrics

            // ── Context Breakdown ────────────────────────────────────────
            html += `
                <div class="sil-context">
                    <div class="sil-context-title">📊 Contexto de Mercado</div>
                    <div class="sil-context-rows">
                        ${contextRows(stats.context, stats.best_context, stats.worst_context)}
                    </div>
                </div>
            `;

            // ── Top Tickers ──────────────────────────────────────────────
            if (stats.top_tickers && stats.top_tickers.length > 0) {
                const maxShow = viewMode === 'simple' ? 3 : 5;
                html += `
                    <div class="sil-tickers">
                        <div class="sil-tickers-title">📈 Donde funciona mejor</div>
                        ${tickerChips(stats.top_tickers.slice(0, maxShow), 'good')}
                    </div>
                `;
            }

            // ── Worst Tickers ────────────────────────────────────────────
            if (stats.worst_tickers && stats.worst_tickers.length > 0) {
                html += `
                    <div class="sil-tickers">
                        <div class="sil-tickers-title">📉 Donde funciona peor</div>
                        ${tickerChips(stats.worst_tickers, 'bad')}
                    </div>
                `;
            }

            // ── Conclusion ───────────────────────────────────────────────
            if (stats.insight) {
                html += `
                    <div class="sil-conclusion">
                        <strong>💡 Conclusión:</strong> ${stats.insight}
                    </div>
                `;
            }

            html += '</div>'; // close sil-card
        });

        grid.innerHTML = html;
    }

    // ── Go ─────────────────────────────────────────────────────────────────
    init();
    

    let strategyData = null;

    async function openStrategyLab() {
        document.getElementById('strategy-lab-overlay').classList.add('active');
        const loading = document.getElementById('sl-loading');
        const container = document.getElementById('sl-container');
        
        loading.style.display = 'block';
        container.style.display = 'none';
        
        try {
            const res = await fetch(`${API}/strategy-optimization?market=${currentMarket}&_t=${Date.now()}`, { cache: 'no-store' });
            
            if (!res.ok) {
                let errText = res.statusText;
                try {
                    const errJson = await res.json();
                    if (errJson.detail) errText = errJson.detail;
                } catch (e) {}
                throw new Error(`API Error (${res.status}): ${errText}. Please ensure the backend server is restarted.`);
            }
            
            const json = await res.json();
            if (!json.data) throw new Error("No optimization data returned from API.");
            
            strategyData = json.data;
            
            renderStrategyLab();
            
            loading.style.display = 'none';
            container.style.display = 'flex';
        } catch (e) {
            loading.innerHTML = `<div style="color:var(--red); padding: 20px; background: rgba(255, 71, 87, 0.1); border-radius: 8px; border: 1px solid var(--red);">
                <strong>Failed to load optimization data</strong><br><br>
                ${e.message}<br><br>
                <em>Hint: Did you restart the Uvicorn server after the recent updates?</em>
            </div>`;
        }
    }

    function closeStrategyLab() {
        document.getElementById('strategy-lab-overlay').classList.remove('active');
    }

    function switchSlTab(tabId, e) {
        document.querySelectorAll('.sl-tab').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.sl-content').forEach(el => el.classList.remove('active'));
        
        const target = e ? e.currentTarget : (window.event?.currentTarget || document.querySelector(`.sl-tab[onclick*="'${tabId}'"]`));
        if (target) target.classList.add('active');
        document.getElementById(`sl-tab-${tabId}`).classList.add('active');
    }

    function fmtPct(val) { return val != null ? (val * 100).toFixed(1) + '%' : '—'; }
    function fmtVal(val) { return val != null ? val.toFixed(2) : '—'; }
    function clr(val, invert=false) { 
        if (val == null) return '';
        if (invert) return val < 0 ? 'color:var(--green)' : 'color:var(--red)';
        return val > 0 ? 'color:var(--green)' : (val < 0 ? 'color:var(--red)' : '');
    }
    function confBadge(conf) {
        const map = { 'high': 'conf-high_confidence', 'medium': 'conf-medium_confidence', 'low': 'conf-low_confidence', 'insufficient_sample': 'conf-low_confidence' };
        return `<span class="confidence-badge ${map[conf] || ''}">${conf.replace('_', ' ')}</span>`;
    }

    function renderStrategyLab() {
        if (!strategyData) return;

        // ── Human Summary Block ─────────────────────────────────────────────
        const top  = strategyData.ranking.top || [];
        const low  = strategyData.ranking.low_quality || [];

        const humanInsights = [];

        // Best performing signal
        if (top.length > 0) {
            const best = top[0];
            const bestLabel = best.name.replace(/__/g, ' con ').replace(/_/g, ' ').toLowerCase();
            humanInsights.push(`La señal de <strong>${bestLabel}</strong> es la más confiable actualmente, con una ganancia esperada de <strong>${fmtVal(best.expectancy_5d)}% por operación</strong> en los últimos datos.`);
        }

        // Second signal insight
        if (top.length > 1) {
            const s2 = top[1];
            const s2Label = s2.name.replace(/__/g, ' con ').replace(/_/g, ' ').toLowerCase();
            humanInsights.push(`Las señales de <strong>${s2Label}</strong> también muestran buen historial (Profit Factor: ${fmtVal(s2.profit_factor)}).`);
        }

        // Low quality warning
        if (low.length > 0) {
            const worst = low[0];
            const worstLabel = worst.name.replace(/__/g, ' con ').replace(/_/g, ' ').toLowerCase();
            humanInsights.push(`⚠️ Las señales de <strong>${worstLabel}</strong> no son fiables actualmente. El sistema las descarta para evitar pérdidas.`);
        }

        // Context insight from market_context if available
        const ctx = strategyData.market_context;
        if (ctx) {
            const breadth = ctx.market_breadth || ctx.breadth;
            if (breadth != null) {
                const bPct = (breadth * 100).toFixed(0);
                if (breadth > 0.6) humanInsights.push(`El mercado está en tendencia alcista (${bPct}% de acciones sobre SMA50), lo que favorece señales de ruptura pero reduce el efectividad de señales de rebote.`);
                else if (breadth < 0.4) humanInsights.push(`El mercado está débil (${bPct}% de acciones sobre SMA50): las señales de rebote tienen mayor efectividad histórica en este contexto.`);
                else humanInsights.push(`El mercado está en zona neutral (${bPct}% de acciones sobre SMA50): ninguna señal recibe un bono de contexto significativo.`);
            }
        }

        const humanHtml = humanInsights.length > 0
            ? humanInsights.map(i => `<div class="sl-human-insight">${i}</div>`).join('')
            : '<div class="sl-human-insight">Cargando análisis del mercado…</div>';

        document.getElementById('sl-summary-box').innerHTML = `
            <div class="sl-human-block">
                <h4>📖 ¿Qué está pasando en el mercado?</h4>
                ${humanHtml}
            </div>
            <div class="sl-summary"><strong>💡 Optimization Insights:</strong><br>${strategyData.summary}</div>`;


        // Ranking
        const rankGrid = document.getElementById('sl-ranking-container');
        let rankHtml = '';
        
        top.slice(0,3).forEach((r, i) => {
            const medals = ['🥇', '🥈', '🥉'];
            rankHtml += `<div class="sl-rank-card sl-rank-top">
                <div style="font-size:14px; font-weight:600; margin-bottom:8px; display:flex; justify-content:space-between;">
                    <span>${medals[i]} ${r.name.replace(/__/g, ' + ').replace(/_/g, ' ').toUpperCase()}</span>
                    <span style="color:var(--purple)">Score: ${r.score}</span>
                </div>
                <div style="font-size:11px; display:flex; justify-content:space-between;">
                    <span><span style="color:var(--text-tertiary)">Exp 5D:</span> <span style="${clr(r.expectancy_5d)}">${fmtVal(r.expectancy_5d)}%</span></span>
                    <span><span style="color:var(--text-tertiary)">Win Rate:</span> ${fmtPct(r.win_rate_5d)}</span>
                    ${confBadge(r.confidence)}
                </div>
            </div>`;
        });
        
        low.slice(0,1).forEach(r => {
            rankHtml += `<div class="sl-rank-card sl-rank-low">
                <div style="font-size:14px; font-weight:600; margin-bottom:8px; display:flex; justify-content:space-between; color:var(--red);">
                    <span>⚠️ AVOID: ${r.name.replace(/__/g, ' + ').replace(/_/g, ' ').toUpperCase()}</span>
                    <span>Score: ${r.score}</span>
                </div>
                <div style="font-size:11px; display:flex; justify-content:space-between;">
                    <span><span style="color:var(--text-tertiary)">Exp 5D:</span> <span style="${clr(r.expectancy_5d)}">${fmtVal(r.expectancy_5d)}%</span></span>
                    <span><span style="color:var(--text-tertiary)">Win Rate:</span> ${fmtPct(r.win_rate_5d)}</span>
                </div>
            </div>`;
        });
        rankGrid.innerHTML = rankHtml;
        
        // Individual Table
        const tbodyInd = document.getElementById('sl-tbody-ind');
        let htmlInd = '';
        Object.entries(strategyData.individual_signals).sort((a,b) => (b[1]?.expectancy_5d || -999) - (a[1]?.expectancy_5d || -999)).forEach(([k, v]) => {
            if (!v) return;
            htmlInd += `<tr>
                <td>${k.replace(/_/g, ' ').toUpperCase()}</td>
                <td>${v.total_signals}</td>
                <td>${confBadge(v.confidence)}</td>
                <td>${fmtPct(v.win_rate_1d)}</td>
                <td>${fmtPct(v.win_rate_5d)}</td>
                <td>${fmtPct(v.win_rate_10d)}</td>
                <td>${fmtPct(v.win_rate_20d)}</td>
                <td style="${clr(v.avg_return_5d)}">${fmtVal(v.avg_return_5d)}%</td>
                <td style="${clr(v.expectancy_5d)}">${fmtVal(v.expectancy_5d)}%</td>
                <td>${fmtVal(v.profit_factor)}</td>
                <td style="${clr(v.max_drawdown_5d, true)}">${fmtVal(v.max_drawdown_5d)}%</td>
            </tr>`;
        });
        tbodyInd.innerHTML = htmlInd;
        
        // Combined Table
        const tbodyComb = document.getElementById('sl-tbody-comb');
        let htmlComb = '';
        Object.entries(strategyData.combined_signals).sort((a,b) => (b[1]?.delta_expectancy_5d || -999) - (a[1]?.delta_expectancy_5d || -999)).forEach(([k, v]) => {
            if (!v) return;
            const dWr = v.delta_win_rate_5d;
            const dEx = v.delta_expectancy_5d;
            htmlComb += `<tr>
                <td>${k.replace(/__/g, ' + ').replace(/_/g, ' ').toUpperCase()}</td>
                <td>${v.total_signals}</td>
                <td>${confBadge(v.confidence)}</td>
                <td>${fmtPct(v.win_rate_5d)}</td>
                <td style="${clr(dWr)}">${dWr > 0 ? '▲' : '▼'} ${fmtPct(dWr)}</td>
                <td style="${clr(v.avg_return_5d)}">${fmtVal(v.avg_return_5d)}%</td>
                <td style="${clr(v.expectancy_5d)}">${fmtVal(v.expectancy_5d)}%</td>
                <td style="${clr(dEx)}">${dEx > 0 ? '▲' : '▼'} ${fmtVal(dEx)}%</td>
            </tr>`;
        });
        tbodyComb.innerHTML = htmlComb;
        
        // Exit Table
        const tbodyExit = document.getElementById('sl-tbody-exit');
        let htmlExit = '';
        Object.entries(strategyData.exit_rules).sort((a,b) => (b[1]?.expectancy || -999) - (a[1]?.expectancy || -999)).forEach(([k, v]) => {
            htmlExit += `<tr>
                <td>${k.toUpperCase()}</td>
                <td>${v.label}</td>
                <td>${v.total_trades}</td>
                <td>${fmtPct(v.win_rate)}</td>
                <td style="${clr(v.avg_return)}">${fmtVal(v.avg_return)}%</td>
                <td style="${clr(v.expectancy)}">${fmtVal(v.expectancy)}%</td>
                <td>${fmtVal(v.profit_factor)}</td>
                <td style="${clr(v.max_drawdown, true)}">${fmtVal(v.max_drawdown)}%</td>
            </tr>`;
        });
        tbodyExit.innerHTML = htmlExit;
    }


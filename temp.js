
    /* ====================================================================
       IOSEF FINANCE TERMINAL – Hybrid Frontend
       HTTP for base data (FastAPI)  +  WebSocket for realtime (Go)
       ==================================================================== */

    const API = 'http://127.0.0.1:8000/api';
    const WS_URL = 'ws://localhost:8080/ws/market';

    let rawData = [];
    let filteredData = [];
    let sortCol = 'composite_score';
    let sortAsc = false;
    let ws = null;
    let wsConnected = false;
    let lastPrices = {};  // For flash animations
    let dropdownsDone = false;
    let currentMarket = 'nasdaq100';
    const activeAlerts = new Map(); // deduplication memory

    // ── Init ──────────────────────────────────────────────────────────────
    async function init() {
        showLoadingSkeleton();
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
            const res = await fetch(`${API}/scan?market=${currentMarket}`);
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
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape') {
                closeModal();
                closeSignalLab();
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

        const rows = filteredData.map(t => {
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

            // Breakout signal
            const signal = t.ma_breakout_signal ? '<span class="breakout-badge">BRK</span>' : '';

            // Flash detection
            const prev = lastPrices[t.ticker];
            let flashCls = '';
            if (prev !== undefined && prev !== t.price) {
                flashCls = t.price > prev ? 'flash-up' : 'flash-down';
            }

            return `<tr onclick="openModal('${t.ticker}')" class="${flashCls}">
                <td class="ticker-cell">${t.ticker}</td>
                <td class="sector-cell">${t.sector || '—'}</td>
                <td>${t.price.toFixed(2)}</td>
                <td class="${chgCls}">${chgSign}${t.change_pct.toFixed(2)}%</td>
                <td><span class="rsi-bar"><span class="rsi-indicator" style="background:${rsiBarColor}"></span><span class="${rsiCls}">${t.rsi.toFixed(1)}</span></span></td>
                <td>${t.relative_volume.toFixed(2)}x</td>
                <td>${t.sma20.toFixed(2)}</td>
                <td>${t.sma50.toFixed(2)}</td>
                <td>${t.sma200.toFixed(2)}</td>
                <td class="${momCls}">${momSign}${t.momentum_1m.toFixed(2)}%</td>
                <td><span class="score-badge ${scoreCls}">${t.composite_score}</span></td>
                <td>${signal}</td>
            </tr>`;
        });

        tbody.innerHTML = rows.join('');
        storePrices(); // Update last known prices after render
    }

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
        const brk = valid.filter(t => t.ma_breakout_signal).sort((a, b) => b.composite_score - a.composite_score).slice(0, 8);
        document.getElementById('breakouts-list').innerHTML = brk.length > 0
            ? brk.map(t => `<li class="side-item" onclick="openModal('${t.ticker}')">
                <span class="sym">${t.ticker}</span>
                <span class="price-col">Score: ${t.composite_score}</span>
                <span class="chg-col" style="color:var(--blue)">⚡ BRK</span>
            </li>`).join('')
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
                fetch(`${API}/ticker/${ticker}`),
                fetch(`${API}/ticker/${ticker}/financials`)
            ]);
            const dData = await dRes.json();
            const fData = await fRes.json();
            const info = dData.data || {};
            const fins = fData.data || {};
            let html = '<div class="modal-layout">';
            
            // Left Column
            html += '<div class="modal-col-left">';
            html += `
            <div class="tf-bar">
                <button class="tf-btn active" data-period="1d" data-interval="1m" onclick="changeTimeframe(this, '${ticker}')">1D</button>
                <button class="tf-btn" data-period="5d" data-interval="5m" onclick="changeTimeframe(this, '${ticker}')">5D</button>
                <button class="tf-btn" data-period="1mo" data-interval="30m" onclick="changeTimeframe(this, '${ticker}')">1M</button>
                <button class="tf-btn" data-period="3mo" data-interval="1d" onclick="changeTimeframe(this, '${ticker}')">3M</button>
                <button class="tf-btn" data-period="1y" data-interval="1d" onclick="changeTimeframe(this, '${ticker}')">1Y</button>
            </div>
            <div id="chart-container"></div>
            `;

            // Financials
            if (Object.keys(fins).length > 0) {
                html += '<h3 style="margin-bottom:10px;font-size:13px;color:var(--text-secondary)">Quarterly Financials</h3>';
                const dates = Object.keys(fins).sort((a, b) => new Date(b) - new Date(a));
                const metrics = Object.keys(fins[dates[0]]);
                html += '<div style="width:100%;overflow:hidden;"><table class="fin-table"><thead><tr><th>Metric</th>';
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
            } else {
                html += '<p style="color:var(--text-tertiary)">No financials available.</p>';
            }
            html += '</div>'; // End Left Column

            // Right Column
            html += '<div class="modal-col-right">';
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
                html += detailCard('Score', `<span class="score-badge ${sCls}">${scanItem.composite_score}</span>`);
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
            html += '</div>'; // End Right Column
            html += '</div>'; // End Modal Layout

            body.innerHTML = html;
            setTimeout(() => initChart(ticker), 0);
        } catch (e) {
            body.innerHTML = '<p style="color:var(--red)">Error loading details.</p>';
        }
    }

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
            const res = await fetch(`${API}/ticker/${ticker}/intraday?period=${period}&interval=${interval}`);
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

    // ── Signal Lab ────────────────────────────────────────────────────────
    async function openSignalLab() {
        const overlay = document.getElementById('signal-lab-overlay');
        overlay.classList.add('active');
        const grid = document.getElementById('signal-lab-grid');
        grid.innerHTML = '<div style="padding:20px;color:var(--text-secondary);text-align:center;">Evaluating historical signals...</div>';
        
        try {
            const res = await fetch(`${API}/signal-evaluation?market=${currentMarket}`);
            const json = await res.json();
            renderSignalLab(json.data);
        } catch (e) {
            grid.innerHTML = `<div style="color:var(--red);padding:20px;">Failed to load evaluation data: ${e}</div>`;
        }
    }

    function closeSignalLab() {
        document.getElementById('signal-lab-overlay').classList.remove('active');
    }

    function renderSignalLab(data) {
        const grid = document.getElementById('signal-lab-grid');
        if (!data || Object.keys(data).length === 0) {
            grid.innerHTML = '<div style="padding:20px;color:var(--text-secondary);">No signal data available.</div>';
            return;
        }

        // Sort entries by 5-day win rate descending
        const sortedEntries = Object.entries(data).sort((a, b) => b[1].win_rate_5d - a[1].win_rate_5d);

        let html = '';
        sortedEntries.forEach(([sigName, stats], index) => {
            const confClass = 'conf-' + stats.confidence;
            const confLabel = stats.confidence.replace('_', ' ');
            const isTopSignal = index < 3;

            const renderBar = (wr) => {
                const pct = (wr * 100).toFixed(0);
                const color = pct >= 60 ? 'bar-green' : (pct < 45 ? 'bar-red' : 'bar-amber');
                return `
                    <div class="metric-row">
                        <span class="metric-label">${wr === stats.win_rate_1d ? '1 Day' : (wr === stats.win_rate_5d ? '5 Days' : '20 Days')}</span>
                        <div class="metric-bar-bg">
                            <div class="metric-bar-fill ${color}" style="width: ${pct}%"></div>
                        </div>
                        <span class="metric-val">${pct}%</span>
                    </div>
                `;
            };

            html += `
                <div class="signal-card ${isTopSignal ? 'top-signal-card' : ''}">
                    <div class="signal-card-header">
                        <div>
                            <div class="signal-name">
                                ${isTopSignal ? '<span style="margin-right:4px;" title="Top Signal">🏆</span>' : ''}
                                ${sigName.replace(/_/g, ' ').toUpperCase()}
                            </div>
                            <div class="signal-count">${stats.total_signals} occurrences (2Y)</div>
                        </div>
                        <div class="confidence-badge ${confClass}">${confLabel}</div>
                    </div>
                    
                    <div style="margin-top: 8px;">
                        <div style="font-size:10px; color:var(--text-tertiary); margin-bottom:6px; text-transform:uppercase;">Win Rate</div>
                        ${renderBar(stats.win_rate_1d)}
                        ${renderBar(stats.win_rate_5d)}
                        ${renderBar(stats.win_rate_20d)}
                    </div>
                    
                    <div style="display:flex; justify-content:space-between; margin-top:10px; padding:10px; background:var(--bg-0); border-radius:4px;">
                        <div style="text-align:center;">
                            <div style="font-size:9px; color:var(--text-tertiary);">Avg Ret 5d</div>
                            <div style="font-size:12px; font-family:var(--font-mono); color:${stats.avg_return_5d >= 0 ? 'var(--green)' : 'var(--red)'};">${stats.avg_return_5d > 0 ? '+' : ''}${stats.avg_return_5d.toFixed(2)}%</div>
                        </div>
                        <div style="text-align:center; border-left:1px solid var(--border); padding-left:10px;">
                            <div style="font-size:9px; color:var(--text-tertiary);">Bullish Ctx</div>
                            <div style="font-size:12px; font-family:var(--font-mono);">${(stats.bullish_context_win_rate * 100).toFixed(0)}%</div>
                        </div>
                        <div style="text-align:center; border-left:1px solid var(--border); padding-left:10px;">
                            <div style="font-size:9px; color:var(--text-tertiary);">Bearish Ctx</div>
                            <div style="font-size:12px; font-family:var(--font-mono);">${(stats.bearish_context_win_rate * 100).toFixed(0)}%</div>
                        </div>
                    </div>
                    
                    <div class="signal-insight">
                        <strong>Insight:</strong> ${stats.insight}
                    </div>
                </div>
            `;
        }
        grid.innerHTML = html;
    }

    // ── Go ─────────────────────────────────────────────────────────────────
    init();
    
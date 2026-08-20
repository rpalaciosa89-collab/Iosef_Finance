/**
 * PaperTradingTab.tsx
 * Rosaura (UX Director): Premium institutional portfolio simulation panel.
 * Shows account equity, open positions with live PnL, and trade history.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { apiFetch } from '../lib/api';

interface Position {
  id: number;
  ticker: string;
  direction: 'LONG' | 'SHORT';
  quantity: number;
  entry_price: number;
  current_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  signal_source: string;
  opened_at: string;
  unrealized_pnl: number | null;
  unrealized_pnl_pct: number | null;
}

interface Trade {
  id: number;
  ticker: string;
  direction: string;
  quantity: number;
  entry_price: number;
  exit_price: number | null;
  pnl: number | null;
  pnl_pct: number | null;
  status: string;
  signal_source: string;
  opened_at: string;
  closed_at: string | null;
  close_reason: string | null;
}

interface Portfolio {
  account: { id: number; name: string; initial_balance: number; cash_balance: number };
  open_positions: Position[];
  trade_history: Trade[];
  total_equity: number;
  total_unrealized_pnl: number;
  total_realized_pnl: number;
  win_rate: number;
  total_trades: number;
}

interface ExecForm {
  ticker: string;
  direction: 'LONG' | 'SHORT';
  quantity: number;
  entry_price: number;
  stop_loss: string;
  take_profit: string;
}

const pnlColor = (v: number | null) =>
  v === null ? '#888' : v >= 0 ? '#00c896' : '#ff4d6d';

const fmt = (n: number | null | undefined, prefix = '$') => {
  if (n === null || n === undefined) return '—';
  return `${prefix}${Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

export function PaperTradingTab() {
  const { } = useAuth();
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [execForm, setExecForm] = useState<ExecForm>({
    ticker: '', direction: 'LONG', quantity: 10, entry_price: 0,
    stop_loss: '', take_profit: '',
  });
  const [execError,   setExecError]   = useState<string | null>(null);
  const [execLoading, setExecLoading] = useState(false);
  const [refreshing, setRefreshing]   = useState(false);
  const [activeSection, setActiveSection] = useState<'portfolio' | 'execute'>('portfolio');

  const fetchPortfolio = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await apiFetch<any>('/paper-trading/portfolio');
      if (!r || r.status === 404) {
        await apiFetch<any>('/paper-trading/account', {
          method: 'POST',
          body: JSON.stringify({ name: 'Iosef Simulation Account', initial_balance: 100000 }),
        });
        return fetchPortfolio();
      }
      setPortfolio(r);
    } catch (e: any) {
      if (e.message !== 'Session expired') setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchPortfolio(); }, [fetchPortfolio]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await apiFetch('/paper-trading/refresh', { method: 'POST' });
      await fetchPortfolio();
    } finally {
      setRefreshing(false);
    }
  };

  const handleExecute = async (e: React.FormEvent) => {
    e.preventDefault();
    setExecLoading(true);
    setExecError(null);
    try {
      const body = {
        ticker: execForm.ticker.toUpperCase(),
        direction: execForm.direction,
        quantity: execForm.quantity,
        entry_price: execForm.entry_price,
        stop_loss:   execForm.stop_loss   ? parseFloat(execForm.stop_loss)   : null,
        take_profit: execForm.take_profit ? parseFloat(execForm.take_profit) : null,
        signal_source: 'IOSEF_ML',
      };
      await apiFetch('/paper-trading/execute', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      await fetchPortfolio();
      setActiveSection('portfolio');
    } catch (e: any) {
      setExecError(e.message);
    } finally {
      setExecLoading(false);
    }
  };

  const handleClose = async (posId: number) => {
    try {
      await apiFetch(`/paper-trading/close/${posId}?close_reason=MANUAL`, { method: 'POST' });
      await fetchPortfolio();
    } catch { /* ignore */ }
  };

  if (loading) return (
    <div style={s.center}><div style={s.spinner} /><span style={{ color: '#888', marginTop: 12 }}>Cargando cartera simulada...</span></div>
  );
  if (error) return <div style={s.errorBox}>{error}</div>;
  if (!portfolio) return null;

  const equity   = portfolio.total_equity;
  const initial  = portfolio.account.initial_balance;
  const totalPnl = equity - initial;
  const totalPct = ((totalPnl / initial) * 100);

  return (
    <div style={s.container}>
      {/* ── Header KPIs ─────────────────────────────────────────────────────── */}
      <div style={s.kpiRow}>
        <div style={s.kpiCard}>
          <div style={s.kpiLabel}>Equity Total</div>
          <div style={{ ...s.kpiValue, color: '#FFF', fontSize: 28 }}>${equity.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
        </div>
        <div style={s.kpiCard}>
          <div style={s.kpiLabel}>P&L Total vs Inicial</div>
          <div style={{ ...s.kpiValue, color: pnlColor(totalPnl), fontSize: 22 }}>
            {totalPnl >= 0 ? '+' : ''}{fmt(totalPnl)} ({totalPct >= 0 ? '+' : ''}{totalPct.toFixed(2)}%)
          </div>
        </div>
        <div style={s.kpiCard}>
          <div style={s.kpiLabel}>Cash Disponible</div>
          <div style={{ ...s.kpiValue, color: '#4a9eff', fontSize: 20 }}>${portfolio.account.cash_balance.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
        </div>
        <div style={s.kpiCard}>
          <div style={s.kpiLabel}>Win Rate</div>
          <div style={{ ...s.kpiValue, color: portfolio.win_rate >= 50 ? '#00c896' : '#ff4d6d', fontSize: 24 }}>{portfolio.win_rate.toFixed(1)}%</div>
        </div>
        <div style={s.kpiCard}>
          <div style={s.kpiLabel}>P&L Realizado</div>
          <div style={{ ...s.kpiValue, color: pnlColor(portfolio.total_realized_pnl) }}>{portfolio.total_realized_pnl >= 0 ? '+' : ''}{fmt(portfolio.total_realized_pnl)}</div>
        </div>
      </div>

      {/* ── Section Tabs ──────────────────────────────────────────────────── */}
      <div style={s.tabBar}>
        <button style={s.tab(activeSection === 'portfolio')} onClick={() => setActiveSection('portfolio')}>
          📊 Portfolio Activo
        </button>
        <button style={s.tab(activeSection === 'execute')} onClick={() => setActiveSection('execute')}>
          ⚡ Ejecutar Señal
        </button>
        <button style={{ ...s.refreshBtn, marginLeft: 'auto' }} onClick={handleRefresh} disabled={refreshing}>
          {refreshing ? '⟳ Actualizando...' : '⟳ Mark-to-Market'}
        </button>
      </div>

      {/* ── Execute Trade Form ────────────────────────────────────────────── */}
      {activeSection === 'execute' && (
        <div style={s.panel}>
          <h3 style={s.panelTitle}>🎯 Simular Ejecución de Señal Institucional</h3>
          <p style={s.hint}>Simula una orden basada en las señales del motor de Iosef Finance. El capital se descuenta automáticamente del balance virtual.</p>
          <form onSubmit={handleExecute} style={s.form}>
            <div style={s.formGrid}>
              <div style={s.fieldGroup}>
                <label style={s.label}>Ticker (del Screener)</label>
                <input style={s.input} value={execForm.ticker} onChange={e => setExecForm(f => ({...f, ticker: e.target.value.toUpperCase()}))} placeholder="AAPL, NVDA, SYK..." required />
              </div>
              <div style={s.fieldGroup}>
                <label style={s.label}>Dirección</label>
                <select style={s.input} value={execForm.direction} onChange={e => setExecForm(f => ({...f, direction: e.target.value as 'LONG' | 'SHORT'}))}>
                  <option value="LONG">LONG (Compra)</option>
                  <option value="SHORT">SHORT (Venta Corta)</option>
                </select>
              </div>
              <div style={s.fieldGroup}>
                <label style={s.label}>Cantidad (Acciones)</label>
                <input style={s.input} type="number" min="1" value={execForm.quantity} onChange={e => setExecForm(f => ({...f, quantity: parseFloat(e.target.value)}))} required />
              </div>
              <div style={s.fieldGroup}>
                <label style={s.label}>Precio de Entrada (USD)</label>
                <input style={s.input} type="number" step="0.01" value={execForm.entry_price || ''} onChange={e => setExecForm(f => ({...f, entry_price: parseFloat(e.target.value)}))} placeholder="Precio actual del screener" required />
              </div>
              <div style={s.fieldGroup}>
                <label style={s.label}>Stop Loss (Opcional)</label>
                <input style={s.input} type="number" step="0.01" value={execForm.stop_loss} onChange={e => setExecForm(f => ({...f, stop_loss: e.target.value}))} placeholder="SL sugerido por el modelo" />
              </div>
              <div style={s.fieldGroup}>
                <label style={s.label}>Take Profit (Opcional)</label>
                <input style={s.input} type="number" step="0.01" value={execForm.take_profit} onChange={e => setExecForm(f => ({...f, take_profit: e.target.value}))} placeholder="TP sugerido por el modelo" />
              </div>
            </div>
            <div style={{ marginTop: 8, color: '#888', fontSize: 13 }}>
              Costo estimado: <strong style={{ color: '#FFF' }}>${((execForm.entry_price || 0) * execForm.quantity).toLocaleString('en-US', {minimumFractionDigits: 2})}</strong>
            </div>
            {execError && <div style={s.errorBox}>{execError}</div>}
            <button type="submit" disabled={execLoading} style={s.goldBtn}>
              {execLoading ? 'Ejecutando...' : '🚀 Simular Operación'}
            </button>
          </form>
        </div>
      )}

      {/* ── Open Positions ────────────────────────────────────────────────── */}
      {activeSection === 'portfolio' && (
        <>
          <div style={s.panel}>
            <h3 style={s.panelTitle}>📈 Posiciones Abiertas ({portfolio.open_positions.length})</h3>
            {portfolio.open_positions.length === 0 ? (
              <div style={s.empty}>No hay posiciones abiertas. Usa "Ejecutar Señal" para iniciar la simulación.</div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={s.table}>
                  <thead>
                    <tr>{['Ticker','Dir.','Qty','Entrada','Actual','SL','TP','P&L USD','P&L %','Señal','Acción'].map(h =>
                      <th key={h} style={s.th}>{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {portfolio.open_positions.map(p => (
                      <tr key={p.id} style={s.tr}>
                        <td style={{ ...s.td, color: '#FFF', fontWeight: 700 }}>{p.ticker}</td>
                        <td style={{ ...s.td, color: p.direction === 'LONG' ? '#00c896' : '#ff4d6d' }}>{p.direction}</td>
                        <td style={s.td}>{p.quantity}</td>
                        <td style={s.td}>${p.entry_price.toFixed(2)}</td>
                        <td style={s.td}>{p.current_price ? `$${p.current_price.toFixed(2)}` : '—'}</td>
                        <td style={{ ...s.td, color: '#ff4d6d' }}>{p.stop_loss ? `$${p.stop_loss.toFixed(2)}` : '—'}</td>
                        <td style={{ ...s.td, color: '#00c896' }}>{p.take_profit ? `$${p.take_profit.toFixed(2)}` : '—'}</td>
                        <td style={{ ...s.td, color: pnlColor(p.unrealized_pnl) }}>
                          {p.unrealized_pnl !== null ? `${p.unrealized_pnl >= 0 ? '+' : ''}$${Math.abs(p.unrealized_pnl).toFixed(2)}` : '—'}
                        </td>
                        <td style={{ ...s.td, color: pnlColor(p.unrealized_pnl_pct) }}>
                          {p.unrealized_pnl_pct !== null ? `${p.unrealized_pnl_pct >= 0 ? '+' : ''}${p.unrealized_pnl_pct.toFixed(2)}%` : '—'}
                        </td>
                        <td style={{ ...s.td, color: '#888', fontSize: 11 }}>{p.signal_source}</td>
                        <td style={s.td}>
                          <button onClick={() => handleClose(p.id)} style={s.closeBtn}>Cerrar</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* ── Trade History ──────────────────────────────────────────────── */}
          <div style={s.panel}>
            <h3 style={s.panelTitle}>📋 Historial de Operaciones ({portfolio.trade_history.length})</h3>
            {portfolio.trade_history.length === 0 ? (
              <div style={s.empty}>Aún no hay operaciones registradas.</div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={s.table}>
                  <thead>
                    <tr>{['Ticker','Dir.','Qty','Entrada','Salida','P&L USD','P&L %','Estado','Razón','Señal'].map(h =>
                      <th key={h} style={s.th}>{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {portfolio.trade_history.map(t => (
                      <tr key={t.id} style={s.tr}>
                        <td style={{ ...s.td, color: '#FFF', fontWeight: 700 }}>{t.ticker}</td>
                        <td style={{ ...s.td, color: t.direction === 'LONG' ? '#00c896' : '#ff4d6d' }}>{t.direction}</td>
                        <td style={s.td}>{t.quantity}</td>
                        <td style={s.td}>${t.entry_price.toFixed(2)}</td>
                        <td style={s.td}>{t.exit_price ? `$${t.exit_price.toFixed(2)}` : '—'}</td>
                        <td style={{ ...s.td, color: pnlColor(t.pnl) }}>
                          {t.pnl !== null ? `${t.pnl >= 0 ? '+' : ''}$${Math.abs(t.pnl).toFixed(2)}` : '—'}
                        </td>
                        <td style={{ ...s.td, color: pnlColor(t.pnl_pct) }}>
                          {t.pnl_pct !== null ? `${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct.toFixed(2)}%` : '—'}
                        </td>
                        <td style={{ ...s.td, color: t.status === 'OPEN' ? '#4a9eff' : '#888', fontSize: 11 }}>{t.status}</td>
                        <td style={{ ...s.td, color: '#888', fontSize: 11 }}>{t.close_reason || '—'}</td>
                        <td style={{ ...s.td, color: '#888', fontSize: 11 }}>{t.signal_source}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────
const s: Record<string, any> = {
  container: { display: 'flex', flexDirection: 'column', gap: 20, padding: '0 4px' },
  center: { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 200 },
  spinner: { width: 32, height: 32, border: '3px solid #222', borderTop: '3px solid #D4AF37', borderRadius: '50%', animation: 'spin 0.8s linear infinite' },
  kpiRow: { display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12 },
  kpiCard: { background: 'rgba(20,20,28,0.7)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 10, padding: '14px 16px' },
  kpiLabel: { fontSize: 11, color: '#888', textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: 6 },
  kpiValue: { fontWeight: 700, fontFamily: '"Roboto Mono", monospace' },
  tabBar: { display: 'flex', gap: 8, alignItems: 'center', borderBottom: '1px solid rgba(255,255,255,0.07)', paddingBottom: 12 },
  tab: (active: boolean) => ({
    padding: '8px 16px', borderRadius: 6, border: 'none', cursor: 'pointer', fontWeight: 600, fontSize: 13,
    background: active ? '#D4AF37' : 'rgba(255,255,255,0.05)',
    color: active ? '#0A0A0A' : '#888',
    transition: 'all 0.15s',
  }),
  refreshBtn: { padding: '7px 14px', borderRadius: 6, border: '1px solid rgba(255,255,255,0.1)', background: 'transparent', color: '#888', cursor: 'pointer', fontSize: 13 },
  panel: { background: 'rgba(15,15,22,0.6)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12, padding: '20px 24px' },
  panelTitle: { margin: '0 0 16px 0', fontSize: 15, fontWeight: 600, color: '#E0E0E0' },
  hint: { color: '#888', fontSize: 13, marginBottom: 20 },
  form: { display: 'flex', flexDirection: 'column', gap: 20 },
  formGrid: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 },
  fieldGroup: { display: 'flex', flexDirection: 'column', gap: 6 },
  label: { fontSize: 12, color: '#AAA' },
  input: { padding: '10px 12px', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6, color: '#FFF', fontSize: 14 },
  goldBtn: { alignSelf: 'flex-start', padding: '12px 28px', background: '#D4AF37', color: '#0A0A0A', border: 'none', borderRadius: 8, fontWeight: 700, cursor: 'pointer', boxShadow: '0 4px 14px rgba(212,175,55,0.39)' },
  errorBox: { background: 'rgba(255,50,50,0.08)', border: '1px solid rgba(255,50,50,0.2)', color: '#ff6b6b', padding: 12, borderRadius: 6, fontSize: 13 },
  empty: { color: '#555', fontSize: 13, padding: '12px 0' },
  table: { width: '100%', borderCollapse: 'collapse' as const, fontSize: 13 },
  th: { padding: '8px 12px', color: '#666', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', textAlign: 'left' as const, borderBottom: '1px solid rgba(255,255,255,0.05)' },
  td: { padding: '10px 12px', color: '#AAA', fontFamily: '"Roboto Mono", monospace', borderBottom: '1px solid rgba(255,255,255,0.03)' },
  tr: { transition: 'background 0.15s' },
  closeBtn: { padding: '4px 10px', background: 'rgba(255,77,109,0.12)', border: '1px solid rgba(255,77,109,0.3)', color: '#ff4d6d', borderRadius: 4, cursor: 'pointer', fontSize: 11 },
};

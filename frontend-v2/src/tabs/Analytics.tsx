/**
 * tabs/Analytics.tsx
 * Tab de Analytics — historial de trades con métricas de rendimiento.
 */
import { useEffect, useState } from 'react';

const HOST = window.location.hostname;
const API_BASE = `http://${HOST}:8002/api`;

interface AnalyticsPayload {
  signal_analytics: Record<string, { total_trades: number; effective_win_rate: number; avg_pnl: number; expiry_rate: number }>;
  asset_analytics: Record<string, { total_trades: number; effective_win_rate: number; avg_pnl: number }>;
  summary_text: string[];
}

export default function Analytics() {
  const [data, setData] = useState<AnalyticsPayload | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/analytics&_t=${Date.now()}`)
      .then(r => r.json())
      .then(setData)
      .catch(console.warn)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="empty-state">
      <span className="icon">📈</span>
      <span>Loading analytics…</span>
    </div>
  );

  if (!data) return (
    <div className="empty-state">
      <span className="icon">⚠️</span>
      <span>No analytics data yet. Trades are tracked as signals are closed.</span>
    </div>
  );

  const signals = Object.entries(data.signal_analytics ?? {})
    .sort(([, a], [, b]) => b.effective_win_rate - a.effective_win_rate);

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
      {/* Summary */}
      {data.summary_text?.length > 0 && (
        <div style={{
          background: 'var(--bg-1)', border: '1px solid var(--border)',
          borderRadius: 6, padding: '14px 16px', marginBottom: 16,
        }}>
          <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.8px', color: 'var(--text-tertiary)', marginBottom: 10 }}>
            Statistical Summary (Carlos)
          </div>
          <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 6 }}>
            {data.summary_text.map((s, i) => (
              <li key={i} style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                • {s}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Signal Performance Table */}
      {signals.length > 0 && (
        <div style={{ background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 6, overflow: 'hidden', marginBottom: 16 }}>
          <div style={{ padding: '10px 16px', background: 'var(--bg-2)', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.8px', color: 'var(--text-tertiary)' }}>
            Signal Performance (Effective Win Rate)
          </div>
          <table>
            <thead>
              <tr>
                {['Signal', 'Trades', 'Eff. Win Rate', 'Avg PnL %', 'Expiry Rate'].map(h => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {signals.map(([name, stats]) => (
                <tr key={name}>
                  <td style={{ textAlign: 'left', fontFamily: 'var(--font-mono)', color: 'var(--blue)' }}>
                    {name.replace(/_/g, ' ')}
                  </td>
                  <td>{stats.total_trades}</td>
                  <td className={stats.effective_win_rate >= 55 ? 'positive' : 'negative'}>
                    {stats.effective_win_rate.toFixed(1)}%
                  </td>
                  <td className={stats.avg_pnl >= 0 ? 'positive' : 'negative'}>
                    {stats.avg_pnl >= 0 ? '+' : ''}{stats.avg_pnl.toFixed(2)}%
                  </td>
                  <td className={stats.expiry_rate >= 50 ? 'negative' : ''}>
                    {stats.expiry_rate.toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {signals.length === 0 && (
        <div className="empty-state">
          <span className="icon">📊</span>
          <span>No closed trades yet. Analytics populate as signals resolve.</span>
        </div>
      )}
    </div>
  );
}

/**
 * tabs/SignalLab.tsx
 * Tab de Signal Lab — muestra estadísticas de evaluación histórica de señales.
 */
import { useEffect, useState } from 'react';
import type { Market } from '../types/market';

const HOST = window.location.hostname;
const API_BASE = `http://${HOST}:8002/api`;

interface SignalStats {
  total_signals: number;
  win_rate_5d: number;
  avg_return_5d: number;
  median_return_5d: number;
  sample_quality: string;
  confidence: string;
  insight: string;
  context?: Record<string, { win_rate: number; avg_return: number; count: number }>;
}

interface LabResponse {
  universe: { tickers: number; period: string };
  signals: Record<string, SignalStats>;
}

interface Props { market: Market }

export default function SignalLab({ market }: Props) {
  const [data, setData] = useState<LabResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE}/signal-evaluation?market=${market}&_t=${Date.now()}`)
      .then(r => r.json())
      .then(setData)
      .catch(console.warn)
      .finally(() => setLoading(false));
  }, [market]);

  if (loading) return (
    <div className="empty-state">
      <span className="icon">🔬</span>
      <span>Running signal evaluation… this may take a moment.</span>
    </div>
  );

  if (!data) return (
    <div className="empty-state">
      <span className="icon">⚠️</span>
      <span>Signal Lab data unavailable.</span>
    </div>
  );

  const signals = Object.entries(data.signals)
    .sort(([, a], [, b]) => b.win_rate_5d - a.win_rate_5d);

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
      <div style={{ marginBottom: 16, color: 'var(--text-tertiary)', fontSize: 11 }}>
        Universe: {data.universe.tickers} tickers · Period: {data.universe.period}
      </div>

      <div className="signal-grid" style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
        gap: 16,
      }}>
        {signals.map(([name, stats]) => {
          const wr = (stats.win_rate_5d * 100).toFixed(1);
          const isGood = stats.win_rate_5d >= 0.55 && stats.avg_return_5d > 0;
          return (
            <div
              key={name}
              style={{
                background: 'var(--bg-1)',
                border: `1px solid ${isGood ? 'var(--green)' : 'var(--border)'}`,
                borderRadius: 6,
                padding: 16,
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <strong style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--blue)' }}>
                  {name.replace(/_/g, ' ').toUpperCase()}
                </strong>
                <span style={{
                  fontSize: 10, padding: '2px 6px', borderRadius: 4,
                  background: stats.confidence === 'high_confidence' ? 'var(--green-dim)' : 'var(--bg-2)',
                  color: stats.confidence === 'high_confidence' ? 'var(--green)' : 'var(--text-tertiary)',
                }}>
                  {stats.sample_quality}
                </span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
                {[
                  { label: 'Win Rate 5D', value: `${wr}%`, color: parseFloat(wr) >= 55 ? 'var(--green)' : 'var(--red)' },
                  { label: 'Avg Return', value: `${stats.avg_return_5d >= 0 ? '+' : ''}${stats.avg_return_5d.toFixed(2)}%`,
                    color: stats.avg_return_5d >= 0 ? 'var(--green)' : 'var(--red)' },
                  { label: 'Signals', value: stats.total_signals.toString(), color: 'var(--text-primary)' },
                ].map(({ label, value, color }) => (
                  <div key={label} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <span style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-tertiary)' }}>{label}</span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 600, color }}>{value}</span>
                  </div>
                ))}
              </div>

              <p style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.4, borderTop: '1px solid var(--border)', paddingTop: 8 }}>
                {stats.insight}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

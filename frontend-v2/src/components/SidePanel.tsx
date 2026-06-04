/**
 * components/SidePanel.tsx
 * Panel lateral: Top Opportunities + Alerts en tiempo real.
 */
import type { TickerEntry, AlertItem } from '../types/market';

interface Props {
  topOpportunities: TickerEntry[];
  alerts: AlertItem[];
  onTickerClick: (t: TickerEntry) => void;
}

function formatTime(date: Date) {
  return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function SidePanel({ topOpportunities, alerts, onTickerClick }: Props) {
  return (
    <aside className="side-panel">
      {/* Top Opportunities */}
      <div className="side-section">
        <div className="side-header">
          <span className="icon">🎯</span>
          Top Opportunities
        </div>
        <ul className="side-list">
          {topOpportunities.length === 0 && (
            <li style={{ padding: '12px', color: 'var(--text-tertiary)', fontSize: 11 }}>
              Scanning for signals…
            </li>
          )}
          {topOpportunities.map(t => (
            <li
              key={t.ticker}
              className="side-item"
              onClick={() => onTickerClick(t)}
              id={`top-opp-${t.ticker}`}
            >
              <span className="sym">{t.ticker}</span>
              <span className="price-col">${t.price.toFixed(2)}</span>
              <span
                className="chg-col"
                style={{ color: t.change_pct >= 0 ? 'var(--green)' : 'var(--red)' }}
              >
                {t.change_pct >= 0 ? '+' : ''}{t.change_pct.toFixed(2)}%
              </span>
            </li>
          ))}
        </ul>
      </div>

      {/* Live Alerts */}
      <div className="side-section">
        <div className="side-header">
          <span className="icon">🔔</span>
          Live Alerts
        </div>
        <ul className="alerts-list">
          {alerts.length === 0 && (
            <li style={{ padding: '12px', color: 'var(--text-tertiary)', fontSize: 11 }}>
              No alerts yet…
            </li>
          )}
          {alerts.slice(0, 20).map((a, i) => (
            <li
              key={`${a.ticker}-${i}`}
              className={`alert-${a.color === 'green' ? 'green' : a.color === 'red' ? 'red' : 'yellow'}`}
            >
              <div className="alert-top">
                <span className="alert-ticker">{a.ticker}</span>
                <span className="alert-time">{formatTime(new Date())}</span>
              </div>
              <span className="alert-msg">{a.message}</span>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}

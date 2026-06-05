/**
 * components/Header.tsx
 * Barra de navegación superior del terminal.
 */
import type { WsStatus } from '../hooks/useMarketData';

interface Props {
  activeTab: 'screener' | 'lab' | 'analytics' | 'paper';
  onTabChange: (tab: 'screener' | 'lab' | 'analytics' | 'paper') => void;
  wsStatus: WsStatus;
  lastUpdated: Date | null;
  tickerCount: number;
}

export function Header({
  activeTab, onTabChange,
  wsStatus, lastUpdated, tickerCount,
}: Props) {
  const statusLabel = wsStatus === 'live' ? 'LIVE' : wsStatus === 'connecting' ? 'CONNECTING' : 'OFFLINE';

  return (
    <header className="header-bar">
      <div className="header-brand">
        <div className="header-logo">IF</div>
        <span className="header-title">Iosef Finance Terminal</span>
      </div>

      <nav className="header-nav">
        {(['screener', 'lab', 'analytics', 'paper'] as const).map(tab => (
          <button
            key={tab}
            id={`nav-tab-${tab}`}
            className={`nav-tab${activeTab === tab ? ' active' : ''}${tab === 'paper' ? ' paper-tab' : ''}`}
            onClick={() => onTabChange(tab)}
          >
            {tab === 'screener' ? '📊 Screener'
              : tab === 'lab' ? '🔬 Signal Lab'
              : tab === 'analytics' ? '📈 Analytics'
              : '💼 Paper Trading'}
          </button>
        ))}
      </nav>

      <div className="header-status">
        <span style={{
          fontSize: 10, fontWeight: 700, textTransform: 'uppercase',
          letterSpacing: '1px', color: '#4a9eff',
          background: 'rgba(74,158,255,0.1)', padding: '3px 8px',
          borderRadius: 4, border: '1px solid rgba(74,158,255,0.25)',
        }}>
          ⚡ TITAN 100
        </span>
        <span>
          <span className={`status-dot ${wsStatus}`} />
          {statusLabel}
        </span>
        <span style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
          {tickerCount} tickers
        </span>
        {lastUpdated && (
          <span style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
            {lastUpdated.toLocaleTimeString()}
          </span>
        )}
      </div>
    </header>
  );
}


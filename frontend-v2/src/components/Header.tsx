/**
 * components/Header.tsx
 * Barra de navegación superior del terminal.
 */
import type { Market } from '../types/market';
import type { WsStatus } from '../hooks/useMarketData';

interface Props {
  activeTab: 'screener' | 'lab' | 'analytics';
  onTabChange: (tab: 'screener' | 'lab' | 'analytics') => void;
  market: Market;
  onMarketChange: (m: Market) => void;
  wsStatus: WsStatus;
  lastUpdated: Date | null;
  tickerCount: number;
}

export function Header({
  activeTab, onTabChange, market, onMarketChange,
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
        {(['screener', 'lab', 'analytics'] as const).map(tab => (
          <button
            key={tab}
            id={`nav-tab-${tab}`}
            className={`nav-tab${activeTab === tab ? ' active' : ''}`}
            onClick={() => onTabChange(tab)}
          >
            {tab === 'screener' ? '📊 Screener'
              : tab === 'lab' ? '🔬 Signal Lab'
              : '📈 Analytics'}
          </button>
        ))}
      </nav>

      <div className="header-status">
        <select
          id="market-selector"
          value={market}
          onChange={e => onMarketChange(e.target.value as Market)}
          style={{ fontSize: 11, padding: '3px 6px' }}
        >
          <option value="nasdaq100">NASDAQ 100</option>
          <option value="sp500">S&amp;P 500</option>
          <option value="europe">Europe</option>
        </select>
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

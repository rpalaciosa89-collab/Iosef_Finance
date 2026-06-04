/**
 * components/StatusBar.tsx
 * Barra de estado inferior del terminal.
 */
import type { Market } from '../types/market';

interface Props {
  market: Market;
  tickerCount: number;
  lastUpdated: Date | null;
  wsStatus: 'connecting' | 'live' | 'offline';
}

export function StatusBar({ market, tickerCount, lastUpdated, wsStatus }: Props) {
  return (
    <footer className="status-bar">
      <span>
        <span className={`status-dot ${wsStatus}`} />
        {wsStatus === 'live'
          ? 'WebSocket Connected'
          : wsStatus === 'connecting'
          ? 'Connecting…'
          : 'REST Fallback'}
      </span>
      <span className="sep" />
      <span>Market: <strong style={{ color: 'var(--text-primary)' }}>{market.toUpperCase()}</strong></span>
      <span className="sep" />
      <span>{tickerCount} tickers loaded</span>
      <span className="sep" />
      {lastUpdated && (
        <span>Last update: <span style={{ fontFamily: 'var(--font-mono)' }}>{lastUpdated.toLocaleTimeString()}</span></span>
      )}
      <span style={{ marginLeft: 'auto', color: 'var(--text-tertiary)' }}>
        Iosef Finance Terminal v2.0 · React + Vite + TypeScript
      </span>
    </footer>
  );
}

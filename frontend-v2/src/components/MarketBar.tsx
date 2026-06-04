/**
 * components/MarketBar.tsx
 * Barra de índices de mercado en tiempo real (tickers de referencia).
 */
import type { TickerEntry } from '../types/market';

interface Props {
  data: TickerEntry[];
}

const REFERENCE_TICKERS = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'AMZN', 'META', 'GOOGL', 'AVGO'];

export function MarketBar({ data }: Props) {
  const refData = REFERENCE_TICKERS
    .map(sym => data.find(d => d.ticker === sym))
    .filter(Boolean) as TickerEntry[];

  return (
    <div className="market-bar">
      {refData.map((t, i) => (
        <div key={t.ticker} className="market-chip">
          <span className="sym">{t.ticker}</span>
          <span className="price">${t.price.toFixed(2)}</span>
          <span
            className="chg"
            style={{ color: t.change_pct >= 0 ? 'var(--green)' : 'var(--red)' }}
          >
            {t.change_pct >= 0 ? '+' : ''}{t.change_pct.toFixed(2)}%
          </span>
          {i < refData.length - 1 && <span className="divider" />}
        </div>
      ))}
      {refData.length === 0 && (
        <span style={{ color: 'var(--text-tertiary)', fontSize: 11 }}>Loading market data…</span>
      )}
    </div>
  );
}

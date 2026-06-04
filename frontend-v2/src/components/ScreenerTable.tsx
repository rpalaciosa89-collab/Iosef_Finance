/**
 * components/ScreenerTable.tsx
 * Tabla principal del screener con sort, filtros y flash de precio en tiempo real.
 * Tipada al 100% contra TickerEntry.
 */
import { useState, useMemo, useRef, useEffect } from 'react';
import type { TickerEntry, SortKey, SortDir } from '../types/market';

interface Props {
  data: TickerEntry[];
  onRowClick: (t: TickerEntry) => void;
}

const COLUMNS: { key: SortKey | string; label: string; sortable?: boolean }[] = [
  { key: 'ticker',               label: 'Ticker',     sortable: true },
  { key: 'sector',               label: 'Sector',     sortable: false },
  { key: 'price',                label: 'Price',      sortable: true },
  { key: 'change_pct',           label: 'Chg %',      sortable: true },
  { key: 'rsi',                  label: 'RSI',        sortable: true },
  { key: 'relative_volume',      label: 'Rel Vol',    sortable: true },
  { key: 'momentum_1m',          label: 'Mom 1M',     sortable: true },
  { key: 'composite_score',      label: 'P(Win)',      sortable: true },
  { key: 'signal_strength_score',label: 'P(Win)',   sortable: true },
  { key: 'signal_status',        label: 'Signal',     sortable: false },
];

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 60 ? 'bg-green-100 text-green-800' : score >= 40 ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800';
  return (
    <span className={`px-2 py-1 rounded text-xs font-medium ${color}`}>
      {score}%
    </span>
  );
}

export function ScreenerTable({ data, onRowClick }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('signal_strength_score');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [query, setQuery] = useState('');
  const [sectorFilter, setSectorFilter] = useState('');

  // Track previous prices for flash animation
  const prevPrices = useRef<Record<string, number>>({});
  const [flashMap, setFlashMap] = useState<Record<string, 'up' | 'down'>>({});

  useEffect(() => {
    const newFlash: Record<string, 'up' | 'down'> = {};
    data.forEach(t => {
      const prev = prevPrices.current[t.ticker];
      if (prev !== undefined && prev !== t.price) {
        newFlash[t.ticker] = t.price > prev ? 'up' : 'down';
      }
      prevPrices.current[t.ticker] = t.price;
    });
    if (Object.keys(newFlash).length) {
      setFlashMap(newFlash);
      const timer = setTimeout(() => setFlashMap({}), 700);
      return () => clearTimeout(timer);
    }
  }, [data]);

  // Unique sectors for filter
  const sectors = useMemo(() => {
    const s = new Set(data.map(d => d.sector ?? '').filter(Boolean));
    return Array.from(s).sort();
  }, [data]);

  const filtered = useMemo(() => {
    let rows = data;
    if (query) rows = rows.filter(r => r.ticker.toLowerCase().includes(query.toLowerCase()));
    if (sectorFilter) rows = rows.filter(r => r.sector === sectorFilter);
    return rows.slice().sort((a, b) => {
      const av = (a as unknown as Record<string, number>)[sortKey] ?? 0;
      const bv = (b as unknown as Record<string, number>)[sortKey] ?? 0;
      return sortDir === 'asc' ? av - bv : bv - av;
    });
  }, [data, query, sectorFilter, sortKey, sortDir]);

  const handleSort = (key: string) => {
    if (!COLUMNS.find(c => c.key === key)?.sortable) return;
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key as SortKey);
      setSortDir('desc');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
      {/* Filter Bar */}
      <div className="filter-bar">
        <div className="filter-group">
          <label htmlFor="ticker-search">Ticker</label>
          <input
            id="ticker-search"
            type="text"
            placeholder="AAPL..."
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
        </div>
        <div className="filter-group">
          <label htmlFor="sector-filter">Sector</label>
          <select
            id="sector-filter"
            value={sectorFilter}
            onChange={e => setSectorFilter(e.target.value)}
          >
            <option value="">All</option>
            {sectors.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <span className="filter-count">{filtered.length} / {data.length}</span>
      </div>

      {/* Table */}
      <div className="table-wrap">
        {filtered.length === 0 ? (
          <div className="empty-state">
            <span className="icon">📡</span>
            <span>Cargando datos de mercado...</span>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                {COLUMNS.map(col => (
                  <th
                    key={col.key}
                    className={[
                      col.sortable ? '' : '',
                      sortKey === col.key ? `sorted sort-${sortDir}` : '',
                    ].join(' ')}
                    onClick={() => handleSort(col.key)}
                    id={`col-${col.key}`}
                  >
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map(t => {
                const flash = flashMap[t.ticker];
                return (
                  <tr
                    key={t.ticker}
                    className={flash ? `flash-${flash}` : ''}
                    onClick={() => onRowClick(t)}
                    id={`row-${t.ticker}`}
                  >
                    <td><span className="ticker-cell">{t.ticker}</span></td>
                    <td><span className="sector-cell">{t.sector ?? '–'}</span></td>
                    <td>${t.price.toFixed(2)}</td>
                    <td className={t.change_pct >= 0 ? 'positive' : 'negative'}>
                      {t.change_pct >= 0 ? '+' : ''}{t.change_pct.toFixed(2)}%
                    </td>
                    <td className={t.rsi > 70 ? 'negative' : t.rsi < 30 ? 'positive' : ''}>
                      {t.rsi.toFixed(1)}
                    </td>
                    <td className={t.relative_volume > 2 ? 'positive' : ''}>
                      {t.relative_volume.toFixed(2)}x
                    </td>
                    <td className={t.momentum_1m >= 0 ? 'positive' : 'negative'}>
                      {t.momentum_1m >= 0 ? '+' : ''}{t.momentum_1m.toFixed(2)}%
                    </td>
                    <td>{t.composite_score}</td>
                    <td><ScoreBadge score={t.signal_strength_score} /></td>
                    <td>
                      {t.signal_status ? (
                        <span className={`lc-pill status-${t.signal_status}`}>
                          {t.signal_status.toUpperCase()}
                        </span>
                      ) : '–'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

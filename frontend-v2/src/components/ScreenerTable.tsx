/**
 * components/ScreenerTable.tsx
 * Tabla principal del screener con sort, filtros y flash de precio en tiempo real.
 * Sprint 12.1: Agrupación Premium vs Mercado con línea divisoria en tiempo real.
 * Tipada al 100% contra TickerEntry.
 */
import { useState, useMemo, useRef, useEffect } from 'react';
import type { TickerEntry, SortKey, SortDir } from '../types/market';

interface Props {
  data: TickerEntry[];
  onRowClick: (t: TickerEntry) => void;
}

const COLUMNS: { key: SortKey | string; label: string; sortable?: boolean; tooltip?: string }[] = [
  { key: 'ticker',               label: 'Ticker',     sortable: true,  tooltip: 'Símbolo bursátil' },
  { key: 'sector',               label: 'Sector',     sortable: false, tooltip: 'Sector económico' },
  { key: 'price',                label: 'Price',      sortable: true,  tooltip: 'Precio actual de mercado' },
  { key: 'change_pct',           label: 'Chg %',      sortable: true,  tooltip: 'Cambio porcentual hoy' },
  { key: 'rsi',                  label: 'RSI',        sortable: true,  tooltip: 'Índice de Fuerza Relativa (0-100). >70 sobrecomprado, <30 sobrevendido' },
  { key: 'relative_volume',      label: 'Rel Vol',    sortable: true,  tooltip: 'Volumen hoy vs. promedio 20 días. >1.5x = volumen inusualmente alto' },
  { key: 'momentum_1m',          label: 'Mom 1M',     sortable: true,  tooltip: 'Cambio de precio en el último mes (20 días)' },
  { key: 'composite_score',      label: 'Score (0-9)',sortable: true,  tooltip: 'Puntuación técnica basada en SMA, RSI, momentum y volumen' },
  { key: 'signal_strength_score',label: 'P(Win)',      sortable: true,  tooltip: 'Score del modelo ML. Mide probabilidad de rendimiento superior al promedio en 5 días.' },
  { key: 'signal_status',        label: 'Signal',     sortable: false, tooltip: 'Estado de la señal: NEW, ACTIVE, WEAKENING' },
];

// Threshold que define qué es una oportunidad "Premium" (alta probabilidad del modelo ML)
const PREMIUM_BUY_THRESHOLD  = 70.0;
const PREMIUM_SELL_THRESHOLD = 30.0;

function isPremiumSignal(t: TickerEntry): boolean {
  return (
    t.signal_strength_score >= PREMIUM_BUY_THRESHOLD ||
    (t.signal_strength_score > 0 && t.signal_strength_score <= PREMIUM_SELL_THRESHOLD)
  );
}

function ScoreBadge({ score, premium }: { score: number; premium: boolean }) {
  if (!score || score === 0) return <span style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>N/A</span>;

  let bg, text;
  if (premium && score >= PREMIUM_BUY_THRESHOLD) {
    bg = 'rgba(16,185,129,0.15)'; text = '#00c896';
  } else if (premium && score <= PREMIUM_SELL_THRESHOLD) {
    bg = 'rgba(239,68,68,0.15)'; text = '#ff4757';
  } else if (score >= 55) {
    bg = 'rgba(16,185,129,0.08)'; text = 'var(--green)';
  } else if (score >= 45) {
    bg = 'rgba(234,179,8,0.1)'; text = '#eab308';
  } else {
    bg = 'rgba(100,100,120,0.1)'; text = 'var(--text-tertiary)';
  }

  return (
    <span style={{
      background: bg, color: text,
      padding: '2px 7px', borderRadius: 4,
      fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600,
      border: premium ? `1px solid ${text}40` : 'none',
    }}>
      {score.toFixed(1)}%
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

    // Sorting secundario respetando el campo elegido por el usuario
    const sorted = rows.slice().sort((a, b) => {
      const av = (a as unknown as Record<string, number>)[sortKey] ?? 0;
      const bv = (b as unknown as Record<string, number>)[sortKey] ?? 0;
      return sortDir === 'asc' ? av - bv : bv - av;
    });

    // Sprint 12.1: Ordenamiento primario: Premium siempre arriba, sin importar lo demás
    const premium = sorted.filter(t => isPremiumSignal(t));
    const nonPremium = sorted.filter(t => !isPremiumSignal(t));
    
    // Premium group siempre ordenado por certidumbre del modelo (descendente)
    // cuando el usuario no ha seleccionado explícitamente otra columna
    if (sortKey === 'signal_strength_score') {
      premium.sort((a, b) => b.signal_strength_score - a.signal_strength_score);
    }

    return { premium, nonPremium };
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

  const totalVisible = filtered.premium.length + filtered.nonPremium.length;

  const renderRow = (t: TickerEntry, premium: boolean) => {
    const flash = flashMap[t.ticker];
    return (
      <tr
        key={t.ticker}
        className={flash ? `flash-${flash}` : ''}
        onClick={() => onRowClick(t)}
        id={`row-${t.ticker}`}
        style={premium ? { background: 'rgba(212,175,55,0.03)' } : undefined}
      >
        <td>
          <span className="ticker-cell" style={premium ? { color: '#D4AF37', fontWeight: 600 } : undefined}>
            {t.ticker}
          </span>
        </td>
        <td><span className="sector-cell">{t.sector ?? '–'}</span></td>
        <td>${t.price > 0 ? t.price.toFixed(2) : '–'}</td>
        <td className={t.change_pct >= 0 ? 'positive' : 'negative'}>
          {t.change_pct !== 0 ? `${t.change_pct >= 0 ? '+' : ''}${t.change_pct.toFixed(2)}%` : '–'}
        </td>
        <td className={t.rsi > 70 ? 'negative' : t.rsi < 30 && t.rsi > 0 ? 'positive' : ''}>
          {t.rsi > 0 ? t.rsi.toFixed(1) : '–'}
        </td>
        <td className={t.relative_volume > 2 ? 'positive' : ''}>
          {t.relative_volume > 0 ? `${t.relative_volume.toFixed(2)}x` : '–'}
        </td>
        <td className={t.momentum_1m >= 0 ? 'positive' : 'negative'}>
          {t.relative_volume > 0 ? `${t.momentum_1m >= 0 ? '+' : ''}${t.momentum_1m.toFixed(2)}%` : '–'}
        </td>
        <td>{t.composite_score > 0 ? t.composite_score : '–'}</td>
        <td><ScoreBadge score={t.signal_strength_score} premium={premium} /></td>
        <td>
          {t.signal_status ? (
            <span className={`lc-pill status-${t.signal_status}`}>
              {t.signal_status.toUpperCase()}
            </span>
          ) : '–'}
        </td>
      </tr>
    );
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
        <span className="filter-count">{totalVisible} / {data.length}</span>
        {filtered.premium.length > 0 && (
          <span style={{
            marginLeft: 8, fontSize: 11, padding: '2px 8px', borderRadius: 4,
            background: 'rgba(212,175,55,0.1)', color: '#D4AF37', border: '1px solid rgba(212,175,55,0.3)',
            fontWeight: 600,
          }}>
            ⚡ {filtered.premium.length} Premium
          </span>
        )}
      </div>

      {/* Table */}
      <div className="table-wrap">
        {totalVisible === 0 ? (
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
                    title={col.tooltip}
                  >
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {/* ── GRUPO PREMIUM (Alta Probabilidad) ── */}
              {filtered.premium.map(t => renderRow(t, true))}

              {/* ── LÍNEA DIVISORIA ── Solo si hay ambos grupos */}
              {filtered.premium.length > 0 && filtered.nonPremium.length > 0 && (
                <tr id="divider-row" style={{ pointerEvents: 'none' }}>
                  <td
                    colSpan={COLUMNS.length}
                    style={{
                      padding: '6px 12px',
                      background: 'var(--bg-0)',
                      borderTop: '1px solid rgba(212,175,55,0.25)',
                      borderBottom: '1px solid rgba(212,175,55,0.25)',
                      position: 'relative',
                    }}
                  >
                    <div style={{
                      display: 'flex', alignItems: 'center', gap: 10,
                    }}>
                      <div style={{ flex: 1, height: 1, background: 'rgba(212,175,55,0.15)' }} />
                      <span style={{
                        fontSize: 10, fontWeight: 600, letterSpacing: '1px',
                        color: 'var(--text-tertiary)', textTransform: 'uppercase', whiteSpace: 'nowrap',
                      }}>
                        ↑ Alta Probabilidad · Resto del Mercado ↓
                      </span>
                      <div style={{ flex: 1, height: 1, background: 'rgba(212,175,55,0.15)' }} />
                    </div>
                  </td>
                </tr>
              )}

              {/* ── GRUPO RESTO DEL MERCADO ── */}
              {filtered.nonPremium.map(t => renderRow(t, false))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

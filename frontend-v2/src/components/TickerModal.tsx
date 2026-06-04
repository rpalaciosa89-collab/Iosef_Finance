/**
 * components/TickerModal.tsx
 * Modal de detalle de ticker: gráfico de velas, señales, plan de trade.
 * Usa lightweight-charts para el gráfico.
 */
import { useEffect, useRef, useState } from 'react';
import { createChart, CandlestickSeries, type IChartApi, type ISeriesApi, type CandlestickData } from 'lightweight-charts';
import type { TickerEntry } from '../types/market';

const HOST = window.location.hostname;
const API_BASE = `http://${HOST}:8002/api`;

interface IntradayBar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface Props {
  ticker: TickerEntry;
  onClose: () => void;
}

const TIMEFRAMES = ['1d', '5d', '1mo', '3mo', '6mo', '1y'];

export function TickerModal({ ticker, onClose }: Props) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const [tf, setTf] = useState('1mo');
  const [loading, setLoading] = useState(true);

  // Build and resize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 360,
      layout: { background: { color: '#0a0b0e' }, textColor: '#8b8fa3' },
      grid: { vertLines: { color: '#1a1d26' }, horzLines: { color: '#1a1d26' } },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: '#2a2e3d' },
      timeScale: { borderColor: '#2a2e3d', timeVisible: true },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#00c896', downColor: '#ff4757',
      borderUpColor: '#00c896', borderDownColor: '#ff4757',
      wickUpColor: '#00c896', wickDownColor: '#ff4757',
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;

    const ro = new ResizeObserver(() => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    });
    ro.observe(chartContainerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, []);

  // Fetch candle data when ticker or timeframe changes
  useEffect(() => {
    if (!candleSeriesRef.current) return;
    setLoading(true);

    fetch(`${API_BASE}/ticker/${ticker.ticker}/intraday?period=${tf}&_t=${Date.now()}`)
      .then(r => r.json())
      .then((d: { bars?: IntradayBar[] }) => {
        if (d.bars && candleSeriesRef.current) {
          const bars: CandlestickData[] = d.bars.map(b => ({
            time: b.time as import('lightweight-charts').Time,
            open: b.open, high: b.high, low: b.low, close: b.close,
          }));
          candleSeriesRef.current.setData(bars);
          chartRef.current?.timeScale().fitContent();
        }
      })
      .catch(console.warn)
      .finally(() => setLoading(false));
  }, [ticker.ticker, tf]);

  const plan = ticker.trade_plan;
  const tracking = ticker.trade_tracking;

  return (
    <div className="modal-overlay active" id="ticker-modal-overlay" onClick={e => {
      if ((e.target as HTMLElement).id === 'ticker-modal-overlay') onClose();
    }}>
      <div className="modal-box">
        {/* Modal header */}
        <div className="modal-top">
          <h2>
            <span className="modal-ticker">{ticker.ticker}</span>
            &nbsp;—&nbsp;
            <span style={{ color: 'var(--text-secondary)', fontSize: 14, fontWeight: 400 }}>
              {ticker.sector ?? 'N/A'} · {ticker.industry ?? ''}
            </span>
          </h2>
          <button className="modal-close" id="modal-close-btn" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body">
          {/* Timeframe bar */}
          <div className="tf-bar">
            {TIMEFRAMES.map(t => (
              <button
                key={t}
                className={`tf-btn${tf === t ? ' active' : ''}`}
                id={`tf-btn-${t}`}
                onClick={() => setTf(t)}
              >
                {t.toUpperCase()}
              </button>
            ))}
          </div>

          {/* Chart */}
          <div id="chart-container" ref={chartContainerRef}>
            {loading && (
              <div style={{
                position: 'absolute', inset: 0, display: 'flex',
                alignItems: 'center', justifyContent: 'center',
                color: 'var(--text-tertiary)', fontSize: 12,
              }}>
                Loading chart…
              </div>
            )}
          </div>

          {/* Detail grid */}
          <div className="detail-grid" style={{ marginTop: 16 }}>
            {[
              { label: 'Price', value: `$${ticker.price.toFixed(2)}` },
              { label: 'Change', value: `${ticker.change_pct >= 0 ? '+' : ''}${ticker.change_pct.toFixed(2)}%`,
                color: ticker.change_pct >= 0 ? 'var(--green)' : 'var(--red)' },
              { label: 'RSI (14)', value: ticker.rsi.toFixed(1) },
              { label: 'SMA 20', value: `$${ticker.sma20.toFixed(2)}` },
              { label: 'SMA 50', value: `$${ticker.sma50.toFixed(2)}` },
              { label: 'SMA 200', value: `$${ticker.sma200.toFixed(2)}` },
              { label: 'Rel Volume', value: `${ticker.relative_volume.toFixed(2)}x` },
              { label: 'Momentum 1M', value: `${ticker.momentum_1m >= 0 ? '+' : ''}${ticker.momentum_1m.toFixed(2)}%`,
                color: ticker.momentum_1m >= 0 ? 'var(--green)' : 'var(--red)' },
              { label: 'Signal Score', value: `${ticker.signal_strength_score.toFixed(0)}/100` },
              { label: 'Signal Status', value: ticker.signal_status?.toUpperCase() || '–' },
            ].map(({ label, value, color }) => (
              <div key={label} className="detail-card">
                <div className="label">{label}</div>
                <div className="value" style={color ? { color } : undefined}>{value}</div>
              </div>
            ))}
          </div>

          {/* Trade Plan */}
          {plan?.entry_price > 0 && (
            <div style={{ marginTop: 16, background: 'var(--bg-0)', border: '1px solid var(--border)', borderRadius: 6, padding: '14px 16px' }}>
              <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.8px', color: 'var(--text-tertiary)', marginBottom: 10 }}>
                Trade Plan · {plan.direction}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                {[
                  { label: 'Entry', value: `$${plan.entry_price.toFixed(2)}` },
                  { label: 'Stop Loss', value: `$${plan.stop_loss.toFixed(2)} (${plan.sl_pct.toFixed(1)}%)`, color: 'var(--red)' },
                  { label: 'Take Profit', value: `$${plan.take_profit.toFixed(2)} (${plan.tp_pct > 0 ? '+' : ''}${plan.tp_pct.toFixed(1)}%)`, color: 'var(--green)' },
                  { label: 'R/R Ratio', value: plan.risk_reward },
                ].map(({ label, value, color }) => (
                  <div key={label} className="detail-card">
                    <div className="label">{label}</div>
                    <div className="value" style={color ? { color } : undefined}>{value}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Live PnL */}
          {tracking?.trade_status === 'open' && (
            <div style={{ marginTop: 12, background: 'var(--bg-0)', border: '1px solid var(--border)', borderRadius: 6, padding: '12px 16px' }}>
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: 8 }}>
                Live Trade Tracking
              </div>
              <div style={{ display: 'flex', gap: 24, fontSize: 13, fontFamily: 'var(--font-mono)' }}>
                <span>
                  PnL:{' '}
                  <strong style={{ color: tracking.pnl_percentage >= 0 ? 'var(--green)' : 'var(--red)' }}>
                    {tracking.pnl_percentage >= 0 ? '+' : ''}{tracking.pnl_percentage.toFixed(2)}%
                  </strong>
                </span>
                <span style={{ color: 'var(--text-tertiary)' }}>
                  Duration: {Math.floor(tracking.trade_duration_seconds / 60)}m
                </span>
                <span style={{ color: 'var(--amber)' }}>Entry Window: {ticker.entry_window_status?.toUpperCase() || '–'}</span>
              </div>
            </div>
          )}

          {/* Human Signal */}
          {ticker.human_signal && (
            <div style={{ marginTop: 12, background: 'var(--bg-0)', border: '1px solid var(--border)', borderRadius: 6, padding: '12px 16px', fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              <strong style={{ color: 'var(--text-primary)' }}>Signal Analysis: </strong>{ticker.human_signal}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

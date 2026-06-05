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
  const [neuralScore, setNeuralScore] = useState<{
    p_win_xgb: number;
    p_win_lstm: number | null;
    p_win_composite: number;
    model: string;
    signal: string;
  } | null>(null);

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

  // Fetch Neural Score (XGBoost + LSTM Ensemble)
  useEffect(() => {
    setNeuralScore(null);
    fetch(`${API_BASE}/neural-score/${ticker.ticker}`)
      .then(r => r.json())
      .then((d: { data?: typeof neuralScore }) => {
        if (d.data) setNeuralScore(d.data);
      })
      .catch(console.warn);
  }, [ticker.ticker]);

  // Null-safe guards: backend guarantees these keys, but we add defaults
  // defensively to prevent React TypeError crashes (black screen bug).
  const plan = ticker.trade_plan ?? { direction: '', entry_price: 0, stop_loss: 0, take_profit: 0, sl_pct: 0, tp_pct: 0, risk_reward: 'N/A' };
  const tracking = ticker.trade_tracking ?? { trade_status: '', pnl_percentage: 0, trade_duration_seconds: 0 };

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
              { label: 'Prob. P(Win)', value: `${ticker.signal_strength_score.toFixed(1)}%` },
              { label: 'Signal Status', value: ticker.signal_status?.toUpperCase() || '–' },
            ].map(({ label, value, color }) => (
              <div key={label} className="detail-card">
                <div className="label">{label}</div>
                <div className="value" style={color ? { color } : undefined}>{value}</div>
              </div>
            ))}
          </div>

          {/* ── Neural Engine Panel (LSTM + XGBoost Ensemble) ── */}
          <div style={{
            marginTop: 16,
            background: 'linear-gradient(135deg, #0d1117 0%, #0f1520 100%)',
            border: '1px solid #1e3a5f',
            borderRadius: 8,
            padding: '14px 16px',
          }}>
            <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.8px', color: '#4a9eff', marginBottom: 12 }}>
              ⚡ Motor Neural — Global LSTM Titan 100
            </div>

            {neuralScore ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
                {[
                  {
                    label: 'P(Win) XGBoost',
                    value: `${(neuralScore.p_win_xgb * 100).toFixed(1)}%`,
                    color: neuralScore.p_win_xgb >= 0.6 ? 'var(--green)' : neuralScore.p_win_xgb <= 0.4 ? 'var(--red)' : 'var(--amber)',
                  },
                  {
                    label: 'P(Win) LSTM',
                    value: neuralScore.p_win_lstm !== null ? `${(neuralScore.p_win_lstm * 100).toFixed(1)}%` : '—',
                    color: neuralScore.p_win_lstm !== null
                      ? neuralScore.p_win_lstm >= 0.6 ? 'var(--green)' : neuralScore.p_win_lstm <= 0.4 ? 'var(--red)' : 'var(--amber)'
                      : 'var(--text-tertiary)',
                  },
                  {
                    label: 'Score Ensemble',
                    value: `${(neuralScore.p_win_composite * 100).toFixed(1)}%`,
                    color: neuralScore.p_win_composite >= 0.6 ? 'var(--green)' : neuralScore.p_win_composite <= 0.4 ? 'var(--red)' : 'var(--amber)',
                  },
                  {
                    label: 'Señal',
                    value: neuralScore.signal,
                    color: neuralScore.signal === 'COMPRA' ? 'var(--green)' : neuralScore.signal === 'VENTA' ? 'var(--red)' : 'var(--amber)',
                  },
                ].map(({ label, value, color }) => (
                  <div key={label} className="detail-card" style={{ borderColor: '#1e3a5f' }}>
                    <div className="label">{label}</div>
                    <div className="value" style={{ color, fontSize: 16, fontWeight: 700 }}>{value}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ color: 'var(--text-tertiary)', fontSize: 12, textAlign: 'center', padding: '8px 0' }}>
                Calculando score neural…
              </div>
            )}
          </div>

          {/* Trade Plan — only shown when a real trade plan exists */}
          {plan?.entry_price > 0 && (
            <div style={{ marginTop: 16, background: 'var(--bg-0)', border: '1px solid var(--border)', borderRadius: 6, padding: '14px 16px' }}>
              <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.8px', color: 'var(--text-tertiary)', marginBottom: 10 }}>
                Señal Predictiva · {plan.direction || 'N/A'}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                {[
                  { label: 'Entry', value: `$${(plan.entry_price ?? 0).toFixed(2)}` },
                  { label: 'Stop Loss', value: `$${(plan.stop_loss ?? 0).toFixed(2)} (${(plan.sl_pct ?? 0).toFixed(1)}%)`, color: 'var(--red)' },
                  { label: 'Take Profit', value: `$${(plan.take_profit ?? 0).toFixed(2)} (${(plan.tp_pct ?? 0) > 0 ? '+' : ''}${(plan.tp_pct ?? 0).toFixed(1)}%)`, color: 'var(--green)' },
                  { label: 'R/R Ratio', value: plan.risk_reward ?? 'N/A' },
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

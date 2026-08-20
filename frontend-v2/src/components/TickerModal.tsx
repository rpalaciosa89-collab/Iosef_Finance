import { useEffect, useState } from 'react';
import type { TickerEntry } from '../types/market';
import { IosefChart } from './IosefChart';
import type { BarData } from './IosefChart';
import { FinancialsTab } from './FinancialsTab';
import { useAuth } from '../context/AuthContext';
import { apiFetch, apiFetchNoAuth } from '../lib/api';

interface Props {
  ticker: TickerEntry;
  onClose: () => void;
}

const TIMEFRAMES = ['1d', '5d', '1mo', '3mo', '6mo', '1y'];

export function TickerModal({ ticker, onClose }: Props) {
  const { isAuthenticated } = useAuth();
  const [tf, setTf] = useState('1mo');
  const [loading, setLoading] = useState(true);
  const [bars, setBars] = useState<BarData[]>([]);
  const [activeTab, setActiveTab] = useState<'technical' | 'fundamentals' | 'backtest'>('technical');
  const [neuralScore, setNeuralScore] = useState<{
    p_win_xgb: number;
    p_win_lstm: number | null;
    p_win_composite: number;
    model: string;
    signal: string;
    alignment?: string;
  } | null>(null);

  const [signalOverlays, setSignalOverlays] = useState<any[]>([]);

  const [backtestData, setBacktestData] = useState<any>(null);
  const [isBacktesting, setIsBacktesting] = useState(false);
  const [backtestError, setBacktestError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setBars([]);
    setSignalOverlays([]);
    apiFetchNoAuth<any>(`/ticker/${ticker.ticker}/intraday?period=${tf}&_t=${Date.now()}`)
      .then((d) => {
        if (d.data && d.data.length > 0) {
          const converted: BarData[] = d.data.map((b: any) => ({
            time: new Date(b.time * 1000).toISOString(),
            open: b.open, high: b.high, low: b.low, close: b.close, volume: b.volume,
          }));
          setBars(converted);
        }
        if (d.signal_overlays && d.signal_overlays.length > 0) {
          setSignalOverlays(d.signal_overlays);
        }
      })
      .catch(console.warn)
      .finally(() => setLoading(false));
  }, [ticker.ticker, tf]);

  useEffect(() => {
    setNeuralScore(null);
    apiFetchNoAuth<any>(`/neural-score/${ticker.ticker}`)
      .then((d) => { if (d.data) setNeuralScore(d.data); })
      .catch(console.warn);
  }, [ticker.ticker]);

  const handleRunBacktest = async () => {
    if (!isAuthenticated) {
      setBacktestError("Acceso Denegado: Inicia sesión primero.");
      return;
    }
    setIsBacktesting(true);
    setBacktestError(null);
    try {
      const end = new Date();
      const start = new Date();
      start.setFullYear(start.getFullYear() - 1);
      const data = await apiFetch<any>(`/backtest/${ticker.ticker}?start_date=${start.toISOString().split('T')[0]}&end_date=${end.toISOString().split('T')[0]}`);
      setBacktestData(data.data);
    } catch (err: any) {
      setBacktestError(err.message);
    } finally {
      setIsBacktesting(false);
    }
  };

  const plan = ticker.trade_plan ?? {
    direction: '', entry_price: 0, stop_loss: 0,
    take_profit: 0, sl_pct: 0, tp_pct: 0, risk_reward: 'N/A'
  };
  const tracking = ticker.trade_tracking ?? {
    trade_status: '', pnl_percentage: 0, trade_duration_seconds: 0
  };

  const tabStyle = (active: boolean, accent: string) => ({
    padding: '8px 4px',
    background: 'transparent',
    border: 'none',
    borderBottom: active ? `2px solid ${accent}` : '2px solid transparent',
    color: active ? '#ffffff' : 'var(--text-tertiary)',
    fontSize: 13,
    fontWeight: active ? 600 : 400,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  } as React.CSSProperties);

  return (
    <div
      className="modal-overlay active"
      id="ticker-modal-overlay"
      onClick={e => {
        if ((e.target as HTMLElement).id === 'ticker-modal-overlay') onClose();
      }}
    >
      <div className="modal-box">
        {/* ── Header ── */}
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

          {/* ── Tab Bar ── */}
          <div style={{ display: 'flex', gap: 16, borderBottom: '1px solid var(--border)', marginBottom: 16 }}>
            <button style={tabStyle(activeTab === 'technical', '#4a9eff')} onClick={() => setActiveTab('technical')}>
              📈 Análisis Predictivo
            </button>
            <button style={tabStyle(activeTab === 'fundamentals', '#00c896')} onClick={() => setActiveTab('fundamentals')}>
              🏦 Salud Financiera
            </button>
            <button style={tabStyle(activeTab === 'backtest', '#D4AF37')} onClick={() => setActiveTab('backtest')}>
              ⚡ Backtesting Cuantitativo
            </button>
          </div>

          {/* ── Contenido de Backtesting ── */}
          {activeTab === 'backtest' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div style={{ background: 'linear-gradient(135deg, rgba(20,20,25,0.8), rgba(10,10,10,0.9))', border: '1px solid rgba(212, 175, 55, 0.2)', borderRadius: 12, padding: '24px' }}>
                <h3 style={{ margin: '0 0 16px 0', color: '#D4AF37', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  Simulador Estadístico Institucional
                </h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 20 }}>
                  Ejecuta una simulación de 1 año sobre los datos históricos de {ticker.ticker} utilizando el algoritmo de cruce de medias como base de rentabilidad (PnL).
                </p>
                <button
                  onClick={handleRunBacktest}
                  disabled={isBacktesting}
                  style={{
                    padding: '12px 24px',
                    backgroundColor: '#D4AF37',
                    color: '#0A0A0A',
                    border: 'none',
                    borderRadius: '8px',
                    fontWeight: 600,
                    cursor: isBacktesting ? 'not-allowed' : 'pointer',
                    opacity: isBacktesting ? 0.7 : 1,
                    transition: 'transform 0.1s',
                    boxShadow: '0 4px 14px 0 rgba(212, 175, 55, 0.39)'
                  }}
                >
                  {isBacktesting ? 'Computando Simulación...' : 'Ejecutar Backtest V2'}
                </button>
                {backtestError && <div style={{ marginTop: 16, color: '#ff6b6b', fontSize: 13 }}>{backtestError}</div>}
              </div>

              {backtestData && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
                  <div className="detail-card" style={{ background: 'rgba(255,255,255,0.03)', borderColor: 'rgba(255,255,255,0.1)' }}>
                    <div className="label">Total Return (1Y)</div>
                    <div className="value" style={{ color: backtestData.total_return_pct >= 0 ? 'var(--green)' : 'var(--red)', fontSize: '24px' }}>
                      {backtestData.total_return_pct >= 0 ? '+' : ''}{backtestData.total_return_pct.toFixed(2)}%
                    </div>
                  </div>
                  <div className="detail-card" style={{ background: 'rgba(255,255,255,0.03)', borderColor: 'rgba(255,255,255,0.1)' }}>
                    <div className="label">Max Drawdown</div>
                    <div className="value" style={{ color: 'var(--red)', fontSize: '24px' }}>
                      {backtestData.max_drawdown_pct.toFixed(2)}%
                    </div>
                  </div>
                  <div className="detail-card" style={{ background: 'rgba(255,255,255,0.03)', borderColor: 'rgba(212, 175, 55, 0.3)' }}>
                    <div className="label" style={{ color: '#D4AF37' }}>Sharpe Ratio</div>
                    <div className="value" style={{ fontSize: '24px', color: '#FFF' }}>
                      {backtestData.sharpe_ratio.toFixed(2)}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Contenido de Salud Financiera ── */}
          {activeTab === 'fundamentals' && (
            <FinancialsTab ticker={ticker.ticker} />
          )}

          {/* ── Contenido de Análisis Predictivo ── */}
          {activeTab === 'technical' && (
            <>
              {/* Barra de Timeframes */}
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

              {/* Motor Gráfico IosefChart */}
              {loading ? (
                <div style={{
                  height: 360, display: 'flex',
                  alignItems: 'center', justifyContent: 'center',
                  color: 'var(--text-tertiary)', fontSize: 12,
                }}>
                  Cargando historial de precios...
                </div>
              ) : (
                <IosefChart data={bars} livePrice={ticker.price} signalOverlays={signalOverlays} />
              )}

              {/* Grid de Indicadores Técnicos */}
              <div className="detail-grid" style={{ marginTop: 16 }}>
                {[
                  { label: 'Price', value: `$${ticker.price.toFixed(2)}` },
                  {
                    label: 'Change', value: `${ticker.change_pct >= 0 ? '+' : ''}${ticker.change_pct.toFixed(2)}%`,
                    color: ticker.change_pct >= 0 ? 'var(--green)' : 'var(--red)'
                  },
                  {
                    label: 'RSI (14)', value: ticker.rsi.toFixed(1),
                    color: ticker.rsi > 70 ? 'var(--red)' : ticker.rsi < 30 ? 'var(--green)' : undefined,
                    hint: ticker.rsi > 70 ? 'Sobrecomprado' : ticker.rsi < 30 ? 'Sobrevendido' : undefined,
                  },
                  { label: 'SMA 20', value: `$${ticker.sma20.toFixed(2)}`,
                    color: ticker.price > ticker.sma20 ? 'var(--green)' : 'var(--red)',
                    hint: ticker.price > ticker.sma20 ? '▲ Sobre' : '▼ Bajo',
                  },
                  { label: 'SMA 50', value: `$${ticker.sma50.toFixed(2)}`,
                    color: ticker.price > ticker.sma50 ? 'var(--green)' : 'var(--red)',
                    hint: ticker.price > ticker.sma50 ? '▲ Sobre' : '▼ Bajo',
                  },
                  { label: 'SMA 200', value: `$${ticker.sma200.toFixed(2)}`,
                    color: ticker.price > ticker.sma200 ? 'var(--green)' : 'var(--red)',
                    hint: ticker.price > ticker.sma200 ? '▲ Sobre' : '▼ Bajo',
                  },
                  { label: 'Rel Volume', value: `${ticker.relative_volume.toFixed(2)}x` },
                  {
                    label: 'Momentum 1M', value: `${ticker.momentum_1m >= 0 ? '+' : ''}${ticker.momentum_1m.toFixed(2)}%`,
                    color: ticker.momentum_1m >= 0 ? 'var(--green)' : 'var(--red)'
                  },
                  { label: 'Prob. P(Win)', value: `${ticker.signal_strength_score.toFixed(1)}%`,
                    hint: 'Score ML: mide probabilidad de superar rendimiento típico en 5 días' },
                  { label: 'Signal Status', value: ticker.signal_status?.toUpperCase() || '–' },
                ].map(({ label, value, color, hint }) => (
                  <div key={label} className="detail-card">
                    <div className="label">{label}</div>
                    <div className="value" style={color ? { color } : undefined} title={hint}>{value}</div>
                    {hint && <div style={{ fontSize: 9, color: 'var(--text-tertiary)', marginTop: 2 }}>{hint}</div>}
                  </div>
                ))}
              </div>

              {/* ── Motor Neural (XGBoost + LSTM Ensemble) ── */}
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
                        value: `${(neuralScore.p_win_xgb).toFixed(1)}%`,
                        color: neuralScore.p_win_xgb >= 55 ? 'var(--green)' : neuralScore.p_win_xgb <= 45 ? 'var(--red)' : 'var(--amber)',
                      },
                      {
                        label: 'P(Win) LSTM',
                        value: neuralScore.p_win_lstm !== null ? `${(neuralScore.p_win_lstm).toFixed(1)}%` : '—',
                        color: neuralScore.p_win_lstm !== null
                          ? neuralScore.p_win_lstm >= 55 ? 'var(--green)' : neuralScore.p_win_lstm <= 45 ? 'var(--red)' : 'var(--amber)'
                          : 'var(--text-tertiary)',
                      },
                      {
                        label: 'Score Ensemble',
                        value: `${(neuralScore.p_win_composite).toFixed(1)}%`,
                        color: neuralScore.p_win_composite >= 55 ? 'var(--green)' : neuralScore.p_win_composite <= 45 ? 'var(--red)' : 'var(--amber)',
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

                {neuralScore?.alignment && (
                  <div style={{
                    marginTop: 10,
                    padding: '6px 10px',
                    borderRadius: 4,
                    fontSize: 11,
                    fontWeight: 600,
                    background: neuralScore.alignment === 'CONFIRMADO' ? 'rgba(0, 200, 150, 0.1)' :
                                 neuralScore.alignment === 'DIVERGENTE' ? 'rgba(255, 150, 50, 0.1)' :
                                 'rgba(128, 128, 128, 0.1)',
                    border: neuralScore.alignment === 'CONFIRMADO' ? '1px solid rgba(0, 200, 150, 0.3)' :
                            neuralScore.alignment === 'DIVERGENTE' ? '1px solid rgba(255, 150, 50, 0.3)' :
                            '1px solid rgba(128, 128, 128, 0.2)',
                    color: neuralScore.alignment === 'CONFIRMADO' ? 'var(--green)' :
                           neuralScore.alignment === 'DIVERGENTE' ? '#ff9632' : 'var(--text-tertiary)',
                  }}>
                    {neuralScore.alignment === 'CONFIRMADO' && '✅ Consistente con el plan de trading'}
                    {neuralScore.alignment === 'DIVERGENTE' && '⚠️ El modelo difiere del análisis técnico. Considere reducir posición.'}
                    {neuralScore.alignment === 'NEUTRAL' && 'Sin dirección clara — espere una señal más definida.'}
                  </div>
                )}
              </div>

              {/* Plan de Trade */}
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
                  {isAuthenticated && (
                    <div style={{ marginTop: 12, textAlign: 'right' }}>
                      <button
                        onClick={async () => {
                          try {
                            await apiFetch('/paper-trading/execute', {
                              method: 'POST',
                              body: JSON.stringify({
                                ticker: ticker.ticker,
                                direction: plan.direction,
                                quantity: 10,
                                entry_price: plan.entry_price,
                                stop_loss: plan.stop_loss,
                                take_profit: plan.take_profit,
                              }),
                            });
                            alert(`✅ Orden simulada ejecutada para ${ticker.ticker}`);
                          } catch (err: any) {
                            alert(`Error: ${err.message}`);
                          }
                        }}
                        style={{
                          padding: '8px 18px',
                          background: 'var(--bg-1)',
                          color: 'var(--text-primary)',
                          border: '1px solid var(--border)',
                          borderRadius: 6,
                          cursor: 'pointer',
                          fontSize: 12,
                          fontWeight: 600,
                        }}
                      >
                        📝 Simular esta operación
                      </button>
                    </div>
                  )}
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
            </>
          )}

        </div>
      </div>
    </div>
  );
}
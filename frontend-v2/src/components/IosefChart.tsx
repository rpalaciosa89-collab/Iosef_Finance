import { useRef, useState, useEffect, useLayoutEffect, useMemo } from 'react';

export type BarData = {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

type SignalOverlay = {
  detected_at: string;
  direction: string;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  score_at_detection: number;
  signal_type: string;
  status: string;
  entry_window: string;
  signal_expired: boolean;
  human_signal: string;
  suggested_action: string;
  pnl_since_detection_pct: number;
  pnl_since_detection_usd: number;
  is_currently_winning: boolean;
};

interface IosefChartProps {
  data: BarData[];
  livePrice?: number;
  signalMarker?: { time: string; price: number; direction: 'LONG' | 'SHORT' };
  signalOverlays?: SignalOverlay[];
}

function getSignalColor(status: string): string {
  switch (status) {
    case 'new': return '#00c896';
    case 'active': return '#16c98d';
    case 'weakening': return '#eab308';
    default: return '#5d6175';
  }
}

function getSignalOpacity(status: string): number {
  switch (status) {
    case 'new': return 1;
    case 'active': return 0.8;
    case 'weakening': return 0.55;
    default: return 0.3;
  }
}

function getSignalSize(status: string): number {
  switch (status) {
    case 'new': return 7;
    case 'active': return 5;
    case 'weakening': return 4;
    default: return 3;
  }
}

function getSignalLabel(status: string): string {
  switch (status) {
    case 'new': return 'NUEVA';
    case 'active': return 'ACTIVA';
    case 'weakening': return 'DÉBIL';
    case 'expired': return 'EXPIRÓ';
    default: return status.toUpperCase();
  }
}

export function IosefChart({ data, livePrice, signalMarker, signalOverlays }: IosefChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 360 });
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [showSignals, setShowSignals] = useState(true);
  const [selectedSignal, setSelectedSignal] = useState<number | null>(null);
  const [expandedCluster, setExpandedCluster] = useState<number | null>(null);

  useLayoutEffect(() => {
    if (!containerRef.current) return;
    const { width } = containerRef.current.getBoundingClientRect();
    if (width > 0) setDimensions({ width, height: 360 });
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const w = entry.contentRect.width;
        if (w > 0) setDimensions({ width: w, height: 360 });
      }
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  if (!data || data.length === 0) {
    return (
      <div ref={containerRef} style={{
        width: '100%', height: 360, display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--text-tertiary)', fontSize: 12, background: 'var(--bg-0)', borderRadius: 6,
        border: '1px solid var(--border)',
      }}>
        Sin datos de precio disponibles
      </div>
    );
  }

  const chartData = [...data];
  if (livePrice && chartData.length > 0) {
    const last = { ...chartData[chartData.length - 1] };
    last.close = livePrice;
    last.high = Math.max(last.high, livePrice);
    last.low = Math.min(last.low, livePrice);
    chartData[chartData.length - 1] = last;
  }

  const { width, height } = dimensions;
  const PADDING_RIGHT = 62;
  const PADDING_BOTTOM = 24;
  const PADDING_TOP = 24;
  const VOLUME_HEIGHT = 50;
  const SIDEBAR_WIDTH = 240;

  const chartW = width - PADDING_RIGHT - (selectedSignal !== null ? SIDEBAR_WIDTH : 0);
  const chartH = height - PADDING_BOTTOM - VOLUME_HEIGHT;

  const minPrice = Math.min(...chartData.map(d => d.low));
  const maxPrice = Math.max(...chartData.map(d => d.high));
  const priceRange = maxPrice - minPrice || 1;
  const pricePadding = priceRange * 0.06;
  const yMin = minPrice - pricePadding;
  const yMax = maxPrice + pricePadding;
  const yRange = yMax - yMin;
  const mapY = (price: number) => PADDING_TOP + ((yMax - price) / yRange) * chartH;

  const maxVol = Math.max(...chartData.map(d => d.volume));
  const volAreaTop = PADDING_TOP + chartH + 4;
  const volAreaH = VOLUME_HEIGHT - 8;
  const mapVolH = (vol: number) => (vol / maxVol) * volAreaH;

  const candleSpace = chartW / chartData.length;
  const candleWidth = Math.max(1, Math.min(12, candleSpace * 0.72));

  const gridLevels = 5;
  const gridLines = Array.from({ length: gridLevels }, (_, i) => {
    const ratio = i / (gridLevels - 1);
    const price = yMax - ratio * yRange;
    const y = mapY(price);
    return { y, price };
  });

  const xLabels: { x: number; label: string }[] = [];
  const labelStep = Math.max(1, Math.floor(chartData.length / 6));
  chartData.forEach((d, i) => {
    if (i % labelStep === 0 || i === chartData.length - 1) {
      const date = d.time.split('T')[0];
      xLabels.push({ x: i * candleSpace + candleSpace / 2, label: date.slice(5) });
    }
  });

  const hoverData = hoverIndex !== null && hoverIndex >= 0 && hoverIndex < chartData.length
    ? chartData[hoverIndex]
    : chartData[chartData.length - 1];

  // ── Signal overlay mapping ──
  const signalPins = useMemo(() => {
    if (!signalOverlays || signalOverlays.length === 0 || !showSignals) return [];

    interface Pin {
      candleIndex: number;
      overlays: SignalOverlay[];
      clusterCount: number;
    }

    const pinMap = new Map<string, Pin>();

    signalOverlays.forEach((s) => {
      if (!s.detected_at) return;
      const detDate = s.detected_at.split('T')[0];
      let bestIdx = -1;

      chartData.forEach((c, i) => {
        const candleDate = c.time.split('T')[0];
        if (candleDate === detDate) { bestIdx = i; }
      });

      if (bestIdx === -1) {
        chartData.forEach((c, i) => {
          const candleDate = c.time.split('T')[0];
          if (candleDate <= detDate) bestIdx = i;
        });
      }

      if (bestIdx < 0 || bestIdx >= chartData.length) return;

      const key = String(bestIdx);
      if (pinMap.has(key)) {
        const existing = pinMap.get(key)!;
        existing.overlays.push(s);
        existing.clusterCount++;
      } else {
        pinMap.set(key, { candleIndex: bestIdx, overlays: [s], clusterCount: 1 });
      }
    });

    return Array.from(pinMap.values());
  }, [signalOverlays, showSignals, chartData]);

  const currentPrice = chartData[chartData.length - 1].close;
  const firstPrice = chartData[0].close;
  const priceUp = currentPrice >= firstPrice;
  const currentY = mapY(currentPrice);
  const currentColor = priceUp ? '#00c896' : '#ff4757';

  const hasSignals = signalOverlays && signalOverlays.length > 0;

  return (
    <div style={{ width: '100%', position: 'relative' }}>
      <div
        ref={containerRef}
        style={{
          width: '100%', height: 360, position: 'relative',
          cursor: 'crosshair', userSelect: 'none',
          background: '#0a0b0e',
          borderRadius: 6,
          border: '1px solid #1a1d26',
          overflow: 'hidden',
        }}
        onMouseLeave={() => setHoverIndex(null)}
        onMouseMove={(e) => {
          const rect = containerRef.current?.getBoundingClientRect();
          if (!rect) return;
          const x = e.clientX - rect.left;
          if (x < chartW) {
            const idx = Math.floor(x / candleSpace);
            setHoverIndex(Math.max(0, Math.min(chartData.length - 1, idx)));
          } else {
            setHoverIndex(null);
          }
        }}
      >
        {/* ── Signal Toggle ── */}
        {hasSignals && (
          <div style={{
            position: 'absolute', top: 6, right: 10, zIndex: 12,
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <button
              onClick={(e) => { e.stopPropagation(); setShowSignals(!showSignals); }}
              style={{
                background: showSignals ? 'rgba(0,200,150,0.12)' : 'rgba(255,255,255,0.04)',
                border: showSignals ? '1px solid rgba(0,200,150,0.3)' : '1px solid rgba(255,255,255,0.1)',
                borderRadius: 4, padding: '2px 8px',
                color: showSignals ? '#00c896' : 'var(--text-tertiary)',
                fontSize: 10, fontWeight: 600, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 4,
              }}
            >
              📍 {showSignals ? 'Señales ON' : 'Señales OFF'}
            </button>
          </div>
        )}

        {/* ── Tooltip OHLCV ── */}
        <div style={{
          position: 'absolute', top: 6, left: 10, zIndex: 10,
          display: 'flex', gap: 10, fontSize: 11,
          color: 'var(--text-secondary)',
          background: 'rgba(10,11,14,0.85)',
          padding: '3px 8px', borderRadius: 4,
          backdropFilter: 'blur(4px)',
        }}>
          <span>O <strong style={{ color: '#e1e4ea' }}>{hoverData.open.toFixed(2)}</strong></span>
          <span>H <strong style={{ color: '#00c896' }}>{hoverData.high.toFixed(2)}</strong></span>
          <span>L <strong style={{ color: '#ff4757' }}>{hoverData.low.toFixed(2)}</strong></span>
          <span>C <strong style={{ color: '#e1e4ea' }}>{hoverData.close.toFixed(2)}</strong></span>
          <span style={{ color: 'var(--text-tertiary)', marginLeft: 4 }}>
            {hoverData.time.split('T')[0]}
          </span>
        </div>

        <svg width={width} height={height} style={{ position: 'absolute', top: 0, left: 0 }}>
          {/* ── Background band (trend) ── */}
          <rect x={0} y={PADDING_TOP} width={chartW} height={chartH}
            fill={priceUp ? 'rgba(0,200,150,0.03)' : 'rgba(255,71,87,0.03)'} />

          {/* ── Grid Lines ── */}
          {gridLines.map(({ y, price }) => (
            <g key={price}>
              <line x1={0} y1={y} x2={chartW} y2={y} stroke="#1a1d26" strokeWidth={1} />
              <text x={chartW + 6} y={y + 4} fill="#5d6175" fontSize={9} fontFamily="JetBrains Mono, monospace">
                {price.toFixed(2)}
              </text>
            </g>
          ))}

          {/* ── Candles ── */}
          {chartData.map((d, i) => {
            const cx = i * candleSpace + candleSpace / 2;
            const isUp = d.close >= d.open;
            const color = isUp ? '#00c896' : '#ff4757';
            const yHigh = mapY(d.high);
            const yLow = mapY(d.low);
            const yOpen = mapY(d.open);
            const yClose = mapY(d.close);
            const bodyTop = Math.min(yOpen, yClose);
            const bodyHeight = Math.max(1, Math.abs(yClose - yOpen));
            const volH = mapVolH(d.volume);
            const volY = volAreaTop + volAreaH - volH;

            const pin = signalPins.find(p => p.candleIndex === i);
            const isExpandedCluster = pin && expandedCluster === pin.candleIndex;

            return (
              <g key={i}>
                <line x1={cx} y1={yHigh} x2={cx} y2={yLow} stroke={color} strokeWidth={1} />
                <rect x={cx - candleWidth / 2} y={bodyTop} width={candleWidth} height={bodyHeight}
                  fill={color} opacity={i === hoverIndex ? 1 : 0.88} />
                <rect x={cx - candleWidth / 2} y={volY} width={candleWidth} height={volH}
                  fill={color} opacity={0.35} />

                {/* ── Signal Pin ── */}
                {pin && (
                  <g onClick={(e) => {
                    e.stopPropagation();
                    if (pin.clusterCount > 1) {
                      setExpandedCluster(expandedCluster === pin.candleIndex ? null : pin.candleIndex);
                    }
                  }}>
                    {pin.clusterCount === 1 || isExpandedCluster ? (
                      (isExpandedCluster ? pin.overlays : pin.overlays.slice(0, 1)).map((s, si) => {
                        const sColor = getSignalColor(s.status);
                        const sOpacity = getSignalOpacity(s.status);
                        const sSize = getSignalSize(s.status);
                        const isLong = s.direction === 'LONG';
                        const markerY = isLong ? yLow + 18 + si * 28 : yHigh - 18 - si * 28;
                        const arrowY = isLong ? markerY - 12 : markerY + 12;

                        return (
                          <g key={si}
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedSignal(selectedSignal === i ? null : i);
                            }}
                            style={{ cursor: 'pointer' }}
                          >
                            {/* Entry price line */}
                            {s.entry_price > 0 && (
                              <line x1={cx - 10} y1={mapY(s.entry_price)} x2={cx + 10} y2={mapY(s.entry_price)}
                                stroke={sColor} strokeWidth={1} opacity={sOpacity} strokeDasharray="2,2" />
                            )}

                            {/* Arrow indicator */}
                            <polygon
                              points={isLong
                                ? `${cx - sSize},${arrowY + sSize} ${cx + sSize},${arrowY + sSize} ${cx},${arrowY - sSize}`
                                : `${cx - sSize},${arrowY - sSize} ${cx + sSize},${arrowY - sSize} ${cx},${arrowY + sSize}`}
                              fill={sColor} opacity={sOpacity}
                            />

                            {/* Score label */}
                            <rect x={cx - 20} y={markerY - 10} width={40} height={16} rx={4}
                              fill={s.status === 'new' ? 'rgba(0,200,150,0.15)' : 'rgba(10,12,16,0.85)'}
                              stroke={sColor} strokeWidth={0.5} opacity={sOpacity} />
                            <text x={cx} y={markerY + 1} fill={sColor} fontSize={9} fontWeight={700}
                              textAnchor="middle" fontFamily="JetBrains Mono, monospace"
                              opacity={sOpacity}>
                              {s.score_at_detection.toFixed(0)}% {isLong ? '▲' : '▼'}
                            </text>

                            {/* Label below/above */}
                            <text x={cx} y={markerY + 16} fill={sColor} fontSize={7} fontWeight={600}
                              textAnchor="middle" fontFamily="Inter, sans-serif" opacity={sOpacity}>
                              {getSignalLabel(s.status)}
                            </text>
                          </g>
                        );
                      })
                    ) : (
                      /* Cluster badge */
                      <g style={{ cursor: 'pointer' }}>
                        <rect x={cx - 14} y={yHigh - 30} width={28} height={18} rx={4}
                          fill="rgba(10,12,16,0.9)" stroke="#D4AF37" strokeWidth={1} />
                        <text x={cx} y={yHigh - 16} fill="#D4AF37" fontSize={9} fontWeight={700}
                          textAnchor="middle" fontFamily="JetBrains Mono, monospace">
                          [{pin.clusterCount}]
                        </text>
                      </g>
                    )}
                  </g>
                )}

                {/* ── Legacy signalMarker ── */}
                {signalMarker && !pin && d.time.split('T')[0] === signalMarker.time.split('T')[0] && (
                  <g transform={`translate(${cx}, ${signalMarker.direction === 'LONG' ? yLow + 15 : yHigh - 15})`}>
                    {signalMarker.direction === 'LONG' ? (
                      <>
                        <polygon points="-5,5 5,5 0,-5" fill="#00c896" />
                        <circle cx={0} cy={12} r={3} fill="#00c896" />
                      </>
                    ) : (
                      <>
                        <polygon points="-5,-5 5,-5 0,5" fill="#ff4757" />
                        <circle cx={0} cy={-12} r={3} fill="#ff4757" />
                      </>
                    )}
                  </g>
                )}
              </g>
            );
          })}

          {/* ── SL/TP lines for selected signal ── */}
          {selectedSignal !== null && signalPins.find(p => p.candleIndex === selectedSignal) && (() => {
            const pin = signalPins.find(p => p.candleIndex === selectedSignal)!;
            const s = pin.overlays[0];
            if (s.stop_loss <= 0 && s.take_profit <= 0) return null;
            return (
              <g>
                {s.stop_loss > 0 && (
                  <>
                    <line x1={0} y1={mapY(s.stop_loss)} x2={chartW} y2={mapY(s.stop_loss)}
                      stroke="#ff4757" strokeWidth={1} strokeDasharray="4,4" opacity={0.5} />
                    <text x={chartW - 2} y={mapY(s.stop_loss) - 4} fill="#ff4757"
                      fontSize={9} fontFamily="JetBrains Mono, monospace" textAnchor="end">
                      SL ${s.stop_loss.toFixed(2)}
                    </text>
                  </>
                )}
                {s.take_profit > 0 && (
                  <>
                    <line x1={0} y1={mapY(s.take_profit)} x2={chartW} y2={mapY(s.take_profit)}
                      stroke="#00c896" strokeWidth={1} strokeDasharray="4,4" opacity={0.5} />
                    <text x={chartW - 2} y={mapY(s.take_profit) - 4} fill="#00c896"
                      fontSize={9} fontFamily="JetBrains Mono, monospace" textAnchor="end">
                      TP ${s.take_profit.toFixed(2)}
                    </text>
                  </>
                )}
              </g>
            );
          })()}

          {/* ── Chart borders ── */}
          <line x1={chartW} y1={PADDING_TOP} x2={chartW} y2={PADDING_TOP + chartH} stroke="#2a2e3d" strokeWidth={1} />
          <line x1={0} y1={PADDING_TOP + chartH} x2={chartW} y2={PADDING_TOP + chartH} stroke="#2a2e3d" strokeWidth={1} />
          <line x1={0} y1={volAreaTop} x2={chartW} y2={volAreaTop} stroke="#1a1d26" strokeWidth={1} />

          {/* ── X Labels ── */}
          {xLabels.map(({ x, label }) => (
            <text key={x} x={x} y={height - 6} fill="#5d6175" fontSize={9} textAnchor="middle" fontFamily="JetBrains Mono, monospace">
              {label}
            </text>
          ))}

          {/* ── Current price line ── */}
          <line x1={0} y1={currentY} x2={chartW} y2={currentY}
            stroke={currentColor} strokeWidth={1} strokeDasharray="3,3" opacity={0.8} />
          <rect x={chartW + 1} y={currentY - 10} width={PADDING_RIGHT - 2} height={20} fill={currentColor} rx={3} />
          <text x={chartW + PADDING_RIGHT / 2} y={currentY + 4} fill="#000" fontSize={10} fontWeight="bold"
            textAnchor="middle" fontFamily="JetBrains Mono, monospace">
            {currentPrice.toFixed(2)}
          </text>

          {/* ── Crosshair ── */}
          {hoverIndex !== null && (
            <g>
              <line x1={hoverIndex * candleSpace + candleSpace / 2} y1={PADDING_TOP}
                x2={hoverIndex * candleSpace + candleSpace / 2} y2={PADDING_TOP + chartH}
                stroke="#4a9eff" strokeWidth={1} strokeDasharray="4,4" opacity={0.5} />
              <line x1={0} y1={mapY(hoverData.close)} x2={chartW} y2={mapY(hoverData.close)}
                stroke="#4a9eff" strokeWidth={1} strokeDasharray="4,4" opacity={0.5} />
            </g>
          )}
        </svg>
      </div>

      {/* ── Signal Sidebar ── */}
      {selectedSignal !== null && signalPins.find(p => p.candleIndex === selectedSignal) && (
        <div style={{
          position: 'absolute', right: 0, top: 0, width: SIDEBAR_WIDTH,
          height: 360, background: 'rgba(10,12,16,0.96)', borderLeft: '1px solid #1a1d26',
          borderTopRightRadius: 6, borderBottomRightRadius: 6,
          padding: '12px', overflowY: 'auto', zIndex: 11,
          display: 'flex', flexDirection: 'column', gap: 10,
        }}>
          {(() => {
            const pin = signalPins.find(p => p.candleIndex === selectedSignal)!;
            const s = pin.overlays[0];
            const sColor = getSignalColor(s.status);
            const isWinning = s.is_currently_winning;
            return (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: '#D4AF37', letterSpacing: '0.5px' }}>
                    📋 Señal
                  </span>
                  <button onClick={() => setSelectedSignal(null)} style={{
                    background: 'none', border: 'none', color: 'var(--text-tertiary)',
                    cursor: 'pointer', fontSize: 14, padding: 0, lineHeight: 1,
                  }}>✕</button>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {/* Direction badge */}
                  <div style={{
                    display: 'inline-flex', alignSelf: 'flex-start',
                    padding: '2px 8px', borderRadius: 3, fontSize: 10, fontWeight: 600,
                    background: s.direction === 'LONG' ? 'rgba(0,200,150,0.1)' : 'rgba(255,71,87,0.1)',
                    color: s.direction === 'LONG' ? '#00c896' : '#ff4757',
                    border: `1px solid ${s.direction === 'LONG' ? 'rgba(0,200,150,0.2)' : 'rgba(255,71,87,0.2)'}`,
                  }}>
                    {s.direction === 'LONG' ? '🔺 LONG' : '🔻 SHORT'}
                  </div>

                  {/* Score */}
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>Score ML</span>
                    <span style={{ fontSize: 13, fontWeight: 700, color: sColor, fontFamily: 'JetBrains Mono, monospace' }}>
                      {s.score_at_detection.toFixed(1)}%
                    </span>
                  </div>

                  {/* Status */}
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>Estado</span>
                    <span style={{ fontSize: 11, fontWeight: 600, color: sColor }}>
                      {getSignalLabel(s.status)}
                    </span>
                  </div>

                  {/* Entry price */}
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>Entrada</span>
                    <span style={{ fontSize: 12, fontWeight: 600, color: '#fff', fontFamily: 'JetBrains Mono, monospace' }}>
                      ${s.entry_price.toFixed(2)}
                    </span>
                  </div>

                  {/* SL / TP */}
                  {s.stop_loss > 0 && (
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>Stop Loss</span>
                      <span style={{ fontSize: 11, color: '#ff4757', fontFamily: 'JetBrains Mono, monospace' }}>
                        ${s.stop_loss.toFixed(2)}
                        {s.entry_price > 0 && s.direction === 'LONG' && (
                          <span style={{ fontSize: 9 }}> ({((s.stop_loss - s.entry_price) / s.entry_price * 100).toFixed(1)}%)</span>
                        )}
                        {s.entry_price > 0 && s.direction === 'SHORT' && (
                          <span style={{ fontSize: 9 }}> (+{((s.stop_loss - s.entry_price) / s.entry_price * 100).toFixed(1)}%)</span>
                        )}
                      </span>
                    </div>
                  )}
                  {s.take_profit > 0 && (
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>Take Profit</span>
                      <span style={{ fontSize: 11, color: '#00c896', fontFamily: 'JetBrains Mono, monospace' }}>
                        ${s.take_profit.toFixed(2)}
                        {s.entry_price > 0 && s.direction === 'LONG' && (
                          <span style={{ fontSize: 9 }}> (+{((s.take_profit - s.entry_price) / s.entry_price * 100).toFixed(1)}%)</span>
                        )}
                        {s.entry_price > 0 && s.direction === 'SHORT' && (
                          <span style={{ fontSize: 9 }}> ({((s.entry_price - s.take_profit) / s.entry_price * 100).toFixed(1)}%)</span>
                        )}
                      </span>
                    </div>
                  )}

                  {/* PnL tracker */}
                  <div style={{
                    marginTop: 4, padding: '8px', borderRadius: 4,
                    background: isWinning ? 'rgba(0,200,150,0.06)' : 'rgba(255,71,87,0.05)',
                    border: `1px solid ${isWinning ? 'rgba(0,200,150,0.15)' : 'rgba(255,71,87,0.12)'}`,
                  }}>
                    <div style={{ fontSize: 9, color: 'var(--text-tertiary)', marginBottom: 4, textTransform: 'uppercase' }}>
                      Rendimiento desde detección
                    </div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: isWinning ? '#00c896' : '#ff4757', fontFamily: 'JetBrains Mono, monospace' }}>
                      {s.pnl_since_detection_pct >= 0 ? '+' : ''}{s.pnl_since_detection_pct.toFixed(2)}%
                    </div>
                    <div style={{
                      marginTop: 4, height: 4, borderRadius: 2,
                      background: 'rgba(255,255,255,0.08)', overflow: 'hidden',
                    }}>
                      <div style={{
                        height: '100%', width: `${Math.min(100, Math.abs(s.pnl_since_detection_pct) * 2)}%`,
                        background: isWinning ? '#00c896' : '#ff4757', borderRadius: 2,
                        transition: 'width 0.3s ease',
                      }} />
                    </div>
                  </div>

                  {s.human_signal && (
                    <div style={{ fontSize: 9, color: 'var(--text-tertiary)', lineHeight: 1.4, marginTop: 4 }}>
                      {s.human_signal}
                    </div>
                  )}

                  {/* Cluster info */}
                  {pin.clusterCount > 1 && (
                    <div style={{
                      fontSize: 9, color: '#D4AF37', marginTop: 6,
                      padding: '5px 8px', borderRadius: 3,
                      background: 'rgba(212,175,55,0.06)', border: '1px solid rgba(212,175,55,0.15)',
                    }}>
                      ⚡ {pin.clusterCount} señales agrupadas en esta vela
                    </div>
                  )}
                </div>
              </>
            );
          })()}
        </div>
      )}
    </div>
  );
}

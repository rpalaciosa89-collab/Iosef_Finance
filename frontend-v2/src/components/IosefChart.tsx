import React, { useRef, useState, useEffect, useLayoutEffect } from 'react';

export type BarData = {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

interface IosefChartProps {
  data: BarData[];
  livePrice?: number; // Optional live tick from WS
}

export function IosefChart({ data, livePrice }: IosefChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 360 });
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  // Capturar dimensión inicial de manera síncrona (evita frame con width=0)
  useLayoutEffect(() => {
    if (!containerRef.current) return;
    const { width } = containerRef.current.getBoundingClientRect();
    if (width > 0) setDimensions({ width, height: 360 });
  }, []);

  // Auto-resize con ResizeObserver
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
      <div
        ref={containerRef}
        style={{
          width: '100%', height: 360,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'var(--text-tertiary)', fontSize: 12,
          background: 'var(--bg-0)', borderRadius: 6,
          border: '1px solid var(--border)',
        }}
      >
        Sin datos de precio disponibles
      </div>
    );
  }

  // Mezclar livePrice en el último candle si está disponible
  const chartData = [...data];
  if (livePrice && chartData.length > 0) {
    const last = { ...chartData[chartData.length - 1] };
    last.close = livePrice;
    last.high = Math.max(last.high, livePrice);
    last.low = Math.min(last.low, livePrice);
    chartData[chartData.length - 1] = last;
  }

  // ── Dimensiones del Canvas ──
  const { width, height } = dimensions;
  const PADDING_RIGHT = 62;
  const PADDING_BOTTOM = 24;
  const PADDING_TOP = 24;
  const VOLUME_HEIGHT = 50; // mini barras de volumen en la parte inferior

  const chartW = width - PADDING_RIGHT;
  const chartH = height - PADDING_BOTTOM - VOLUME_HEIGHT;

  // ── Escala de Precios ──
  const minPrice = Math.min(...chartData.map(d => d.low));
  const maxPrice = Math.max(...chartData.map(d => d.high));
  const priceRange = maxPrice - minPrice || 1;
  const pricePadding = priceRange * 0.06;
  const yMin = minPrice - pricePadding;
  const yMax = maxPrice + pricePadding;
  const yRange = yMax - yMin;
  const mapY = (price: number) => PADDING_TOP + ((yMax - price) / yRange) * chartH;

  // ── Escala de Volumen ──
  const maxVol = Math.max(...chartData.map(d => d.volume));
  const volAreaTop = PADDING_TOP + chartH + 4;
  const volAreaH = VOLUME_HEIGHT - 8;
  const mapVolH = (vol: number) => (vol / maxVol) * volAreaH;

  // ── Candelas ──
  const candleSpace = chartW / chartData.length;
  const candleWidth = Math.max(1, Math.min(12, candleSpace * 0.72));

  // ── Grid lines horizontales ──
  const gridLevels = 5;
  const gridLines = Array.from({ length: gridLevels }, (_, i) => {
    const ratio = i / (gridLevels - 1);
    const price = yMax - ratio * yRange;
    const y = mapY(price);
    return { y, price };
  });

  // ── Labels del eje X (fechas) ──
  const xLabels: { x: number; label: string }[] = [];
  const labelStep = Math.max(1, Math.floor(chartData.length / 6));
  chartData.forEach((d, i) => {
    if (i % labelStep === 0 || i === chartData.length - 1) {
      const date = d.time.split('T')[0];
      xLabels.push({ x: i * candleSpace + candleSpace / 2, label: date.slice(5) }); // MM-DD
    }
  });

  // ── Hover & Crosshair ──
  const hoverData = hoverIndex !== null && hoverIndex >= 0 && hoverIndex < chartData.length
    ? chartData[hoverIndex]
    : chartData[chartData.length - 1];

  const currentPrice = chartData[chartData.length - 1].close;
  const firstPrice = chartData[0].close;
  const priceUp = currentPrice >= firstPrice;
  const currentY = mapY(currentPrice);
  const currentColor = priceUp ? '#00c896' : '#ff4757';

  return (
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
        {/* ── Grid Lines horizontales ── */}
        {gridLines.map(({ y, price }) => (
          <g key={price}>
            <line x1={0} y1={y} x2={chartW} y2={y} stroke="#1a1d26" strokeWidth={1} />
            <text x={chartW + 6} y={y + 4} fill="#5d6175" fontSize={9} fontFamily="JetBrains Mono, monospace">
              {price.toFixed(2)}
            </text>
          </g>
        ))}

        {/* ── Velas Japonesas ── */}
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

          // Volumen
          const volH = mapVolH(d.volume);
          const volY = volAreaTop + volAreaH - volH;

          return (
            <g key={i}>
              {/* Wick */}
              <line x1={cx} y1={yHigh} x2={cx} y2={yLow} stroke={color} strokeWidth={1} />
              {/* Body */}
              <rect
                x={cx - candleWidth / 2}
                y={bodyTop}
                width={candleWidth}
                height={bodyHeight}
                fill={color}
                opacity={i === hoverIndex ? 1 : 0.88}
              />
              {/* Volume bar */}
              <rect
                x={cx - candleWidth / 2}
                y={volY}
                width={candleWidth}
                height={volH}
                fill={color}
                opacity={0.35}
              />
            </g>
          );
        })}

        {/* ── Bordes del área del gráfico ── */}
        <line x1={chartW} y1={PADDING_TOP} x2={chartW} y2={PADDING_TOP + chartH} stroke="#2a2e3d" strokeWidth={1} />
        <line x1={0} y1={PADDING_TOP + chartH} x2={chartW} y2={PADDING_TOP + chartH} stroke="#2a2e3d" strokeWidth={1} />

        {/* ── Línea de separación de volumen ── */}
        <line x1={0} y1={volAreaTop} x2={chartW} y2={volAreaTop} stroke="#1a1d26" strokeWidth={1} />

        {/* ── Labels Eje X ── */}
        {xLabels.map(({ x, label }) => (
          <text key={x} x={x} y={height - 6} fill="#5d6175" fontSize={9} textAnchor="middle" fontFamily="JetBrains Mono, monospace">
            {label}
          </text>
        ))}

        {/* ── Precio Actual (línea punteada + badge) ── */}
        <line
          x1={0} y1={currentY} x2={chartW} y2={currentY}
          stroke={currentColor} strokeWidth={1} strokeDasharray="3,3" opacity={0.8}
        />
        <rect x={chartW + 1} y={currentY - 10} width={PADDING_RIGHT - 2} height={20} fill={currentColor} rx={3} />
        <text x={chartW + PADDING_RIGHT / 2} y={currentY + 4} fill="#000" fontSize={10} fontWeight="bold" textAnchor="middle" fontFamily="JetBrains Mono, monospace">
          {currentPrice.toFixed(2)}
        </text>

        {/* ── Crosshair al hacer hover ── */}
        {hoverIndex !== null && (
          <g>
            <line
              x1={hoverIndex * candleSpace + candleSpace / 2}
              y1={PADDING_TOP}
              x2={hoverIndex * candleSpace + candleSpace / 2}
              y2={PADDING_TOP + chartH}
              stroke="#4a9eff" strokeWidth={1} strokeDasharray="4,4" opacity={0.5}
            />
            <line
              x1={0} y1={mapY(hoverData.close)}
              x2={chartW} y2={mapY(hoverData.close)}
              stroke="#4a9eff" strokeWidth={1} strokeDasharray="4,4" opacity={0.5}
            />
          </g>
        )}
      </svg>
    </div>
  );
}

import type { TickerEntry } from '../types/market';

interface Props {
  data: TickerEntry[];
}

export function ActionableConclusions({ data }: Props) {
  const longSignals = data
    .filter(t => t.trade_plan?.direction === 'LONG' && t.trade_plan?.entry_price > 0 && t.signal_strength_score >= 55.0)
    .sort((a, b) => b.signal_strength_score - a.signal_strength_score)
    .slice(0, 5);

  const shortSignals = data
    .filter(t => t.trade_plan?.direction === 'SHORT' && t.trade_plan?.entry_price > 0 && t.signal_strength_score >= 55.0)
    .sort((a, b) => b.signal_strength_score - a.signal_strength_score)
    .slice(0, 5);

  if (longSignals.length === 0 && shortSignals.length === 0) {
    return null;
  }

  const renderCard = (t: TickerEntry, isLong: boolean) => {
    let timeStr = 'N/A';
    if (t.signal_detected_at) {
      try {
        const d = new Date(t.signal_detected_at);
        timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      } catch (e) { }
    }

    const color = isLong ? 'var(--green)' : 'var(--red)';
    const bgDim = isLong ? 'rgba(16, 185, 129, 0.05)' : 'rgba(239, 68, 68, 0.05)';
    const border = isLong ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)';

    return (
      <div key={t.ticker} style={{
        background: 'var(--bg-1)',
        border: `1px solid ${border}`,
        borderRadius: 8,
        padding: 16,
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        position: 'relative',
        overflow: 'hidden'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
            <strong style={{ fontSize: 18, color: '#FFF' }}>{t.ticker}</strong>
            <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>${t.price.toFixed(2)}</span>
          </div>
          <div style={{
            fontSize: 10, fontWeight: 600, padding: '4px 8px', borderRadius: 4,
            background: bgDim, color: color, letterSpacing: '0.5px'
          }}>
            {isLong ? 'COMPRAR' : 'VENDER'}
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-tertiary)' }}>
          <span>P(Win) {t.signal_strength_score.toFixed(1)}%</span>
          <span style={{ color: '#D4AF37', fontFamily: 'var(--font-mono)' }}>{timeStr}</span>
        </div>

        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8,
          background: 'var(--bg-2)', padding: '12px', borderRadius: 6, border: '1px solid var(--border)'
        }}>
          <div>
            <div style={{ fontSize: 9, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Entry</div>
            <div style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: '#FFF' }}>
              ${t.trade_plan.entry_price.toFixed(2)}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 9, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Stop Loss</div>
            <div style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--red)' }}>
              ${t.trade_plan.stop_loss.toFixed(2)}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 9, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Take Profit</div>
            <div style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--green)' }}>
              ${t.trade_plan.take_profit.toFixed(2)}
            </div>
          </div>
        </div>

      </div>
    );
  };

  return (
    <div style={{ flexShrink: 0, padding: '12px 12px 0', background: 'var(--bg-1)', borderBottom: '1px solid var(--border)' }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10,
        paddingBottom: 8, borderBottom: '1px solid rgba(212, 175, 55, 0.15)'
      }}>
        <span style={{ fontSize: 16 }}>⚡</span>
        <h2 style={{ fontSize: 13, fontWeight: 600, color: '#D4AF37', margin: 0, textTransform: 'uppercase', letterSpacing: '1px' }}>
          Oportunidades Accionables
        </h2>
        <span style={{ fontSize: 10, color: 'var(--text-tertiary)', marginLeft: 'auto' }}>
          P(Win) &ge; 55% · Con plan de trading
        </span>
      </div>

      {longSignals.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <div style={{
            fontSize: 11, fontWeight: 600, color: 'var(--green)', marginBottom: 6,
            textTransform: 'uppercase', letterSpacing: '0.8px'
          }}>
            ✅ Mejores para COMPRAR (LONG)
          </div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
            gap: 10,
          }}>
            {longSignals.map(t => renderCard(t, true))}
          </div>
        </div>
      )}

      {shortSignals.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <div style={{
            fontSize: 11, fontWeight: 600, color: 'var(--red)', marginBottom: 6,
            textTransform: 'uppercase', letterSpacing: '0.8px'
          }}>
            🔻 Mejores para VENDER (SHORT)
          </div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
            gap: 10,
            paddingBottom: 12,
          }}>
            {shortSignals.map(t => renderCard(t, false))}
          </div>
        </div>
      )}
    </div>
  );
}

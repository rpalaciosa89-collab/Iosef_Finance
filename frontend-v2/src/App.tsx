/**
 * App.tsx — Iosef Finance Terminal v2.0
 * Componente raíz: orquesta layout, estado global y tabs de navegación.
 */
import { useState, useMemo, lazy, Suspense } from 'react';
import { useMarketData } from './hooks/useMarketData';
import { Header } from './components/Header';
import { MarketBar } from './components/MarketBar';
import { ScreenerTable } from './components/ScreenerTable';
import { SidePanel } from './components/SidePanel';
import { StatusBar } from './components/StatusBar';
import { TickerModal } from './components/TickerModal';
import { ErrorBoundary } from './components/ErrorBoundary';
import type { TickerEntry } from './types/market';
import './index.css';

// Lazy-load heavy tabs
const SignalLab = lazy(() => import('./tabs/SignalLab'));
const Analytics = lazy(() => import('./tabs/Analytics'));

type Tab = 'screener' | 'lab' | 'analytics';

export default function App() {
  const { scan, alerts, wsStatus, lastUpdated, market, setMarket } = useMarketData();
  const [activeTab, setActiveTab] = useState<Tab>('screener');
  const [selectedTicker, setSelectedTicker] = useState<TickerEntry | null>(null);

  const data = scan?.data ?? [];

  // Top 5 by signal strength for the side panel
  const topOpportunities = useMemo(() =>
    data
      .filter(t => t.signal_strength_score >= 60)
      .sort((a, b) => b.signal_strength_score - a.signal_strength_score)
      .slice(0, 5),
    [data]
  );

  return (
    <div className="app-shell">
      <Header
        activeTab={activeTab}
        onTabChange={setActiveTab}
        market={market}
        onMarketChange={setMarket}
        wsStatus={wsStatus}
        lastUpdated={lastUpdated}
        tickerCount={data.length}
      />

      <MarketBar data={data} />

      <div className="app-layout">
        <main className="main-panel">
          {activeTab === 'screener' && (
            <ScreenerTable data={data} onRowClick={setSelectedTicker} />
          )}

          {activeTab !== 'screener' && (
            <Suspense fallback={
              <div className="empty-state">
                <span className="icon">⚡</span>
                <span>Loading module…</span>
              </div>
            }>
              {activeTab === 'lab' && <SignalLab market={market} />}
              {activeTab === 'analytics' && <Analytics />}
            </Suspense>
          )}
        </main>

        <SidePanel
          topOpportunities={topOpportunities}
          alerts={alerts}
          onTickerClick={setSelectedTicker}
        />
      </div>

      <StatusBar
        market={market}
        tickerCount={data.length}
        lastUpdated={lastUpdated}
        wsStatus={wsStatus}
      />

      {/* Ticker detail modal — wrapped in ErrorBoundary to prevent black screen crashes */}
      {selectedTicker && (
        <ErrorBoundary
          fallback={
            <div className="modal-overlay active" id="ticker-modal-overlay" onClick={() => setSelectedTicker(null)}>
              <div className="modal-box" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, minHeight: 200 }}>
                <span style={{ fontSize: 28 }}>⚠️</span>
                <strong style={{ color: 'var(--text-primary)' }}>Error al cargar el ticker</strong>
                <button className="modal-close" style={{ position: 'static' }} onClick={() => setSelectedTicker(null)}>Cerrar</button>
              </div>
            </div>
          }
        >
          <TickerModal
            ticker={selectedTicker}
            onClose={() => setSelectedTicker(null)}
          />
        </ErrorBoundary>
      )}
    </div>
  );
}

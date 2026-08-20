import { useState, useMemo, lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useMarketData } from './hooks/useMarketData';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Header } from './components/Header';
import { MarketBar } from './components/MarketBar';
import { ScreenerTable } from './components/ScreenerTable';
import { SidePanel } from './components/SidePanel';
import { StatusBar } from './components/StatusBar';
import { TickerModal } from './components/TickerModal';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ActionableConclusions } from './components/ActionableConclusions';
import type { TickerEntry } from './types/market';
import LoginPage from './pages/Login';
import './index.css';

// Lazy-load heavy tabs
const SignalLab    = lazy(() => import('./tabs/SignalLab'));
const Analytics   = lazy(() => import('./tabs/Analytics'));
const PaperTrading = lazy(() => import('./tabs/PaperTrading').then(m => ({ default: m.PaperTradingTab })));

type Tab = 'screener' | 'lab' | 'analytics' | 'paper';

function Dashboard() {
  const { scan, alerts, wsStatus, lastUpdated, market } = useMarketData();
  const [activeTab, setActiveTab] = useState<Tab>('screener');
  const [selectedTicker, setSelectedTicker] = useState<TickerEntry | null>(null);
  const { logout } = useAuth();

  const data = scan?.data ?? [];

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
        wsStatus={wsStatus}
        lastUpdated={lastUpdated}
        tickerCount={data.length}
        onLogout={logout}
      />

      <MarketBar data={data} />

      <div className="app-layout">
        <main className="main-panel">
          {activeTab === 'screener' && (
            <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, overflow: 'hidden' }}>
              <ActionableConclusions data={data} />
              {/* flex:1 + minHeight:0 allows the table-wrap inside to get a bounded height and scroll */}
              <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
                <ScreenerTable data={data} onRowClick={setSelectedTicker} />
              </div>
            </div>
          )}

          {activeTab !== 'screener' && (
            <Suspense fallback={
              <div className="empty-state">
                <span className="icon">⚡</span>
                <span>Loading module…</span>
              </div>
            }>
              {activeTab === 'lab'       && <SignalLab market={market} />}
              {activeTab === 'analytics'  && <Analytics />}
              {activeTab === 'paper'      && <PaperTrading />}
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

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) {
    return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', color: 'var(--text-tertiary)' }}>Verificando sesión...</div>;
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
};

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route 
            path="/dashboard" 
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            } 
          />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

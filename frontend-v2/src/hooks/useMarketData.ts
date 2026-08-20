/**
 * hooks/useMarketData.ts
 * Hook central de datos de mercado.
 * Maneja: polling del backend, integración con WebSocket realtime,
 * y exposición de estado tipado limpio a los componentes.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import type { ScanResponse, Market, AlertItem } from '../types/market';
import { apiFetch } from '../lib/api';

const WS_URL = `ws://${window.location.hostname}:8080/ws/market`;

export type WsStatus = 'connecting' | 'live' | 'offline';

interface UseMarketDataReturn {
  scan: ScanResponse | null;
  alerts: AlertItem[];
  wsStatus: WsStatus;
  lastUpdated: Date | null;
  market: Market;
  setMarket: (m: Market) => void;
  refresh: () => void;
}

export function useMarketData(): UseMarketDataReturn {
  const [market, setMarket] = useState<Market>('titan100');
  const [scan, setScan] = useState<ScanResponse | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [wsStatus, setWsStatus] = useState<WsStatus>('connecting');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── REST fetch ──────────────────────────────────────────────
  const fetchScan = useCallback(async (m: Market) => {
    try {
      const data = await apiFetch<ScanResponse>(`/scan?market=${m}&_t=${Date.now()}`);
      setScan(data);
      if (data.alerts?.length) {
        setAlerts(prev => [...data.alerts!, ...prev].slice(0, 50));
      }
      setLastUpdated(new Date());
      // REST es la fuente principal de datos → marcar como LIVE
      setWsStatus('live');
    } catch (err) {
      console.warn('[useMarketData] fetch failed:', err);
    }
  }, []);

  // ── WebSocket (realtime snapshots from Go service) ──────────
  // Nota: El servicio Go (puerto 8080) aún no está implementado.
  // El WebSocket es opcional; los datos fluyen por REST polling.
  const connectWs = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);

    ws.onopen = () => setWsStatus('live');

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.data && Array.isArray(msg.data)) {
          setScan(msg as ScanResponse);
          setLastUpdated(new Date());
        }
      } catch { /* ignore malformed frames */ }
    };

    ws.onclose = () => {
      // Solo marcar offline si no hay datos REST aún
      setTimeout(connectWs, 5000);
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  }, []);

  // ── Bootstrap ───────────────────────────────────────────────
  useEffect(() => {
    fetchScan(market);
    connectWs();

    // REST polling every 60s as fallback when WS is alive, every 15s if offline
    const interval = setInterval(() => {
      if (wsStatus !== 'live') fetchScan(market);
    }, 15_000);
    pollRef.current = interval;

    return () => {
      clearInterval(interval);
      wsRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Re-fetch on market change ────────────────────────────────
  useEffect(() => {
    fetchScan(market);
  }, [market, fetchScan]);

  return {
    scan,
    alerts,
    wsStatus,
    lastUpdated,
    market,
    setMarket,
    refresh: () => fetchScan(market),
  };
}

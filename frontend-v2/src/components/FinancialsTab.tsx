import React, { useEffect, useState } from 'react';

const HOST = window.location.hostname;
const API_BASE = `http://${HOST}:8002/api`;

interface FinancialsProps {
  ticker: string;
}

interface FinancialData {
  income: Record<string, Record<string, number | null>>;
  balance: Record<string, Record<string, number | null>>;
  cashflow: Record<string, Record<string, number | null>>;
}

export function FinancialsTab({ ticker }: FinancialsProps) {
  const [data, setData] = useState<FinancialData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/ticker/${ticker}/financials`)
      .then(r => r.json())
      .then(d => {
        if (d.data && d.data.income) {
          setData(d.data);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) {
    return <div style={{ color: 'var(--text-tertiary)', padding: 40, textAlign: 'center' }}>Analizando estados financieros...</div>;
  }

  if (!data || Object.keys(data.income).length === 0) {
    return <div style={{ color: 'var(--text-tertiary)', padding: 40, textAlign: 'center' }}>Datos financieros no disponibles.</div>;
  }

  // Extraer los años (keys del diccionario principal)
  const years = Object.keys(data.income).sort(); // sort chronological
  
  // Helpers para extraer valores de forma segura (las keys de yfinance pueden variar ligeramente)
  const getVal = (dict: any, year: string, key: string) => dict[year]?.[key] || 0;
  
  // Pre-calcular máximos para las barras proporcionales CSS
  let maxRevenue = 0;
  let maxAssets = 0;
  
  years.forEach(y => {
    maxRevenue = Math.max(maxRevenue, getVal(data.income, y, "Total Revenue"));
    maxAssets = Math.max(maxAssets, getVal(data.balance, y, "Total Assets"));
  });

  const formatB = (val: number) => `$${(val / 1e9).toFixed(1)}B`;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, padding: '10px 0' }}>
      
      {/* ── MOTOR DE GANANCIAS (INCOME) ── */}
      <div style={{ background: 'var(--bg-0)', border: '1px solid var(--border)', borderRadius: 8, padding: 20 }}>
        <h3 style={{ fontSize: 14, margin: '0 0 16px 0', color: 'var(--text-primary)', display: 'flex', justifyContent: 'space-between' }}>
          <span>Motor de Ganancias</span>
          <span style={{ fontSize: 12, color: 'var(--text-tertiary)', fontWeight: 'normal' }}>Ingresos vs Beneficio Neto</span>
        </h3>
        
        <div style={{ display: 'flex', gap: 12, height: 180, alignItems: 'flex-end', paddingTop: 20 }}>
          {years.map(y => {
            const rev = getVal(data.income, y, "Total Revenue");
            const net = getVal(data.income, y, "Net Income") || getVal(data.income, y, "Net Income Common Stockholders");
            const hRev = maxRevenue > 0 ? (rev / maxRevenue) * 100 : 0;
            const hNet = maxRevenue > 0 ? (Math.abs(net) / maxRevenue) * 100 : 0;
            
            return (
              <div key={y} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, height: '100%' }}>
                <div style={{ position: 'relative', width: '100%', flex: 1, display: 'flex', alignItems: 'flex-end', justifyContent: 'center' }}>
                  {/* Barra Revenue (Fondo oscuro) */}
                  <div style={{ width: '60%', height: `${hRev}%`, background: '#1e3a5f', borderRadius: '4px 4px 0 0', position: 'absolute', bottom: 0, transition: 'height 0.5s ease' }} />
                  {/* Barra Net Income (Brillante al frente) */}
                  <div style={{ width: '60%', height: `${hNet}%`, background: net >= 0 ? '#00c896' : '#ff4757', borderRadius: '4px 4px 0 0', position: 'absolute', bottom: 0, zIndex: 2, transition: 'height 0.5s ease' }} />
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{y.split('-')[0]}</div>
                <div style={{ fontSize: 10, color: 'var(--text-primary)', fontWeight: 600 }}>{formatB(rev)}</div>
              </div>
            );
          })}
        </div>
        <div style={{ display: 'flex', gap: 16, marginTop: 16, fontSize: 11, justifyContent: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><div style={{ width: 10, height: 10, background: '#1e3a5f', borderRadius: 2 }}/> Ingresos Totales</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><div style={{ width: 10, height: 10, background: '#00c896', borderRadius: 2 }}/> Beneficio Neto</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        
        {/* ── FORTALEZA DEL BALANCE (BALANCE SHEET) ── */}
        <div style={{ background: 'var(--bg-0)', border: '1px solid var(--border)', borderRadius: 8, padding: 20 }}>
          <h3 style={{ fontSize: 14, margin: '0 0 16px 0', color: 'var(--text-primary)', display: 'flex', justifyContent: 'space-between' }}>
            <span>Balance General</span>
            <span style={{ fontSize: 12, color: 'var(--text-tertiary)', fontWeight: 'normal' }}>Activos vs Deuda</span>
          </h3>
          {years.length > 0 && (() => {
            const lastY = years[years.length - 1];
            const assets = getVal(data.balance, lastY, "Total Assets");
            const debt = getVal(data.balance, lastY, "Total Debt");
            const cash = getVal(data.balance, lastY, "Cash And Cash Equivalents");
            
            const debtPct = assets > 0 ? (debt / assets) * 100 : 0;
            
            return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 6 }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Activos Totales</span>
                    <span style={{ fontWeight: 600, color: '#4a9eff' }}>{formatB(assets)}</span>
                  </div>
                  <div style={{ width: '100%', height: 6, background: 'var(--bg-1)', borderRadius: 3, overflow: 'hidden' }}>
                    <div style={{ width: '100%', height: '100%', background: '#4a9eff' }} />
                  </div>
                </div>

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 6 }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Deuda Total</span>
                    <span style={{ fontWeight: 600, color: debtPct > 60 ? 'var(--red)' : 'var(--amber)' }}>{formatB(debt)}</span>
                  </div>
                  <div style={{ width: '100%', height: 6, background: 'var(--bg-1)', borderRadius: 3, overflow: 'hidden' }}>
                    <div style={{ width: `${Math.min(debtPct, 100)}%`, height: '100%', background: debtPct > 60 ? 'var(--red)' : 'var(--amber)' }} />
                  </div>
                </div>

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 6 }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Efectivo Disponible</span>
                    <span style={{ fontWeight: 600, color: 'var(--green)' }}>{formatB(cash)}</span>
                  </div>
                </div>
              </div>
            );
          })()}
        </div>

        {/* ── GENERACIÓN DE EFECTIVO (CASH FLOW) ── */}
        <div style={{ background: 'var(--bg-0)', border: '1px solid var(--border)', borderRadius: 8, padding: 20 }}>
          <h3 style={{ fontSize: 14, margin: '0 0 16px 0', color: 'var(--text-primary)' }}>Generación de Efectivo (FCF)</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, height: '100%', justifyContent: 'center' }}>
            {years.map(y => {
              const fcf = getVal(data.cashflow, y, "Free Cash Flow");
              return (
                <div key={y} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)', width: 30 }}>{y.split('-')[0]}</div>
                  <div style={{ flex: 1, height: 16, display: 'flex', alignItems: 'center' }}>
                    {fcf > 0 ? (
                      <div style={{ width: '100%', display: 'flex' }}>
                        <div style={{ width: '50%' }}></div>
                        <div style={{ width: '50%', display: 'flex' }}>
                           <div style={{ height: 8, background: 'var(--green)', borderRadius: '0 4px 4px 0', minWidth: 4, width: `${Math.min((fcf/maxRevenue)*100, 100)}%` }}/>
                        </div>
                      </div>
                    ) : (
                      <div style={{ width: '100%', display: 'flex' }}>
                        <div style={{ width: '50%', display: 'flex', justifyContent: 'flex-end' }}>
                           <div style={{ height: 8, background: 'var(--red)', borderRadius: '4px 0 0 4px', minWidth: 4, width: `${Math.min((Math.abs(fcf)/maxRevenue)*100, 100)}%` }}/>
                        </div>
                        <div style={{ width: '50%' }}></div>
                      </div>
                    )}
                  </div>
                  <div style={{ fontSize: 12, fontWeight: 600, width: 45, textAlign: 'right', color: fcf >= 0 ? 'var(--green)' : 'var(--red)' }}>
                    {formatB(fcf)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

      </div>
    </div>
  );
}

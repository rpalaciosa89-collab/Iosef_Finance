# 2. Perfil del Sistema

## Stack Real

| Capa | Tecnología | Versión |
|---|---|---|
| Backend runtime | Python | 3.12+ |
| Backend framework | FastAPI + Uvicorn | Última |
| Frontend framework | React + Vite | React 19, Vite 8 |
| Frontend language | TypeScript | ~5.6 |
| Caché | Redis | 7 (Alpine) |
| Base de datos | SQLite (x2: SQLAlchemy + sqlite3 directo) | — |
| ML Framework | PyTorch, XGBoost, scikit-learn | — |
| Datos de mercado | yfinance | — |
| Contenerización | Docker + Docker Compose | 3.8 |
| Serving frontend | Nginx (Alpine) | — |

## Arquitectura Real

```
┌─────────────────────────────────────────────────┐
│                  Docker Compose                   │
│                                                   │
│  ┌──────────┐  ┌──────────────┐  ┌────────────┐ │
│  │  Redis:7 │  │ Backend:8002 │  │ Frontend:80│ │
│  │  :6379   │  │ uvicorn      │  │ Nginx      │ │
│  │          │  │ server:app   │  │ React SPA  │ │
│  └──────────┘  └──────┬───────┘  └────────────┘ │
│                        │                          │
│               ┌────────┴────────┐                │
│               │  SQLite x2      │                │
│               │  Parquet cache  │                │
│               │  Modelos .pth   │                │
│               └─────────────────┘                │
│                                                   │
│  Fuente externa: yfinance API (datos de mercado)  │
│  Fuente externa: DeepSeek API (LLM)               │
└─────────────────────────────────────────────────┘
```

## Entry Points

| Entrypoint | Archivo | Ejecutor | Rol |
|---|---|---|---|
| Backend real (Docker) | `backend/server.py` | `uvicorn server:app` | API principal en `/api/*` |
| Backend alternativo | `backend/app/main.py` | `uvicorn app.main:app` | API modular en `/api/v1/*` |
| Frontend SPA | `frontend-v2/src/main.tsx` | Vite dev / Nginx | UI completa |
| Scripts ML | `backend/scripts/train_*.py` | Python CLI | Entrenamiento offline |
| Script descarga | `backend/scripts/download_titan_history.py` | Python CLI | Datos históricos |

## Dependencias Críticas

| Dependencia | Tipo | Riesgo |
|---|---|---|
| yfinance | API externa (gratuita) | Rate limiting, cambios de schema, indisponibilidad |
| Redis | Infraestructura interna | Punto único de fallo para caché |
| DeepSeek API | API externa (LLM) | Disponibilidad, costos, latencia |
| PyTorch | ML runtime | Compatibilidad de dispositivos (MPS/CPU) |
| XGBoost | ML runtime | Modelo actual entrenado con datos sintéticos |

## Componentes Clave

| Componente | Ubicación | Estado |
|---|---|---|
| Screener cuantitativo | `server.py` L568-908 | Funcional, dependiente de yfinance |
| Signal evaluation | `app/services/signal_evaluation.py` | Funcional, 21 tests |
| Scoring ML | `app/services/scoring.py` | Funcional, pero datos sintéticos |
| LSTM inference | `app/services/lstm_inference.py` | Funcional, modelo preentrenado |
| Paper trading | `app/api/paper_trading.py` | Funcional, con endpoints |
| Backtesting | `app/api/backtest.py` | Funcional, wrapper de Backtester |
| Auth (JWT) | `app/core/security.py`, `app/api/auth.py` | Funcional, con riesgos de seguridad |
| Persistencia trades | `app/services/persistence.py` | Funcional, SQLite directo |
| Analytics | `app/services/analytics.py` | Funcional, queries SQL estáticas |
| LLM proxy | `app/api/endpoints/llm.py` | Funcional, client DeepSeek |

## Universo de Datos

- **Titan 100:** 100 tickers institucionales curados manualmente
- **Histórico:** ~15 años de datos OHLCV diarios en formato Parquet (~90 tickers descargados)
- **Caché:** Redis con TTL por tipo de dato (scan: 60s, ticker: 30s, intraday: 10s, financials: 24h)
- **Snapshots:** JSON en disco como respaldo de caché

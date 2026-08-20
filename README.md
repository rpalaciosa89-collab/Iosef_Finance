# Iosef_Finance

Plataforma financiera web-first de alto rendimiento inspirada en Finviz, diseñada para análisis cuantitativo, flujos de datos en tiempo real y automatización mediante agentes inteligentes.

## Estructura del Proyecto

* **`backend/`**: API REST con **Python 3.12+** y **FastAPI**. Entrypoint: `server.py` (uvicorn server:app). Auth JWT, screener cuantitativo (Titan 100), paper trading, backtesting, analytics, scoring ML (XGBoost + LSTM).
* **`frontend-v2/`**: SPA con **React 19 + Vite 8 + TypeScript**. Dashboard con Screener, Signal Lab, Analytics y Paper Trading.
* **`cache/`**: Redis para caché de datos de mercado con TTL por tipo de dato.
* **`snapshots/`**: Respaldos JSON del estado del mercado.
* **`data/`**: Datos históricos OHLCV en formato Parquet (~90 tickers, 15 años).
* **`agents/`**: Agentes autónomos de análisis financiero.
* **`auditoria_integral_2026/`**: Auditoría integral y plan de producción (PDCA por Olas).

## Requisitos de Entorno

* **Python 3.12+**
* **Node.js 20+**
* **Redis** (brew install redis o Docker)
* **Docker + Docker Compose** (opcional, recomendado para despliegue)

## Variables de Entorno Requeridas

Copia `backend/.env.example` a `backend/.env` y configura:

| Variable | Descripción |
|---|---|
| `JWT_SECRET_KEY` | Clave secreta para firmar tokens JWT (obligatorio, generar con `openssl rand -hex 32`) |
| `CORS_ORIGINS` | Orígenes permitidos para CORS (default: `http://localhost:5173,http://localhost:3000`) |
| `REDIS_HOST` | Host de Redis (default: `localhost`) |
| `REDIS_PORT` | Puerto de Redis (default: `6379`) |

## Inicio Rápido (Docker — Recomendado)

```bash
# 1. Configurar variables de entorno
cp backend/.env.example backend/.env
# Editar backend/.env y establecer JWT_SECRET_KEY

# 2. Construir e iniciar
JWT_SECRET_KEY=tu_clave_secreta docker compose up --build

# 3. Acceder
# Frontend: http://localhost:80
# Backend API: http://localhost:8002
# Health check: http://localhost:8002/api/health
```

## Inicio Rápido (Desarrollo Local)

1. Instalar dependencias del backend:
   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

2. Iniciar Redis:
   ```bash
   brew services start redis   # macOS
   # o: redis-server
   ```

3. Ejecutar el backend:
   ```bash
   cd backend
   JWT_SECRET_KEY=dev-secret uvicorn server:app --reload --port 8002
   ```

4. Ejecutar el frontend:
   ```bash
   cd frontend-v2
   npm install
   npm run dev
   ```

5. Acceder: `http://localhost:5173`

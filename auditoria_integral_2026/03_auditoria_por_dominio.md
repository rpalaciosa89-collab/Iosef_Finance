# 4. Auditoría por Dominio

---

## 4.1 Arquitectura

**Estado:** Media-Baja

**Fortalezas:**
- Separación clara de responsabilidades: backend API, frontend SPA, Redis caché, scripts ML offline
- Docker Compose funcional para entorno reproducible
- Uso de Parquet para datos históricos (eficiente, columnar)
- Redis con TTL diferenciados por tipo de dato

**Debilidades:**
- **Deriva arquitectónica crítica:** Dos aplicaciones FastAPI coexisten sin consolidación clara
- La ruta `/api/v1/*` de `app/main.py` nunca se usa en Docker, pero sí en desarrollo local
- No hay capa de abstracción para el cliente HTTP en frontend
- Doble estrategia de persistencia (SQLAlchemy + sqlite3 directo)
- No hay separación de entornos (dev/staging/prod) en configuración

**Recomendaciones:**
1. Consolidar en un solo backend entrypoint
2. Definir una arquitectura de capas explícita: routers → services → data access
3. Documentar el flujo de datos end-to-end

---

## 4.2 Backend

**Estado:** Media

**Fortalezas:**
- FastAPI bien estructurado con routers modulares
- Scoring pipeline con ensemble XGBoost + LSTM
- Paper trading con endpoints completos (crear, ejecutar, cerrar, refresh)
- Persistencia de trades con validación rigurosa
- Background tasks para sector sync y scanning

**Debilidades:**
- `server.py` tiene ~1400 líneas, mezclando configuración, rutas y lógica de negocio
- Endpoints mock en `app/api/endpoints/market.py` y `screener.py`
- Dependencia fuerte de `yfinance` sin abstracción
- No hay rate limiting ni throttling en endpoints
- Manejo de errores inconsistente entre endpoints
- Sin versión de API (headers o URL)

**Recomendaciones:**
1. Refactorizar `server.py` extrayendo routers a módulos separados
2. Crear abstracción sobre `yfinance` para facilitar mocking y cambio de proveedor
3. Agregar rate limiting con slowapi o similar
4. Versionar la API (v1, v2) en la URL

---

## 4.3 Frontend

**Estado:** Media

**Fortalezas:**
- React 19 + Vite 8 con TypeScript
- ErrorBoundary implementado para evitar pantallas blancas
- Separación por tabs (Screener, SignalLab, Analytics, PaperTrading)
- ESLint configurado
- StrictMode activado

**Debilidades:**
- URLs de API hardcodeadas en ~4 archivos diferentes
- Sin cliente HTTP centralizado
- Sin tests (0 tests frontend)
- Estilos inline extensos (ej. Login.tsx con ~100 líneas de estilos inline)
- Uso de `any` en múltiples componentes
- Sin manejo consistente de estados de carga/error
- Sin variables de entorno de Vite (`VITE_*`)

**Recomendaciones:**
1. Crear `src/lib/api.ts` como cliente HTTP centralizado
2. Usar `import.meta.env.VITE_API_BASE` para la URL del backend
3. Agregar Vitest + @testing-library/react
4. Migrar estilos inline a CSS Modules
5. Eliminar tipos `any`

---

## 4.4 Seguridad

**Estado:** Baja

**Fortalezas:**
- Bcrypt para hashing de contraseñas
- JWT para autenticación stateless
- `.env` en `.gitignore`
- `.env.example` versionado

**Debilidades:**
- **JWT secret hardcodeado** con fallback en código fuente
- **CORS `*` con `allow_credentials=True`** — combinación insegura
- Token JWT en `localStorage` (vulnerable a XSS)
- Token TTL de 7 días (ventana de abuso extensa)
- Sin refresh token ni invalidación
- Dos fuentes de verdad para secretos (`security.py` vs `config.py`)
- Sin validación de input en parámetros de ruta (ticker)
- Sin rate limiting
- Sin HTTPS/TLS forzado
- Credenciales admin documentadas en `MANUAL_ARRANQUE.md`

**Recomendaciones:**
1. Eliminar fallback hardcodeado de JWT secret
2. Restringir CORS a orígenes explícitos
3. Migrar token a cookie HttpOnly + Secure
4. Reducir TTL a 15-60 min + refresh token
5. Unificar configuración de secretos
6. Agregar validación regex en parámetros de ruta
7. Implementar rate limiting
8. Forzar HTTPS en producción

---

## 4.5 Datos y Persistencia

**Estado:** Media

**Fortalezas:**
- Parquet como formato de datos históricos (eficiente, comprimido)
- ~90 tickers del Titan 100 con 15 años de historia descargados
- Pipeline de descarga robusto con reintentos y rate limiting
- Persistencia de trades con validación exhaustiva de campos
- Caché Redis con TTL por tipo de dato

**Debilidades:**
- **Dos bases de datos SQLite separadas:** `iosef_finance.db` (SQLAlchemy) y `trades_history.db` (sqlite3 directo)
- No hay estrategia de backup de bases de datos
- SQLite no es adecuado para concurrencia en producción
- Archivos `.db` en raíz del repo sin protección en `.gitignore`
- Sin migraciones de esquema (Alembic)
- Dependencia de `yfinance` sin abstracción para cambio de proveedor

**Recomendaciones:**
1. Unificar bases de datos o migrar a PostgreSQL
2. Agregar Alembic para migraciones
3. Implementar backups automatizados
4. Proteger archivos `.db` en `.gitignore`

---

## 4.6 Redis y Caché

**Estado:** Media-Alta

**Fortalezas:**
- Redis como capa de velocidad principal
- TTL diferenciados por tipo de dato (scan: 60s, ticker: 30s, intraday: 10s, financials: 24h, sector: 30d)
- Rate limiting para sector sync (0.8s delay, max 3 retries, exponential backoff)
- Snapshot JSON en disco como respaldo
- Manejo de `ConnectionError` en helpers de Redis

**Debilidades:**
- Sin autenticación en Redis (sin contraseña)
- Sin healthcheck en Docker Compose para Redis
- Sin métricas de hit/miss rate
- Sin estrategia de warm-up de caché

**Recomendaciones:**
1. Agregar `requirepass` a Redis
2. Agregar healthcheck en docker-compose
3. Instrumentar hit/miss rate para monitoreo

---

## 4.7 ML / Analítica

**Estado:** Media

**Fortalezas:**
- Pipeline de entrenamiento LSTM sólido: feature engineering, entrenamiento, gráficos, checkpoints
- Reentrenamiento continuo (fine-tuning) con versionado por fecha
- Inferencia LSTM bien implementada: singleton, CPU, manejo de errores
- Ensemble XGBoost (40%) + LSTM (60%) para scoring compuesto
- Feature engineering replicado exactamente entre training e inferencia
- Uso de MPS/CUDA/CPU con detección automática de dispositivo
- Métricas de entrenamiento registradas (loss, convergencia)

**Debilidades:**
- **XGBoost entrenado con datos sintéticos** — sin validez estadística
- Sin validación del modelo (train/val/test split con time-series cross-validation)
- Sin monitoreo de data drift o model drift
- Sin registro de versiones de modelo en producción
- `compute_ml_score()` retorna 50.0 (neutral) si falla la carga del modelo — puede enmascarar errores
- Sin tests para el pipeline de inferencia LSTM

**Recomendaciones:**
1. Reentrenar XGBoost con datos reales de trades históricos
2. Implementar time-series cross-validation
3. Agregar monitoreo de drift (data + model)
4. Versionar modelos y registrar métricas en cada deploy
5. Agregar tests de integración para el pipeline ML

---

## 4.8 DevOps / Docker

**Estado:** Baja

**Fortalezas:**
- Docker Compose funcional con 3 servicios
- Multi-stage build para frontend (build en Node, serve en Nginx)
- Redis con volumen persistente
- `restart: unless-stopped` en todos los servicios

**Debilidades:**
- **Sin CI/CD** — no hay GitHub Actions, Jenkins, GitLab CI
- **Sin healthchecks** en Docker Compose
- Sin variables de entorno para backend (solo REDIS_HOST y REDIS_PORT)
- Sin secrets management
- Sin `.dockerignore` verificado
- Sin límites de recursos (memoria/CPU) en containers
- Sin redes personalizadas en Docker Compose
- Build de backend instala dependencias cada vez (sin cacheo de capas)
- `pip install --no-cache-dir` sin `--no-deps` verificado

**Recomendaciones:**
1. Crear GitHub Actions workflow con test, lint, build
2. Agregar healthchecks a todos los servicios
3. Inyectar variables de entorno desde `.env` en docker-compose
4. Agregar resource limits a containers
5. Optimizar Dockerfile con cacheo de capas

---

## 4.9 Calidad y Testing

**Estado:** Baja

**Fortalezas:**
- 33 tests unitarios backend (12 scoring + 21 signal_evaluation)
- Todos los tests existentes pasan (33/33)
- ESLint configurado en frontend
- Herramientas de calidad declaradas en `pyproject.toml` (black, isort, mypy, pytest)

**Debilidades:**
- **0 tests de frontend**
- **0 tests de integración HTTP**
- Sin tests end-to-end (E2E)
- Sin cobertura de código medida
- Sin type checking automatizado (mypy declarado pero sin ejecución en CI)
- Sin formateo automatizado (black/isort declarados pero sin CI)
- ~13 scripts de test/debug sueltos en `backend/` sin integrar en suite formal
- Sin tests de performance o carga

**Recomendaciones:**
1. Agregar tests de integración HTTP con `httpx.AsyncClient` + `pytest-asyncio`
2. Agregar Vitest + @testing-library/react para frontend
3. Configurar coverage con `pytest-cov`
4. Ejecutar mypy, black, isort en CI
5. Consolidar scripts de test sueltos en la suite formal

---

## 4.10 Performance

**Estado:** Media

**Fortalezas:**
- Redis como capa de caché para datos de mercado
- Parquet como formato eficiente para datos históricos
- LSTM inference en CPU optimizada para single-sample
- Snapshot JSON como respaldo de caché
- Rate limiting en descargas de yfinance

**Debilidades:**
- Operaciones bloqueantes en event loop de FastAPI
- `yf.download` es síncrono y bloqueante
- Polling del frontend cada N segundos en lugar de WebSocket
- Sin lazy loading ni code splitting en frontend
- Sin compresión de respuestas HTTP (gzip/brotli)
- Sin límites de payload en endpoints

**Recomendaciones:**
1. Mover operaciones bloqueantes a `run_in_executor()` o background tasks
2. Implementar WebSocket para datos en tiempo real
3. Agregar compresión gzip en FastAPI y Nginx
4. Configurar límites de payload

---

## 4.11 Operación y Mantenibilidad

**Estado:** Media

**Fortalezas:**
- Documentación operativa en `MANUAL_ARRANQUE.md`
- Documentación de sprints en `docs/sprints/`
- QA security report disponible
- Scripts de utilidad (cambio de contraseña, check de DB)
- `.env.example` para configuración

**Debilidades:**
- README desactualizado (menciona módulos inexistentes)
- Sin logging estructurado (JSON)
- Sin health endpoint (`/health` o `/api/health`)
- Sin métricas de aplicación (Prometheus/Grafana)
- Sin estrategia de backup de datos
- Scripts de test sueltos sin documentar
- Sin guía de troubleshooting

**Recomendaciones:**
1. Actualizar README con arquitectura real
2. Agregar health endpoint
3. Implementar logging estructurado
4. Agregar métricas de aplicación
5. Documentar guía de troubleshooting

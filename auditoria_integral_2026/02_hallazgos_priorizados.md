# 3. Hallazgos Priorizados

---

## H-001: Deriva arquitectónica — Dos backends divergentes

- **ID:** H-001
- **Severidad:** Crítica
- **Categoría:** Arquitectura
- **Hallazgo:** Confirmado

**Evidencia:**
- [server.py](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/backend/server.py) expone rutas en `/api/*` y es el entrypoint real en Docker
- [main.py](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/backend/app/main.py#L7-L24) expone rutas en `/api/v1/*` y es el entrypoint documentado en README
- [Dockerfile](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/backend/Dockerfile#L21-L22) arranca `uvicorn server:app`, no `app.main:app`
- [README.md](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/README.md#L42-L44) instruye `uvicorn app.main:app --reload`

**Explicación:** El proyecto mantiene dos aplicaciones FastAPI con distintos prefijos de ruta, distintos routers y probablemente distintas dependencias. Docker usa `server.py`, pero el README y desarrollo local usan `app/main.py`. Esto genera confusión sobre cuál es el backend canónico y riesgo de que cambios en uno no se reflejen en el otro.

**Impacto:** Endpoints inconsistentes entre entornos, bugs por divergencia de implementación, confusión operativa, riesgo de deploy incorrecto.

**Escenario de riesgo:** Un desarrollador agrega un endpoint en `app/main.py`, prueba localmente, pero en Docker el endpoint no existe porque `server.py` no lo incluye.

**Recomendación concreta:** Unificar en un solo entrypoint. La opción más segura es consolidar todo en `server.py` (el que ya usa Docker) y eliminar `app/main.py` como entrypoint independiente, o migrar `server.py` para que sea un router dentro de `app/main.py`.

**Esfuerzo estimado:** Medio
**Prioridad:** Inmediata

---

## H-002: JWT secret hardcodeado con fallback inseguro

- **ID:** H-002
- **Severidad:** Crítica
- **Categoría:** Seguridad
- **Hallazgo:** Confirmado

**Evidencia:**
- [security.py:L7](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/backend/app/core/security.py#L7): `SECRET_KEY = os.getenv("JWT_SECRET_KEY", "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")`
- [.env.example](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/backend/.env.example#L1-L26) no incluye `JWT_SECRET_KEY`
- [docker-compose.yml](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/docker-compose.yml#L12-L23) no inyecta `JWT_SECRET_KEY`

**Explicación:** Si `JWT_SECRET_KEY` no se configura como variable de entorno, el sistema usa un valor hardcodeado visible en el repositorio. Cualquier persona con acceso al código fuente puede firmar tokens JWT válidos y autenticarse como cualquier usuario.

**Impacto:** Compromiso total del sistema de autenticación. Un atacante puede generar tokens para cualquier cuenta, incluyendo administradores.

**Escenario de riesgo:** El deploy de producción omite configurar `JWT_SECRET_KEY`. Un ex-empleado o alguien que clone el repo puede generar tokens válidos contra la instancia productiva.

**Recomendación concreta:**
1. Eliminar el valor por defecto. Lanzar excepción si `JWT_SECRET_KEY` no está configurada.
2. Agregar `JWT_SECRET_KEY` a `.env.example` (sin valor real).
3. Inyectar `JWT_SECRET_KEY` en `docker-compose.yml` vía secrets o variables de entorno.
4. Rotar el secreto actual inmediatamente.

**Esfuerzo estimado:** Bajo
**Prioridad:** Inmediata

---

## H-003: Modelo XGBoost entrenado con datos sintéticos

- **ID:** H-003
- **Severidad:** Crítica
- **Categoría:** ML
- **Hallazgo:** Confirmado

**Evidencia:**
- [train_xgboost.py:L21-L48](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/backend/scripts/train_xgboost.py#L21-L48): `generate_synthetic_dataset()` genera features con `np.random` y labels con una función logística artificial
- [train_xgboost.py:L27](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/backend/scripts/train_xgboost.py#L27): `np.random.seed(42)` — reproducible pero sintético
- [scoring.py:L10-L16](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/backend/app/services/scoring.py#L10-L16): El modelo se carga y usa en producción
- [scoring.py:L18-L38](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/backend/app/services/scoring.py#L18-L38): `compute_ml_score()` usa el modelo para inferencia real

**Explicación:** El scoring de machine learning que alimenta las señales de trading se basa en un modelo XGBoost entrenado con datos generados aleatoriamente mediante `np.random`. Las predicciones no tienen correlación con el comportamiento real del mercado.

**Impacto:** Las señales de compra/venta generadas por el componente ML no tienen validez estadística. Los usuarios están tomando decisiones basadas en ruido aleatorio.

**Escenario de riesgo:** Un usuario confía en una señal con score alto generada por el modelo sintético y realiza una operación real con pérdidas.

**Recomendación concreta:**
1. Reentrenar XGBoost con datos reales del historial de trades (`trades_history.db`).
2. Implementar validación cruzada temporal (time-series split) para evitar data leakage.
3. Versionar el modelo y registrar métricas en cada reentrenamiento.
4. Agregar un flag `model_trained_on_real_data` para evitar despliegues con datos sintéticos.

**Esfuerzo estimado:** Alto
**Prioridad:** Inmediata

---

## H-004: CORS `*` con `allow_credentials=True`

- **ID:** H-004
- **Severidad:** Alta
- **Categoría:** Seguridad
- **Hallazgo:** Confirmado

**Evidencia:**
- [server.py:L998-L1004](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/backend/server.py#L998-L1004): `app.add_middleware(CORSMiddleware, allow_origins=["*"], ..., allow_credentials=True)`

**Explicación:** La combinación de `allow_origins=["*"]` con `allow_credentials=True` es explícitamente rechazada por los navegadores modernos (la especificación CORS lo prohíbe). Además, `*` permite que cualquier origen haga requests con credenciales, exponiendo datos de usuario a sitios maliciosos.

**Impacto:** Vulnerabilidad cross-origin. En la práctica, el navegador puede bloquear requests legítimos, o en navegadores más antiguos, permitir fuga de datos.

**Recomendación concreta:**
1. Especificar orígenes explícitos: `["http://localhost:5173", "http://localhost:3000"]` para dev, el dominio real para producción.
2. Si se requiere `allow_credentials=True`, nunca usar `"*"`.

**Esfuerzo estimado:** Bajo
**Prioridad:** Próximo sprint

---

## H-005: Ausencia total de CI/CD

- **ID:** H-005
- **Severidad:** Alta
- **Categoría:** DevOps
- **Hallazgo:** Confirmado

**Evidencia:**
- No existe `.github/workflows/`, `Jenkinsfile`, `.gitlab-ci.yml` ni `Makefile`
- [.github/](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/.github/copilot-instructions.md) solo contiene instrucciones para Copilot
- No hay scripts de build/test/lint unificados

**Explicación:** No existe ningún pipeline automatizado que ejecute tests, linting, type checking, build o security scanning. Cada cambio debe verificarse manualmente.

**Impacto:** Riesgo alto de regresiones no detectadas. Sin barreras automatizadas, bugs pueden llegar a producción sin ser detectados.

**Recomendación concreta:**
1. Crear GitHub Actions workflow que ejecute: pytest, mypy, eslint, npm build.
2. Agregar step de security scanning (bandit para Python, npm audit para frontend).
3. Configurar el pipeline para ejecutarse en cada PR y push a main.

**Esfuerzo estimado:** Medio
**Prioridad:** Próximo sprint

---

## H-006: URLs hardcodeadas en frontend (sin variables de entorno)

- **ID:** H-006
- **Severidad:** Alta
- **Categoría:** Frontend
- **Hallazgo:** Confirmado

**Evidencia:**
- [Login.tsx:L25-L31](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/frontend-v2/src/pages/Login.tsx#L25-L31): `const API_BASE = "http://localhost:8002/api"`
- [useMarketData.ts:L10-L12](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/frontend-v2/src/hooks/useMarketData.ts#L10-L12): construye `API_BASE` con `window.location.hostname` pero fuerza `http://` y puerto `8002`
- [PaperTrading.tsx:L9-L10](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/frontend-v2/src/tabs/PaperTrading.tsx#L9-L10): `const API_BASE = "http://localhost:8002/api"`
- [vite.config.ts](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/frontend-v2/vite.config.ts#L1-L7): sin proxy configurado

**Explicación:** Las URLs de la API están hardcodeadas en al menos 4 archivos distintos. El login siempre apunta a `localhost:8002`, lo que rompe en entornos Docker, staging o producción. No se usa `import.meta.env.VITE_API_BASE` ni proxy de Vite.

**Impacto:** Imposibilidad de desplegar en entornos que no sean `localhost:8002` sin recompilar. Cada cambio de entorno requiere modificar código fuente.

**Recomendación concreta:**
1. Definir `VITE_API_BASE` en variables de entorno de Vite.
2. Centralizar todas las llamadas HTTP en un solo módulo/cliente.
3. Configurar proxy de Vite para desarrollo local.
4. Usar `window.location.origin` o ruta relativa en producción (mismo dominio con Nginx reverse proxy).

**Esfuerzo estimado:** Medio
**Prioridad:** Próximo sprint

---

## H-007: Sin tests de frontend

- **ID:** H-007
- **Severidad:** Alta
- **Categoría:** Testing
- **Hallazgo:** Confirmado

**Evidencia:**
- [package.json](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/frontend-v2/package.json#L6-L31): no incluye vitest, jest, @testing-library/react, playwright ni cypress
- No existe script `test` en package.json
- No hay archivos `*.test.tsx` o `*.spec.tsx` en `frontend-v2/src/`

**Impacto:** Cualquier cambio en componentes, hooks, contextos o páginas no tiene validación automatizada. Riesgo alto de regresiones visuales y funcionales.

**Recomendación concreta:**
1. Instalar Vitest + @testing-library/react.
2. Crear tests para: AuthContext (login/logout), ProtectedRoute, Login page, PaperTrading flujo básico.
3. Agregar `npm run test` al pipeline CI.

**Esfuerzo estimado:** Medio
**Prioridad:** Próximo sprint

---

## H-008: Token JWT en localStorage (vulnerable a XSS)

- **ID:** H-008
- **Severidad:** Alta
- **Categoría:** Seguridad
- **Hallazgo:** Confirmado

**Evidencia:**
- [AuthContext.tsx:L12-L29](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/frontend-v2/src/context/AuthContext.tsx#L12-L29): `localStorage.getItem("token")`, `localStorage.setItem("token", token)`
- Token con TTL de 7 días ([security.py:L9](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/backend/app/core/security.py#L9))

**Explicación:** El token JWT se almacena en `localStorage`, accesible desde cualquier script JavaScript. Si existe una vulnerabilidad XSS (ej. dependencia comprometida), el token puede ser robado. Además, no hay refresh token ni mecanismo de invalidación.

**Impacto:** Robo de sesión, suplantación de identidad.

**Recomendación concreta:**
1. Migrar a cookies HttpOnly + Secure + SameSite=Strict para el token.
2. Reducir TTL del token a 15-60 minutos.
3. Implementar refresh token con rotación.

**Esfuerzo estimado:** Medio
**Prioridad:** Próximo sprint

---

## H-009: Sin tests de integración HTTP

- **ID:** H-009
- **Severidad:** Alta
- **Categoría:** Testing
- **Hallazgo:** Confirmado

**Evidencia:**
- [qa_security_report.md:L56-L60](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/docs/qa_security_report.md#L56-L59): recomienda "Agregar tests de integración para endpoints HTTP usando `httpx.AsyncClient`"
- Solo existen tests unitarios para `scoring.py` y `signal_evaluation.py`
- No hay tests para: endpoints de auth, paper trading, screener, backtesting, analytics

**Impacto:** Los endpoints HTTP no tienen validación automatizada de contratos, respuestas, estados HTTP o manejo de errores.

**Recomendación concreta:**
1. Crear `backend/tests/test_api/` con tests usando `httpx.AsyncClient` + `pytest-asyncio`.
2. Priorizar: `test_auth.py`, `test_paper_trading.py`, `test_screener.py`.
3. Usar TestClient de FastAPI para tests rápidos sin levantar servidor.

**Esfuerzo estimado:** Medio
**Prioridad:** Próximo sprint

---

## H-010: Inconsistencia de configuración JWT entre `security.py` y `config.py`

- **ID:** H-010
- **Severidad:** Media
- **Categoría:** Seguridad
- **Hallazgo:** Confirmado

**Evidencia:**
- [security.py:L7](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/backend/app/core/security.py#L7): usa `JWT_SECRET_KEY` con fallback hardcodeado
- [config.py:L22](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/backend/app/config.py#L22): define `SECRET_KEY` con fallback diferente
- `security.py` no lee de `config.py`; son dos fuentes de verdad separadas

**Explicación:** Existen dos claves secretas configuradas en lugares distintos con nombres distintos. `server.py` importa `security.py`, mientras que `app/main.py` probablemente usa `config.py`. Si alguien cambia una pero no la otra, se generan tokens que no pueden verificarse.

**Impacto:** Posible inconsistencia de tokens entre entornos o migraciones. Confusión sobre cuál es la clave canónica.

**Recomendación concreta:**
1. Unificar en una sola fuente de configuración.
2. `security.py` debe leer de `config.py` o de una instancia de `Settings`.
3. Eliminar uno de los dos fallbacks.

**Esfuerzo estimado:** Bajo
**Prioridad:** Próximo sprint

---

## H-011: Bug de contrato en Analytics (URL mal formada)

- **ID:** H-011
- **Severidad:** Media
- **Categoría:** Frontend
- **Hallazgo:** Confirmado

**Evidencia:**
- [Analytics.tsx:L20-L25](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/frontend-v2/src/tabs/Analytics.tsx#L20-L25): `fetch(\`\${API_BASE}/analytics&_t=...\`)` — falta `?` antes del query param

**Explicación:** La URL generada es `/api/analytics&_t=...` en lugar de `/api/analytics?_t=...`. Esto puede causar que el parámetro `_t` no sea interpretado como query param, rompiendo el cache-busting.

**Impacto:** Posible fallo en la carga de analytics, datos stale servidos desde caché del navegador.

**Recomendación concreta:** Corregir a `fetch(\`\${API_BASE}/analytics?_t=...\`)`.

**Esfuerzo estimado:** Bajo
**Prioridad:** Próximo sprint

---

## H-012: Posible desalineación de contrato Signal Lab

- **ID:** H-012
- **Severidad:** Media
- **Categoría:** Frontend/Backend
- **Hallazgo:** Riesgo probable

**Evidencia:**
- [SignalLab.tsx:L35-L39](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/frontend-v2/src/tabs/SignalLab.tsx#L35-L39): espera `data.signals` y `data.universe`
- [server.py:L1328-L1355](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/backend/server.py#L1328-L1355): el endpoint envuelve la respuesta en `{ cached, market, data }`

**Explicación:** El frontend espera acceder a `data.signals` directamente, pero la respuesta real del backend tiene una capa adicional de envoltura. Si no hay desempaquetado en el frontend, `data.signals` será `undefined`.

**Impacto:** Signal Lab puede mostrar datos vacíos o incorrectos sin error visible.

**Recomendación concreta:** Verificar y alinear el contrato de respuesta. Agregar test de integración para este endpoint.

**Esfuerzo estimado:** Bajo
**Prioridad:** Próximo sprint

---

## H-013: WebSocket declarado pero no implementado

- **ID:** H-013
- **Severidad:** Media
- **Categoría:** Backend
- **Hallazgo:** Confirmado

**Evidencia:**
- [useMarketData.ts:L54-L57](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/frontend-v2/src/hooks/useMarketData.ts#L54-L57): `// TODO: implementar WebSocket`
- [useMarketData.ts:L11-L12](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/frontend-v2/src/hooks/useMarketData.ts#L11-L12): `WS_URL` apunta a `ws://HOST:8080/ws/market`
- No hay endpoint WebSocket en `server.py` ni servicio en `docker-compose.yml`

**Impacto:** El frontend hace polling cada N segundos en lugar de recibir actualizaciones en tiempo real. Latencia innecesaria y carga adicional en el backend.

**Recomendación concreta:** Implementar WebSocket en backend o eliminar el código muerto del frontend para evitar confusión.

**Esfuerzo estimado:** Medio
**Prioridad:** Backlog

---

## H-014: Operaciones bloqueantes en endpoints síncronos

- **ID:** H-014
- **Severidad:** Media
- **Categoría:** Performance
- **Hallazgo:** Confirmado

**Evidencia:**
- [server.py:L1328-L1384](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/backend/server.py#L1328-L1384): `evaluate_signals()` y `run_strategy_optimization()` se ejecutan sincrónicamente en el endpoint
- `yf.download` en [server.py:L568-L570](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/backend/server.py#L568-L570) es bloqueante

**Explicación:** FastAPI es asíncrono, pero varias operaciones pesadas (descarga de datos, evaluación de señales, optimización) se ejecutan de forma síncrona, bloqueando el event loop.

**Impacto:** Bajo carga concurrente, las requests se encolan y los tiempos de respuesta se degradan.

**Recomendación concreta:**
1. Ejecutar operaciones bloqueantes con `run_in_executor()` o `BackgroundTasks`.
2. Mover `evaluate_signals()` y `run_strategy_optimization()` a tareas en background con Redis como cola.

**Esfuerzo estimado:** Medio
**Prioridad:** Backlog

---

## H-015: Doble persistencia SQLite (SQLAlchemy + sqlite3 directo)

- **ID:** H-015
- **Severidad:** Media
- **Categoría:** Datos
- **Hallazgo:** Confirmado

**Evidencia:**
- [database.py:L5-L12](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/backend/app/db/database.py#L5-L12): SQLAlchemy con `iosef_finance.db`
- [persistence.py:L7](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/backend/app/services/persistence.py#L7): `sqlite3.connect()` directo a `trades_history.db`

**Explicación:** El sistema usa dos bases de datos SQLite separadas con dos estrategias de acceso distintas (ORM vs SQL directo). Esto complica backups, migraciones, transacciones cross-db y consistencia.

**Impacto:** Riesgo de inconsistencia entre datos de usuario/paper trading y datos de trades históricos. Imposibilidad de hacer joins entre ambas fuentes.

**Recomendación concreta:** Unificar en una sola base de datos SQLite con SQLAlchemy, o migrar a PostgreSQL para producción.

**Esfuerzo estimado:** Alto
**Prioridad:** Backlog

---

## H-016: README desactualizado — Módulos inexistentes

- **ID:** H-016
- **Severidad:** Baja
- **Categoría:** Documentación
- **Hallazgo:** Confirmado

**Evidencia:**
- [README.md:L9-L15](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/README.md#L9-L15): menciona `frontend/` y `realtime/` como módulos, pero no existen
- [README.md:L41-L43](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/README.md#L41-L44): instruye `fastapi dev app/main.py`, pero Docker ejecuta `uvicorn server:app`

**Impacto:** Confusión para nuevos desarrolladores. Instrucciones de arranque incorrectas.

**Recomendación concreta:** Actualizar README con la estructura real del proyecto y el entrypoint correcto.

**Esfuerzo estimado:** Bajo
**Prioridad:** Backlog

---

## H-017: Archivos .db en raíz del backend sin protección en .gitignore

- **ID:** H-017
- **Severidad:** Baja
- **Categoría:** Configuración
- **Hallazgo:** Confirmado

**Evidencia:**
- [.gitignore:L59-L68](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/.gitignore#L59-L68): excluye `data/*.db` pero no `backend/app.db` ni `backend/iosef_finance.db`
- Existen `backend/app.db`, `backend/iosef_finance.db`, `iosef_finance.db`, `check_db.py` en la raíz

**Impacto:** Riesgo de commit accidental de bases de datos con datos sensibles de usuarios.

**Recomendación concreta:** Agregar `backend/*.db` y `*.db` (con exclusiones para data/) al `.gitignore`.

**Esfuerzo estimado:** Bajo
**Prioridad:** Backlog

---

## H-018: Estilos inline y tipos `any` en frontend

- **ID:** H-018
- **Severidad:** Baja
- **Categoría:** Frontend
- **Hallazgo:** Confirmado

**Evidencia:**
- [Login.tsx:L95-L196](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/frontend-v2/src/pages/Login.tsx#L95-L196): estilos inline extensos
- [TickerModal.tsx:L37-L39](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/frontend-v2/src/components/TickerModal.tsx#L37-L39): uso de `any`
- [PaperTrading.tsx:L342-L374](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/frontend-v2/src/tabs/PaperTrading.tsx#L342-L374): estilos inline en JSX

**Impacto:** Mantenibilidad reducida, inconsistencia visual, pérdida de type safety.

**Recomendación concreta:** Migrar a CSS Modules o styled-components. Eliminar tipos `any`.

**Esfuerzo estimado:** Medio
**Prioridad:** Backlog

---

## H-019: Sin healthchecks en Docker Compose

- **ID:** H-019
- **Severidad:** Baja
- **Categoría:** DevOps
- **Hallazgo:** Confirmado

**Evidencia:**
- [docker-compose.yml](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/docker-compose.yml#L1-L36): ningún servicio define `healthcheck`
- `depends_on` solo garantiza inicio, no que el servicio esté healthy

**Impacto:** Docker puede enviar tráfico a un backend que aún está inicializando. Redis puede no estar listo cuando el backend intenta conectarse.

**Recomendación concreta:** Agregar healthchecks para Redis (`redis-cli ping`), backend (`curl /api/health`) y frontend (`curl localhost:80`).

**Esfuerzo estimado:** Bajo
**Prioridad:** Backlog

---

## H-020: Sin variables de entorno en docker-compose para el backend

- **ID:** H-020
- **Severidad:** Media
- **Categoría:** DevOps
- **Hallazgo:** Confirmado

**Evidencia:**
- [docker-compose.yml:L18-L20](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/docker-compose.yml#L18-L20): solo define `REDIS_HOST` y `REDIS_PORT`
- No se inyectan: `JWT_SECRET_KEY`, `DATABASE_URL`, `DEEPSEEK_API_KEY`, variables de CORS

**Impacto:** El backend en Docker usa valores por defecto (incluyendo el JWT secret hardcodeado).

**Recomendación concreta:** Agregar todas las variables de entorno necesarias al servicio backend en `docker-compose.yml`, idealmente desde un archivo `.env`.

**Esfuerzo estimado:** Bajo
**Prioridad:** Próximo sprint

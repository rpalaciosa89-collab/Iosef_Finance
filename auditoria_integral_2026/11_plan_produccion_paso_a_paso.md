# Plan de Producción Paso a Paso — Iosef Finance

**Basado en:** Auditoría Integral 2026 (auditoria_integral_2026/)
**Fecha:** 2026-06-09
**Metodología:** PDCA por Olas con Verificación Integrada

---

## PARTE 0 — METODOLOGÍA

### 0.1 Metodología Seleccionada

**PDCA por Olas con Entrega Incremental Continua**

Se eligió esta combinación por tres razones:

| Criterio | PDCA por Olas |
|---|---|
| Cambios pequeños y verificables | Cada paso mide <50 líneas, cada paso se verifica |
| Mejora continua sin regresiones | Cada ola incluye checkpoint de regresión completa |
| Documentación viva | El `CHANGELOG` se actualiza en cada paso, no al final |
| Priorización por valor | Las olas siguen la matriz valor/esfuerzo de la auditoría |
| Rollback seguro | Cada paso es atómico y reversible |
| Ejecución por agentes | Cada ola se puede delegar a un agente con su prompt |

### 0.2 Principios de Ejecución

1. **Un paso = un archivo tocado (idealmente).** Si tocas más de un archivo, documenta por qué.
2. **Verificar antes de avanzar.** Ningún paso se cierra sin CHECK explícito.
3. **Si algo se rompe, se repara en el mismo paso.** No se acumula deuda.
4. **Documentación en el momento.** El `CHANGELOG.md` de la ola se actualiza al cerrar cada paso.
5. **Commits atómicos.** Un commit por paso con mensaje `[Ola X.Y] descripción`.
6. **Nunca desplegar sin tests verdes.** A partir de la Ola 3, CI debe pasar antes de continuar.

### 0.3 Estructura de una Ola PDCA

```
OLA N: [Nombre descriptivo]
├── PLAN   → Definir qué pasos se ejecutan y qué hallazgos se resuelven
├── DO     → Ejecutar cada paso atómico
├── CHECK  → Verificación cruzada: tests, build, funcionalidad
├── ACT    → Documentar, commitear, ajustar plan de siguientes olas
└── DOC    → Actualizar CHANGELOG de la ola
```

### 0.4 Formato de Cada Paso

```markdown
## Paso X.Y: [Título]
- Hallazgo: H-XXX
- Archivos: [lista]
- Esfuerzo: Bajo/Medio/Alto (~minutos)
- Acción: [qué se hace exactamente]
- CHECK: [cómo verifico que funcionó]
- Resultado esperado: [qué debo ver]
```

### 0.5 Visión General de las 6 Olas

| Ola | Nombre | Hallazgos | Pasos | Esfuerzo | Valor |
|---|---|---|---|---|---|
| Ola 1 | Seguridad Inmediata | H-002, H-004, H-010, H-017, H-020 | 7 pasos | ~4h | Crítico |
| Ola 2 | Higiene Operativa | H-019, H-011, H-016, QA ticker regex | 6 pasos | ~3h | Alto |
| Ola 3 | Base de CI/CD + Testing | H-005, H-009, H-007 | 7 pasos | ~8h | Alto |
| Ola 4 | Consolidación Arquitectura | H-001, H-006, H-012 | 8 pasos | ~8h | Crítico |
| Ola 5 | Autenticación Robusta | H-008, H-010 (residual) | 5 pasos | ~6h | Alto |
| Ola 6 | ML y Performance | H-003, H-013, H-014, H-015 | 10 pasos | ~12h | Crítico |

---

## OLA 1 — SEGURIDAD INMEDIATA

**Objetivo:** Eliminar los 3 vectores de ataque más graves y preparar el sistema de configuración para que sea seguro por defecto.

**Hallazgos que resuelve:** H-002, H-004, H-010, H-017, H-020
**Duración estimada:** ~4 horas
**Valor:** Crítico — Sin esto, cualquier otro cambio es inseguro.

### Paso 1.0: Crear backup del estado actual
- **Hallazgo:** Preparación
- **Archivos:** `auditoria_integral_2026/ola1/backup_antes.md`
- **Esfuerzo:** Bajo (~5 min)
- **Acción:** Documentar el estado actual de `security.py`, `server.py` (bloque CORS), `config.py`, `.gitignore`.
- **CHECK:** Confirmar que los archivos existen y son legibles.
- **Resultado esperado:** Backup documental listo para rollback manual.

### Paso 1.1: Eliminar JWT secret hardcodeado (H-002)
- **Hallazgo:** H-002 (Crítico)
- **Archivos:** `backend/app/core/security.py`
- **Esfuerzo:** Bajo (~10 min)
- **Acción:**
  ```python
  # ANTES (L7)
  SECRET_KEY = os.getenv("JWT_SECRET_KEY", "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")

  # DESPUÉS
  SECRET_KEY = os.getenv("JWT_SECRET_KEY")
  if not SECRET_KEY:
      raise RuntimeError("JWT_SECRET_KEY environment variable is required")
  ```
- **CHECK:**
  1. Iniciar backend SIN `JWT_SECRET_KEY` → Debe lanzar `RuntimeError` y no arrancar.
  2. Iniciar backend CON `JWT_SECRET_KEY` → Debe arrancar normalmente.
  3. Login → Debe generar token válido.
- **Resultado esperado:** Sin variable de entorno, el backend rechaza arrancar. Con ella, funciona normalmente.

### Paso 1.2: Unificar configuración de secretos (H-010)
- **Hallazgo:** H-010 (Media)
- **Archivos:** `backend/app/core/security.py`, `backend/app/config.py`
- **Esfuerzo:** Bajo (~15 min)
- **Acción:**
  1. En `config.py`: renombrar `SECRET_KEY` a `JWT_SECRET_KEY` y quitar el fallback inseguro.
  2. En `security.py`: importar de `config.py`:
     ```python
     from app.config import settings
     SECRET_KEY = settings.JWT_SECRET_KEY
     ```
  3. Eliminar la lectura directa de `os.getenv` en `security.py`.
- **CHECK:**
  1. `config.py` tiene un solo campo `JWT_SECRET_KEY`.
  2. `security.py` no contiene `os.getenv("JWT_SECRET_KEY")`.
  3. Backend arranca con `JWT_SECRET_KEY` configurada en `.env`.
- **Resultado esperado:** Una sola fuente de verdad para el secreto JWT. Sin hardcodeos.

### Paso 1.3: Restringir CORS (H-004)
- **Hallazgo:** H-004 (Alta)
- **Archivos:** `backend/server.py`
- **Esfuerzo:** Bajo (~10 min)
- **Acción:**
  En `server.py`, buscar el bloque `app.add_middleware(CORSMiddleware, ...)` y cambiarlo:
  ```python
  # ANTES
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["*"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )

  # DESPUÉS
  import os
  cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
  cors_origins = [o.strip() for o in cors_origins_str.split(",")]

  app.add_middleware(
      CORSMiddleware,
      allow_origins=cors_origins,
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```
- **CHECK:**
  1. Frontend en `localhost:5173` → Requests exitosos.
  2. Curl desde origen no autorizado → Rechazado con error CORS.
  3. `curl -H "Origin: http://evil.com" http://localhost:8002/api/health` → Sin header CORS en respuesta.
- **Resultado esperado:** Solo los orígenes configurados pueden hacer requests con credenciales.

### Paso 1.4: Inyectar variables de entorno en docker-compose (H-020)
- **Hallazgo:** H-020 (Media), H-002 (reforzado)
- **Archivos:** `docker-compose.yml`, `backend/.env.example`
- **Esfuerzo:** Bajo (~15 min)
- **Acción:**
  1. En `docker-compose.yml`, agregar al servicio `backend`:
     ```yaml
     backend:
       environment:
         - REDIS_HOST=redis
         - REDIS_PORT=6379
         - JWT_SECRET_KEY=${JWT_SECRET_KEY}
         - CORS_ORIGINS=${CORS_ORIGINS:-http://localhost:5173,http://localhost:3000}
         - DATABASE_URL=${DATABASE_URL:-sqlite:///./iosef_finance.db}
     ```
  2. En `.env.example`, agregar:
     ```
     JWT_SECRET_KEY=generar_con_openssl_rand_hex_32
     CORS_ORIGINS=http://localhost:5173,http://localhost:3000
     ```
  3. Crear `.env` (si no existe) con valores reales generados por `openssl rand -hex 32`.
- **CHECK:**
  1. `docker-compose up` con `.env` configurado → Backend arranca.
  2. `docker-compose up` sin `JWT_SECRET_KEY` en `.env` → Backend no arranca (por Paso 1.1).
  3. Verificar con `docker-compose config` que las variables se inyectan.
- **Resultado esperado:** Docker Compose transmite todas las variables necesarias al backend.

### Paso 1.5: Proteger archivos .db en .gitignore (H-017)
- **Hallazgo:** H-017 (Baja)
- **Archivos:** `.gitignore`
- **Esfuerzo:** Bajo (~5 min)
- **Acción:** Agregar al final de `.gitignore`:
  ```
  # Database files (do not commit)
  backend/*.db
  *.db
  !data/.gitkeep
  ```
- **CHECK:**
  1. `git status` → `backend/app.db`, `backend/iosef_finance.db`, `iosef_finance.db` NO aparecen como untracked.
  2. `data/.gitkeep` sigue apareciendo (si está modificado).
- **Resultado esperado:** Ningún archivo `.db` puede ser commiteado accidentalmente.

### Paso 1.6: Verificación de regresión — Ola 1 completa
- **Hallazgo:** Todos los de Ola 1
- **Archivos:** Todos los modificados
- **Esfuerzo:** Bajo (~20 min)
- **Acción:**
  1. Ejecutar suite de tests existente: `cd backend && python -m pytest tests/ -v`
  2. Iniciar backend con `.env`: `cd backend && JWT_SECRET_KEY=test uvicorn server:app --port 8002`
  3. Iniciar frontend: `cd frontend-v2 && npm run dev`
  4. Login manual en `http://localhost:5173/login`
  5. Verificar que screener, paper trading y analytics cargan datos.
- **CHECK:**
  1. 33/33 tests pasan.
  2. Backend arranca sin errores.
  3. Frontend hace login exitoso.
  4. Funcionalidad core intacta.
- **Resultado esperado:** Todo funciona exactamente igual que antes, pero seguro.

### Paso 1.7: Documentar Ola 1
- **Archivos:** `auditoria_integral_2026/ola1/CHANGELOG_ola1.md`
- **Esfuerzo:** Bajo (~10 min)
- **Acción:** Documentar los cambios realizados, resultados de verificaciones, y ajustes al plan de Ola 2.
- **CHECK:** El documento existe y describe cada paso con su resultado.

---

## OLA 2 — HIGIENE OPERATIVA

**Objetivo:** Agregar health checks, corregir bugs visibles, validar inputs y actualizar documentación.

**Hallazgos que resuelve:** H-019, H-011, H-016, QA ticker regex
**Duración estimada:** ~3 horas
**Valor:** Alto — Establece las bases de operabilidad y debugging.

### Paso 2.0: Crear backup del estado post-Ola-1
- **Esfuerzo:** Bajo (~5 min)
- **Acción:** Documentar estado en `auditoria_integral_2026/ola2/backup_antes.md`.

### Paso 2.1: Agregar health endpoint al backend (H-019)
- **Hallazgo:** H-019 (Baja)
- **Archivos:** `backend/server.py`
- **Esfuerzo:** Bajo (~10 min)
- **Acción:** Agregar ANTES de `if __name__ == "__main__"`:
  ```python
  @app.get("/api/health")
  def health_check():
      return {"status": "ok", "service": "iosef-backend"}
  ```
- **CHECK:**
  1. `curl http://localhost:8002/api/health` → `{"status": "ok", "service": "iosef-backend"}`.
  2. Status code 200.
- **Resultado esperado:** Health endpoint funcional y respondiendo en <100ms.

### Paso 2.2: Corregir bug de URL en Analytics (H-011)
- **Hallazgo:** H-011 (Media)
- **Archivos:** `frontend-v2/src/tabs/Analytics.tsx`
- **Esfuerzo:** Bajo (~5 min)
- **Acción:** Cambiar `&_t=` por `?_t=` en la línea de fetch.
- **CHECK:**
  1. Abrir Analytics en el frontend.
  2. Verificar en Network tab que la URL es `/api/analytics?_t=...`.
  3. Verificar que los datos de analytics cargan correctamente.
- **Resultado esperado:** URL bien formada, cache-busting funciona.

### Paso 2.3: Agregar validación regex para parámetros ticker
- **Hallazgo:** QA Report (no catalogado como H-XXX)
- **Archivos:** `backend/server.py` (rutas que aceptan ticker)
- **Esfuerzo:** Bajo (~15 min)
- **Acción:**
  1. Crear validador en `backend/app/core/validators.py`:
     ```python
     import re
     TICKER_PATTERN = re.compile(r'^[A-Za-z0-9\.\-]{1,10}$')
     
     def validate_ticker(ticker: str) -> str:
         if not TICKER_PATTERN.match(ticker):
             raise ValueError(f"Invalid ticker format: {ticker}")
         return ticker.upper()
     ```
  2. Usar en rutas relevantes de `server.py` que reciben `ticker` como path parameter.
- **CHECK:**
  1. `curl http://localhost:8002/api/ticker/AAPL` → 200.
  2. `curl http://localhost:8002/api/ticker/AAPL;rm -rf /` → 422 o 400.
  3. `curl http://localhost:8002/api/ticker/../../` → 422 o 400.
- **Resultado esperado:** Tickers válidos pasan, inyecciones son rechazadas.

### Paso 2.4: Agregar healthchecks en Docker Compose (H-019)
- **Hallazgo:** H-019 (Baja)
- **Archivos:** `docker-compose.yml`
- **Esfuerzo:** Bajo (~10 min)
- **Acción:** Agregar bloques `healthcheck` a cada servicio:
  ```yaml
  redis:
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  backend:
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8002/api/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s

  frontend:
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:80"]
      interval: 30s
      timeout: 5s
      retries: 3
  ```
- **CHECK:**
  1. `docker-compose up -d` → `docker-compose ps` muestra todos como healthy.
  2. Matar Redis → backend no arranca (dependencia).
  3. `docker-compose ps` muestra unhealthy para Redis.
- **Resultado esperado:** Docker monitorea la salud de cada servicio.

### Paso 2.5: Actualizar README (H-016)
- **Hallazgo:** H-016 (Baja)
- **Archivos:** `README.md`
- **Esfuerzo:** Bajo (~15 min)
- **Acción:**
  1. Reemplazar la sección "Estructura del Proyecto" con la estructura real.
  2. Actualizar instrucciones de arranque para reflejar `server.py` como entrypoint canónico.
  3. Agregar sección de "Variables de Entorno Requeridas".
- **CHECK:**
  1. Un desarrollador nuevo puede seguir el README y arrancar el proyecto.
  2. Las instrucciones coinciden con `docker-compose.yml`.
- **Resultado esperado:** Documentación precisa y útil.

### Paso 2.6: Verificación de regresión — Ola 2 completa
- **Esfuerzo:** Bajo (~15 min)
- **Acción:**
  1. Tests backend: `pytest tests/ -v` → 33/33.
  2. Health endpoint: `curl /api/health` → 200.
  3. Docker: `docker-compose up -d` → 3 servicios healthy.
  4. Frontend: login, screener, analytics, paper trading funcionan.
  5. Validación ticker: probar casos válidos e inválidos.
- **Resultado esperado:** Todo opera correctamente.

### Paso 2.7: Documentar Ola 2
- **Archivos:** `auditoria_integral_2026/ola2/CHANGELOG_ola2.md`

---

## OLA 3 — BASE DE CI/CD + TESTING

**Objetivo:** Crear pipeline automatizado y primera capa de tests de integración.

**Hallazgos que resuelve:** H-005, H-009, H-007
**Duración estimada:** ~8 horas
**Valor:** Alto — Establece la red de seguridad para todas las olas siguientes.

### Paso 3.0: Crear backup del estado post-Ola-2
- **Esfuerzo:** Bajo (~5 min)

### Paso 3.1: Crear estructura de directorios para CI
- **Hallazgo:** H-005 (Alta)
- **Archivos:** `.github/workflows/ci.yml` (nuevo)
- **Esfuerzo:** Bajo (~10 min)
- **Acción:** Crear directorio `.github/workflows/`.
- **CHECK:** `ls .github/workflows/` → el directorio existe.

### Paso 3.2: Pipeline — tests backend + lint
- **Hallazgo:** H-005 (Alta)
- **Archivos:** `.github/workflows/ci.yml`
- **Esfuerzo:** Medio (~30 min)
- **Acción:** Crear workflow con jobs:
  ```yaml
  name: CI

  on:
    push:
      branches: [main]
    pull_request:
      branches: [main]

  jobs:
    backend-tests:
      runs-on: ubuntu-latest
      defaults:
        run:
          working-directory: backend
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with:
            python-version: "3.12"
        - run: pip install -r requirements.txt
        - run: pip install pytest
        - run: JWT_SECRET_KEY=ci-test-key python -m pytest tests/ -v
  ```
- **CHECK:**
  1. Push a main → workflow se dispara.
  2. Tests pasan en CI.
  3. PR con tests rotos → CI falla y bloquea merge.

### Paso 3.3: Pipeline — build frontend + lint
- **Hallazgo:** H-005 (Alta)
- **Archivos:** `.github/workflows/ci.yml` (ampliación)
- **Esfuerzo:** Bajo (~15 min)
- **Acción:** Agregar job al workflow:
  ```yaml
  frontend-build:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend-v2
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - run: npm ci
      - run: npm run lint
      - run: npm run build
  ```
- **CHECK:**
  1. `npm run build` exitoso en CI.
  2. `npm run lint` sin errores (o con errores documentados como warnings).
- **Resultado esperado:** Frontend compila y pasa lint en cada push/PR.

### Paso 3.4: Crear tests de integración para auth (H-009)
- **Hallazgo:** H-009 (Alta)
- **Archivos:** `backend/tests/test_api/test_auth.py` (nuevo)
- **Esfuerzo:** Medio (~2h)
- **Acción:**
  1. Crear `backend/tests/test_api/__init__.py`.
  2. Crear `backend/tests/conftest.py` con fixtures de TestClient:
     ```python
     import pytest
     from fastapi.testclient import TestClient

     @pytest.fixture
     def client():
         import os
         os.environ["JWT_SECRET_KEY"] = "test-secret-for-ci"
         from server import app
         return TestClient(app)
     ```
  3. Escribir tests en `test_auth.py`:
     - `test_register_user` → 200, retorna token
     - `test_register_duplicate_user` → 409 o 400
     - `test_login_valid` → 200, retorna access_token
     - `test_login_invalid_password` → 401
     - `test_protected_endpoint_no_token` → 401
     - `test_protected_endpoint_valid_token` → 200
     - `test_token_expiry` → 401 tras expiración (avanzado)
- **CHECK:**
  1. `pytest tests/test_api/test_auth.py -v` → todos pasan.
  2. CI ejecuta estos tests automáticamente.
- **Resultado esperado:** Cobertura de integración para el flujo completo de auth.

### Paso 3.5: Crear tests de integración para paper trading (H-009)
- **Hallazgo:** H-009 (Alta)
- **Archivos:** `backend/tests/test_api/test_paper_trading.py` (nuevo)
- **Esfuerzo:** Medio (~2h)
- **Acción:** Escribir tests:
  - `test_create_account` → 200, retorna account_id
  - `test_get_account` → 200, retorna saldo y posiciones
  - `test_execute_trade_buy` → 200, posición creada
  - `test_execute_trade_sell` → 200, posición cerrada
  - `test_execute_trade_insufficient_funds` → 400
  - `test_execute_trade_unauthorized` → 401
  - `test_refresh_positions` → 200, precios actualizados
- **CHECK:**
  1. `pytest tests/test_api/test_paper_trading.py -v` → todos pasan.
  2. CI ejecuta estos tests automáticamente.
- **Resultado esperado:** Cobertura de integración para el core de negocio.

### Paso 3.6: Instalar Vitest y crear primeros tests frontend (H-007)
- **Hallazgo:** H-007 (Alta)
- **Archivos:** `frontend-v2/package.json`, `frontend-v2/src/__tests__/` (nuevo)
- **Esfuerzo:** Medio (~2h)
- **Acción:**
  1. `npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom`
  2. Agregar script en `package.json`: `"test": "vitest run"`
  3. Configurar `vite.config.ts` para tests.
  4. Crear `src/__tests__/AuthContext.test.tsx`:
     - `test_login_sets_token`
     - `test_logout_clears_token`
     - `test_is_authenticated_returns_false_initially`
     - `test_protected_route_redirects_when_no_token`
  5. Crear `src/__tests__/ProtectedRoute.test.tsx`.
- **CHECK:**
  1. `npm run test` → todos pasan.
  2. CI ejecuta tests frontend automáticamente.
- **Resultado esperado:** Primera cobertura de tests frontend. Auth flow verificado.

### Paso 3.7: Verificación de regresión — Ola 3 completa
- **Esfuerzo:** Medio (~30 min)
- **Acción:**
  1. `pytest tests/ -v` → 33 unitarios + ~12 integración = ~45 tests pasan.
  2. `npm run test` → ~6 tests frontend pasan.
  3. `npm run build` → exitoso.
  4. `npm run lint` → sin errores nuevos.
  5. Push a main → CI completo pasa.
- **Resultado esperado:** Pipeline CI verde con tests de backend + frontend.

### Paso 3.8: Documentar Ola 3
- **Archivos:** `auditoria_integral_2026/ola3/CHANGELOG_ola3.md`

---

## OLA 4 — CONSOLIDACIÓN ARQUITECTURA

**Objetivo:** Unificar el backend y centralizar la comunicación frontend-backend.

**Hallazgos que resuelve:** H-001, H-006, H-012
**Duración estimada:** ~8 horas
**Valor:** Crítico — Resuelve la deriva arquitectónica y prepara para despliegues flexibles.

### Paso 4.0: Crear backup del estado post-Ola-3
- **Esfuerzo:** Bajo (~5 min)

### Paso 4.1: Mapear todas las rutas de server.py
- **Hallazgo:** H-001 (Crítica)
- **Archivos:** `backend/server.py` (solo lectura/mapeo)
- **Esfuerzo:** Bajo (~20 min)
- **Acción:** Hacer catálogo completo de rutas en `server.py`: endpoints, métodos HTTP, query params.
- **CHECK:** Lista completa documentada en `auditoria_integral_2026/ola4/catalogo_rutas.md`.
- **Resultado esperado:** Visibilidad total de la superficie API actual.

### Paso 4.2: Mapear todas las rutas de app/main.py
- **Hallazgo:** H-001 (Crítica)
- **Archivos:** `backend/app/main.py` + routers montados
- **Esfuerzo:** Bajo (~20 min)
- **Acción:** Hacer catálogo de rutas montadas por `app/main.py`.
- **CHECK:** Lista completa en el mismo documento de catálogo.
- **Resultado esperado:** Diferencia clara entre ambos catálogos.

### Paso 4.3: Extraer routers de server.py a módulos
- **Hallazgo:** H-001 (Crítica)
- **Archivos:** `backend/server.py` + nuevos archivos en `backend/app/api/`
- **Esfuerzo:** Alto (~3h)
- **Acción:**
  1. Crear `backend/app/api/server_routes.py` (o dividir en varios).
  2. Extraer cada bloque de rutas de `server.py` a su propio router.
  3. Mantener `server.py` como entrypoint delgado que solo monta routers e inicializa servicios.
  4. Ejemplo de `server.py` resultante (~50 líneas):
     ```python
     from fastapi import FastAPI
     from app.api.server_routes import router as api_router
     # ... imports

     app = FastAPI(title="Iosef Finance")
     app.add_middleware(...)
     app.include_router(api_router, prefix="/api")
     # ... startup events, background tasks
     ```
- **CHECK:**
  1. `pytest tests/ -v` → todos los tests pasan.
  2. Todas las rutas de `/api/*` siguen respondiendo igual.
  3. `docker-compose up` → backend funciona.
  4. Frontend: screener, paper trading, analytics, signal lab cargan datos.
- **Resultado esperado:** `server.py` es delgado. Rutas en módulos. Sin cambios funcionales.

### Paso 4.4: Eliminar o consolidar app/main.py
- **Hallazgo:** H-001 (Crítica)
- **Archivos:** `backend/app/main.py`
- **Esfuerzo:** Medio (~1h)
- **Acción:**
  1. Determinar qué rutas de `app/main.py` no existen en `server.py`: market, screener, llm.
  2. Si son útiles, migrarlas a los routers de `server.py`.
  3. Si son mocks, eliminarlas o moverlas a `backend/app/api/endpoints/` con un flag `ENABLE_MOCK_ENDPOINTS`.
  4. Eliminar `app/main.py` como entrypoint o renombrarlo a `app/main_legacy.py`.
  5. Actualizar referencias en `README.md` y `pyproject.toml`.
- **CHECK:**
  1. `pytest tests/ -v` → pasan.
  2. No existe referencia a `app.main:app` en configuraciones activas.
  3. `docker-compose up` → backend arranca.
- **Resultado esperado:** Un solo entrypoint canónico: `server:app`.

### Paso 4.5: Centralizar URLs en frontend con VITE_API_BASE (H-006)
- **Hallazgo:** H-006 (Alta)
- **Archivos:** `frontend-v2/src/lib/api.ts` (nuevo), `.env`, `.env.example`
- **Esfuerzo:** Medio (~1.5h)
- **Acción:**
  1. Crear `frontend-v2/src/lib/api.ts`:
     ```typescript
     const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8002/api";

     export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
       const url = `${API_BASE}${path}`;
       const token = localStorage.getItem("token");
       const headers: Record<string, string> = {
         "Content-Type": "application/json",
         ...(options?.headers as Record<string, string> || {}),
       };
       if (token) {
         headers["Authorization"] = `Bearer ${token}`;
       }
       const response = await fetch(url, { ...options, headers });
       if (!response.ok) {
         if (response.status === 401) {
           localStorage.removeItem("token");
           window.location.href = "/login";
         }
         const error = await response.json().catch(() => ({ detail: "Unknown error" }));
         throw new Error(error.detail || `HTTP ${response.status}`);
       }
       return response.json();
     }
     ```
  2. Crear `.env` en `frontend-v2/` con `VITE_API_BASE=http://localhost:8002/api`.
  3. Crear `.env.example` con `VITE_API_BASE=http://localhost:8002/api`.
- **CHECK:**
  1. Reemplazar una llamada fetch (ej. en Analytics.tsx) con `apiFetch`.
  2. Verificar que carga datos correctamente.
  3. Probar con 401 forzado → redirige a login.
- **Resultado esperado:** Cliente HTTP centralizado con manejo de auth y errores.

### Paso 4.6: Migrar todas las llamadas fetch a apiFetch (H-006)
- **Hallazgo:** H-006 (Alta)
- **Archivos:** Todos los componentes con fetch
- **Esfuerzo:** Medio (~1.5h)
- **Acción:** Reemplazar cada `fetch(...)` en:
  - `Login.tsx`
  - `useMarketData.ts`
  - `TickerModal.tsx`
  - `PaperTrading.tsx`
  - `SignalLab.tsx`
  - `FinancialsTab.tsx`
  - `Analytics.tsx`
  - `ScreenerTable.tsx`
  - `SidePanel.tsx`
- **CHECK:**
  1. `npm run build` → sin errores.
  2. Login → exitoso.
  3. Screener → carga datos.
  4. Paper Trading → crea cuenta, ejecuta trades.
  5. Analytics → carga gráficos.
  6. Signal Lab → muestra señales.
- **Resultado esperado:** Cero `fetch` directos. Todas las llamadas pasan por `apiFetch`.

### Paso 4.7: Verificar contrato Signal Lab (H-012)
- **Hallazgo:** H-012 (Media)
- **Archivos:** `frontend-v2/src/tabs/SignalLab.tsx`, `backend/server.py` (ruta signal lab)
- **Esfuerzo:** Bajo (~30 min)
- **Acción:**
  1. Inspeccionar la respuesta real del endpoint de signal lab.
  2. Comparar con lo que espera `SignalLab.tsx`.
  3. Si hay desalineación, corregir en el frontend (desempaquetar `response.data`).
  4. Agregar test de integración para este endpoint.
- **CHECK:**
  1. Signal Lab muestra datos reales (no vacíos).
  2. Test de integración pasa.
- **Resultado esperado:** Contrato alineado, Signal Lab funcional.

### Paso 4.8: Verificación de regresión — Ola 4 completa
- **Esfuerzo:** Medio (~30 min)
- **Acción:**
  1. `pytest tests/ -v` → todos los tests pasan (~50).
  2. `npm run test` → tests frontend pasan.
  3. `npm run build` → exitoso.
  4. `docker-compose up` → 3 servicios healthy.
  5. Check manual: login, screener, paper trading, analytics, signal lab.
  6. CI pipeline verde.
- **Resultado esperado:** Arquitectura unificada. Frontend configurable. Sin regresiones.

### Paso 4.9: Documentar Ola 4
- **Archivos:** `auditoria_integral_2026/ola4/CHANGELOG_ola4.md`

---

## OLA 5 — AUTENTICACIÓN ROBUSTA

**Objetivo:** Migrar el token JWT de localStorage a cookie HttpOnly con refresh token.

**Hallazgos que resuelve:** H-008
**Duración estimada:** ~6 horas
**Valor:** Alto — Elimina el principal vector de robo de sesión.

### Paso 5.0: Crear backup del estado post-Ola-4
- **Esfuerzo:** Bajo (~5 min)

### Paso 5.1: Reducir TTL del access token a 15 minutos
- **Hallazgo:** H-008 (Alta)
- **Archivos:** `backend/app/core/security.py`
- **Esfuerzo:** Bajo (~5 min)
- **Acción:** Cambiar `ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7` → `15`.
- **CHECK:**
  1. Login → token generado.
  2. Esperar 15 min (o forzar con fecha en el pasado) → 401.
- **Resultado esperado:** Token de corta duración.

### Paso 5.2: Configurar backend para cookies HttpOnly
- **Hallazgo:** H-008 (Alta)
- **Archivos:** `backend/app/api/auth.py`
- **Esfuerzo:** Medio (~1h)
- **Acción:**
  1. Modificar endpoint de login para setear cookie:
     ```python
     from fastapi.responses import JSONResponse
     
     response = JSONResponse(content={"message": "Login successful"})
     response.set_cookie(
         key="access_token",
         value=access_token,
         httponly=True,
         secure=False,  # True en producción con HTTPS
         samesite="strict",
         max_age=900,  # 15 minutos
     )
     return response
     ```
  2. Crear endpoint `POST /api/auth/logout` que borra la cookie.
  3. Modificar `deps.py` para leer token de cookie además del header.
- **CHECK:**
  1. Login → response incluye `Set-Cookie`.
  2. Request subsecuente → cookie se envía automáticamente.
  3. `document.cookie` en consola del navegador → no muestra `access_token`.
- **Resultado esperado:** Token invisible desde JavaScript.

### Paso 5.3: Agregar endpoint logout
- **Hallazgo:** H-008 (Alta)
- **Archivos:** `backend/app/api/auth.py`
- **Esfuerzo:** Bajo (~15 min)
- **Acción:**
  ```python
  @router.post("/logout")
  def logout():
      response = JSONResponse(content={"message": "Logged out"})
      response.delete_cookie("access_token")
      return response
  ```
- **CHECK:** Logout → cookie eliminada → siguiente request sin token → 401.

### Paso 5.4: Adaptar frontend a cookies (sin localStorage)
- **Hallazgo:** H-008 (Alta)
- **Archivos:** `frontend-v2/src/context/AuthContext.tsx`, `frontend-v2/src/lib/api.ts`
- **Esfuerzo:** Medio (~2h)
- **Acción:**
  1. `AuthContext.tsx`: eliminar `localStorage.setItem("token")` y `getItem`.
  2. Login: solo hacer POST, el backend setea la cookie.
  3. `isAuthenticated`: verificar con `GET /api/auth/me` en lugar de leer localStorage.
  4. Logout: llamar `POST /api/auth/logout`.
- **CHECK:**
  1. Login → cookie seteada, `isAuthenticated = true`.
  2. Recargar página → sigue autenticado (cookie persiste).
  3. Logout → cookie eliminada, redirigido a login.
  4. `npm run test` → actualizar tests de AuthContext.
- **Resultado esperado:** Sin localStorage para auth. Sesión gestionada por cookies.

### Paso 5.5: Verificación de regresión — Ola 5 completa
- **Esfuerzo:** Medio (~30 min)
- **Acción:**
  1. `pytest tests/ -v` → todos pasan.
  2. `npm run test` → tests frontend pasan (actualizados para cookies).
  3. `npm run build` → exitoso.
  4. Login → cookie → funcionalidad completa.
  5. Logout → cookie eliminada.
  6. XSS simulado: `document.cookie` no contiene token.
- **Resultado esperado:** Auth robusto. Sin token en JavaScript.

### Paso 5.6: Documentar Ola 5
- **Archivos:** `auditoria_integral_2026/ola5/CHANGELOG_ola5.md`

---

## OLA 6 — ML Y PERFORMANCE

**Objetivo:** Reentrenar XGBoost con datos reales, implementar WebSocket y resolver bloqueos.

**Hallazgos que resuelve:** H-003, H-013, H-014, H-015 (parcial)
**Duración estimada:** ~12 horas
**Valor:** Crítico — Validación del modelo ML y mejora de performance.

### Paso 6.0: Crear backup del estado post-Ola-5
- **Esfuerzo:** Bajo (~5 min)

### Paso 6.1: Extraer features reales de trades_history.db
- **Hallazgo:** H-003 (Crítica)
- **Archivos:** `backend/scripts/extract_training_data.py` (nuevo)
- **Esfuerzo:** Medio (~2h)
- **Acción:**
  1. Leer `trades_history.db` → trades cerrados.
  2. Para cada trade, obtener datos históricos del parquet correspondiente.
  3. Calcular features (log_return, volatility, momentum, RSI, MACD).
  4. Label: 1 si el trade fue ganador (pnl > 0), 0 si perdedor.
  5. Guardar dataset en `backend/data/training_dataset.parquet`.
- **CHECK:**
  1. El script se ejecuta sin errores.
  2. `training_dataset.parquet` existe y tiene >100 filas.
  3. Verificar distribución de labels (~balance razonable).
- **Resultado esperado:** Dataset de entrenamiento real listo.

### Paso 6.2: Reentrenar XGBoost con datos reales
- **Hallazgo:** H-003 (Crítica)
- **Archivos:** `backend/scripts/train_xgboost.py`
- **Esfuerzo:** Medio (~2h)
- **Acción:**
  1. Modificar `train_xgboost.py` para:
     a. Cargar `training_dataset.parquet` en lugar de generar datos sintéticos.
     b. Implementar time-series split (no random split).
     c. Guardar métricas en `backend/artifacts/xgboost_metrics.json`.
     d. Guardar modelo versionado: `xgboost_signal_scorer_v2.pkl`.
  2. Si no hay suficientes datos reales, mantener dataset sintético como fallback PERO con un flag `trained_on_real_data = False` + warning en logs.
- **CHECK:**
  1. `python scripts/train_xgboost.py` → entrena con datos reales.
  2. Métricas guardadas en JSON.
  3. Modelo nuevo cargado por `scoring.py`.
  4. `compute_ml_score()` retorna valores basados en datos reales (no 50.0 fijo).
- **Resultado esperado:** Modelo ML fundamentado en datos reales de trading.

### Paso 6.3: Agregar flag de validación del modelo en scoring
- **Hallazgo:** H-003 (Crítica)
- **Archivos:** `backend/app/services/scoring.py`
- **Esfuerzo:** Bajo (~15 min)
- **Acción:**
  ```python
  MODEL_TRAINED_ON_REAL_DATA = os.getenv("MODEL_TRAINED_ON_REAL_DATA", "false").lower() == "true"
  
  if not MODEL_TRAINED_ON_REAL_DATA:
      logger.warning("XGBoost model trained on synthetic data. Predictions are NOT reliable for production use.")
  ```
- **CHECK:** Log muestra warning si el flag no está activo.
- **Resultado esperado:** Transparencia sobre la validez del modelo.

### Paso 6.4: Implementar WebSocket en backend (H-013)
- **Hallazgo:** H-013 (Media)
- **Archivos:** `backend/app/api/ws.py` (nuevo), `backend/server.py`
- **Esfuerzo:** Medio (~2h)
- **Acción:**
  1. Crear endpoint WebSocket en `/ws/market`:
     ```python
     from fastapi import WebSocket
     
     @app.websocket("/ws/market")
     async def market_ws(websocket: WebSocket):
         await websocket.accept()
         while True:
             # Enviar snapshot del mercado cada 5s
             data = get_market_snapshot()
             await websocket.send_json(data)
             await asyncio.sleep(5)
     ```
  2. Montar en `server.py`.
- **CHECK:**
  1. `wscat -c ws://localhost:8002/ws/market` → recibe JSON cada 5s.
  2. Sin memory leak tras 100 mensajes.
- **Resultado esperado:** WebSocket funcionando.

### Paso 6.5: Conectar frontend al WebSocket (H-013)
- **Hallazgo:** H-013 (Media)
- **Archivos:** `frontend-v2/src/hooks/useMarketData.ts`
- **Esfuerzo:** Medio (~1.5h)
- **Acción:**
  1. Activar la lógica de WebSocket comentada en `useMarketData.ts`.
  2. Usar `ws://` para dev, `wss://` para prod.
  3. Fallback a polling si WebSocket falla.
  4. Reemplazar polling por eventos del WebSocket.
- **CHECK:**
  1. Frontend recibe datos en tiempo real (sin polling).
  2. Network tab muestra conexión WebSocket (101 Switching Protocols).
  3. Si WebSocket falla, polling se activa automáticamente.
- **Resultado esperado:** Datos en tiempo real, menor carga en backend.

### Paso 6.6: Mover operaciones bloqueantes a run_in_executor (H-014)
- **Hallazgo:** H-014 (Media)
- **Archivos:** `backend/server.py` (rutas afectadas)
- **Esfuerzo:** Medio (~1.5h)
- **Acción:**
  1. Identificar endpoints síncronos pesados (signal evaluation, strategy optimization).
  2. Envolver en `run_in_executor`:
     ```python
     import asyncio
     from concurrent.futures import ThreadPoolExecutor

     executor = ThreadPoolExecutor(max_workers=4)

     @app.get("/api/signals")
     async def get_signals():
         loop = asyncio.get_event_loop()
         result = await loop.run_in_executor(executor, evaluate_signals)
         return result
     ```
- **CHECK:**
  1. Dos requests concurrentes a endpoint pesado → se ejecutan en paralelo.
  2. Tiempo de respuesta no bloquea otras requests.
  3. Tests pasan.
- **Resultado esperado:** Event loop liberado. Requests concurrentes sin bloqueo.

### Paso 6.7: Unificar persistencia SQLite bajo SQLAlchemy (H-015 parcial)
- **Hallazgo:** H-015 (Media)
- **Archivos:** `backend/app/services/persistence.py`, `backend/app/db/database.py`
- **Esfuerzo:** Alto (~3h)
- **Acción:**
  1. Crear modelo SQLAlchemy para `Trade` en `backend/app/models/trade.py`.
  2. Migrar `save_closed_trade` y `get_closed_trades_history` a usar SQLAlchemy.
  3. Ambas operaciones usan la misma sesión de base de datos (`iosef_finance.db`).
  4. Mantener `trades_history.db` como respaldo legacy (no eliminarla aún).
- **CHECK:**
  1. Paper trading → cerrar trade → se guarda con SQLAlchemy.
  2. Analytics → cargar historial → datos consistentes.
  3. Tests de paper trading pasan.
  4. `trades_history.db` sigue intacta (seguridad).
- **Resultado esperado:** Una sola estrategia de acceso a datos.

### Paso 6.8: Agregar rate limiting a endpoints de auth
- **Hallazgo:** No catalogado, seguridad
- **Archivos:** `backend/server.py`, `backend/requirements.txt`
- **Esfuerzo:** Bajo (~30 min)
- **Acción:**
  1. Instalar `slowapi`.
  2. Configurar rate limiter:
     ```python
     from slowapi import Limiter
     from slowapi.util import get_remote_address

     limiter = Limiter(key_func=get_remote_address)
     app.state.limiter = limiter

     @app.post("/api/auth/login")
     @limiter.limit("5/minute")
     async def login(...):
         ...
     ```
- **CHECK:**
  1. 6 requests en 1 minuto → el 6to retorna 429.
  2. Esperar 1 minuto → request vuelve a funcionar.
- **Resultado esperado:** Protección contra fuerza bruta.

### Paso 6.9: Verificación de regresión — Ola 6 completa
- **Esfuerzo:** Medio (~30 min)
- **Acción:**
  1. `pytest tests/ -v` → todos pasan.
  2. `npm run test` → todos pasan.
  3. `npm run build` → exitoso.
  4. `docker-compose up` → 3 servicios healthy.
  5. Check manual completo.
  6. CI pipeline verde.
- **Resultado esperado:** Sistema más rápido, más seguro, ML validado.

### Paso 6.10: Documentar Ola 6
- **Archivos:** `auditoria_integral_2026/ola6/CHANGELOG_ola6.md`

---

## PARTE 3 — CHECKPOINT DE PRODUCCIÓN

Al completar las 6 Olas, ejecutar el checklist de producción:

### Antes del despliegue productivo

- [ ] `JWT_SECRET_KEY` generado con `openssl rand -hex 32`, nunca hardcodeado
- [ ] CORS restringido a dominio(s) de producción
- [ ] `secure=True` en cookie de auth
- [ ] HTTPS configurado en Nginx (frontend)
- [ ] XGBoost entrenado con datos reales (`MODEL_TRAINED_ON_REAL_DATA=true`)
- [ ] CI/CD pipeline verde en main
- [ ] Test coverage >70% (backend)
- [ ] Healthchecks confirmados en Docker Compose
- [ ] Rate limiting activo en `/api/auth/login`
- [ ] `docker-compose up` exitoso en entorno staging
- [ ] Logging estructurado (JSON) configurado
- [ ] Backup de base de datos programado (cron)
- [ ] Monitoreo básico: health endpoint, Redis ping
- [ ] Documentación de despliegue actualizada

---

## PARTE 4 — PROMPT MAESTRO PARA EJECUCIÓN DE CADA OLA

El siguiente prompt puede usarse para delegar cada ola a un agente. Cambiar `OLA_N` y `NOMBRE_OLA` según corresponda.

```text
Eres el agente "Ejecutor de Ola N — NOMBRE_OLA" del plan de producción de Iosef Finance.

Tu misión es ejecutar TODOS los pasos de la Ola N del documento:
auditoria_integral_2026/11_plan_produccion_paso_a_paso.md

REGLAS DE ORO:
1. Ejecuta los pasos en orden numérico estricto. No saltes pasos.
2. Cada paso termina con un CHECK. Si el CHECK falla, NO avances. Repara primero.
3. Documenta CADA paso en auditoria_integral_2026/olaN/CHANGELOG_olaN.md inmediatamente después de completarlo.
4. Haz commits atómicos: un commit por paso con mensaje [Ola N.Y] descripción.
5. Al finalizar la ola, ejecuta la verificación de regresión completa.
6. Si encuentras un problema no previsto, documenta en CHANGELOG y propón ajuste al plan.

ESTADO ACTUAL DEL PROYECTO:
- Backend: FastAPI, entrypoint server:app, Dockerizado
- Frontend: React + Vite + TypeScript
- Tests: pytest (backend), Vitest (frontend)
- CI: GitHub Actions configurado
- Variables de entorno: JWT_SECRET_KEY, CORS_ORIGINS, DATABASE_URL

ANTES DE EMPEZAR:
1. Lee auditoria_integral_2026/11_plan_produccion_paso_a_paso.md
2. Lee auditoria_integral_2026/02_hallazgos_priorizados.md
3. Crea la carpeta auditoria_integral_2026/olaN/
4. Documenta el estado inicial en backup_antes.md

DURANTE LA EJECUCIÓN:
- Si un CHECK falla, describe el error, arréglalo, y documenta la solución.
- Si un paso requiere más esfuerzo del estimado, documenta por qué.
- No modifiques archivos fuera del alcance de la ola.

AL FINALIZAR:
- Verifica que docker-compose up funciona.
- Verifica que los tests pasan.
- Verifica que el frontend funciona.
- Documenta el CHANGELOG completo.
- Reporta: pasos completados, tiempo real vs estimado, problemas encontrados, próximos pasos sugeridos.

Empieza por el Paso N.0: Crear backup del estado actual.
```

---

## RESUMEN DE VALOR ENTREGADO POR OLA

| Ola | Nombre | Score antes | Score después | Tiempo |
|---|---|---|---|---|
| Ola 1 | Seguridad Inmediata | 3/10 | 5/10 | ~4h |
| Ola 2 | Higiene Operativa | 5/10 | 6/10 | ~3h |
| Ola 3 | CI/CD + Testing | 6/10 | 7.5/10 | ~8h |
| Ola 4 | Consolidación Arquitectura | 7.5/10 | 8.5/10 | ~8h |
| Ola 5 | Autenticación Robusta | 8.5/10 | 9/10 | ~6h |
| Ola 6 | ML y Performance | 9/10 | **9.5/10** | ~12h |

**Total estimado:** ~41 horas de trabajo en ~6 sesiones independientes.
**Meta final:** Proyecto **APTO PARA PRODUCCIÓN** (score >9/10).

---

*Documento generado el 2026-06-09 como parte de la planificación post-auditoría integral.*
*Metodología: PDCA por Olas con Verificación Integrada.*
*Próximo paso: ejecutar Ola 1.*

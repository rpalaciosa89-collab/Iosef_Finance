# Plan de Mejoras — Spec-Driven Development + Loop Engineering

**Fecha:** 2026-08-20
**Autor:** CTO / Quant Lead
**Basado en:** auditoría integral 2026 + evaluación de estado actual (2026-08-20)
**Estado actual del sistema:** MVP funcional, NO apto para producción (~4/10)
**Objetivo de este plan:** convertir `Iosef Finance` en un sistema con **edge cuantitativo demostrable**, **arquitectura mantenible** y **proceso de entrega con verificación continua**, aplicando **Spec-Driven Development (SDD)** y **Loop Engineering**.

---

## 0. Resumen Ejecutivo

El sistema funciona de extremo a extremo (screener de 98 tickers Titan 100, Signal Lab, backtester, paper trading, auth JWT, cache Redis/parquet), pero la auditoría de estado encontró **4 problemas de fondo** que ningún hotfix ha resuelto:

1. **No hay edge estadístico demostrado:** el único modelo en producción (XGBoost) tiene ROC-AUC **0.552** (ruido, no señal). El score del screener es una heurística aditiva con pesos arbitrarios (`server.py`), y el backtester simula una estrategia MA crossover que **no** se corresponde con las señales que la plataforma emite.
2. **Bug activo de persistencia:** el cache parquet falla en cada scan (`Could not convert ISO timestamp to double`, visible en `/tmp/iosef_backend.log`).
3. **Configuración divergente:** `DATABASE_URL` de `.env` se ignora en runtime (`app/db/database.py` lee `os.getenv` sin `load_dotenv`); CORS se define en 2 lugares; hay 2 entrypoints.
4. **Operaciones bloqueantes en el event loop:** `yfinance` sincrónico dentro de endpoints async (`paper_trading.py:23`, `signal_evaluation.py:109`, `server.py:run_scan`) → se satura con usuarios concurrentes.

Este plan corrige esos 4 problemas en **5 Olas PDCA** (Olas 3–7, continuando la numeración del plan de producción), cada ítem con una **Spec formal** y un **bucle de verificación** cerrado.

---

## 1. Metodología: Loop Engineering

Loop Engineering = **estructurar el desarrollo como bucles cerrados de retroalimentación**, donde cada bucle tiene una entrada (estado), una transformación (trabajo) y una salida verificable (métrica/criterio). Si la salida no cumple el criterio, el bucle se repite sin avanzar al siguiente. Nadie "passa de fase" por opinión; se pasa por **evidencia medible**.

### 1.1 Los 4 bucles

```
┌─────────────────────────────────────────────────────────────────────────┐
│  BUCLE 4 · PRODUCTO (semanas) — mejora continua del backlog              │
│  Entry: métricas de producción | Exit: roadmap actualizado               │
└───────────────────────────▲─────────────────────────────────────────────┘
                            │ retro interno (retrospectiva)
┌───────────────────────────┴─────────────────────────────────────────────┐
│  BUCLE 3 · OLA (días–semana) — PDCA de una ola completa                  │
│  PLAN → DO → CHECK (tests+lint+build+arita) → ACT (changelog+commit)     │
└───────────────────────────▲─────────────────────────────────────────────┘
                            │ criterios de salida de ola
┌───────────────────────────┴─────────────────────────────────────────────┐
│  BUCLE 2 · ITEM / SPEC (horas–días) — una Spec implementada en TDD       │
│  Spec → RED → GREEN → REFACTOR → VERIFY (métricas) → CHANGELOG+commit    │
└───────────────────────────▲─────────────────────────────────────────────┘
                            │ tests verdes + métricas target cumplidas
┌───────────────────────────┴─────────────────────────────────────────────┐
│  BUCLE 1 · INNER (minutos) — microciclo edit–test rápido                 │
│  editar → pytest/vitest → corregir                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Reglas de cada bucle

| Bucle | Cadencia | Entrada | Transformación | Salida / Criterio para avanzar |
|---|---|---|---|---|
| 1 · Inner | < 5 min | línea de código | edit → test | suite pertinente en verde (máx. 60 s por spec) |
| 2 · Item | horas | Spec aprobada | RED → GREEN → REFACTOR | tests verdes + `DoD` de la Spec cumplida |
| 3 · Ola | días | lista de ítems | DO ordenado + CHECK | 100% tests backend + build frontend + changelog actualizado |
| 4 · Producto | semanas | métricas de estado | retro → re-priorizar backlog | roadmap v2 publicado |

### 1.3 Métricas de bucle (obligatorias, se registran en el CHANGELOG de cada ola)

| Métrica | Cómo se mide | Target |
|---|---|---|
| `back.tests_verdes` | `./venv/bin/python -m pytest backend/tests -q` | 100% y nunca bajar en olas posteriores |
| `back.tests_tiempo` | tiempo de la suite | < 5 min (hoy 104 s) |
| `front.build_ok` | `npm run build` en frontend-v2 | exit 0 sin errores TS |
| `front.tests_verdes` | `npm test` (vitest) | 100% de los tests declarados |
| `scan.cache_ok` | presencia de `cache/parquet/scan_*.parquet` reciente + log sin errores | 3 scans seguidos sin `[parquet] Write error` |
| `scan.p95` | latencia P95 del scan con caché caliente | < 30 s |
| `api.p95_bloqueo` | instrumentación de llamadas >50 ms en event loop | 0 bloqueos >50 ms en endpoints async |
| `bt.cost_model` | todo reporte de backtest incluye costs/slippage | 100% de reportes |
| `bt.benchmark` | todo reporte incluye SPY como benchmark | 100% de reportes |
| `ml.auc_oos` | AUC en validación walk-forward | ≥ 0.56 para promoción a señal |
| `db.unificado` | una sola ruta de DB usada por el runtime | 1 (hoy hay 3 candidatas) |

### 1.4 Gate de ola (no se cierra una ola si):

- Hay tests rojos.
- El CHANGELOG de la ola no documenta cada ítem su métrica.
- Alguna métrica de una ola anterior **regresó** (no se avanza, se repara primero).

---

## 2. Spec-Driven Development (SDD)

Cada modificación se **especifica antes de codificar**. La Spec es el contrato: si el código cumple la Spec y los criterios de aceptación, el ítem está terminado. No se acepta código sin Spec.

### 2.1 Ciclo de vida de una Spec

```
1. DRAFT   → se escribe la Spec (plantilla de §2.2)
2. REVIEW  → PL/QA/Quant la revisan (1 sesión, máx. 30 min)
3. TEST    → se escriben los tests que describen la Spec (TDD RED)
4. CODE    → implementación mínima hasta GREEN
5. VERIFY  → se corren métricas de §1.3 relevantes al ítem
6. MERGE   → commit atómico `[OlaX.Y] <título>`
7. CHANGELOG → se actualiza la ola con resultado + métricas
```

### 2.2 Plantilla oficial de Spec

La plantilla vive en `docs/specs/_TEMPLATE.md`. Características no negociables de toda Spec:

- **ID** único (`SP-<Ola>.<item>`).
- **Contexto y problema** medible (dato de la auditoría/evaluación, no opinión).
- **Root cause** (archivo:línea si existe).
- **Comportamiento** en **Given / When / Then** — siempre en términos observables por API, UI o DB.
- **Criterios de aceptación** — checklist numérico/booleano, medibles con comandos.
- **Tests a escribir primero** (rutas de archivos de test).
- **Implementación** (orientación técnica, no pseudocódigo final).
- **Verificación** (comandos exactos).
- **Definition of Done** — cierre de bucle.

### 2.3 Ubicación

- Master con todas las specs: `docs/plan_mejoras_sdd_loop_engineering.md` (este archivo).
- Plantilla reutilizable: `docs/specs/_TEMPLATE.md`.
- Cambios por ola: `auditoria_integral_2026/olaN/` (convención existente: cada ola tiene `backup_antes.md` + `CHANGELOG_olaN.md`).

---

## 3. Backlog priorizado — 5 Olas (3–7)

> Convención de commits: `[OlaN.X] <título>` por ítem. Todos los pasos son atómicos.

### Ola 3 — Estabilización y configuración única (crítico, corto plazo)

| ID | Título | Severidad | Esfuerzo |
|---|---|---|---|
| SP-3.1 | Fix del cache parquet (round-trip de tipos mixtos) | Crítica | Bajo |
| SP-3.2 | Cargar `.env` real en runtime (unificar `DATABASE_URL`) | Crítica | Bajo |
| SP-3.3 | Unificar CORS y eliminar el entrypoint secundario | Alta | Bajo |
| SP-3.4 | Activar WAL + `PRAGMA` en SQLite y conectar migraciones Alembic | Alta | Medio |
| SP-3.5 | Recortar vulnerabilidad de path/validación de ticker en endpoints | Media | Bajo |

### Ola 4 — Validación cuantitativa (edge real — el corazón del producto)

| ID | Título | Severidad | Esfuerzo |
|---|---|---|---|
| SP-4.1 | Backtester: costos + slippage + benchmark SPY + métricas estandarizadas | Crítica | Alto |
| SP-4.2 | XGBoost: walk-forward + purged/embargo CV + gate AUC ≥ 0.56 | Crítica | Alto |
| SP-4.3 | Motor de scoring pluggable (Heurístico vs ML) con etiqueta de fuente | Alta | Medio |
| SP-4.4 | Umbrales de muestra exigentes + warnings duros en API y UI | Media | Bajo |

### Ola 5 — Rendimiento y concurrencia

| ID | Título | Severidad | Esfuerzo |
|---|---|---|---|
| SP-5.1 | Sacar `yfinance` del event loop (thread pool + caché TTL) | Crítica | Medio |
| SP-5.2 | Paper trading: precios por lote y actualización asíncrona de MTM | Alta | Medio |
| SP-5.3 | Signal Lab y Strategy Optimizer como background jobs con estado | Media | Alto |

### Ola 6 — Persistencia unificada y entrega

| ID | Título | Severidad | Esfuerzo |
|---|---|---|---|
| SP-6.1 | Unificar `trades_history.db` y `iosef_finance.db` en un solo esquema | Alta | Alto |
| SP-6.2 | Activar CI/CD como gate (workflow `ci.yml` existe, falta cubrirlo) | Alta | Medio |
| SP-6.3 | Healthchecks + degradación graceful en docker-compose | Media | Bajo |
| SP-6.4 | Logging estructurado (JSON) + correlación por request | Media | Medio |

### Ola 7 — Hardening de producto y monitoreo

| ID | Título | Severidad | Esfuerzo |
|---|---|---|---|
| SP-7.1 | Monitoreo de drift de modelos (feature distribution + AUC en rolling) | Alta | Alto |
| SP-7.2 | Frontend: cliente API centralizado (`src/lib/api.ts`), sin URLs sueltas | Media | Medio |
| SP-7.3 | Eliminar `any` + errores tipados en frontend | Media | Medio |
| SP-7.4 | Tests E2E críticos (login → scan → paper trade) | Media | Alto |

---

## 4. Specs detalladas

### OLA 3

---

#### SP-3.1 — Fix del cache parquet (round-trip de tipos mixtos)

- **Contexto:** cada scan intenta escribir `cache/parquet/scan_titan100.parquet` y falla con `Could not convert '2026-08-20T06:57:54.871572Z' with type str: tried to convert to double`. El cache parquet **nunca funciona**; el sistema depende de Redis/JSON.
- **Root cause:** `server.py:975` — `pa.Table.from_pydict` infiere el tipo de cada columna desde la primera fila; el payload tiene columnas que mezclan `str` (timestamps ISO, `signal_detected_at`, `situation`) y numéricos, y a veces el mismo campo varía de tipo entre filas.
- **Comportamiento (G/W/T):**
  - **GIVEN** un payload de scan con campos mixtos (str timestamp ISO + floats + bools)
  - **WHEN** se invoca `_write_parquet_cache(market, payload)` y luego `_read_parquet_cache(market)` dentro del TTL
  - **THEN** la escritura no lanza excepción, y el `data` leído es **round-trip fiel** al original (mismo número de registros, mismas claves, valores preservados como string/número sin pérdida).
- **Criterios de aceptación:**
  1. `backend/tests/test_parquet_cache.py` crece con casos mixtos y pasa.
  2. 3 scans consecutivos sin `[parquet] Write error` en logs.
  3. `redis_get("scan:titan100")` y el cache parquet devuelven el mismo `data` (comparación de diccionarios).
- **Tests (TDD, primero):**
  - `test_round_trip_mixed_types` — payload real con `signal_detected_at` ISO string y `rsi` float; assert equal tras ida y vuelta.
  - `test_write_no_error_on_mixed` — verifica que no se eleva excepción.
  - `test_read_ignores_stale` — fuera de TTL devuelve `None`.
- **Implementación:** normalizar antes de `from_pydict`: convertir explícitamente cada columna a `pa.array` con tipo determinístico (ej. strings para campos de texto, `pa.float64()` para numéricos) o serializar todos los valores vía `str()` en un registro `meta` aparte. Alternativa más simple: escribir el payload completo como JSON en el `.parquet` (una sola columna de bytes) y parsear al leer — la corrección importa más que el útil de compresión.
- **Verificación:**
  ```
  ./venv/bin/python -m pytest backend/tests/test_parquet_cache.py -v
  # forzar 2 scans: curl -s http://localhost:8002/api/scan/force-refresh
  grep "parquet" /tmp/iosef_backend.log
  ```
- **DoD:** tests verdes · log limpio · commit `[Ola3.1]`.

---

#### SP-3.2 — Cargar `.env` real en runtime (unificar `DATABASE_URL`)

- **Contexto:** `app/db/database.py:6` lee `os.getenv("DATABASE_URL", "sqlite:///./iosef_finance.db")`, pero nadie ejecuta `load_dotenv()`. El `.env` del backend (que sí configura `pydantic-settings`) **no controla la DB que usa SQLAlchemy**. El runtime trabaja con `./iosef_finance.db` (CWD `backend/`), mientras `config.py` declara `../data/iosef_finance.db`. Hay 3 archivos candidatos y el usuario ni se entera de cuál tiene los datos.
- **Root cause:** falta de carga de `.env` en el entrypoint + dos fuentes de verdad (pydantic en `config.py` vs `os.getenv` en `database.py`/`server.py`).
- **Comportamiento (G/W/T):**
  - **GIVEN** un `.env` en `backend/.env` con `DATABASE_URL=sqlite:///...`
  - **WHEN** se inicia `server.py`
  - **THEN** el motor de SQLAlchemy apunta EXACTAMENTE a esa URL; un GET a `/api/health` reporta en el meta la ruta de la DB activa.
- **Criterios de aceptación:**
  1. `health_check()` devuelve `{"database": "<ruta activa>"}`.
  2. `./venv/bin/python -c "import os; print(os.getenv('DATABASE_URL'))"` refleja el valor del `.env`.
  3. `pytest` sigue en verde (los tests setean sus propias env vars, no romper).
- **Implementación:** en `server.py` (antes de imports del modelo): `from dotenv import load_dotenv; load_dotenv()` con `override=False`; en `app/db/database.py` pasar por `settings.DATABASE_URL` en vez de `os.getenv`, o delegar toda la config a `app/config.py` (fuente única). Añadir `python-dotenv` a `requirements.txt` si no está.
- **Verificación:**
  ```
  ./venv/bin/python -m pytest backend/tests -q
  curl -s http://localhost:8002/api/health
  ```
- **DoD:** una sola DB activa documentada en `/api/health` · tests verdes · commit `[Ola3.2]`.

---

#### SP-3.3 — Unificar CORS y eliminar el entrypoint secundario

- **Contexto:** CORS se define en `server.py:1010` (desde `CORS_ORIGINS` env) y en `app/main.py:24-27` (desde `settings.BACKEND_CORS_ORIGINS`). Hay 2 aplicaciones FastAPI (`server.py` es el canónico; `main.py` parece legacy). Configuraciones paralelas que ya se desincronizaron.
- **Comportamiento (G/W/T):**
  - **GIVEN** la variable `CORS_ORIGINS` con valor `a,b,c`
  - **WHEN** el backend procesa una request con `Origin: a` y otra con `Origin: z`
  - **THEN** la primera incluye header `Access-Control-Allow-Origin: a`; la segunda NO incluye el header.
- **Criterios de aceptación:**
  1. Un solo lugar define orígenes permitidos (env `CORS_ORIGINS`), consumido por `server.py`.
  2. `app/main.py` se elimina o se convierte en módulo de cargadores reutilizable.
  3. Test de integración que prueba los 2 casos (origin permitido/rechazado) usando `TestClient` con el header `Origin`.
- **Implementación:** borrar `main.py` (verificar que ningún import lo usa) y centralizar la lectura en `server.py`; mover `add_cache_control_headers` y routers a funciones de fábrica reutilizables si hace falta.
- **Verificación:** `pytest backend/tests -q` + request con `curl -H "Origin: http://localhost:5174" -D- http://localhost:8002/api/health`.
- **DoD:** 1 único entrypoint · CORS testado · commit `[Ola3.3]`.

---

#### SP-3.4 — SQLite WAL + migraciones Alembic

- **Contexto:** paper trading en SQLite con `check_same_thread=False`, sin WAL, sin migraciones. Cualquier cambio de esquema se hace a mano y los entornos divergen.
- **Comportamiento (G/W/T):**
  - **GIVEN** un esquema administrado por Alembic (`alembic/` en backend)
  - **WHEN** se aplica `alembic upgrade head`
  - **THEN** la DB queda con WAL activo (`PRAGMA journal_mode=wal`) y el esquema coincide con los modelos SQLAlchemy (sin `-` drift).
- **Criterios de aceptación:**
  1. `alembic revision` del estado inicial de los modelos (users, paper_accounts, paper_positions, paper_trades) aplica sin error sobre DB vacía.
  2. `alembic check` reporta 0 drift.
  3. `PRAGMA journal_mode` responde `wal`.
  4. Tests de paper trading en verde (recrean esquema vía `Base.metadata` o migraciones).
- **Verificación:** `cd backend && ../venv/bin/alembic upgrade head && ../venv/bin/alembic check && ../venv/bin/python -m pytest tests/ -q`.
- **DoD:** migraciones versionadas · WAL activo · testeado · commit `[Ola3.4]`.

---

#### SP-3.5 — Validación estricta de ticker en endpoints

- **Contexto:** el pattern regex `^[A-Za-z0-9\.\-]{1,10}$` existe en `server.py:1123` para `get_ticker_detail`, pero no está garantizado en todos los endpoints (paper trading, backtest, neural score).
- **Comportamiento (G/W/T):**
  - **GIVEN** un endpoint público o autenticado que recibe `ticker`
  - **WHEN** el ticker contiene caracteres fuera de `A-Za-z0-9.-` (ej. `"' OR 1=1 --`)
  - **THEN** responde `422 Unvalidated ticker format` y nunca ejecuta SQL ni yfinance con el input crudo.
- **Criterios de aceptación:**
  1. `backend/tests/test_validators.py` cubre inyección, strings largos y tickers válidos (`BRK-B`, `AAPL`).
  2. Todos los endpoints con parámetro ticker usan el validador común (`app/core/validators.py` — ya existe, verificar cobertura).
- **Verificación:** `pytest backend/tests/test_validators.py -v`.
- **DoD:** validador aplicado en todos los endpoints con ticker · tests · commit `[Ola3.5]`.

---

### OLA 4 — Validación cuantitativa (el corazón del producto)

---

#### SP-4.1 — Backtester con costos, slippage, benchmark y métricas estandarizadas

- **Contexto:** `app/services/backtester.py` (63 líneas) es una **simulación mock**: cruza SMA20/SMA50 como proxy, no usa las señales reales de la plataforma, no contempla comisiones, slippage, SL/TP ni benchmark. Devuelve solo `total_return`, `max_drawdown`, `sharpe`. Cualquier expectancy positiva reportada hoy es **no reproducible** porque no corresponde al motor real de señales.
- **Comportamiento (G/W/T):**
  - **GIVEN** un ticker, rango de fechas y una estrategia (señales reales de la plataforma o una especificada)
  - **WHEN** se ejecuta `Backtester.run()`
  - **THEN** el reporte incluye: costos aplicados (default 10 bps + 5 bps slippage, configurables), retorno neto vs bruto, métricas contra benchmark **SPY** (retorno exceso, tracking error, Information Ratio, Sortino, max drawdown, expectativa por trade, profit factor, hit rate) y una serie de equity descargable.
- **Criterios de aceptación:**
  1. `BacktestResult` nuevo schema (response model) con campos obligatorios: `net_total_return_pct`, `gross_total_return_pct`, `costs_pct`, `benchmark_return_pct`, `ir`, `sortino`, `expectancy_per_trade`, `profit_factor`, `win_rate`, `max_drawdown_pct`.
  2. Dos ejecuciones del mismo input dan el mismo resultado (determinismo, sin `yf.download` aleatorio).
  3. Una estrategia long-only sin señales devuelve `expectancy <= 0` si costos > retorno bruto (el costo se ve reflejado).
  4. Test con fixture de precios sintéticos (sin red) valida el cálculo de `ir` y `sortino` a mano.
- **Tests (TDD, primero):**
  - `backend/tests/test_backtester.py::test_costs_reduce_net_return`
  - `backend/tests/test_backtester.py::test_benchmark_metrics_healthy_input`
  - `backend/tests/test_backtester.py::test_deterministic`
  - `backend/tests/test_backtester.py::test_exit_via_sl_tp`
- **Implementación:** reescribir `backtester.py` con un `ExecutionModel` (comisión fija + bps, slippage bps), `BenchmarkProxy` (SPY vía cache local/parquet, nunca bloqueante), cálculo vectorizado de métricas (importar `numpy`; si hay `scipy`, usar stats robustos). Conectar el endpoint `/api/backtest/{ticker}` a un job async para no bloquear.
- **Verificación:**
  ```
  ./venv/bin/python -m pytest backend/tests/test_backtester.py -v
  curl -s "http://localhost:8002/api/backtest/AAPL?start=2024-01-01&end=2025-01-01" | jq '.costs_pct, .ir, .sortino'
  ```
- **DoD:** reporte completo con costos+benchmark · determinista · tests con fixture sin red · commit `[Ola4.1]`.

---

#### SP-4.2 — XGBoost con walk-forward + gate AUC ≥ 0.56

- **Contexto:** el modelo en producción tiene `roc_auc: 0.5518` (meta en `backend/models/xgboost_signal_scorer_meta.json`). Es 0.05 mejor que azar: **no es señal**. Fue entrenado con 37,458 muestras de 98 tickers (datos reales), pero sin partición temporal estricta — riesgo alto de sobreajuste/leakage.
- **Comportamiento (G/W/T):**
  - **GIVEN** el pipeline de entrenamiento `scripts/train_xgboost_real.py`
  - **WHEN** se reentrena con partición temporal walk-forward (5 folds cronológicos, purged + embargo, sin muestras overlapping entre train/validación)
  - **THEN** el meta-reporte incluye el AUC OOS promedio, y el entrenamiento **solo se promueve a producción si `auc_oos >= 0.56`**; si no, se rechaza el deploy y `compute_ml_score` sigue con el modelo vigente (o fallback 50).
- **Criterios de aceptación:**
  1. `backend/models/xgboost_signal_scorer_meta.json` nuevo formato incluye: `auc_oos_mean`, `auc_oos_std`, `cv_folds`, `embargo_days`, `promoted: bool`.
  2. Si `promoted == false`, la API `/api/ml/model-info` devuelve `status: "archived"` y el frontend NO muestra "ML score" como confianza.
  3. `verify_sample_independent`: ninguna fila de validación comparte el mismo timestamp ± embargo con filas de train.
  4. Script idempotente y con seed fijo.
- **Tests (TDD, primero):**
  - `backend/tests/test_ml_validation.py::test_purge_and_embargo_separation` (temporal).
  - `backend/tests/test_ml_validation.py::test_gate_promotion_threshold` (mock con AUC 0.55 → no promueve; 0.58 → promueve).
  - `backend/tests/test_ml_validation.py::test_meta_reports_oos`.
- **Implementación:** en `scripts/train_xgboost_real.py` añadir `WalkForwardSplit(purge, embargo)` (ya existen utilidades ligeras en `app/core/validators.py`; si no, implementar en `app/services/ml_validation.py`); calcular métricas; escribir meta con `promoted`; `compute_ml_score` de `scoring.py` respeta `promoted`.
- **Verificación:**
  ```
  cd backend && ../venv/bin/python scripts/train_xgboost_real.py --cv walkforward
  cat models/xgboost_signal_scorer_meta.json
  ./venv/bin/python -m pytest backend/tests/test_ml_validation.py -v
  ```
- **DoD:** meta con AUC OOS real + gate aplicado · tests de separación temporal · commit `[Ola4.2]`.

---

#### SP-4.3 — Motor de scoring pluggable (Heurístico vs ML) con etiqueta de fuente

- **Contexto:** el `/api/scan` calcula el `composite_score` con pesos manuales en `server.py:666-684` (SMA/RSI/momentum/volumen) sin validación estadística. El score ML existe (`scoring.compute_ml_score`) pero NO participa en el screener. El usuario cree que el score viene del modelo cuando es heurística.
- **Comportamiento (G/W/T):**
  - **GIVEN** una petición al screener
  - **WHEN** se calcula el score de cada ticker
  - **THEN** el objeto de cada ticker incluye `score_source: "heuristic" | "ml" | "ensemble"` y `components: { heuristic: <n>, ml: <n> | null, auc_gate: "passed"|"failed" }`, devuelto al frontend sin ambigüedad.
- **Criterios de aceptación:**
  1. `ScoringEngine` (nuevo módulo `app/services/scoring_engine.py`) con interfaz `score(features) → (value, source, components)`.
  2. Backward compatibility: los campos `composite_score` y `signal_strength_score` se mantienen para no romper el frontend, pero ahora alimentados por el engine.
  3. Cuando `promoted==false` (SP-4.2), la fuente es `heuristic` y el score ML aparece como `null`.
- **Tests (TDD, primero):**
  - `backend/tests/test_scoring_engine.py::test_heuristica_etiquetada`
  - `backend/tests/test_scoring_engine.py::test_ml_cuando_promoted`
  - `backend/tests/test_scoring_engine.py::test_ml_null_sin_promoted`
- **Verificación:** `pytest backend/tests/test_scoring_engine.py -v` + `curl /api/scan | jq '.[0].score_source'`.
- **DoD:** fuente de score transparente en API y UI · tests · commit `[Ola4.3]`.

---

#### SP-4.4 — Umbrales de muestra exigentes y warnings duros

- **Contexto:** `signal_evaluation.py:9-10` usa `MIN_TICKER_SAMPLE=3` y `MIN_TICKER_CONFIDENT=5`. Con 3 ocurrencias un ticker aparece en "Mejor comportamiento" sin warning prominente. En finanzas eso es noise floor.
- **Comportamiento (G/W/T):**
  - **GIVEN** un top/bottom ticker cuya muestra `count < 8`
  - **WHEN** la API devuelve signal stats
  - **THEN** el elemento incluye `sample_warning: "insufficient"` y el insight textual lo declara; la UI lo pinta con badge ámbar.
- **Criterios de aceptación:**
  1. Constantes reducidas: `MIN_TICKER_SAMPLE=8`, `MIN_TICKER_CONFIDENT=20`.
  2. `generate_insight` (o su equivalente en el nuevo motor) antecede "Datos insuficientes" cuando `count < 8`.
  3. `/api/signal-evaluation` incluye `sampling` por señal con `warning_level: "ok"|"limited"|"insufficient"`.
- **Verificación:** `pytest backend/tests/test_signal_evaluation.py -v` (actualizar fixtures a los nuevos umbrales).
- **DoD:** umbrales nuevos · warning por API + UI · tests actualizados · commit `[Ola4.4]`.

---

### OLA 5 — Rendimiento y concurrencia

#### SP-5.1 — Sacar `yfinance` del event loop

- **Contexto:** `run_scan` (server.py), `_fetch_live_price` (paper_trading.py:23), `evaluate_signals` (signal_evaluation.py:109) y `fetch_data` (backtester.py:13) hacen llamadas de red **bloqueantes** dentro del event loop. Eso satura la API con pocos usuarios concurrentes.

- **Comportamiento (G/W/T):**
  - **GIVEN** una request a un endpoint que consume datos de mercado
  - **WHEN** la fuente de datos está disponible
  - **THEN** la request nunca mantiene el event loop bloqueado >50 ms: el fetch ocurre via `run_in_executor` (thread pool limitado) o en background task, y la respuesta puede ser `202 Accepted` con estado de progreso.
- **Criterios de aceptación:**
  1. `_fetch_live_price` en paper trading pasa a `async` delegando a executor; los endpoints piden precios por lote (un solo fetch para N posiciones).
  2. Instrumentación en middleware reporta `api.p95_bloqueo`; debe quedar en 0 bloqueos >50 ms bajo prueba de carga local (30 requests concurrentes).
  3. `run_scan` background ya es async (background_scanner) — se le aplica mismo patrón de executor para el `yf.download`.
- **Verificación:** `./venv/bin/python -m pytest backend/tests -q` (los tests de paper trading existentes pasan con client async) + prueba de concurrencia con `hey`/`ab` de 30 hilos.
- **DoD:** 0 bloqueos >50 ms medidos · tests verdes · commit `[Ola5.1]`.

#### SP-5.2 — Paper trading: precios en lote y MTM asíncrono

- **Contexto:** `refresh_positions` (paper_trading.py:147) hace `_fetch_live_price` ticker a ticker (N llamadas yfinance), secuencial y bloqueante.
- **Comportamiento (G/W/T):**
  - **GIVEN** una cartera con N posiciones abiertas
  - **WHEN** se actualiza el MTM
  - **THEN** se realiza **una** llamada al proveedor para todos los tickers, se actualizan `current_price` juntos, y el endpoint de portfolio devuelve en <1 s con cache local de 15 s.
- **Criterios de aceptación:**
  1. `tests/test_api/test_paper_trading.py` verifica que `refresh_positions` usa el fetch en lote (mock de `batch_quote`).
  2. `get_portfolio` sin cambios de contrato (schema idéntico).
- **Verificación:** `pytest backend/tests/test_api/test_paper_trading.py -v`.
- **DoD:** fetch por lote · MTM sin bloqueo · tests · commit `[Ola5.2]`.

#### SP-5.3 — Signal Lab y Strategy Optimizer como background jobs

- **Contexto:** `/api/signal-evaluation` y `/api/strategy-optimization` ejecutan cálculos pesados sincrónicamente en la request.
- **Comportamiento (G/W/T):**
  - **GIVEN** una petición de análisis pesado
  - **WHEN** el servidor recibe la request
  - **THEN** responde `202` con `job_id`, y el frontend hace polling a `/api/jobs/{job_id}` hasta `status: "done"|"error"`; el resultado se cachea (Redis, TTL 1 h).
- **Criterios de aceptación:**
  1. Nuevo módulo `app/services/jobs.py` con almacén en Redis (estado + resultado).
  2. Toda llamada pesada usa el patrón de job; endpoints legacy quedan deprecados vía header.
  3. Test de integración: crear job → consultar estado → completar → consultar resultado.
- **Verificación:** `pytest backend/tests/test_api/test_jobs.py -v` + llamada real con `curl`.
- **DoD:** análisis pesados fuera de la request · polling funcional · tests · commit `[Ola5.3]`.

---

### OLA 6 — Persistencia unificada y entrega

#### SP-6.1 — Unificar `trades_history.db` e `iosef_finance.db`

- **Contexto:** hay fuentes de verdad paralelas: `backend/iosef_finance.db` (SQLAlchemy: users/paper), `data/trades_history.db` (historial de trades, 217 KB), `backend/data/trades_history.db`. La señal «trade history» que debe alimentar al reentrenamiento está fragmentada.
- **Comportamiento (G/W/T):**
  - **GIVEN** el nuevo esquema unificado (users, paper_accounts, paper_positions, paper_trades, trade_history)
  - **WHEN** se migra los datos existentes
  - **THEN** queda un solo archivo de DB activo (el de `DATABASE_URL`), sin pérdida de trades históricos y con `alembic` versionando el esquema.
- **Criterios de aceptación:**
  1. Script de migración `scripts/unify_trades_db.py` reporta conteo de trades antes/después y migra sin duplicados (idempotente).
  2. `get_history` endpoint usa el esquema unificado.
  3. `data/trades_history.db` y `backend/data/trades_history.db` quedan como legacy con `README-migration.md`.
- **Verificación:** `../venv/bin/python scripts/unify_trades_db.py --dry-run` luego `--apply` + `pytest`.
- **DoD:** 1 DB activa · migración idempotente documentada · commit `[Ola6.1]`.

#### SP-6.2 — CI/CD como gate

- **Contexto:** existe `.github/workflows/ci.yml` (untracked en git, requiere validación). Sin gate real: los push/PR a `main` no están protegidos por tests.
- **Comportamiento (G/W/T):**
  - **GIVEN** un PR a `main`
  - **WHEN** CI ejecuta (backend pytest + frontend build/test)
  - **THEN** si algún paso falla, el PR queda bloqueado (branch protection `required status checks`) y se puede inspeccionar el reporte en el workflow.
- **Criterios de aceptación:**
  1. Workflow validado: ejecuta suite completa en ~7 min, sin dependencias del entorno local del usuario (usa `requirements.txt`/`pyproject`, no `/Users/...`).
  2. GitHub: regla de rama con `ci/backend` y `ci/frontend` como required.
  3. Un PR de prueba con un test roto — el CI bloquea el merge (verificado en repo).
- **Verificación:** push de prueba a un branch + revisar checks en GitHub.
- **DoD:** CI verde en repo · branch protection configurado · commit `[Ola6.2]`.

#### SP-6.3 — Healthchecks y degradación graceful

- **Contexto:** el healthcheck existe (`/api/health`) pero no expone dependencias; Redis y yfinance están implícitos.
- **Comportamiento (G/W/T):**
  - **GIVEN** Redis caído o yfinance con error
  - **WHEN** se consulta `/api/health`
  - **THEN** responde `{"status":"degraded", "dependencies":{"redis":"down","data_provider":"error","database":"ok"}}` (HTTP 200 si core funciona, 503 si DB no) y los endpoints críticos degradan a cache en vez de fallar.
- **Criterios de aceptación:**
  1. `health_check()` incluye `redis` (ping), `database` (SELECT 1), `data_provider` (último timestamp de scan exitoso).
  2. Comportamiento documentado y testeado con mocks (Redis down → `/api/scan` sirve snapshot parquet/JSON).
- **Verificación:** `pytest backend/tests/test_health.py -v`.
- **DoD:** health con dependencias · degradación testeada · commit `[Ola6.3]`.

#### SP-6.4 — Logging estructurado

- **Contexto:** logs mixtos con `print` (server.py:983), `logging` básico y prints de uvicorn. Imposible correlacionar errores por request o hacer dashboards.
- **Comportamiento (G/W/T):**
  - **GIVEN** una petición con `X-Request-Id`
  - **WHEN** el backend registra eventos
  - **THEN** todos los logs son JSON con `timestamp`, `level`, `request_id`, `route`, `latency_ms`; el `request_id` se propaga a llamadas a Redis/DB.
- **Criterios de aceptación:**
  1. Middleware genera `request_id` (o respeta el header) y lo inyecta en el logger vía `contextvars`.
  2. Se eliminan `print` del código de servicios (server.py, paper_trading.py, etc.).
  3. Test: `caplog` captura un log JSON con `request_id`.
- **Verificación:** `pytest backend/tests/test_logging.py -v`.
- **DoD:** logs JSON con correlación · sin `print` residual · commit `[Ola6.4]`.

---

### OLA 7 — Hardening y monitoreo

#### SP-7.1 — Monitoreo de drift de modelos

- **Contexto:** los modelos entrenados (XGBoost, LSTM) no tienen supervisión de drift; se degradan sin alerta (riesgo señalado por la auditoría).
- **Comportamiento (G/W/T):**
  - **GIVEN** un modelo en producción
  - **WHEN** las distribuciones de features (o livescores) se desvían >2σ respecto a la referencia de entrenamiento
  - **THEN** `/api/ml/model-info` reporta `drift: "stable"|"watch"|"alert"` y se emite una alerta log/endpoint para el equipo.
- **Criterios de aceptación:**
  1. `app/services/drift_monitor.py`: ventana deslizante de features (log_return, volatility_20, momentum_10, rsi_14, macd_hist) con PSI/K-S vs entrenamiento.
  2. Estado persistido en Redis (TTL 1 h) y expuesto en `/api/ml/model-info`.
  3. Test con feature shift artificial → `drift=alert`.
- **Verificación:** `pytest backend/tests/test_drift_monitor.py -v` + `curl /api/ml/model-info`.
- **DoD:** drift monitor activo + alerta · commit `[Ola7.1]`.

#### SP-7.2 — Cliente API centralizado en frontend

- **Contexto:** las llamadas al backend usan `fetch` dispersas con `VITE_API_BASE` repetido; el fix de CORS/URLs se ha tocado a mano (ver sprint 11). Riesgo de URLs sueltas.
- **Comportamiento (G/W/T):**
  - **GIVEN** cualquier componente que necesite la API
  - **WHEN** invoca una función de `src/lib/api.ts`
  - **THEN** se usa un único `fetchJson` con: base de `import.meta.env.VITE_API_BASE`, timeout, handling de 401 (refresh/logout), y errores tipados (`ApiError`).
- **Criterios de aceptación:**
  1. `grep -r "fetch(" frontend-v2/src` no devuelve `fetch` fuera de `src/lib/api.ts`.
  2. Tests unitarios de `api.ts` (mock fetch) cubren 200, 401 y timeout.
- **Verificación:** `cd frontend-v2 && npm test`.
- **DoD:** cliente único · tests de red · commit `[Ola7.2]`.

#### SP-7.3 — Eliminar `any` y tipar errores

- **Contexto:** frontend con `tsconfig` que permite `any`; errores extraídos con `(error as any).message` en múltiples sitios.
- **Comportamiento (G/W/T):**
  - **GIVEN** un tsconfig con `noImplicitAny` y `strict`
  - **WHEN** se compila/build
  - **THEN** hay 0 usos de `any` y los errores se tipan vía `ApiError`/`Result<T>`.
- **Criterios de aceptación:**
  1. `tsconfig.app.json` con `"noImplicitAny": true` y `"strict": true`.
  2. `eslint` pasa sin reglas desactivadas para `any` (`@typescript-eslint/no-explicit-any`).
- **Verificación:** `cd frontend-v2 && npm run lint && npm run build`.
- **DoD:** build estricto · 0 `any` · commit `[Ola7.3]`.

#### SP-7.4 — E2E críticos (login → scan → paper trade)

- **Contexto:** sin pruebas E2E del viaje completo del usuario; regresiones tipo SYK-401 (sprint 11) pueden reaparecer.
- **Comportamiento (G/W/T):**
  - **GIVEN** un usuario con credenciales válidas
  - **WHEN** se ejecuta la suite E2E (Playwright)
  - **THEN** el flujo login → dashboard → abrir ticker → ejecutar paper trade cierra con estado `completed` y el portfolio refleja la operación.
- **Criterios de aceptación:**
  1. `frontend-v2/e2e/` con 3 specs: `login.spec.ts`, `scan.spec.ts`, `paper-trade.spec.ts`.
  2. Se corre contra el stack local (backend en 8002 + frontend dev server) sin mocks de red para verificar integración real.
- **Verificación:** `cd frontend-v2 && npx playwright test`.
- **DoD:** E2E verde contra stack local · commit `[Ola7.4]`.

---

## 5. Plan de ejecución con bucles

### 5.1 Orden y dependencias

```
Ola 3 (estabilización)  ───►  Ola 4 (validez cuantitativa)  ───►  Ola 5 (rendimiento)
        │                              │                                  │
        └────► Ola 6 (entrega) ◄───────┘                                  │
                        └────────────────────────► Ola 7 (monitoreo/E2E) ◄┘
```

Dependencias clave:
- SP-3.2 y SP-3.3 **antes** de cualquier refactor de servicios (config correcta evita debugging a ciegas).
- SP-3.1 **antes** de Ola 5 (el cache parquet debe ser fiable para servir datos sin bloquear).
- SP-4.1 y SP-4.2 **independientes entre sí**, pero ambas **antes** de SP-4.3 (el engine necesita el gate y el modelo de costos).
- SP-6.1 depende de SP-3.2 (fuente única de URL) y de SP-3.4 (migraciones).

### 5.2 Cadencia de bucles sugerida

| Ola | Duración estimada | Bucles internos | Gate de salida |
|---|---|---|---|
| 3 | 2–3 días | 5 items × (1–2 bucles) | 100% tests + scan sin errores parquet |
| 4 | 4–5 días | 4 items × (2–3 bucles, los cuant viven su propio bucle interno de experimentación) | AUC OOS reportado + backtester con costos |
| 5 | 3–4 días | 3 items × (1–2 bucles) | 0 bloqueos >50 ms + MTM < 1 s |
| 6 | 2–3 días | 4 items × (1 bucle) | CI verde en repo + 1 DB |
| 7 | 3–4 días | 4 items × (1–2 bucles) | drift monitor live + E2E verde |

Total: **~2 semanas de desarrollo enfocado** para pasar de "MVP sin edge demostrable" a "sistema con validación cuantitativa y entrega con gate".

### 5.3 Regla de retroalimentación (bucle 4)

Al cerrar cada ola, el CHANGELOG de la ola debe responder 4 preguntas:
1. ¿Qué métricas de §1.3 mejoraron y cuánto?
2. ¿Qué Spec se atrasó y por qué (se mueve a la ola siguiente o se canceló)? 
3. ¿Qué supuesto financiero/cuantitativo se confirmó o refutó con datos?
4. ¿Qué ítem nuevo del backlog aparece como consecuencia?

---

## 6. Riesgos y rollback

| Riesgo | Mitigación |
|---|---|
| Corregir el parquet rompe el formato actual | Backup del payload JSON/Redis previo (`cache/parquet/` es prescindible; nunca es única fuente). |
| Reentrenar XGBoost degrada el score actual | El gate AUC ≥ 0.56 **impide** el despliegue automático; el modelo vigente sigue en `compute_ml_score` hasta que el nuevo pase. |
| Refactor a jobs async rompe endpoints del frontend | Endpoints legacy mantienen contrato; se deprecan por header y se migra el frontend en la misma ola. |
| Migración de DB pierde trades | `--dry-run` obligatorio; backup de los 3 archivos `.db` en `auditoria_integral_2026/ola6/backup_antes.md`. |
| `yfinance` sin SLA durante Ola 5 | Todos los refactors toleran fallo de proveedor: cache por TTL + snapshot parquet como fallback. |

---

## 7. Conclusión

El plan convierte la deuda identificada en **19 specs accionables** organizadas en 5 olas, donde **ningún trabajo se cierra sin evidencia medible** (loop engineering) y **ningún código se escribe sin contrato previo** (spec-driven development). Con ~2 semanas de ejecución disciplinada, `Iosef Finance` deja de ser "un MVP que funciona" y pasa a ser "un sistema que **puede demostrar** si su edge existe".

---

*Anexos referenciados: `docs/specs/_TEMPLATE.md` · `auditoria_integral_2026/` · `docs/MANUAL_ARRANQUE.md`*
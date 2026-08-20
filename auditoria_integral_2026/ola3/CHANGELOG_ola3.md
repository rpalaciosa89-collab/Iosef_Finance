# Ola 3 — Estabilización y Configuración Única — CHANGELOG

**Fecha:** 2026-08-20
**Metodología:** Spec-Driven Development + Loop Engineering (plan `docs/plan_mejoras_sdd_loop_engineering.md`)
**Estado previo:** 52 tests | parquet cache roto | config divergente | 2 entrypoints | SQLite sin WAL/migraciones

---

## Resumen

Cerradas 5 specs de la Ola 3. La plataforma ahora arranca con configuración unificada,
cache parquet funcional, migraciones versionadas y validación de inputs. Todos los cambios
fueron commit atómicos `[Ola3.X]` y pusheados a `origin/main`.

## Specs Cerradas

| ID | Título | Estado |
|---|---|---|
| SP-3.1 | Fix cache parquet (round-trip tipos mixtos) | ✅ |
| SP-3.2 | Cargar `.env` real (unificar DATABASE_URL) | ✅ |
| SP-3.3 | Unificar CORS y eliminar entrypoint secundario | ✅ |
| SP-3.4 | SQLite WAL + migraciones Alembic | ✅ |
| SP-3.5 | Validación de ticker en endpoints | ✅ |

## Métricas de Bucle (registro obligatorio)

| Métrica | Antes | Después | Target |
|---|---|---|---|
| `back.tests_verdes` | 52 | **77** | 100% |
| `back.tests_tiempo` | 104 s | **73 s** | < 5 min |
| `front.build_ok` | — | ✅ exit 0 | exit 0 |
| `scan.cache_ok` | ❌ `[parquet] Write error` en cada scan | ✅ escribe+lee 98 tickers | 3 scans sin error |
| `db.unificado` | 3 candidatas + `.env` ignorado | **1 activa** (`sqlite:///./iosef_finance.db`, reportada en `/api/health`) | 1 |
| `db.wal` | no | **WAL activo** | wal |
| `db.drift_alembic` | sin migraciones | **0 drift** (`alembic check`) | 0 |

## Commits

```
aed5953 [Ola3.1] fix(cache): reparar cache parquet con blob JSON (round-trip tipos mixtos)
686470b [Ola3.2] config: cargar .env real, unificar DATABASE_URL via settings, health reporta DB
ff2b9c9 [Ola3.3] refactor: eliminar entrypoint app/main.py, CORS unico desde CORS_ORIGINS
e2c6397 [Ola3.4] db: activar SQLite WAL y migraciones Alembic (esquema inicial + stamp DB real)
ad100fa chore: excluir artefactos SQLite WAL (db-shm, db-wal) del repo
4019604 [Ola3.5] security: validar ticker en schema paper-trading y endpoint backtest
```

## Retrospectiva (bucle 4)

1. **Qué mejoró y cuánto:** tests 52→77 (+48%); parquet cache operativo; config unificada; WAL + Alembic; validación de inputs.
2. **Qué se atrasó:** nada. Todos los ítems en el tiempo previsto.
3. **Supuesto confirmado:** el runtime realmente usaba `./iosef_finance.db` (no el `.env`) — confirmado al exponer la DB en `/api/health`.
4. **Nuevos ítems para backlog:**
   - Refactor del `startup_event` (deprecation warning de FastAPI `on_event`).
   - `datetime.utcnow()` deprecado en `security.py`, `server.py`, modelos (migrar a `datetime.now(UTC)`).
   - Rate limiting de yfinance: considerar proveedor secundario o backoff.
   - Reducir warnings de pytest (2380 → objetivo < 200).

## Estado Actual

- **Tests:** 77 passed
- **Build frontend:** OK
- **Runtime:** backend en 8002 con health `{"status":"ok","database":"sqlite:///./iosef_finance.db"}`
- **Siguiente ola:** Ola 4 — Validación cuantitativa (SP-4.1 backtester con costos/benchmark, SP-4.2 walk-forward XGBoost)
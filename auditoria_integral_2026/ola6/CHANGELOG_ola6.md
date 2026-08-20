# Ola 6 — Persistencia Unificada y Entrega — CHANGELOG

**Fecha:** 2026-08-20
**Metodología:** Spec-Driven Development + Loop Engineering
**Estado previo:** 3 fuentes de DB | CI sin alembic check | health sin dependencias | logs mixtos con print

---

## Specs Cerradas

| ID | Título | Estado |
|---|---|---|
| SP-6.1 | Unificar persistencia de trades en la DB SQLAlchemy | ✅ |
| SP-6.2 | CI/CD como gate (workflow + alembic check) | ✅ |
| SP-6.3 | Healthchecks con dependencias + degradación graceful | ✅ |
| SP-6.4 | Logging estructurado JSON + request_id | ✅ |

## Métricas de Bucle

| Métrica | Antes | Después | Target |
|---|---|---|---|
| `back.tests_verdes` | 111 | **120** | 100% |
| `db.unificado` | persistence en `data/trades_history.db` paralela | **1 DB** (`iosef_finance.db`, WAL) | 1 |
| `ci.gate` | workflow sin alembic | pytest + **alembic check** + frontend | gate completo |
| `health.deps` | solo status/service | **redis + database + data_provider** | 3 deps |
| `logs.formato` | prints + logging plano | **JSON con request_id, route, latency_ms** | JSON |
| `logs.prints` | 15 prints en servicios | **0** (fuera de `__main__`) | 0 |

## Commits

```
cfd288b [Ola6.1] refactor(db): unificar persistencia de trades en la DB SQLAlchemy
9f5c5b1 [Ola6.2+6.3] ci: workflow con alembic check; health con dependencias + degradacion
3163288 [Ola6.4] feat(logging): logging estructurado JSON con request_id
```

## Retrospectiva (bucle 4)

1. **Qué mejoró:** una sola DB para todo (WAL + migraciones); CI valida drift de esquema; health diagnostica Redis/DB/proveedor; logs correlacionables por request_id.
2. **Qué se atrasó:** nada.
3. **Supuesto confirmado:** las DBs legacy de trades estaban vacías — la unificación no perdió datos; el código que escribía en el archivo paralelo ahora escribe en la DB unificada (contrastado con tests).
4. **Nuevos ítems:** backend de trades debería migrar a tabla SQLAlchemy (hoy `sqlite3` directo sobre el mismo archivo — funcional pero no ORM); branch protection en GitHub pendiente de configurar manualmente.

## Estado Actual

- **Tests:** 120 passed
- **Siguiente ola:** Ola 7 — Hardening (drift monitor, cliente API frontend, tipado, E2E)
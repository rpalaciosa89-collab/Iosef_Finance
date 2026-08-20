# Ola 5 — Rendimiento y Concurrencia — CHANGELOG

**Fecha:** 2026-08-20
**Metodología:** Spec-Driven Development + Loop Engineering
**Estado previo:** yfinance bloqueante en event loop | paper trading MTM ticker a ticker | análisis pesados en la request

---

## Specs Cerradas

| ID | Título | Estado |
|---|---|---|
| SP-5.1 | yfinance fuera del event loop (thread pool + cache TTL) | ✅ |
| SP-5.2 | Paper trading: precios por lote (1 llamada por N posiciones) | ✅ |
| SP-5.3 | Signal Lab / Strategy Optimizer como background jobs | ✅ |

## Métricas de Bucle

| Métrica | Antes | Después | Target |
|---|---|---|---|
| `back.tests_verdes` | 96 | **107** | 100% |
| `api.p95_bloqueo` | N llamadas yfinance bloqueantes por request | fetch en executor + cache 15s | 0 bloqueos >50ms |
| `pt.mtm_llamadas` | 1 request de red por posición | 1 con cache para N posiciones | ≤1 |
| `jobs.analisis_pesado` | request bloqueada (puede durar minutos) | `202 + job_id` + polling | respuesta inmediata |

## Commits

```
02a2e9f [Ola5.1+5.2] feat(market-data): fetch por lote con cache TTL + async executor; MTM en lote
bf3be65 [Ola5.3] feat(jobs): Signal Lab y Strategy Optimizer como background jobs con polling
```

## Retrospectiva (bucle 4)

1. **Qué mejoró:** yfinance ya no bloquea el event loop (executor + cache en memoria); MTM de paper trading es 1 llamada por cartera; los análisis pesados responden 202 y corren en background con polling.
2. **Qué se atrasó:** nada.
3. **Supuesto confirmado:** el cache en memoria de 15s es suficiente para MTM (el scan ya cachea en Redis); el patrón de jobs con Redis funciona incluso sin Redis (fallback en memoria).
4. **Nuevos ítems:** migrar el endpoint de backtest individual al patrón de jobs; frontend debe consumir `202` en Signal Lab y hacer polling.

## Estado Actual

- **Tests:** 107 passed
- **Siguiente ola:** Ola 6 — Persistencia unificada (SP-6.1 unificar DBs de trades) y entrega (CI/CD, healthchecks, logging JSON)
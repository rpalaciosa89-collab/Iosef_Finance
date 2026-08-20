# Ola 7 — Hardening y Monitoreo — CHANGELOG

**Fecha:** 2026-08-20
**Metodología:** Spec-Driven Development + Loop Engineering
**Estado previo:** sin drift monitor | fetch dispersos en frontend | tsconfig sin strict | sin E2E

---

## Specs Cerradas

| ID | Título | Estado |
|---|---|---|
| SP-7.1 | Monitoreo de drift de modelos (PSI stable/watch/alert) | ✅ |
| SP-7.2 | Cliente API centralizado frontend (ApiError, timeout, 401) | ✅ |
| SP-7.3 | Tipado estricto frontend (strict + noImplicitAny, 0 anys) | ✅ |
| SP-7.4 | E2E críticos (login → scan → paper trade) | ✅ |

## Métricas de Bucle

| Métrica | Antes | Después | Target |
|---|---|---|---|
| `back.tests_verdes` | 120 | **126** | 100% |
| `front.tests_verdes` | 9 | **9 + 4 E2E** | 100% |
| `front.strict` | sin strict, 15 anys | **strict + noImplicitAny, 0 anys** | 0 anys |
| `front.fetch_disperso` | fetch en AuthContext + api.ts | **solo api.ts** | 1 capa |
| `ml.drift` | sin monitoreo | **PSI con stable/watch/alert** en /api/model-info | activo |
| `e2e.flujo` | 0 | **4 specs verdes** (login ok/error, scan, paper trade) | 4 |

## Commits

```
66486e3 [Ola7.1] feat(ml): drift monitor PSI con niveles stable/watch/alert
9159dcb [Ola7.2] feat(frontend): cliente API centralizado con ApiError tipado
a3ae5c6 [Ola7.3] refactor(frontend): tsconfig strict + noImplicitAny, 0 anys
0932040 [Ola7.4] test(e2e): Playwright login/scan/paper trade + job CI
```

## Retrospectiva (bucle 4)

1. **Qué mejoró:** drift monitoreado por PSI; frontend con una sola capa HTTP tipada; build estricto sin `any`; flujo completo del usuario cubierto por E2E en CI.
2. **Qué se atrasó:** nada. 
3. **Supuesto confirmado:** los tipos reales del backend son más ricos que los asumidos (IntradayBar.time es unix int; BacktestResult usa total_return_pct) — el strict obligó a descubrir y documentar el contrato real.
4. **Deuda residual documentada:** 15 errores de lint `react-hooks` (setState en effects, useMemo condicional) en código pre-existente — requieren refactor estructural de componentes (fuera del alcance de las olas 3-7).

## Estado Final del Programa (Olas 3-7)

| Dimensión | Inicio (2026-08-20) | Final |
|---|---|---|
| Tests backend | 52 | **126** (+142%) |
| Tests frontend | 2 | **9 unit + 4 E2E** |
| Edge ML | AUC 0.552 sin validar (falso edge) | **AUC OOS 0.5037 medido, gate honesto** |
| Backtester | mock sin costos | **costos + SPY + IR/Sortino/PF** |
| Config | 3 DBs, 2 entrypoints, .env ignorado | **1 DB + WAL + Alembic + 1 entrypoint** |
| Rendimiento | yfinance bloqueante | **executor + cache + jobs async** |
| Observabilidad | prints | **logs JSON con request_id + health deps** |
| Entrega | sin CI efectivo | **CI pytest+alembic+frontend+E2E** |
| Seguridad inputs | parcial | **validación ticker en todos los endpoints** |
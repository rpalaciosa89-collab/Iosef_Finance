# Ola 4 — Validación Cuantitativa (el corazón del producto) — CHANGELOG

**Fecha:** 2026-08-20
**Metodología:** Spec-Driven Development + Loop Engineering
**Estado previo:** backtester mock sin costos | XGBoost con AUC 0.552 (no validado temporalmente) | score screener no etiquetado | umbrales de muestra de 3/5

---

## Resumen

Cerradas 4 specs de la Ola 4. **El hallazgo más importante:** con validación temporal
honesta (walk-forward + embargo), el modelo XGBoost tiene **AUC OOS = 0.5037** — NO
tiene edge demostrable. El gate lo detectó y archivó el modelo. La plataforma ahora
es honesta: el ML score devuelve 50 (sin señal) hasta que un retrain real supere el umbral.

## Specs Cerradas

| ID | Título | Estado |
|---|---|---|
| SP-4.1 | Backtester con costos/slippage/benchmark SPY + métricas estandarizadas | ✅ |
| SP-4.2 | XGBoost walk-forward + gate AUC ≥ 0.56 | ✅ |
| SP-4.3 | Motor de scoring pluggable (heurística vs ML) con etiqueta de fuente | ✅ |
| SP-4.4 | Umbrales de muestra exigentes + warnings duros | ✅ |

## Métricas de Bucle

| Métrica | Antes | Después | Target |
|---|---|---|---|
| `back.tests_verdes` | 77 | **96** | 100% |
| `ml.auc_oos` | no medido | **0.5037** (3 folds, embargo 5d) | ≥ 0.56 para promover |
| `ml.promoted` | asumido | **false → archived** | gate honesto |
| `ml.score_fallback` | usaba modelo sin gate | **50.0 (sin señal)** | 50 si no promovido |
| `bt.cost_model` | ❌ sin costos | ✅ comisión 10bps + slippage 5bps | 100% reportes |
| `bt.benchmark` | ❌ | ✅ SPY en todos los reportes (IR, Sortino, DD) | 100% |
| `score.transparencia` | ❌ score sin fuente | ✅ `score_source` + `score_components` + `auc_gate` | siempre etiquetado |
| `sample.umbrales` | 3/5 | **8/20** + `sampling.warning_level` | ≥8/≥20 |

## Commits

```
fe80db2 [Ola4.1] feat(backtest): motor con costos/slippage, benchmark SPY y metricas estandarizadas
53c0269 [Ola4.2] feat(ml): walk-forward + gate AUC>=0.56. Retrain honesto: AUC OOS 0.5037 -> archivado
809ae1a [Ola4.3] feat(scoring): motor pluggable heuristica/ML con etiqueta de fuente
f43b6c3 [Ola4.4] feat(signals): umbrales de muestra exigentes + sampling.warning_level
```

## Retrospectiva (bucle 4)

1. **Qué mejoró y cuánto:** tests 77→96 (+25%); backtester realista con costos y benchmark; ML gateado con evidencia; transparencia total del origen del score.
2. **Qué se atrasó:** nada.
3. **Supuesto confirmado (crítico):** el AUC OOS 0.5037 confirma que el XGBoost **no predice mejor que azar**. El AUC "test" de 0.553 que reportaba el pipeline anterior era optimista (leakage por split aleatorio temporal). **Decisión de producto:** no exponer ML score como certeza hasta superar el gate.
4. **Nuevos ítems para backlog (Ola 5/6):**
   - Investigar features más informativas (volumen, sector relativo, microestructura) para un retrain con posibilidades de superar el gate.
   - LSTM global: aplicar el mismo walk-forward gate (hoy no está gateado).
   - El screener usa ahora el engine etiquetado: revisar que el frontend muestre el badge de fuente.

## Estado Actual

- **Tests:** 96 passed
- **ML:** archivado (honesto) — el producto ya no muestra "certeza ML" falsa
- **Backtester:** con costos + SPY + métricas estándar
- **Siguiente ola:** Ola 5 — Rendimiento y concurrencia (yfinance fuera del event loop, paper trading por lote, jobs async)
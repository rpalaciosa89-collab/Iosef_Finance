# Investigación de Edge — XGBoost v2 (AUC Gate)

**Fecha:** 2026-08-20
**Estado:** Concluida — veredicto negativo documentado
**Relacionado:** SP-4.2 (gate AUC ≥ 0.56) · SP-4.3 (scoring pluggable)

---

## Hipótesis probadas

| # | Hipótesis | Resultado |
|---|---|---|
| H1 | El XGBoost v1 (AUC test 0.553) tenía edge real | ❌ Refutada: AUC OOS 0.5037 (leakage en el split aleatorio) |
| H2 | Más features (volumen, ATR, gap, fuerza relativa, distancia SMA, rango) mejoran la predicción | ❌ Refutada: v2 = 0.4903 vs v1 = 0.4931 (label outperform) |
| H3 | El label correcto es "outperform del mercado" (no la mediana propia) | ❌ No genera edge (0.49 en todas las ventanas) |
| H4 | Otras ventanas (1/5/10/20 días) tienen señal | ❌ Refutada: todas entre 0.48–0.50 |

## Evidencia (walk-forward 3 folds, embargo = ventana)

| Experimento | AUC OOS | Promoted |
|---|---|---|
| fwd1_outperform | 0.5027 | no |
| fwd1_median | 0.5026 | no |
| fwd5_outperform (v2 features) | 0.4903 | no |
| fwd5_median | 0.4973 | no |
| fwd10_outperform | 0.4814 | no |
| fwd10_median | 0.4862 | no |
| fwd20_outperform | 0.4863 | no |
| fwd20_median | 0.4907 | no |
| fwd5_outperform (v1 features) | 0.4931 | no |
| fwd5_median (v1 features, reporte original) | 0.5037 | no |

Reportes completos: `models/research_v2_report.json`, `models/research_grid_report.json`

## Veredicto científico

**Con features de precio/volumen (OHLCV) y XGBoost estándar, no existe edge
predictivo de dirección en el universo Titan 100 a horizontes de 1–20 días.**
Todas las AUC OOS están dentro del ruido de 0.48–0.51, y ninguna alcanza el
umbral de promoción de 0.56. Esto es consistente con la literatura de mercados
eficientes: la acción del precio a corto plazo no contiene señal direccional
explotable con modelos lineales/árboles sobre 2 años de datos.

## Decisión de negocio (recomendada)

1. **NO desplegar ML direccional** en producción. El gate lo impide correctamente.
2. **Pivotar el producto**: el screener es un *filtro de atención* (heurística
   etiquetada como tal), NO un predictor. La interfaz ya lo refleja
   (`score_source: heuristic`, `ml: null`).
3. **Investigar edge alternativo** si se quiere ML en el futuro:
   - Datos no-OHLCV: fundamentales, flujo de órdenes, microestructura, sentimiento.
   - Horizonte mayor (mensual/trimestral) con datos de 5–10 años.
   - Modelo de *riesgo* (volatilidad, drawdown) en vez de dirección — más
     plausible y con valor real para gestión de cartera.
   - Backtest de la heurística del screener como estrategia de *ranking*
     (no de dirección) para validar si el filtro aporta alfa.
4. **Mantener el gate AUC ≥ 0.56**: es el seguro contra el autoengaño.

## Estado del pipeline

- El modelo en producción queda **archivado** (`promoted: false`) — ML score = 50.
- El reporte queda versionado para re-abrir la investigación con datos nuevos.
- Scripts reutilizables: `scripts/research_features_v2.py`, `scripts/research_grid.py`.
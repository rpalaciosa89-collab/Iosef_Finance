# Plan Quirúrgico de Corrección — Iosef Finance

**Rol dual:**
- **Ejecutor:** Ingeniero de software cuantitativo senior. Experiencia en ML aplicado a
  finanzas, backtesting riguroso, y deployment de modelos en producción.
- **Revisor (en cada paso):** Ingeniero Financiero Senior, 25 años en Wall Street
  (mismo del informe de evaluación). No ejecuta — verifica, cuestiona, exige
  evidencia numérica, y detiene el proceso si algo no cumple.

**Objetivo:** Transformar Iosef Finance de una herramienta "CONDICIONAL" (edge real
pero frágil) a una herramienta **predictiva efectiva** donde cada componente esté
respaldado por evidencia estadística, cada decisión de diseño tenga justificación
matemática, y el inversor reciba señales en las que pueda confiar.

**Regla de oro:** Ningún paso avanza sin que el Revisor dé el visto bueno con un
número. "Se ve bien" no es un visto bueno. "+0.15% de mejora en Sharpe" sí lo es.

**Principio de no regresión:** Cada cambio debe preservar o mejorar todo lo que ya
funciona. Si un fix rompe algo que antes funcionaba, se revierte y se reconsidera.

---

## Filosofía del plan

Este plan sigue tres principios industriales:

1. **Mejora continua (Kaizen):** Cambios pequeños, medibles, iterativos. Nada de
   refactors masivos. Cada paso toca un archivo, un concepto, una métrica.

2. **Integridad de datos (Single Source of Truth):** Todos los módulos deben
   beber de la misma fuente. Si dos partes de la app calculan RSI diferente,
   una de las dos está mintiendo.

3. **Validación independiente (Out-of-sample testing):** Todo modelo se prueba
   con datos que nunca vio. El backtesting incluye costos reales, slippage, y
   sesgo de supervivencia.

---

## Fase 0 — Preparación: Infraestructura de validación

**Antes de tocar una sola línea de código predictivo**, necesitamos poder medir
si los cambios mejoran o empeoran las predicciones.

### Paso 0.1 — Crear test harness de backtesting

**Archivo nuevo:** `backend/tests/test_financial_validation.py`

**Qué hace:**
- Carga el modelo XGBoost actual (el .json o .pkl en disco)
- Corre backtesting walk-forward sobre los últimos 12 meses de datos del Titan 100
- Calcula métricas pre-fix para tener baseline:
  - Win rate por tipo de señal
  - Retorno medio, mediano
  - Sharpe ratio
  - Maximum drawdown
  - Profit factor (ganancias totales / pérdidas totales)
  - Calmar ratio

**Salida esperada:** Un archivo `backend/data/baseline_metrics_YYYY-MM-DD.json`
con todas las métricas. Este archivo es **sagrado** — es la referencia contra la
que se comparará cada cambio.

**Criterio de aceptación del Revisor:**
- [ ] El test harness corre en < 5 minutos
- [ ] Las métricas son reproducibles (misma semilla = mismos resultados)
- [ ] El baseline está documentado con fecha y commit hash

---

### Paso 0.2 — Establecer umbrales de aceptación

**Archivo a modificar:** `backend/tests/test_financial_validation.py`

**Qué hace:** Define los umbrales mínimos que cualquier nueva versión del modelo
debe superar para ser aceptada:

```python
ACCEPTANCE_THRESHOLDS = {
    "sharpe_ratio": 0.3,          # Minimo absoluto (>0 significa que hay edge)
    "win_rate_global": 0.52,      # Debe ser > 50% con IC 95%
    "max_drawdown": -0.25,        # No mas de 25% de drawdown
    "profit_factor": 1.05,        # Ganancias > Perdidas por al menos 5%
    "calmar_ratio": 0.2,          # Retorno anualizado / max drawdown
}
```

**Criterio de aceptación del Revisor:**
- [ ] Los umbrales son alcanzables por el modelo actual (si no, ajustar)
- [ ] Los umbrales son lo suficientemente exigentes para filtrar modelos malos
- [ ] Documentar por qué cada umbral tiene ese valor

---

## Fase 1 — Corrección del Label de Entrenamiento (Hallazgo #1, CRÍTICO)

**Problema:** El modelo predice `retorno_5d > mediana(ticker)` en vez de `retorno_5d > 0`.
El inversor no gana dinero con "caer menos que el promedio".

### Paso 1.1 — Crear nuevo script de entrenamiento con label correcto

**Archivo nuevo:** `backend/scripts/train_xgboost_v3.py`

**Qué hace:**
- Reentrena el XGBoost desde cero con el dataset histórico de 2 años
- **Nuevo label:** `y = 1` si `close[t+5] > close[t]`, `y = 0` en caso contrario
- Mismas features: log_return, volatility_20, momentum_10, rsi_14, macd_hist
- Mismos hiperparámetros (por ahora — solo cambiamos el label)
- Guarda el modelo como `backend/data/xgb_model_v3_direction.json`

**Buenas prácticas aplicadas:**
- Train/validation/test split temporal (no aleatorio — en finanzas el tiempo importa)
- Los últimos 3 meses son test set (out-of-sample puro)
- Validación cruzada walk-forward con 6 folds de 2 meses cada uno
- Feature importance report (para entender qué features impulsan la predicción)

**Criterio de aceptación del Revisor:**
- [ ] El accuracy out-of-sample es significativamente > 50% (test binomial, p < 0.05)
- [ ] El modelo nuevo NO puede tener peor Sharpe que el baseline del Paso 0.1
- [ ] Si accuracy < 52%, detener — el label de dirección absoluta es más difícil
  de predecir (esperado). Documentar la diferencia.
- [ ] Las features más importantes tienen sentido económico (no es ruido)

**Verificación numérica obligatoria:**
```
Accuracy baseline (outperf relativa): X%
Accuracy v3     (dirección absoluta): Y%
Diferencia: Y - X = Z pp
¿Z es aceptable dado que el problema es inherentemente más difícil? SÍ/NO
```

---

### Paso 1.2 — Validación estadística del nuevo modelo

**Archivo:** `backend/scripts/train_xgboost_v3.py` (mismo script, sección de validación)

**Qué hace:**
- Calcula el intervalo de confianza al 95% del accuracy out-of-sample
- Calcula el p-value de un test binomial contra H0: accuracy = 50%
- Genera curva ROC y calcula AUC
- Calcula el distribution shift entre train y test (¿hay data drift?)
- Genera calibration plot (¿el modelo está bien calibrado? ¿P=70% realmente gana 70%?)

**Criterio de aceptación del Revisor:**
- [ ] p-value del test binomial < 0.05 (el modelo es mejor que una moneda)
- [ ] AUC > 0.52 (mínimo para tener edge práctico)
- [ ] No hay data drift significativo (KS test train vs test < 0.15)
- [ ] La calibración es razonable: el bucket de "P entre 55-60%" gana entre 55-60% de las veces

**Si el modelo NO pasa estos tests → FASE 1 FRACASÓ. No continuar.**

Significa que predecir dirección absoluta es demasiado difícil con solo 5 features
técnicas. En ese caso, el Revisor debe recomendar:
- Añadir features (volumen, put/call ratio, VIX, sector momentum)
- Aumentar el universo de entrenamiento (más tickers, más años)
- Cambiar el horizonte de predicción (¿10 días en vez de 5?)
- O aceptar que el label original (outperformance relativa) es el correcto pero
  renombrarlo claramente en la UI

---

### Paso 1.3 — Renombrar P(Win) en la UI para reflejar el nuevo significado

**Archivos a modificar:**
- `frontend-v2/src/components/ScreenerTable.tsx` (tooltips de columna)
- `frontend-v2/src/components/TickerModal.tsx` (label y hint de la card)

**Si el Paso 1.1 tuvo éxito (modelo v3 con label dirección absoluta):**
- `P(Win)` → `P(Sube 5d)`
- Tooltip: "Probabilidad estimada de que el precio esté más alto en 5 días."

**Si el Paso 1.1 fracasó (modelo v3 no supera tests):**
- `P(Win)` → `P(Outperform)`
- Tooltip: "Probabilidad de que esta acción supere su rendimiento típico en 5 días.
  NOTA: No es probabilidad de que el precio suba. Vea el Composite Score para dirección."

**Criterio de aceptación del Revisor:**
- [ ] El nuevo nombre NO induce a error sobre lo que mide
- [ ] El tooltip es visible sin hacer hover (o con un icono ℹ️)

---

## Fase 2 — Eliminación del LSTM del Ensemble (Hallazgo #2, CRÍTICO)

**Problema:** El LSTM produce ~50% para la mayoría de tickers, matando 57% de las
señales del XGBoost. La varianza del ensemble es mayor que la del XGBoost puro.

### Paso 2.1 — Test A/B: XGBoost puro vs. Ensemble 40/60

**Archivo:** `backend/tests/test_lstm_contribution.py`

**Qué hace:**
- Sobre 500 muestras out-of-sample:
  - Calcula accuracy del XGBoost puro
  - Calcula accuracy del Ensemble 40/60
  - Calcula accuracy del LSTM puro
  - Calcula accuracy de un baseline naive (siempre predecir la clase mayoritaria)
- Test de McNemar para determinar si la diferencia es estadísticamente significativa

**Criterio de aceptación del Revisor:**
- [ ] El ensemble es **significativamente mejor** que XGBoost puro (p < 0.05 en McNemar)
  → Si SÍ: mantener ensemble pero ajustar ponderación
  → Si NO: eliminar LSTM del ensemble
- [ ] El LSTM puro NO es significativamente mejor que el baseline naive
  → Si SÍ (es mejor): el LSTM tiene valor pero la ponderación es incorrecta
  → Si NO: el LSTM es ruido, eliminar sin contemplaciones

### Paso 2.2 — Si el LSTM no aporta: eliminarlo del endpoint neural-score

**Archivo a modificar:** `backend/server.py` — función `get_composite_score()` y endpoint `/api/neural-score/{ticker}`

**Qué hace:**
- `get_composite_score()` ahora devuelve `p_win_composite = p_win_xgb` directamente
- El campo `p_win_lstm` se mantiene en la respuesta pero con valor `null`
- El campo `model` cambia de `"ensemble"` a `"xgb_v3"`
- La UI muestra solo XGBoost (sin las 3 barras)

**Criterio de aceptación del Revisor:**
- [ ] El número de señales COMPRA + VENTA aumentó (más accionabilidad)
- [ ] La precisión de las señales NO empeoró (misma accuracy, más señales = mejor)
- [ ] `npm run build` exitoso
- [ ] Tests existentes siguen pasando

### Paso 2.3 — Si el LSTM tiene valor parcial: recalibrar ponderación

**Archivo a modificar:** `backend/app/services/lstm_inference.py`

**Qué hace (solo si el Paso 2.1 mostró que el LSTM supera al baseline naive):**
- Probar ponderaciones 70/30, 80/20, 90/10 (XGBoost/LSTM)
- Para cada ponderación, calcular accuracy + número de señales accionables
- Elegir la ponderación que maximiza `accuracy × √(señales_accionables)`
  (penaliza tener pocas señales)
- Guardar en archivo de configuración: `backend/config/model_weights.json`

**Criterio de aceptación del Revisor:**
- [ ] La nueva ponderación produce más señales accionables que 40/60
- [ ] La nueva ponderación NO reduce el accuracy
- [ ] El archivo de configuración está versionado

---

## Fase 3 — Recalibración de Stop-Loss y Take-Profit (Hallazgo #3, ALTO)

**Problema:** 5/6 señales tienen PnL negativo en simulación porque las pérdidas son
más grandes que las ganancias. Los multiplicadores de ATR no reflejan la realidad.

### Paso 3.1 — Auditoría de distribución de retornos

**Archivo nuevo:** `backend/scripts/audit_stops.py`

**Qué hace:**
- Para cada tipo de señal, analiza la distribución de:
  - Máximo adverse excursion (MAE): cuánto se movió el precio en contra antes de
    llegar al TP o SL
  - Máximo favorable excursion (MFE): cuánto se movió a favor
- Calcula el percentil 95 del MAE y el percentil 50 del MFE
- Compara con los niveles actuales de SL y TP

**Salida esperada:**
```
Tipo de señal: momentum_down
  SL actual: 1.5x ATR → percentil de MAE que cubre: 72%
  SL óptimo (95% MAE): 2.3x ATR
  TP actual: 3.0x ATR → percentil de MFE que alcanza: 45%
  TP óptimo (50% MFE): 2.1x ATR
```

**Criterio de aceptación del Revisor:**
- [ ] Los multiplicadores actuales cubren menos del 85% de los MAE
  → Confirmación de que los stops son demasiado ajustados
- [ ] Los multiplicadores de TP actuales son alcanzados en < 50% de los casos
  → Confirmación de que los takes son demasiado ambiciosos

### Paso 3.2 — Optimización de multiplicadores por tipo de señal

**Archivo:** `backend/scripts/audit_stops.py` (mismo script)

**Qué hace:**
- Para cada tipo de señal, busca la combinación (SL_mult, TP_mult) que maximiza
  el profit factor en datos out-of-sample
- Aplica restricciones:
  - SL_mult entre 1.0 y 4.0 (no stops ridículamente amplios)
  - TP_mult entre 1.5 y 5.0
  - Profit factor > 1.0 (obligatorio — si no se puede, dejar señal como "solo entrada")
- Los multiplicadores se guardan en `backend/config/atr_multipliers.json`

**Criterio de aceptación del Revisor:**
- [ ] Cada tipo de señal tiene multiplicadores optimizados independientemente
- [ ] El profit factor out-of-sample es ≥ 1.0 para al menos 4/6 señales
- [ ] Si una señal no logra profit factor ≥ 1.0 con ningún multiplicador, marcar
  como `"solo_direccion": true` (solo indica dirección, no genera precios de SL/TP)
- [ ] El PnL medio global en simulación ahora es **positivo** (comparar con baseline −0.64%)

### Paso 3.3 — Actualizar generación de trade plans con nuevos multiplicadores

**Archivo a modificar:** `backend/server.py` — función `_generate_trade_plan()`

**Qué hace:**
- Lee `backend/config/atr_multipliers.json`
- Si el tipo de señal tiene `solo_direccion: true`, genera plan sin SL ni TP
  (solo entry y dirección)
- Si tiene multiplicadores optimizados, los usa
- Si no tiene entrada en el archivo (nueva señal), usa defaults conservadores

**Criterio de aceptación del Revisor:**
- [ ] Los trade plans ahora reflejan multiplicadores por señal
- [ ] Las señales marcadas como "solo dirección" muestran "SL/TP no disponible"
  en vez de números incorrectos
- [ ] `npm run build` + tests pasando

---

## Fase 4 — Corrección del Sesgo Direccional (Hallazgo #4, ALTO)

**Problema:** 53 LONGs vs 14 SHORTs en mercado con 0% de breadth. El composite score
favorece direccionalidad LONG incluso en mercados bajistas.

### Paso 4.1 — Ajuste contextual del composite score

**Archivo a modificar:** `backend/server.py` — función `run_scan()`, sección del
composite score (líneas ~686-700)

**Qué hace:**
- En contexto bearish (breadth < 0.4):
  - Penalizar `price > sma50`: el bonus baja de +2 a +1 (estar sobre SMA50 en
    mercado bajista es menos significativo)
  - Penalizar `momentum_1m > 0`: el bonus baja de +2 a +1
  - Bonus adicional para SHORTs: si la señal es bajista, +1 extra
- En contexto bullish (breadth > 0.6):
  - Sin cambios (los bonus actuales son apropiados para mercados alcistas)
- En contexto neutral:
  - Sin cambios

**Resultado esperado:** Redistribución de LONG/SHORT más balanceada en mercado
bearish. No debería eliminar todos los LONGs — solo reducir los marginales.

**Criterio de aceptación del Revisor:**
- [ ] La proporción LONG/SHORT en mercado bearish pasa de ~4:1 a ~2:1 o mejor
- [ ] Los LONGs que sobreviven son los de mayor calidad (score ≥ 7, P(Win) ≥ 60%)
- [ ] No se introducen señales SHORT falsas (acciones que simplemente están planas)

### Paso 4.2 — Validación de direccionalidad en backtest

**Archivo:** `backend/tests/test_financial_validation.py` (extender)

**Qué hace:**
- Simula la estrategia en 3 regímenes de mercado (bearish, neutral, bullish)
  usando datos históricos de los últimos 5 años
- Calcula el retorno y Sharpe para cada régimen por separado
- Verifica que la estrategia no pierde dinero desproporcionadamente en bear markets

**Criterio de aceptación del Revisor:**
- [ ] El retorno en mercado bearish NO es significativamente peor que en neutral
- [ ] La estrategia reduce exposición en bear markets (menos señales LONG activas)
- [ ] El Sharpe en cada régimen es ≥ 0 por separado

---

## Fase 5 — Transparencia y Gobernanza (Hallazgos #5, #6, #7)

Estos hallazgos no requieren cambios de modelo sino de **transparencia** y
**gestión de expectativas** del usuario.

### Paso 5.1 — Indicador de confianza por señal

**Archivo a modificar:** `frontend-v2/src/components/ScreenerTable.tsx`

**Qué hace:**
- Agregar una columna o badge que indique la confiabilidad de la predicción:
  - 🟢 **Alta confianza:** P(Win) fuera del intervalo [45%, 55%] Y composite ≥ 6
  - 🟡 **Media confianza:** P(Win) fuera del intervalo O composite ≥ 6 (no ambos)
  - ⚪ **Baja confianza:** P(Win) dentro de [45%, 55%] Y composite < 6

**Criterio de aceptación del Revisor:**
- [ ] El inversor puede identificar de un vistazo qué señales son más confiables
- [ ] Las señales de baja confianza no se ocultan (transparencia) pero se atenúan visualmente

### Paso 5.2 — Explicación de tasa de expiración

**Archivo a modificar:** `frontend-v2/src/tabs/Analytics.tsx`

**Qué hace:**
- Añadir un tooltip o texto explicativo sobre la tasa de expiración:
  "De cada 100 señales, ~10 expiran antes de ser accionables. Esto es normal
  y actúa como filtro natural: las señales que expiran suelen ser las de
  menor calidad."

**Criterio de aceptación del Revisor:**
- [ ] El inversor entiende que la expiración no es un bug
- [ ] La app muestra cuántas señales expiraron Y cuál habría sido su resultado
  (para demostrar que las expiradas efectivamente eran malas)

### Paso 5.3 — Warning de riesgo de cola

**Archivo a modificar:** `frontend-v2/src/components/TickerModal.tsx`

**Qué hace:**
- En la sección del Plan de Trading, añadir una nota pequeña:
  "⚠️ El stop-loss se calcula con volatilidad histórica. En eventos extremos,
  el precio puede saltarse este nivel. Nunca invierta más de lo que puede perder."
- Esta nota es obligatoria por buenas prácticas — toda plataforma que da SL/TP
  debe advertir sobre slippage.

**Criterio de aceptación del Revisor:**
- [ ] El warning es visible pero no alarmista
- [ ] Cumple con estándares de la industria (similares a Interactive Brokers, Schwab)

---

## Fase 6 — Verificación Final y Documentación

### Paso 6.1 — Re-ejecutar test harness completo

**Archivo:** `backend/tests/test_financial_validation.py`

**Qué hace:**
- Corre el modelo final (v3 con label dirección absoluta, sin LSTM o con ponderación
  optimizada, stops recalibrados) contra el baseline del Paso 0.1
- Genera informe comparativo:

```
Métrica               Baseline    Post-Fix    Delta
─────────────────────────────────────────────────────
Win Rate global       54.0%       XX.X%       +X.Xpp
Sharpe Ratio          0.XX        X.XX        +X.XX
Profit Factor         0.9X        X.XX        +X.XX
Max Drawdown          -XX.X%      -XX.X%      +X.Xpp
Señales accionables   X/10        Y/10        +Z
PnL medio simulado    -0.64%      +X.XX%      +X.XXpp ✅
```

**Criterio de aceptación del Revisor:**
- [ ] **TODAS** las métricas mejoraron o se mantuvieron igual
- [ ] Ninguna métrica empeoró más allá del ruido estadístico (±0.5pp en WR,
  ±0.05 en Sharpe)
- [ ] El PnL medio simulado ahora es **positivo**
- [ ] Si alguna métrica empeoró → investigar causa, documentar, decidir si es
  un trade-off aceptable

### Paso 6.2 — Documentación del modelo v3

**Archivo nuevo:** `backend/docs/MODEL_v3.md`

**Qué documenta:**
- Label de entrenamiento y justificación del cambio
- Features utilizadas e importancia relativa
- Hiperparámetros y proceso de optimización
- Métricas de validación (accuracy, AUC, calibration)
- Limitaciones conocidas (sesgos, regímenes donde falla)
- Workflow de reentrenamiento (cuándo y cómo actualizar el modelo)

### Paso 6.3 — CHANGELOG de la versión

**Archivo a modificar:** `CHANGELOG.md` (raíz del proyecto)

**Qué documenta:**
- Versión: v2.0 → v3.0
- Cambios: label dirección absoluta, eliminación/recalibración LSTM, stops
  optimizados, ajuste contextual de scores, badges de confianza
- Métricas comparativas (tabla del Paso 6.1)
- Breaking changes (si los hay)
- Instrucciones de migración (si aplica)

---

## Resumen de Archivos Afectados

| Archivo | Fase | Tipo de cambio |
|---|---|---|
| `backend/tests/test_financial_validation.py` | 0, 1, 6 | **NUEVO** — test harness y baseline |
| `backend/tests/test_lstm_contribution.py` | 2 | **NUEVO** — A/B test LSTM |
| `backend/scripts/train_xgboost_v3.py` | 1 | **NUEVO** — reentrenamiento con label dirección |
| `backend/scripts/audit_stops.py` | 3 | **NUEVO** — auditoría de stops |
| `backend/server.py` | 2, 3, 4 | Modificar: endpoint neural, trade plan, composite |
| `backend/app/services/lstm_inference.py` | 2 | Modificar: usar configuración de pesos |
| `backend/config/model_weights.json` | 2 | **NUEVO** — pesos del modelo |
| `backend/config/atr_multipliers.json` | 3 | **NUEVO** — multiplicadores por señal |
| `frontend-v2/src/components/ScreenerTable.tsx` | 1, 5 | Modificar: tooltips, badge confianza |
| `frontend-v2/src/components/TickerModal.tsx` | 1, 5 | Modificar: labels, warning riesgo |
| `frontend-v2/src/tabs/Analytics.tsx` | 5 | Modificar: explicación expiración |
| `backend/docs/MODEL_v3.md` | 6 | **NUEVO** — documentación del modelo |

---

## Orden de Ejecución

1. **Fase 0** — Infraestructura (sin esto, no sabemos si mejoramos)
2. **Fase 1** — Label de entrenamiento (el corazón del modelo)
3. **Fase 2** — LSTM (depende del nuevo modelo)
4. **Fase 3** — Stops (usa el nuevo modelo para decidir dirección, luego optimiza stops)
5. **Fase 4** — Sesgo direccional (ajuste contextual)
6. **Fase 5** — Transparencia (UI, sin impacto en predicciones)
7. **Fase 6** — Verificación final + documentación

**El Revisor detiene el proceso si cualquier fase no cumple sus criterios.**
No se avanza con deuda técnica ni con "después lo arreglamos".

---

## Criterio de Éxito Global

Al finalizar las 6 fases, el Revisor debe poder firmar:

> "La plataforma Iosef Finance v3.0 ha sido evaluada con datos out-of-sample.
> El modelo predictivo mide lo que el inversor necesita (dirección absoluta de
> precio). El ensemble ha sido optimizado para maximizar señales accionables sin
> sacrificar precisión. Los stops y takes han sido calibrados por tipo de señal
> para lograr profit factor positivo. La UI comunica con transparencia las
> limitaciones del sistema. La plataforma es APROPIADA para inversores minoristas
> que entienden que ninguna predicción es garantía."

**Si el Revisor no puede firmar esto, el plan no está completo.**

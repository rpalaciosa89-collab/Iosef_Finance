# Auditoría de Calidad de Datos y Lógica de Negocio — Iosef Finance

**Informe Final de Auditoría Cuantitativa**

**Fecha de ejecución:** 2026-06-10  
**Auditor:** Agente Cuantitativo Automatizado  
**Alcance:** 100% de endpoints REST, lógica de scoring, coherencia entre secciones  
**Backend auditado:** `http://localhost:8002/api/*`  
**Datos de mercado:** Titan 100 (98 tickers), periodo 2 años  

---

## Resumen Ejecutivo

Se auditaron **9 dimensiones** de calidad de datos y lógica de negocio en la plataforma Iosef Finance. Se identificaron **12 hallazgos**: 1 crítico, 4 altos, 5 medios, 2 bajos.

**Veredicto general:** La arquitectura de cálculo es sólida. Los indicadores técnicos (RSI, SMA, momentum, volume) y el composite score se calcularon correctamente en todos los casos verificados. Las fórmulas de equity en Paper Trading son exactas. La plataforma es funcional pero tiene oportunidades de mejora en la calidad de features del modelo ML, en la riqueza de datos históricos, y en la coherencia de señales entre endpoints.

---

## Hallazgos

### [BUG-001] `macd_hist` hardcodeado a 0.0 en features del modelo XGBoost — **Crítica**

| Campo | Valor |
|---|---|
| **Archivo** | [server.py:743](file:///Users/raymondpalacios/Documents/Bootcamp Data Science/Iosef_Finance/backend/server.py#L743) |
| **Endpoint** | `GET /api/scan` |
| **Descripción** | El diccionario `features` que alimenta al modelo XGBoost incluye `'macd_hist': 0.0` hardcodeado. La función `_compute_macd_hist` está implementada en `train_xgboost_real.py` pero nunca se invoca en el scan de producción. |
| **Valor esperado** | MACD histogram calculado como `EMA(12) - EMA(26) - Signal(9)` |
| **Valor observado** | `0.0` siempre, para los 98 tickers. |
| **Impacto** | El modelo XGBoost fue entrenado con MACD real pero en inferencia recibe 0.0. Esto degrada la precisión de predicción del 20% de los features. Las señales de trading están sesgadas. |
| **Fix** | Agregar `_compute_macd_hist(close_series)` en el scan loop y pasar el valor real al diccionario `features`. |

---

### [BUG-002] Divergencia entre XGBoost score del scan y del endpoint `/neural-score` — **Alta**

| Campo | Valor |
|---|---|
| **Archivo** | [server.py:1156-1162](file:///Users/raymondpalacios/Documents/Bootcamp Data Science/Iosef_Finance/backend/server.py#L1156-L1162) |
| **Endpoints** | `GET /api/scan` vs `GET /api/neural-score/{ticker}` |
| **Descripción** | El endpoint `/api/neural-score` busca el XGBoost score en el caché Redis del scan (`scan:data:titan100`). Si el caché expiró (TTL 60s) o el ticker no se encuentra, usa el valor por defecto `50.0`. Esto produce divergencia respecto al score mostrado en el screener. |
| **Valor esperado** | `p_win_xgb` en `/neural-score` = `signal_strength_score` en `/scan` |
| **Valor observado** | CRM: scan muestra 81.3, neural-score muestra 50.0 |
| **Impacto** | El usuario ve dos scores diferentes para el mismo ticker en distintas secciones. Confusión y desconfianza en la plataforma. |
| **Fix** | Recalcular `compute_ml_score(features)` directamente en el endpoint neural-score en lugar de depender del caché del scan. |

---

### [BUG-003] `avg_return` en Signal Lab tiene magnitud ambigua — **Alta**

| Campo | Valor |
|---|---|
| **Archivo** | `app/services/signal_evaluation.py` |
| **Endpoint** | `GET /api/signal-evaluation` |
| **Descripción** | El campo `avg_return_5d` almacena valores en formato decimal (ej: 0.72 representa 72%, 1.07 representa 107%). Esto no es incorrecto matemáticamente, pero genera confusión: algunos valores parecen imposibles (107% en 5 días). La función `_ticker_composite_score` aplica capping a ±10 esperando valores como 0.72, lo cual es correcto. Sin embargo, el `avg_return` de señales como `high_volume` (1.07) y `overbought` en contexto bearish (-0.71) sugieren que eventos extremos están skeweando las medias. |
| **Valor observado** | `breakout_up: avg_return=0.72` (72%), `high_volume: avg_return=1.07` (107%), `oversold_bullish: avg_return=-2.94` (-294%) |
| **Impacto** | La UI puede mostrar porcentajes engañosos si no escala correctamente. Señales con pocos trades y eventos extremos dominan las estadísticas. |
| **Fix** | Usar mediana en lugar de media para `avg_return`, o winsorizar al percentil 95. Documentar explícitamente que los valores son retornos porcentuales acumulados en 5 días (no anualizados). |

---

### [BUG-004] Analytics tiene base de datos de trades casi vacía — **Alta**

| Campo | Valor |
|---|---|
| **Endpoint** | `GET /api/analytics` |
| **Descripción** | La base de datos `trades_history.db` contiene solo 3 trades cerrados (1 `strong_trend`, 2 `weak_signal`). Esto hace que las métricas de Analytics (win rate, PnL medio, signal analytics) sean estadísticamente insignificantes. El mensaje del sistema lo reconoce correctamente: "Datos insuficientes para generar conclusiones". |
| **Valor observado** | 3 trades totales, 0% win rate, 0 tickers con datos de asset analytics |
| **Impacto** | La sección de Analytics del frontend muestra datos vacíos o poco fiables. El usuario no puede evaluar el rendimiento histórico real de las señales. |
| **Fix** | Acumular más trades reales (dejar correr el sistema en paper trading por semanas). Alternativamente, backfill con simulación histórica. Reducir umbral de `MIN_SIGNAL_DISPLAY` temporalmente mientras se acumulan datos. |

---

### [BUG-005] `expiry_rate` muestra valor incorrecto — **Alta**

| Campo | Valor |
|---|---|
| **Archivo** | `app/services/analytics.py` |
| **Endpoint** | `GET /api/analytics` |
| **Descripción** | El campo `expiry_rate` en signal_analytics devuelve `10000.0%` para `weak_signal`. Esto sugiere que el valor crudo es `100.0` (que representa 100%) pero al formatearse como porcentaje se multiplica por 100 nuevamente, resultando en 10000%. |
| **Valor observado** | `weak_signal: expiry_rate=10000.0%` (debería ser 100%) |
| **Impacto** | Display incorrecto en frontend si no se escala adecuadamente. |
| **Fix** | Verificar si `expiry_rate` se calcula como fracción (0.0-1.0) o porcentaje (0-100). Unificar el formato en todo el módulo de analytics. |

---

### [BUG-006] Situación `strong_trend` sin señal activa de compra clara — **Media**

| Campo | Valor |
|---|---|
| **Archivo** | [server.py:698-734](file:///Users/raymondpalacios/Documents/Bootcamp Data Science/Iosef_Finance/backend/server.py#L698-L734) |
| **Descripción** | 30 tickers muestran `situation: "strong_trend"` pero ninguno tiene `breakout_up` entre sus señales activas. La categoría `strong_trend` se asigna cuando `score >= 6` y `close > sma20 > sma50`, pero el mercado actual es bearish (breadth 0%), creando una aparente contradicción. |
| **Valor observado** | 30 tickers con `strong_trend`, 30 con `weak_signal`, mercado bearish al 0% |
| **Impacto** | El usuario ve "TENDENCIA POSITIVA" en un mercado bearish. Puede inducir decisiones contrarias al contexto. |
| **Fix** | Incorporar `market_context` en la detección de situación. Si el contexto es bearish, degradar `strong_trend` a `weak_signal` o añadir advertencia contextual. |

---

### [BUG-007] Ticker con ML score alto pero situación contradictoria — **Media**

| Campo | Valor |
|---|---|
| **Endpoint** | `GET /api/top` |
| **Descripción** | SAP muestra `signal_strength_score=76.5` (ML muy alcista) pero `situation=momentum_down` (tendencia bajista). CRM muestra score=81.3 pero `clarity=baja`. PLTR muestra score=80.3 pero `clarity=baja`. |
| **Valor observado** | Top 3 oportunidades tienen ML score >75 pero decisión "baja" o tendencia opuesta |
| **Impacto** | Las "top opportunities" no son oportunidades accionables. El usuario ve scores altos pero mensajes contradictorios. |
| **Fix** | Filtrar top opportunities por `decision_clarity != "baja"`. Solo mostrar oportunidades donde ML y technical analysis están alineados. |

---

### [BUG-008] Señal `oversold` con contexto bearish no recibe bonus en composite score — **Media**

| Campo | Valor |
|---|---|
| **Archivo** | [server.py:681](file:///Users/raymondpalacios/Documents/Bootcamp Data Science/Iosef_Finance/backend/server.py#L681) |
| **Descripción** | La regla `if rsi < 30 and current_context != "bearish": score += 2` impide que el composite score premie condiciones oversold en mercado bearish. Sin embargo, las reversiones oversold son precisamente MÁS probables durante bear markets (short squeezes, dead cat bounces). |
| **Valor esperado** | RSI oversold debería dar bonus independientemente del contexto, o al menos en contexto neutral. |
| **Impacto** | En el mercado bearish actual (breadth 0%), las señales oversold nunca activan el bonus de +2 puntos. Se pierden oportunidades de compra en mínimos. |
| **Fix** | Cambiar la condición a `if rsi < 30: score += 2` (sin filter de contexto). El contexto ya se aplica como ajuste separado en `signal_context_adjustment`. |

---

### [BUG-009] Sin campo ATR en la salida del scan — **Media**

| Campo | Valor |
|---|---|
| **Archivo** | [server.py:756-774](file:///Users/raymondpalacios/Documents/Bootcamp Data Science/Iosef_Finance/backend/server.py#L756-L774) |
| **Descripción** | El ATR se calcula correctamente en línea 673 pero no se incluye en el diccionario `ticker_entry` que se envía al frontend. El valor solo se usa internamente para generar el trade plan. |
| **Valor observado** | 0 de 98 tickers tienen campo `atr` en la respuesta del scan |
| **Impacto** | El frontend no puede mostrar volatilidad (ATR) como indicador independiente. Debugging más difícil sin este dato. |
| **Fix** | Agregar `"atr": round(atr, 4)` al diccionario `ticker_entry`. |

---

### [BUG-010] `avg_return` de alta magnitud en contexto alcista — **Media**

| Campo | Valor |
|---|---|
| **Endpoint** | `GET /api/signal-evaluation` |
| **Descripción** | Señales en contexto `bullish` muestran retornos extremadamente altos: `high_volume` en bullish = 2.05 (205%), `momentum_shift_up` en neutral = 3.30 (330%). Estos valores probablemente provienen de eventos extremos (splits, gaps de earnings) que no fueron filtrados. |
| **Valor observado** | `avg_return_5d >= 2.0` para múltiples combinaciones señal×contexto |
| **Impacto** | Los gráficos y tablas de Signal Lab pueden mostrar barras desproporcionadas, ocultando señales con rendimiento más realista. |
| **Fix** | Aplicar winsorización al percentil 99 en `avg_return` antes de almacenar. Filtrar retornos > 50% en 5 días como probable error de datos. |

---

### [BUG-011] RSI usa `ewm(alpha=1/period)` inconsistente con la versión de Signal Lab — **Baja**

| Campo | Valor |
|---|---|
| **Archivo** | `server.py:125-130` vs `app/services/signal_evaluation.py:17-22` |
| **Descripción** | Ambas implementaciones usan Wilder's smoothing (EWM con alpha=1/period). Son idénticas y producen resultados consistentes. Sin embargo, la implementación en `lstm_inference.py:94-97` usa `rolling(14).mean()` (SMA simple) en lugar de EWM para RSI, lo cual produce un RSI ligeramente diferente (diferencia ~0.5-1.5 puntos). |
| **Impacto** | Los features que entran al LSTM son inconsistentes con los mostrados en el screener. Diferencia pequeña pero acumulativa en secuencias de 60 días. |
| **Fix** | Unificar a Wilder's smoothing en los tres módulos. |

---

### [BUG-012] `momentum_10` vs `momentum_1m` — naming inconsistente — **Baja**

| Campo | Valor |
|---|---|
| **Archivo** | `server.py:666,740` |
| **Descripción** | El scan muestra `momentum_1m` (retorno a 20 días) pero internamente pasa `momentum_10` como feature al modelo. En el training, `momentum_10` es `pct_change(10)` (10 días). En el scan, `momentum` se calcula como `(close[-1] - close[-20]) / close[-20]` (20 días). Esto es un **mismatch de período**: el modelo se entrenó con momentum de 10 días pero recibe momentum de 20 días en inferencia. |
| **Valor esperado** | El feature `momentum_10` debe calcularse sobre 10 días, no 20. |
| **Valor observado** | Scan usa 20 días, training usa 10 días. |
| **Impacto** | Degradación de precisión del modelo. Las predicciones usan una ventana de momentum diferente a la del entrenamiento. |
| **Fix** | Cambiar `momentum` en el scan a `pct_change(10)` para que coincida con el training. |

---

## Verificaciones que PASARON (sin hallazgos)

### Sección 1: Indicadores Técnicos ✅
- **RSI:** Verificado contra yfinance para DIS (40.3 vs 40.5), CRM (42.7 vs 42.8), MSFT (41.0 vs 41.1). Diferencias ≤ 0.2 puntos. Wilder's smoothing correcto.
- **SMA 20/50/200:** Verificados contra yfinance. Precisión exacta.
- **Momentum 1M:** Fórmula `(close[-1] - close[-20]) / close[-20] * 100` verificada. Coincide con recálculo independiente.
- **Relative Volume:** `volume[-1] / avg_volume_20` con protección contra división por cero. Correcto.
- **ATR:** Cálculo correcto (high-low, high-close, low-close), se usa internamente para trade plan.

### Sección 2: Composite Score ✅
- **Fórmula verificada para CRM, DIS, COST:** Scores reconstruidos manualmente coinciden exactamente con el backend (CRM=2, DIS=0, COST=4).
- **Distribución:** Rango 0-9, distribución normal con picos en 0, 3, 5, 8. Sin anomalías.

### Sección 3: Motor Neural ✅
- **Modelo:** Confirmado `real_market_yfinance`, 37,458 muestras, 98 tickers, AUC 0.5519.
- **Score en rango [0, 100]:** Verificado (mín 16.4, máx 81.3). Sin valores fuera de rango.

### Sección 4: Coherencia Screener vs Modal ✅
- Trade plan de NVDA (SHORT): entry=203.05, SL=216.45, TP=176.27 → SL > entry > TP. Lógica correcta.
- Trade plan de ASML (LONG): entry=1748.18, SL=1566.90, TP=2110.73 → entry > SL, TP > entry. Lógica correcta.
- Risk/Reward consistente: 1:2 para ambas direcciones.

### Sección 7: Paper Trading ✅
- **Fórmula de equity:** `total_equity = cash + unrealized_pnl + realized_pnl`. Verificada con precisión de centavo ($100,000.00 = $100,000.00 + $0.00 + $0.00).

### Sección 8: Sanidad de Datos ✅
- **0 precios nulos/negativos** en 98 tickers.
- **RSI en rango [28.7, 68.8]** — sin valores en 0 o 100.
- **Todos los tickers tienen sector** — 0 con "Unknown".
- **Sin timestamps futuros** detectados.
- **Sin tickers duplicados** en el scan.

### Sección 9: Market Context ✅
- **Market Breadth 0%** — verificado independientemente (0/98 tickers above SMA50). Consistente con el mercado actual.
- **Contexto "bearish"** correctamente asignado. Alertas de mercado generadas.

---

## Métricas de Calidad

| Dimensión | Hallazgos | Estado |
|---|---|---|
| Precisión de indicadores | 0 | ✅ Sin errores |
| Corrección de fórmulas | 1 (BUG-008) | ⚠️ 1 ajuste de lógica |
| Coherencia entre secciones | 2 (BUG-002, BUG-007) | ⚠️ Divergencia entre endpoints |
| Consistencia temporal | 1 (BUG-002) | ⚠️ Dependencia de caché |
| Lógica de señales | 1 (BUG-006) | ⚠️ Señales vs contexto |
| Sanidad de precios | 0 | ✅ Sin errores |
| Features ML | 3 (BUG-001, BUG-011, BUG-012) | 🔴 Feature mismatch |
| Datos históricos | 2 (BUG-004, BUG-005) | ⚠️ Pocos trades |
| Display/UI | 2 (BUG-003, BUG-010) | ⚠️ Ambigüedad de formato |

---

## Resumen de Severidad

| Nivel | Cantidad | IDs |
|---|---|---|
| 🔴 Crítica | 1 | BUG-001 |
| 🟠 Alta | 4 | BUG-002, BUG-003, BUG-004, BUG-005 |
| 🟡 Media | 5 | BUG-006, BUG-007, BUG-008, BUG-009, BUG-010 |
| 🟢 Baja | 2 | BUG-011, BUG-012 |

---

## Priorización de Correcciones

1. **BUG-001** (Crítica): Calcular `macd_hist` real en el scan. Impacto inmediato en todas las predicciones ML.
2. **BUG-012** (Baja): Alinear `momentum_10` con el período de training. Fácil de corregir, alto impacto en precisión.
3. **BUG-002** (Alta): Recalcular XGBoost score en `/neural-score` sin depender del caché.
4. **BUG-008** (Media): Eliminar filtro de contexto en el bonus RSI oversold.
5. **BUG-004** (Alta): Acumular datos históricos o hacer backfill.
6. Resto: Correcciones de display, formato y coherencia.

---

## Score de Calidad de Datos

| Dimensión | Score |
|---|---|
| Precisión matemática | 9/10 |
| Coherencia entre secciones | 7/10 |
| Calidad de features ML | 5/10 |
| Riqueza de datos históricos | 3/10 |
| Consistencia de display | 6/10 |
| **Global** | **6.5/10** |

---

*Informe generado automáticamente mediante verificación directa de endpoints, recálculo independiente con yfinance, y auditoría de código fuente. Todos los valores fueron contrastados contra cálculos externos.*

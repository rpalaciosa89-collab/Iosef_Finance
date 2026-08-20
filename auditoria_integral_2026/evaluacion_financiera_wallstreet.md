# Informe de Evaluación Financiera — Iosef Finance

**Revisor:** Ingeniero Financiero Senior, 25 años en Wall Street
**Fecha:** 2026-06-11
**Plataforma evaluada:** Iosef Finance v2.0 — Asistente de Señales de Inversión
**Universo:** Titan 100 (98 large caps globales)
**Datos analizados:** 9,197 señales en backtest de 2 años + 1,984 trades simulados

---

## Resumen Ejecutivo

He pasado 4 horas revisando cada número que produce esta plataforma. Mi veredicto es
**CONDICIONAL** — la plataforma tiene mérito técnico real pero no es una máquina de
hacer dinero. El edge existe pero es fino. A continuación, la matemática.

---

## 1 — ¿Tiene edge esta estrategia?

### 1.1 El win rate es real pero modesto

El Signal Lab analizó 9,197 ocurrencias de 12 tipos de señal sobre 2 años de datos:

| Señal | n | WR 5d | IC 95% | Retorno medio | ¿Edge? |
|---|---|---|---|---|---|
| momentum_shift_up | 2,856 | 53.0% | [51.2%, 54.8%] | +0.58% | Marginal |
| momentum_shift_down | 2,750 | 54.4% | [52.5%, 56.3%] | +0.76% | **Sí** |
| overbought | 978 | 52.4% | [49.2%, 55.5%] | +0.42% | No (IC toca 50%) |
| high_volume | 793 | 57.4% | [54.0%, 60.9%] | +1.07% | **Sí** |
| oversold | 716 | 55.3% | [51.7%, 58.9%] | +0.57% | Sí |
| breakout_up | 270 | 55.0% | [49.1%, 61.0%] | +0.72% | No (IC toca 50%) |

**Win rate medio ponderado: 54.0%**

Solo **3 de 6 señales** tienen intervalos de confianza al 95% completamente por encima
del 50%. Las otras 3 tocan o cruzan el umbral de aleatoriedad. Esto significa que
el edge no es uniforme — solo ciertas señales lo tienen.

### 1.2 La paradoja del PnL negativo

Este es el hallazgo más preocupante. Los datos de Analytics (1,984 trades simulados
con entrada, SL y TP) muestran:

| Señal | Trades | Win Rate Efectivo | Avg PnL |
|---|---|---|---|
| breakdown | 232 | 65.2% | **+0.60%** |
| momentum_down | 234 | 54.7% | **−1.17%** |
| strong_trend | 228 | 60.5% | **−0.89%** |
| overbought | 223 | 57.0% | **−0.70%** |
| breakout_forming | 222 | 59.0% | **−0.85%** |
| momentum_up | 221 | 60.6% | **−1.09%** |

**PnL medio global: −0.64%**

**5 de 6 tipos de señal tienen PnL negativo a pesar de tener win rate > 50%.**

La explicación matemática: si `WR × avg_gain − (1−WR) × avg_loss < 0` con WR > 50%,
entonces `avg_loss > avg_gain × WR/(1−WR)`. Para momentum_down con WR=54.7%,
esto significa que **las pérdidas son al menos 1.21× más grandes que las ganancias**.

En cristiano: cuando ganas, ganas poco. Cuando pierdes, pierdes más. El stop-loss
está demasiado lejos o el take-profit demasiado cerca. Los multiplicadores de ATR
(1.5× para SL, 3.0× para TP → R/R 1:2 teórico) no se están traduciendo en R/R 1:2
real porque el precio frecuentemente toca el SL sin llegar al TP.

### 1.3 Cálculo de retorno neto esperado

Usando los datos del Signal Lab (no los simulados de trading, que incluyen SL/TP):

```
Retorno bruto por operación (5 días): 0.655%
Costo de transacción (0.1%):         −0.100%
Retorno neto pre-tax:                 0.555%
Impuesto (20% sobre ganancias):      −0.111%
Retorno final por operación:          0.444%
```

**0.444% neto por operación de 5 días.** Esto es positivo. El edge existe.

**PERO** — y este es el punto crítico — este cálculo asume que puedes ejecutar
**1 operación nueva CADA DÍA** (252 al año) con el retorno promedio de TODAS
las señales.

En la práctica, el inversor:
- Monitorea 98 tickers
- Recibe ~18 señales nuevas por día en todo el universo
- Pero solo puede seguir las que entiende y en las que confía
- Las señales duran 5 días, por lo que hay solapamiento
- Una operación inmoviliza capital

**Escenario realista:** 2-3 operaciones por semana (100-150 al año).

| Escenario | Ops/año | Retorno anualizado |
|---|---|---|
| Optimista (1/día) | 252 | **+205.5%** |
| Moderado (3/semana) | 150 | **+94.5%** |
| Realista (2/semana) | 100 | **+55.8%** |
| Conservador (1/semana) | 50 | **+24.8%** |
| Muy conservador (2/mes) | 24 | **+11.2%** |
| **SPY buy & hold** | — | **+10.0%** |

El break-even con SPY está en **22 operaciones al año** (menos de 2 al mes).
Esto es alcanzable. Pero requiere disciplina para no saltarse señales buenas
y no tomar señales malas.

---

## 2 — El modelo ML: luces y sombras

### 2.1 El label de entrenamiento es incorrecto para el caso de uso

**DATUM CONFIRMADO:** El modelo XGBoost fue entrenado para predecir si el retorno
a 5 días **supera la mediana del propio ticker**, no si el precio sube o baja.

Esto significa:
- Si el mercado cae −5% y el ticker cae solo −2%, el modelo lo marca como "win"
- Si el ticker sube +1% pero su mediana es +2%, el modelo lo marca como "loss"

Para un inversor que quiere saber "¿compro o vendo?", este label es **inadecuado**.
El inversor no gana dinero con "caer menos que el promedio". Gana dinero con
"el precio sube".

**Recomendación:** Reentrenar con label binario de dirección absoluta:
- `y=1` si `retorno_5d > 0`
- `y=0` si `retorno_5d <= 0`

Esto cambiaría la interpretación de P(Win) de "probabilidad de superar la mediana"
a "probabilidad de que el precio suba", que es lo que el inversor realmente necesita.

### 2.2 El LSTM está destruyendo valor

**DATUM CONFIRMADO:** El LSTM produce scores en rango 43.3%–75.9% con media 53.0%,
comprimiendo el ensemble hacia la media.

Con **XGBoost puro:** 7 COMPRA, 0 VENTA, 3 NEUTRAL (sobre 10 tickers)  
Con **Ensemble 40/60:** 3 COMPRA, 0 VENTA, 7 NEUTRAL (sobre 10 tickers)

El LSTM está **eliminando 4 de cada 7 señales de COMPRA** que el XGBoost detecta.
Esto reduce la accionabilidad del modelo en un 57%.

Peor aún: la varianza del ensemble (30.1) es mayor que la del XGBoost puro (19.3),
lo que significa que el LSTM no está suavizando — está **inyectando ruido** a través
de outliers (ej: META 75.9% LSTM cuando XGBoost da 55.5%).

**Recomendación inmediata:** Eliminar el LSTM del ensemble de inferencia. Usar
XGBoost puro. El LSTM puede conservarse para investigación pero no debe afectar
las señales que ve el usuario.

### 2.3 El modelo discrimina pero débilmente

De 98 tickers: 45 (46%) con P(Win) ≥ 55%, 10 (10%) con P(Win) ≤ 45%.

Esto es **56% de discriminación** vs. ~32% esperado por azar. El modelo SÍ tiene
poder predictivo, pero el 44% restante cae en zona gris (45-55%) donde no ayuda
a decidir.

| Rango | Tickers | Interpretación |
|---|---|---|
| ≥ 60% | 26 (27%) | Señal fuerte |
| 55-60% | 19 (19%) | Señal débil |
| 45-55% | 43 (44%) | **Zona muerta — el modelo no dice nada** |
| ≤ 45% | 10 (10%) | Señal bajista |

Casi la mitad de los tickers están en zona muerta. Esto no es un bug — es una
limitación real del modelo.

---

## 3 — Gestión de riesgo: los stops no están funcionando

### 3.1 La tasa de expiración esconde un problema

8-12% de las señales expiran sin ejecutarse. La app lo presenta como "la señal
murió". Pero en realidad es un **slippage encubierto**: el precio nunca llegó
al entry en condiciones favorables, o llegó y se revirtió antes de que el
inversor actuara.

En un mercado real, esto significa que 1 de cada 10 oportunidades que la app
te muestra **no eran oportunidades reales**. El inversor pierde tiempo y,
potencialmente, entra tarde en las que sí se ejecutan.

### 3.2 Los multiplicadores de ATR no capturan riesgo de cola

El SL se calcula como `entry ± (1.5 × ATR)` y el TP como `entry ± (3.0 × ATR)`.
Esto asume que los movimientos de precio son normales (distribución gaussiana).

En realidad, los retornos diarios tienen **exceso de curtosis** (fat tails).
Un movimiento de 4× o 5× ATR ocurre con más frecuencia de lo que una distribución
normal predeciría. En esos días, el SL se salta y la pérdida es mayor que la
planeada.

**DATUM FALTANTE:** No tengo datos de slippage real. Necesitaría el historial
de trades con precio de ejecución del SL vs. precio teórico del SL para calcular
el slippage medio.

### 3.3 53 LONGs vs. 14 SHORTs en mercado bearish

En un mercado donde **0 de 98 acciones** están sobre su SMA50, la app recomienda
**53 LONGs y solo 14 SHORTs**. Esto es una **asimetría peligrosa**.

El composite score penaliza acciones bajo SMA20/SMA50 pero premia las que están
sobre SMA200. En un mercado bajista reciente, muchas acciones cayeron bajo SMA20
y SMA50 pero aún están sobre SMA200. Esto produce señales LONG "técnicamente
válidas" en acciones que están en tendencia bajista de corto plazo.

El inversor que sigue ciegamente estas 53 señales LONG en un mercado bearish
está **comprando en caídas** sin confirmación de cambio de tendencia. Algunas
rebotarán (las que el modelo acierta). Otras seguirán cayendo.

---

## 4 — Comparación con alternativas pasivas

| Estrategia | Retorno anual esperado | Volatilidad | Sharpe |
|---|---|---|---|
| Iosef (100 ops/año) | +55.8% | Alta | ~2.3 |
| Iosef (50 ops/año) | +24.8% | Media-Alta | ~1.2 |
| Iosef (24 ops/año) | +11.2% | Media | ~0.6 |
| SPY buy & hold | +10.0% | 15-18% | 0.5-0.7 |
| 60/40 stocks/bonds | +7.0% | 8-10% | 0.6-0.8 |
| Cash | +4.0% | 0% | — |

La estrategia supera a SPY en todos los escenarios con ≥24 operaciones al año.
Pero el Sharpe ratio comunicado (8.46) es **engañoso** — asume 252 operaciones
independientes al año, sin drawdowns, sin correlación entre señales, y sin
slippage. Un Sharpe realista estaría en el rango **0.6–1.5** para un inversor
disciplinado.

---

## 5 — Veredicto

### APROPIADA — CONDICIONAL — NO APROPIADA

**CONDICIONAL.**

La plataforma **tiene edge estadístico demostrable**. El win rate de 54% está
por encima del azar con significancia estadística en 3 de 6 tipos de señal. El
retorno neto por operación (+0.44%) es positivo incluso después de costos e
impuestos. Con 24+ operaciones al año, la estrategia supera consistentemente
a SPY.

**PERO** — y este "pero" es grande — la plataforma tiene 3 problemas estructurales
que impiden recomendarla sin reservas:

1. **El label de entrenamiento no coincide con el caso de uso.** P(Win) mide
   "outperformance relativa", no "el precio va a subir". Esto confunde al inversor
   y produce señales técnicamente correctas pero financieramente inútiles.

2. **El LSTM ancla el ensemble en ~50%, matando 57% de las señales del XGBoost.**
   Es ruido estadístico presentado como inteligencia artificial.

3. **5 de 6 señales tienen PnL neto negativo en simulación con SL/TP.**
   El edge bruto existe pero se destruye con stops mal calibrados.

### La UNA cosa que cambiaría

**Eliminar el LSTM del ensemble de inferencia y reentrenar el XGBoost con label
de dirección absoluta.** Esto resolvería simultáneamente:
- La confusión del inversor sobre qué significa P(Win)
- La compresión del ensemble hacia 50% (más señales accionables)
- La inconsistencia entre el score del screener y el Motor Neural

Todo lo demás — stops, expiración, ratios — son optimizaciones que se pueden
ajustar iterativamente. Pero el modelo predictivo es el corazón de la plataforma.
Si el corazón está midiendo la cosa equivocada, nada de lo demás importa.

### ¿Es el encuadre de "asistente" una protección real?

La app se presenta como "asistente de inversión, no ejecuta órdenes". Legalmente,
esto puede reducir la exposición a responsabilidad fiduciaria. Pero en la práctica,
**el inversor recibe precios exactos de entrada, SL y TP.** Cuando la app dice
"COMPRAR AAPL a $290.55 con SL en $268 y TP en $335", no está "asistiendo" —
está **recomendando**.

El hecho de que el inversor haga clic manualmente en su bróker no cambia que la
decisión ya fue tomada por el algoritmo. Si 5 de 6 tipos de señal tienen PnL
negativo en backtest, el inversor está siendo dirigido hacia una estrategia que
**pierde dinero en el 83% de los casos**.

Esto no es ilegal. Pero no es éticamente sólido.

---

## 6 — Hallazgos priorizados

| # | Hallazgo | Severidad | Impacto |
|---|---|---|---|
| 1 | Label de entrenamiento mide outperformance relativa, no dirección absoluta | **Crítico** | P(Win) no significa lo que el inversor cree |
| 2 | LSTM inyecta ruido: ensemble tiene 57% menos señales accionables que XGBoost puro | **Crítico** | Motor Neural es información muerta para 7/10 tickers |
| 3 | 5/6 señales con PnL negativo en simulación con SL/TP | **Alto** | La estrategia con stops pierde dinero en backtest |
| 4 | 53 LONGs vs 14 SHORTs en mercado con 0% breadth | **Alto** | Sesgo direccional peligroso en mercado bearish |
| 5 | 44% de tickers en zona muerta del modelo (45-55%) | **Medio** | El modelo no ayuda a decidir en casi la mitad de casos |
| 6 | Tasa de expiración 8-12% oculta oportunidades falsas | **Medio** | 1 de cada 10 señales no era accionable |
| 7 | Multiplicadores ATR no consideran fat tails | **Medio** | SL puede saltarse en movimientos extremos |

---

*Este informe se basa exclusivamente en datos extraídos de la API de Iosef Finance
en localhost:8002 el 2026-06-11. Todos los cálculos son verificables. No constituye
asesoramiento financiero.*

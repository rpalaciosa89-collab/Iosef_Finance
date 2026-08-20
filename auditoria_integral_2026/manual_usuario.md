# Manual de Usuario — Iosef Finance

## Índice

1. [📊 Screener — Tabla Principal](#1--screener--tabla-principal)
2. [📈 Ticker Modal — Ficha de la Acción](#2--ticker-modal--ficha-de-la-acción)
3. [⚡ Motor Neural — Score del Modelo ML](#3--motor-neural--score-del-modelo-ml)
4. [📋 Plan de Trading — Señal Predictiva](#4--plan-de-trading--señal-predictiva)
5. [📉 Gráfico — Capa de Señales](#5--gráfico--capa-de-señales)
6. [🧠 Cómo tomar una decisión](#6--cómo-tomar-una-decisión)
7. [⛔ Errores comunes de interpretación](#7--errores-comunes-de-interpretación)

---

## 1 — 📊 Screener — Tabla Principal

Es la primera pantalla que ves al abrir la app. Muestra **98 acciones del Titan 100**
ordenadas por P(Win) de mayor a menor. Cada fila es un ticker y cada columna un
indicador. A continuación, qué significa cada columna, cómo interpretarla y qué
hacer con esa información.

---

### Ticker

| Concepto | Explicación |
|---|---|
| **¿Qué es?** | El símbolo bursátil de la empresa (ej: AAPL = Apple, TSLA = Tesla) |
| **¿Qué significa un valor alto?** | No aplica. Es solo un identificador |
| **¿Qué significa un valor bajo?** | No aplica |
| **¿Cómo se calcula?** | Es el código oficial de la bolsa (NYSE, NASDAQ, etc.) |
| **¿Qué debo hacer con este dato?** | Identificar la empresa. Si no la conoces, haz clic para investigar |

---

### Sector

| Concepto | Explicación |
|---|---|
| **¿Qué es?** | El sector económico al que pertenece la empresa |
| **Ejemplos** | Technology, Healthcare, Consumer Cyclical, Financial Services, Energy |
| **¿Cómo se calcula?** | Proviene de Yahoo Finance (clasificación GICS) |
| **¿Qué debo hacer con este dato?** | Diversificar: no poner todo tu dinero en un solo sector. Si ves 10 Technology en rojo, el sector está débil |

---

### Price

| Concepto | Explicación |
|---|---|
| **¿Qué es?** | El precio actual de mercado de la acción, en dólares |
| **¿Qué significa un valor alto?** | La acción cotiza a un precio nominal alto (ej: $1,777 ASML). No significa que sea "cara" en términos de valoración |
| **¿Qué significa un valor bajo?** | Precio nominal bajo (ej: $20 IBE.MC). No significa que sea "barata" |
| **¿Cómo se calcula?** | Último precio de cierre o precio en tiempo real de Yahoo Finance |
| **¿Qué debo hacer con este dato?** | Saber cuánto cuesta comprar 1 acción. El precio solo importa para calcular cuántas acciones puedes comprar con tu capital |

---

### Chg % (Change %)

| Concepto | Explicación |
|---|---|
| **¿Qué es?** | El cambio porcentual del precio en el día de hoy |
| **¿Qué significa verde (+)?** | La acción está subiendo hoy. Ej: +4.52% (LOW) = está teniendo un buen día |
| **¿Qué significa rojo (−)?** | La acción está bajando hoy. Ej: −6.32% (NOW) = está teniendo un mal día |
| **¿Cómo se calcula?** | `((precio_actual − precio_cierre_ayer) / precio_cierre_ayer) × 100` |
| **¿Qué debo hacer con este dato?** | Contexto inmediato. Un cambio > ±3% es un movimiento fuerte. Si el cambio es extremo (> ±5%) y tienes una posición, revisa si debes ajustar |

---

### RSI (Relative Strength Index, 14 días)

| Concepto | Explicación |
|---|---|
| **¿Qué es?** | Índice de Fuerza Relativa. Mide si una acción está "sobrecomprada" o "sobrevendida" en una escala de 0 a 100 |
| **> 70 (rojo)** | **Sobrecomprada.** La acción ha subido mucho rápido. Puede corregir a la baja. Ej: UNH 73.9 → precaución si vas a comprar |
| **30–70 (neutro)** | Zona neutral. Ni sobrecomprada ni sobrevendida. Ej: AAPL 42.7 |
| **< 30 (verde)** | **Sobrevendida.** La acción ha caído mucho rápido. Posible rebote técnico. Ej: TM 30.7, NFLX 30.0 |
| **¿Cómo se calcula?** | Promedio de ganancias ÷ promedio de pérdidas en los últimos 14 días, usando suavizado exponencial (Wilder's smoothing) |
| **¿Qué debo hacer?** | RSI > 70: no compres (espera corrección). RSI < 30: posible oportunidad de compra si otros indicadores confirman. RSI entre 30-70: indiferente |

---

### Rel Vol (Relative Volume)

| Concepto | Explicación |
|---|---|
| **¿Qué es?** | Compara el volumen de negociación de hoy vs. el promedio de los últimos 20 días |
| **< 1.0x** | Volumen por debajo del promedio. Día normal o tranquilo. Ej: HEI 0.40x |
| **1.0x – 1.5x** | Volumen normal o ligeramente elevado |
| **> 1.5x** | **Volumen inusualmente alto.** Hay interés inusual en la acción. Ej: LVMUY 1.90x |
| **¿Cómo se calcula?** | `volumen_hoy / promedio_volumen_20_días` |
| **¿Qué debo hacer?** | Volumen > 1.5x + precio subiendo = compradores entrando con fuerza (señal alcista). Volumen > 1.5x + precio bajando = vendedores saliendo (señal bajista). Confirma la dirección del movimiento |

---

### Mom 1M (Momentum 1 Mes)

| Concepto | Explicación |
|---|---|
| **¿Qué es?** | El cambio porcentual del precio en el último mes (20 días hábiles) |
| **Verde (+)** | La acción ha subido en el último mes. Ej: +56.24% (ARM) = tendencia muy alcista |
| **Rojo (−)** | La acción ha bajado en el último mes. Ej: −24.23% (INTU) = tendencia bajista fuerte |
| **¿Cómo se calcula?** | `((precio_hoy − precio_hace_20_días) / precio_hace_20_días) × 100` |
| **¿Qué debo hacer?** | Momentum positivo + score alto = tendencia alcista saludable (posible compra). Momentum muy negativo + P(Win) alto = posible oportunidad de rebote. Momentum > 30%: precaución, puede estar sobre-extendido |

---

### Score (0-9) — Composite Score

| Concepto | Explicación |
|---|---|
| **¿Qué es?** | Puntuación técnica de 0 a 9 basada en 7 condiciones objetivas. Es una nota de "salud técnica" de la acción |
| **8–9** | **Excelente.** La acción cumple casi todas las condiciones técnicas positivas. Ej: JNJ 9, ORCL 9 |
| **6–7** | **Buena.** Señal técnica favorable. Ej: CRWD 7 |
| **3–5** | **Neutral.** Condiciones mixtas. Ej: AAPL 5 |
| **0–2** | **Débil.** Pocas o ninguna condición positiva. Ej: INTU "–" (0) |
| **¿Cómo se calcula?** | Se suma 1 punto por cada condición que se cumple: precio > SMA20 (+1), precio > SMA50 (+2), precio > SMA200 (+3), RSI < 30 (+2) o RSI > 70 (−2), momentum > 0 (+2), volumen relativo > 1.5x (+1), cambio diario > 0 (+1). Máximo teórico: 11, pero se presenta sobre 9 |
| **¿Qué debo hacer?** | Score 8-9: base técnica sólida para comprar. Score 0-2: base técnica débil, no es momento de comprar (aunque el P(Win) sea alto — ver sección 7) |

---

### P(Win) — Probabilidad de Éxito del Modelo ML

| Concepto | Explicación |
|---|---|
| **¿Qué es?** | **NO es probabilidad de que el precio suba.** Es la probabilidad estimada por el modelo XGBoost de que esta acción tenga un rendimiento **superior a su propio promedio** en los próximos 5 días |
| **≥ 60%** | El modelo detecta alta probabilidad de que la acción supere su rendimiento típico en 5 días. Puede ser tanto por rebote (si cayó mucho) como por continuación de tendencia |
| **45–60%** | Zona gris. El modelo no encuentra un patrón claro |
| **≤ 45%** | Baja probabilidad de superar su rendimiento típico |
| **⚠️ IMPORTANTE** | Una acción que cayó −24% en el mes (INTU) puede tener P(Win) 58% porque el modelo detecta patrón de reversión a la media. No significa que "va a subir" — significa que probablemente tendrá un rendimiento mejor que su propio promedio (que es muy negativo) |
| **¿Cómo se calcula?** | Modelo XGBoost entrenado con 37K muestras históricas sobre 98 tickers, 5 features: log_return, volatilidad, momentum_10d, RSI_14, MACD_histogram |
| **¿Qué debo hacer?** | P(Win) alto + Score alto = señal más confiable. P(Win) alto + Score bajo = potencial rebote, pero más arriesgado. Combínalo SIEMPRE con el composite score y el plan de trading |

---

### Signal (Estado de la Señal)

| Concepto | Explicación |
|---|---|
| **¿Qué es?** | El estado del ciclo de vida de la señal para ese ticker |
| **NEW** | Señal recién detectada. Ventana de entrada abierta. Momento óptimo para actuar |
| **ACTIVE** | Señal detectada anteriormente, sigue vigente. Aún se puede actuar |
| **WEAKENING** | La señal está perdiendo fuerza. La ventana de entrada se cierra. Actuar con cautela o esperar |
| **EXPIRED** | La señal expiró. Ya no es válida |
| **— (vacío)** | Sin señal activa para este ticker en este momento |
| **¿Qué debo hacer?** | Prioriza NEW y ACTIVE. Evita WEAKENING si puedes. Ignora EXPIRED y vacíos |

---

## 2 — 📈 Ticker Modal — Ficha de la Acción

Al hacer clic en cualquier ticker del screener, se abre una ventana con 3 pestañas
y múltiples secciones. Esto es lo que contiene:

---

### 📈 Pestaña: Análisis Predictivo

#### Gráfico de velas (Candlestick Chart)

| Elemento | Qué es |
|---|---|
| **Velas verdes** | El precio de cierre fue mayor que el de apertura (alcista) |
| **Velas rojas** | El precio de cierre fue menor que el de apertura (bajista) |
| **Barras inferiores** | Volumen de negociación (más altas = más actividad) |
| **Toggle "📍 Señales ON/OFF"** | Activa/desactiva los marcadores de señales en el gráfico |
| **Fondo verde/rojo** | Tendencia general del período (verde = alcista, rojo = bajista) |
| **Pins de señal** | Flechas ▲ (LONG) / ▼ (SHORT) con el score en la vela de detección |
| **Color del pin** | Verde brillante = señal NUEVA, verde = ACTIVA, ámbar = debilitándose, gris = expirada |
| **Panel lateral** | Al hacer clic en un pin: detalle completo de la señal con SL, TP, rendimiento |

**Timeframes disponibles:**

| Botón | Período | Velas | Usar para |
|---|---|---|---|
| 1D | 1 día | ~390 (1min) | Ver movimiento intradía, acción del precio hoy |
| 5D | 5 días | ~390 (5min) | Ver tendencia de la semana |
| 1MO | 1 mes | ~286 (30min) | Ver tendencia de corto plazo |
| 3MO | 3 meses | ~64 (1d) | Ver tendencia de mediano plazo |
| 6MO | 6 meses | ~124 (1d) | Contexto semestral |
| 1Y | 1 año | ~251 (1d) | Tendencia de largo plazo, soportes y resistencias |

---

#### Cards de Indicadores Técnicos

| Card | Significado | Cómo leerlo |
|---|---|---|
| **Price** | Precio actual de mercado | El número en sí |
| **Change** | Cambio % hoy | Verde = sube, Rojo = baja |
| **RSI (14)** | Fuerza relativa | >70 rojo "Sobrecomprado", <30 verde "Sobrevendido". Con hint debajo |
| **SMA 20** | Media móvil simple de 20 días | ▲ Sobre = precio > SMA20 (positivo). ▼ Bajo = precio < SMA20 (negativo) |
| **SMA 50** | Media móvil simple de 50 días | ▲ Sobre = tendencia de mediano plazo positiva. ▼ Bajo = negativa |
| **SMA 200** | Media móvil simple de 200 días | ▲ Sobre = tendencia de largo plazo positiva. ▼ Bajo = tendencia bajista de fondo |
| **Rel Volume** | Volumen vs. promedio 20d | >1.5x = actividad inusual |
| **Momentum 1M** | Rendimiento en el último mes | Verde = positivo, Rojo = negativo |
| **Prob. P(Win)** | Score del modelo ML | Tooltip: "Mide probabilidad de superar rendimiento típico en 5 días" |
| **Signal Status** | Estado del ciclo de vida | NEW / ACTIVE / WEAKENING / — |

**Interpretación combinada de las SMAs:**
- Precio > SMA20 > SMA50 > SMA200 → **Tendencia alcista perfecta** (todas las medias alineadas)
- Precio < SMA20 < SMA50 < SMA200 → **Tendencia bajista perfecta** (todas las medias alineadas)
- SMA20 y SMA50 cruzadas → **Zona de indecisión o cambio de tendencia**

---

## 3 — ⚡ Motor Neural — Score del Modelo ML

Esta sección muestra el resultado del modelo de machine learning que combina
XGBoost + LSTM.

| Campo | Significado |
|---|---|
| **P(Win) XGBoost** | Score del modelo XGBoost entrenado con indicadores técnicos puntuales (RSI, MACD, momentum, volatilidad). Es el más reactivo a cambios de precio |
| **P(Win) LSTM** | Score del modelo de red neuronal LSTM que analiza 60 días de secuencia histórica. Tiende a ser más conservador (~50%) |
| **Score Ensemble** | Combinación ponderada: 40% XGBoost + 60% LSTM. Es el score "oficial" |
| **Señal** | COMPRA (≥55%), VENTA (≤45%), NEUTRAL (45-55%) |
| **Badge de alineación** | ✅ CONFIRMADO = el motor neural coincide con el plan de trading del screener. ⚠️ DIVERGENTE = el motor difiere (reduce tamaño de posición). NEUTRAL = sin dirección clara |

---

## 4 — 📋 Plan de Trading — Señal Predictiva

Esta sección te da los precios exactos para operar. Aparece solo si hay un plan
calculado.

| Campo | Significado |
|---|---|
| **LONG / SHORT** | LONG = comprar esperando que suba. SHORT = vender esperando que baje |
| **Entry** | Precio de entrada recomendado. Es el precio actual al momento de la detección |
| **Stop Loss** | Precio donde debes vender para limitar pérdidas. En LONG está por debajo del entry. En SHORT está por encima |
| **Take Profit** | Precio objetivo donde tomar ganancias. En LONG está por encima. En SHORT está por debajo |
| **R/R Ratio** | Ratio riesgo/recompensa. 1:2 significa que por cada $1 que arriesgas, esperas ganar $2 |
| **Botón 📝 Simular** | Ejecuta esta operación en Paper Trading (cuenta simulada de $100,000) sin salir del modal |

**Cómo verificar que el plan tiene sentido:**

- **LONG válido:** Entry > Stop Loss ✅ y Entry < Take Profit ✅
- **SHORT válido:** Entry < Stop Loss ✅ y Entry > Take Profit ✅

---

### 🏦 Pestaña: Salud Financiera

Muestra datos fundamentales de la empresa si están disponibles:
- Ingresos (Revenue) y Beneficio Neto (Net Income) por año fiscal
- Balance: Activos Totales, Deuda Total, Efectivo
- Flujo de Caja Libre (Free Cash Flow)

Útil para evaluar si la empresa es sólida más allá del análisis técnico.

---

### ⚡ Pestaña: Backtesting Cuantitativo

Simulación histórica de 1 año usando un algoritmo de cruce de medias móviles.

| Campo | Significado |
|---|---|
| **Total Return (1Y)** | Rendimiento total que habrías obtenido en el último año siguiendo la estrategia. Positivo = habrías ganado, Negativo = habrías perdido |
| **Max Drawdown** | La mayor caída desde un pico. Mide el peor escenario posible. Ej: −15% significa que en el peor momento perdiste 15% |
| **Sharpe Ratio** | Rendimiento ajustado por riesgo. > 1.0 es bueno, > 2.0 es excelente, < 0.5 es pobre |

---

## 5 — 📉 Gráfico — Capa de Señales

Cuando una acción tiene señal activa y el toggle "📍 Señales" está en ON,
el gráfico muestra:

| Elemento visual | Qué indica |
|---|---|
| **Flecha ▲ verde** | Señal LONG (compra). La flecha apunta hacia arriba |
| **Flecha ▼ roja** | Señal SHORT (venta). La flecha apunta hacia abajo |
| **Score (ej: "66%")** | Probabilidad asignada por el modelo al momento de la detección |
| **Etiqueta (NUEVA / ACTIVA / DÉBIL)** | Estado actual del ciclo de vida de la señal |
| **Badge [N]** | Señales agrupadas (N señales en la misma vela o cercanas). Click para expandir |
| **Líneas punteadas SL/TP** | Aparecen al hacer clic en un pin. Roja = Stop Loss, Verde = Take Profit |
| **Panel lateral** | Al hacer clic en el pin: dirección, score, estado, entry, SL con %, TP con %, barra de rendimiento desde detección |

---

## 6 — 🧠 Cómo tomar una decisión

### Paso 1 — Escanear la tabla

Busca tickers que cumplan **al menos 3 de estas 4 condiciones**:

- [ ] P(Win) ≥ 55%
- [ ] Composite Score ≥ 6
- [ ] Signal Status = NEW o ACTIVE
- [ ] RSI entre 30 y 70 (evitar extremos salvo que busques rebotes)

### Paso 2 — Abrir el ticker

Haz clic y verifica:
- [ ] El gráfico muestra contexto favorable (no está en caída libre reciente)
- [ ] Las SMAs están alineadas o al menos el precio está sobre SMA200
- [ ] El Motor Neural dice COMPRA (si buscas LONG) o VENTA (si buscas SHORT)
- [ ] El badge de alineación dice ✅ CONFIRMADO

### Paso 3 — Revisar el Plan de Trading

- [ ] Entry, SL y TP son lógicos para la dirección (ver sección 4)
- [ ] El R/R Ratio es ≥ 1:2 (arriesgas poco para ganar más)
- [ ] El SL está a una distancia que puedes tolerar (< 10% del entry)

### Paso 4 — Ejecutar (en tu bróker real) o simular (Paper Trading)

Usa los precios exactos del plan de trading. No los ajustes manualmente —
están calculados con ATR (volatilidad real) y adaptados al tipo de señal.

---

## 7 — ⛔ Errores comunes de interpretación

### ❌ "P(Win) 66% significa 66% de probabilidad de ganar dinero"

**Falso.** P(Win) mide probabilidad de que la acción supere su **propio rendimiento
promedio** en 5 días. Si una acción viene cayendo −5% diario, "superar su promedio"
puede significar caer solo −1%. No es lo mismo que "el precio va a subir".

### ❌ "Score 0 y P(Win) 66% es contradictorio"

**No necesariamente.** El composite score (0-9) mide condiciones técnicas objetivas
(SMAs, RSI, volumen). P(Win) es un modelo ML que detecta patrones estadísticos
que el ojo humano no ve. Pueden divergir. Cuando divergen, confía más en el
composite score para dirección y en el P(Win) para timing.

### ❌ "Si el Motor Neural dice NEUTRAL, ignoro todo"

**No.** NEUTRAL solo significa que el modelo no encuentra sesgo claro. El plan
de trading puede seguir siendo válido. Usa el badge de alineación para decidir:
- CONFIRMADO → actúa con confianza
- DIVERGENTE → actúa con posición reducida
- NEUTRAL → espera o actúa con mucha cautela

### ❌ "Rel Vol 0.36x significa que casi no se opera"

Significa que hoy el volumen está al 36% del promedio. Puede ser un día tranquilo
o festivo. No es necesariamente malo. Solo presta atención cuando > 1.5x.

### ❌ "RSI 45 es malo"

No. 45 está en zona neutral. No es ni sobrecomprado ni sobrevendido. Es un valor
normal que no da señal por sí mismo.

### ❌ "Verde en Chg % significa que debo comprar"

No. El cambio diario es solo el movimiento de hoy. Una acción puede subir +3%
hoy y aun así estar en tendencia bajista de largo plazo. Siempre mira el contexto
en timeframes mayores (1MO, 6MO).

---

*Este manual describe Iosef Finance v2.0. Todos los indicadores se calculan en tiempo real con datos de Yahoo Finance. Los scores del modelo ML se basan en datos históricos y no garantizan resultados futuros.*

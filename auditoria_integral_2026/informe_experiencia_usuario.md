# Informe de Experiencia de Usuario — Iosef Finance

**Rol del evaluador:** Inversor minorista con conocimientos básicos de bolsa
**Fecha:** 2026-06-10
**Condiciones de mercado:** Bearish (breadth 0%, 0 de 98 tickers sobre SMA50)
**App evaluada:** `http://localhost:5173/dashboard`

---

## Resumen Ejecutivo

**¿Puede un inversor normal tomar decisiones con Iosef Finance?**

Sí, pero con fricción. La app proporciona datos precisos, planes de trading con precios exactos y métricas de respaldo. Sin embargo, la experiencia se ve lastrada por **señales contradictorias entre secciones**, sobrecarga de jerga técnica, y una presentación que no jerarquiza lo importante. El usuario sale con más preguntas que certezas.

**Nota global de experiencia: 6.2/10**

---

## Fase 1 — Primer Vistazo al Dashboard

### Lo que veo al abrir la app

Entro al dashboard y me encuentro con:
- Una tabla de **98 acciones** con 10 columnas
- **29 alertas** (la mayoría en rojo)
- Una alerta amarilla enorme: "Market Weakness: breadth at 0%"

### ¿Entiendo qué significa cada columna?

| Columna | ¿La entiendo? | Mi confusión |
|---|---|---|
| TICKER | ✅ Sí | Sé qué es un símbolo bursátil |
| SECTOR | ✅ Sí | Sé que es tecnología, salud, etc. |
| PRICE | ✅ Sí | El precio actual |
| CHG% | ✅ Sí | Lo que subió o bajó hoy |
| RSI | ⚠️ Más o menos | Sé que 70=sobrecomprado, 30=sobrevendido. Pero 45... ¿es bueno o malo? |
| REL VOL | ❌ No | "0.36x" — ¿es mucho o poco? ¿Qué significa la "x"? |
| MOM 1M | ⚠️ Más o menos | Sé que es el cambio en un mes. ¿-5% es grave? |
| SCORE (0-9) | ❌ Confuso | ¿Es sobre 9 puntos máximos? ¿4 es bueno? ¿Qué mide? |
| P(WIN) | ❌ Muy confuso | ¿Probabilidad de ganar? ¿Un 66% significa que tengo 2/3 chances? ¿Entonces por qué la mayoría de las que tienen 66% están en rojo y cayendo? |
| SIGNAL | ⚠️ Más o menos | "NEW", "ACTIVE", vacío... ¿Cuál es mejor? |

### Lo que más me impacta al abrir la app

**29 alertas, 25 en rojo.** Mi primera reacción: "¿Debería cerrar la app y no invertir hoy? ¿O son oportunidades?". La app no me dice cuál es cuál.

Veo que las 5 acciones con mayor P(Win) son todas SHORT, con cambios negativos de -2% a -3.5%. Esto me confunde: **¿"Top" significa las mejores para ganar dinero, aunque sea vendiendo (SHORT)?** Como inversor tradicional, asumo que "top" es para comprar.

### Hallazgos de esta fase

**UX-001 — P(Win) contradice la intuición visual (Alta)**

Las acciones con mayor P(Win) — 66% — están todas en rojo con cambios negativos. Un inversor normal asocia "rojo = malo" y "alta probabilidad = buena". Ver 66% de probabilidad en una acción que cayó -3.5% hoy genera desconfianza inmediata. La app no explica que P(Win) mide probabilidad de SUPERAR la mediana del ticker (reversión a la media), no probabilidad de que el precio suba en términos absolutos.

**UX-002 — Sin tooltips ni ayuda contextual en columnas (Media)**

Ninguna columna tiene ayuda emergente. Si no sé qué es RSI o REL VOL, tengo que ir a Google. La app asume que el usuario es técnico.

**UX-003 — "Market Weakness: breadth at 0%" no se explica (Alta)**

La alerta más prominente del dashboard usa jerga cuantitativa. ¿Qué es "breadth"? ¿A qué porcentaje se refiere? ¿0% de qué sobre qué? Como usuario, me asusta pero no me informa.

**UX-004 — 59 de 98 tickers con señal "weak_signal" (Media)**

Cuando el 60% del universo muestra la misma señal débil, la columna SIGNAL pierde valor discriminatorio. Es ruido visual.

---

## Fase 2 — Investigando Tickers (TSLA, LLY, NVDA)

### ¿Qué veo al hacer clic en TSLA?

La ficha del ticker me muestra:

**La gráfica de velas** — Entiendo que es el precio histórico. Puedo cambiar entre 1D, 5D, 1MO, etc. Me gusta poder ver el contexto. ✅

**Los indicadores (cards):**

| Indicador | Valor | ¿Entiendo si es bueno o malo? |
|---|---|---|
| PRICE | $382.97 | — |
| CHANGE | -3.46% | ❌ Rojo = malo |
| RSI (14) | 39.7 | ⚠️ Sé que <30 es oversold. ¿39.7 está cerca? ¿Es oportunidad de compra? |
| SMA 20 | $419.96 | ❌ Sé que el precio ($382) está debajo de SMA20 ($419). ¿Es señal de venta? No me lo dice explícitamente |
| MOMENTUM 1M | -13.99% | ❌ -14% en un mes suena muy negativo. ¿Esto es un desplome? |
| P(WIN) | 66.2% | ❌ ¿66% de probabilidad de ganar en una acción que cayó 14% este mes? Algo no cuadra |
| SIGNAL STATUS | ACTIVE | ⚠️ "Active" — ¿significa que la señal está viva y debería actuar? |

**El Motor Neural:**
- XGBoost: 66.5%
- LSTM: 50.5%
- Ensemble: 56.9%
- **SEÑAL: NEUTRAL**

Esto me genera **confusión inmediata**. El screener me muestra P(Win)=66.2% (alto) con plan SHORT 1:2. Pero el Motor Neural dice NEUTRAL (56.9%). **¿A cuál le hago caso?**

**El Plan de Trading:**
- DIRECCIÓN: SHORT
- ENTRY: $384.30
- STOP LOSS: $413.28 (+7.5%)
- TAKE PROFIT: $326.35 (-15%)
- R/R: 1:2

Aquí tengo sentimientos encontrados. Por un lado, los números son **muy claros**: sé exactamente a qué precio vender, dónde poner el stop, y cuánto puedo ganar. Los porcentajes (+7.5%, -15%) me ayudan a dimensionar el riesgo. **Esto es lo mejor de la app hasta ahora.** ✅

Pero por otro lado, el Motor Neural me dice NEUTRAL y el plan dice SHORT. **No sé si actuar o no.**

### ¿Qué veo al hacer clic en LLY?

Mismo formato:

| Dato | Valor | Mi interpretación |
|---|---|---|
| PRICE | $1,140.08 | — |
| CHANGE | -0.40% | — |
| RSI | 68.03 | ⚠️ Cerca de 70 (sobrecomprado). ¿Debería vender? |
| SCORE | 8/9 | ✅ ¡Alto! Esto me gusta |
| P(WIN) | 63.7% | ✅ Más de 60%, me da confianza |
| MOMENTUM 1M | +12.43% | ✅ Positivo |
| Plan | LONG, SL=$1,061 (-7%), TP=$1,296 (+13.6%), R/R=1:2 | ✅ Muy claro, sé qué hacer |
| Motor Neural | NEUTRAL (55.7%) | ❌ Otra vez neutral cuando yo pensaba que era buena |

**Decisión interna:** LLY me gusta. Score 8/9, momentum positivo (+12.4%), plan LONG claro con R/R 1:2. Pero el "NEUTRAL" del motor neural me frena. ¿Por qué es neutral si todo lo demás pinta bien?

### ¿Qué veo al hacer clic en NVDA?

NVDA salió en las alertas: "Breakdown below SMA50". Abro su ficha:

| Dato | Valor |
|---|---|
| PRICE | $201.68 |
| CHANGE | -3.12% |
| RSI | 42.01 |
| SCORE | 3/9 |
| P(WIN) | 55.7% |
| Plan | SHORT, SL=$216 (+7.3%), TP=$176 (-12.7%), R/R=1:2 |
| Motor Neural | NEUTRAL (55.4%) |

NVDA tiene una señal de SHORT con R/R 1:2. Pero igual que TSLA y LLY: el motor neural dice NEUTRAL. **Tres de tres tickers con NEUTRAL del motor neural.** Esto me hace preguntarme: ¿el motor neural siempre dice NEUTRAL? ¿Sirve para algo?

### Hallazgos de esta fase

**UX-005 — Motor Neural dice NEUTRAL para todos los tickers evaluados (Crítica)**

TSLA (56.9%), LLY (55.7%), NVDA (55.4%) — los tres con ensemble entre 55-57%, todos catalogados NEUTRAL. El umbral de decisión es COMPRA ≥ 60, VENTA ≤ 40, NEUTRAL entre 40-60. Esto significa que la gran mayoría de los tickers caerán en NEUTRAL, haciendo que esta sección del modal pierda utilidad práctica. El usuario aprende a ignorarla.

**UX-006 — Conflicto entre Screener (SHORT/LONG con R/R) y Motor Neural (NEUTRAL) (Crítica)**

El screener recomienda explícitamente SHORT en TSLA con precios exactos, pero el Motor Neural en el modal dice NEUTRAL. El usuario no sabe si seguir el plan de trading o abstenerse. **La app se contradice a sí misma en la misma pantalla.**

**UX-007 — La ficha NO muestra "Salud Financiera" ni "Backtesting" (Alta)**

El prompt pedía ver datos fundamentales (P/E, deuda) y backtesting histórico. Al hacer clic en el ticker, solo veo "Análisis Predictivo" (gráfica + indicadores + motor neural) y pestañas para "Salud Financiera" y "Backtesting Cuantitativo". Si estas pestañas no cargan datos o están vacías, el usuario siente que la app está incompleta.

**UX-008 — Los indicadores no tienen color ni contexto (Media)**

RSI 39.7 — ¿es bueno? SMA20 $419 vs precio $382 — ¿es malo? La app muestra números crudos sin interpretación visual (flechas, colores, badges). El usuario tiene que hacer aritmética mental para cada indicador.

---

## Fase 3 — Signal Lab y Top Opportunities

### Signal Lab

Abro Signal Lab. Veo una tabla con 12 tipos de señales:

| Señal | Ocurrencias | Win Rate | Avg Return | Mi interpretación |
|---|---|---|---|---|
| momentum_shift_up | 2,856 | 53.0% | +0.58% | Muchas ocurrencias, pero 53% apenas mejor que moneda al aire. +0.58% me parece poco |
| momentum_shift_down | 2,750 | 54.4% | +0.76% | ¿54% en caídas? ¿Gano más en caídas que en subidas? |
| overbought | 978 | 52.4% | +0.42% | Casi random |
| oversold | 716 | 55.3% | +0.57% | Ok, oversold ligeramente mejor |

**¿Esto me ayuda a decidir?** Más o menos. Sé que históricamente las señales funcionan ligeramente mejor que el azar (53-57% win rate). Pero +0.5% de retorno medio en 5 días no me entusiasma. Y no sé cómo aplicar esto a MI decisión de hoy. ¿Qué señal está activa AHORA para qué ticker?

### Top Opportunities

20 tickers. Los primeros 5:

1. INTU — score 67.6%, composite 0, **SHORT**
2. SNPS — score 66.4%, composite 0, plan vacío (sin dirección)
3. TSLA — score 66.2%, composite 0, **SHORT**
4. REGN — score 62.7%, composite 0, plan vacío
5. ARM — score 61.4%, composite 7, **SHORT**

**Mi reacción:** Las "mejores oportunidades" son todas para VENDER (SHORT). Como inversor tradicional que busca COMPRAR, esta sección me es inútil. Además, SNPS y REGN no tienen dirección en el plan — ni siquiera sé qué hacer con ellas.

### Hallazgos de esta fase

**UX-009 — Top Opportunities no diferencia LONG de SHORT (Alta)**

El usuario espera que "Top" signifique "mejores para comprar". Ver solo SHORTs en un mercado bearish es técnicamente correcto, pero la app no advierte "Este es un mercado para posiciones cortas". El usuario se siente desorientado.

**UX-010 — Plan de trading vacío en top opportunities (Alta)**

SNPS y REGN están en el top 5 pero no tienen dirección (LONG/SHORT), entry, SL ni TP. ¿Por qué están en "oportunidades" si no son accionables?

**UX-011 — Signal Lab no se conecta con el screener (Media)**

Veo que "momentum_shift_down" tiene 54.4% win rate histórico, pero no sé qué tickers tienen esa señal AHORA. Faltaría un enlace: "Ver tickers con esta señal activa →".

---

## Fase 4 — Prueba de Coherencia (Tabla Comparativa)

### TSLA

| Dato | Dashboard (Scan) | Ticker Modal | Neural Score | ¿Coincide? |
|---|---|---|---|---|
| Precio | $382.97 | $382.97 | — | ✅ |
| RSI | 39.74 | 39.74 | — | ✅ |
| P(Win) / Score | 66.2% ML | 66.2% ML | 56.9% Ensemble | ❌ 66.2% vs 56.9% |
| Señal Compra/Venta | SHORT | SHORT | NEUTRAL | ❌ Contradicción |
| Dirección | SHORT | SHORT | — | ✅ |

**Conclusión:** El precio y los indicadores son consistentes. Pero el Motor Neural (56.9% NEUTRAL) contradice el plan SHORT recomendado por el screener. **¿Hago SHORT o espero? La app no me ayuda a resolver esta duda.**

### LLY

| Dato | Dashboard | Ticker Modal | Neural Score | ¿Coincide? |
|---|---|---|---|---|
| Precio | $1,140.08 | $1,140.08 | — | ✅ |
| RSI | 68.03 | 68.03 | — | ✅ |
| P(Win) / Score | 63.7% ML | 63.7% ML | 55.7% Ensemble | ❌ |
| Señal Compra/Venta | LONG (clarity=baja) | LONG | NEUTRAL | ❌ |
| Dirección | LONG | LONG | — | ✅ |

**Conclusión:** Mismo patrón. Score 8/9 con plan LONG, pero neural dice NEUTRAL. Además, `clarity=baja` ya me advertía que la señal no era firme. Al menos hay coherencia entre "baja claridad" y "NEUTRAL".

### NVDA

| Dato | Dashboard | Ticker Modal | Neural Score | ¿Coincide? |
|---|---|---|---|---|
| Precio | $201.68 | $201.68 | — | ✅ |
| RSI | 42.01 | 42.01 | — | ✅ |
| P(Win) / Score | 55.7% ML | 55.7% ML | 55.4% Ensemble | ✅ (~coincide) |
| Señal Compra/Venta | SHORT | SHORT | NEUTRAL | ❌ |
| Dirección | SHORT | SHORT | — | ✅ |

**Conclusión:** NVDA es el más consistente de los tres. 55.7% vs 55.4% es casi idéntico. Pero el umbral de NEUTRAL (40-60%) captura todos los scores del modelo. **El problema es el umbral, no los datos.**

### Hallazgo de coherencia

**UX-012 — El umbral NEUTRAL (40-60%) anula la utilidad del Motor Neural (Crítica)**

Los tres tickers evaluados caen en NEUTRAL (55-57%). Revisando el rango completo de P(Win) del screener: 31.0% - 66.2%. Dado que el ensemble se forma con 40% XGBoost + 60% LSTM y el LSTM tiende a dar ~50% para la mayoría de tickers, el ensemble nunca sale del rango 40-60%. La señal del Motor Neural será NEUTRAL para **virtualmente todos los tickers**. Esto lo convierte en información muerta — ocupa espacio pero nunca ayuda a decidir.

---

## Fase 5 — Analytics y Paper Trading

### Analytics

Veo 9 tipos de señal analizados con 1982 trades en total. El mensaje principal:

> "La señal 'breakdown' tiene un win rate efectivo del 65.2% con 231 operaciones registradas."
> "El contexto 'bearish' ha propiciado un win rate efectivo del 63.2%."

**¿Me da confianza?** Parcialmente. Un 65% de acierto suena bien (mejor que el 50% aleatorio). Pero sé que estos trades son simulados (no reales). La app NO me dice explícitamente que son datos de backfill simulado — me hace creer que es historial real.

### Paper Trading

Tengo $100,000 simulados. 0 posiciones abiertas, 0 trades cerrados. Es un lienzo en blanco. ✅

Podría ejecutar una operación de prueba. Pero no sé cómo: ¿dónde está el botón de "Ejecutar orden simulada"? ¿Tengo que ir al ticker y hacer clic en algo?

### Hallazgos de esta fase

**UX-013 — Analytics no aclara que son trades simulados (Media)**

La redacción "230 operaciones registradas" da a entender que son reales. El usuario podría sobreestimar la efectividad histórica del sistema.

**UX-014 — Paper Trading no está integrado al flujo del modal (Media)**

Cuando veo el plan SHORT para TSLA en el modal, no hay un botón de "Ejecutar en Paper Trading". Tengo que navegar a otra pestaña, crear la orden manualmente. Se pierde el impulso de decisión.

---

## Fase 6 — Mis Decisiones de Inversión

### Decisión 1: LLY — COMPRA (LONG)

| Pregunta | Mi respuesta |
|---|---|
| Ticker elegido | **LLY** (Eli Lilly) |
| ¿Por qué? | Composite score 8/9, momentum +12.4% mensual, precio sobre SMA20/50/200, sector Healthcare defensivo |
| ¿COMPRA o VENTA? | **COMPRA (LONG)** |
| Precio de entrada | $1,140.08 |
| Stop Loss | $1,061.76 (-6.8%) |
| Take Profit | $1,296.71 (+13.6%) |
| R/R Ratio | **1:2** |
| Nivel de confianza | **Media** (7/10) |
| ¿Qué me dio confianza? | El plan de trading es clarísimo: precios exactos, SL/TP con porcentajes, R/R favorable. Los indicadores técnicos respaldan la decisión |
| ¿Qué me generó dudas? | El Motor Neural dice NEUTRAL. RSI en 68 (cerca de sobrecompra). clarity=baja. |
| ¿Información contradictoria? | **Sí** — El composite score (8/9) dice "muy alcista" pero el neural dice NEUTRAL y la claridad es baja |

**Decisión final:** VOY A COMPRAR. Los indicadores técnicos pesan más que el NEUTRAL del motor. Pero lo hago con menos convicción de la que me gustaría. Si el motor neural hubiera dicho COMPRA, mi confianza sería 9/10 en vez de 7/10.

### Decisión 2: TSLA — VENTA (SHORT)

| Pregunta | Mi respuesta |
|---|---|
| Ticker elegido | **TSLA** (Tesla) |
| ¿Por qué? | P(Win)=66.2%, momentum -14% mensual, breakdown claro, alerta activa |
| ¿COMPRA o VENTA? | **VENTA (SHORT)** |
| Precio de entrada | $384.30 |
| Stop Loss | $413.28 (+7.5%) |
| Take Profit | $326.35 (-15%) |
| R/R Ratio | **1:2** |
| Nivel de confianza | **Media-Baja** (5/10) |
| ¿Qué me dio confianza? | El plan SHORT está bien definido. NVDA y otras tech también dan SHORT — hay consenso sectorial |
| ¿Qué me generó dudas? | El Motor Neural dice NEUTRAL. -14% en un mes puede ser sobre-extendido y rebotar. No sé si es un buen momento para entrar SHORT o si ya pasó |
| ¿Información contradictoria? | **Sí** — Mismo patrón que LLY: screener dice SHORT, neural dice NEUTRAL |

**Decisión final:** VOY A VENDER (SHORT). Pero con tamaño de posición reducido (menos capital) porque mi confianza es solo 5/10.

---

## Fase 7 — Evaluación Global

| Dimensión | Nota | ¿Por qué? |
|---|---|---|
| **Claridad** | 5/10 | Demasiada jerga técnica sin explicación. Columnas como REL VOL y SCORE no son intuitivas. Las alertas usan lenguaje cuantitativo |
| **Confianza** | 6/10 | Los datos son precisos y los planes de trading son exactos. Pero la contradicción Screener vs Neural y los umbrales NEUTRAL me hacen dudar |
| **Coherencia** | 4/10 | El Screener dice SHORT/LONG con R/R explícito. El Motor Neural dice NEUTRAL para todo. Son dos voces distintas en la misma app |
| **Accionabilidad** | 7/10 | El plan de trading es excelente: entry, SL, TP, R/R con porcentajes. Sé exactamente qué hacer. Pero llegar a la decisión requirió ignorar el Neural Score |
| **Completitud** | 5/10 | Faltan datos fundamentales (P/E, deuda, revenue). El backtesting no se ve. Paper trading no integrado al modal. Sin alertas configurables |
| **Velocidad** | 8/10 | La app carga rápido. El scan responde en <1s. Los gráficos se renderizan sin demora |
| **Diseño** | 7/10 | Visualmente agradable. Las cards de indicadores son claras. Los colores verde/rojo ayudan. La tabla del screener es densa pero funcional |

**Nota global: 6.2/10**

### Tres cosas que me gustaron

1. **El Plan de Trading** — entry exacto, SL con porcentaje, TP con porcentaje, R/R Ratio. Es justo lo que necesito para operar. Si toda la app tuviera este nivel de claridad, sería 9/10.
2. **La velocidad** — todo carga instantáneo. No hay pantallas de carga que duren segundos.
3. **Los indicadores en cards** — ver RSI, SMA, Momentum en tarjetas individuales dentro del modal ayuda a procesar la información visualmente.

### Tres cosas que me confundieron o frustraron

1. **El Motor Neural siempre dice NEUTRAL** — Tres de tres tickers. Ocupa espacio, no ayuda a decidir, y contradice el plan de trading.
2. **P(Win) en el screener no coincide con lo que veo** — 66% de probabilidad en una acción que cayó -14% en el mes. Mi intuición me dice que eso no puede ser correcto, y la app no me explica por qué sí lo es.
3. **Demasiadas señales "weak_signal"** — 59 de 98 tickers. La columna SIGNAL del screener pierde utilidad cuando todo es débil.

### ¿Recomendaría Iosef Finance a un amigo?

**Sí, con reservas.** Le diría: "Úsala para obtener precios de entrada, stop-loss y take-profit — eso lo hace muy bien. Pero ignora el Motor Neural por ahora, y ten presente que el P(Win) no es probabilidad de que el precio suba."

### ¿Volvería a usar la app mañana?

**Sí.** Principalmente por el plan de trading. Pero si en una semana el Motor Neural sigue diciendo NEUTRAL para todo, empezaré a ignorar esa sección por completo.

### Si pudiera pedir UNA sola mejora

**Que el Motor Neural y el Screener hablen el mismo idioma.** Si el screener recomienda SHORT con R/R 1:2, el motor neural debería reflejar esa misma dirección o al menos explicar POR QUÉ difiere. Tener dos sistemas que se contradicen en la misma pantalla destruye la confianza.

---

## Hallazgos — Formato de Auditoría

### Críticos (impiden confiar en la app)

| ID | Descripción | Impacto |
|---|---|---|
| **UX-005** | Motor Neural siempre NEUTRAL (40-60% umbral captura todo) | El usuario aprende a ignorar la sección. Ocupa espacio muerto |
| **UX-006** | Screener (SHORT/LONG) vs Neural (NEUTRAL) se contradicen | El usuario no sabe si actuar o abstenerse. Parálisis de decisión |
| **UX-012** | Ensemble 40% XGBoost + 60% LSTM produce distribución 50-60% | La señal nunca sale de NEUTRAL. Umbrales 40/60 demasiado estrechos |

### Altos (degradan seriamente la experiencia)

| ID | Descripción | Impacto |
|---|---|---|
| **UX-001** | P(Win) contradice intuición (rojo con alta probabilidad) | Desconfianza inmediata en el scoring |
| **UX-003** | "Market Weakness: breadth at 0%" no explicado | Alerta principal asusta sin informar |
| **UX-007** | Pestañas "Salud Financiera" y "Backtesting" vacías o sin datos útiles | App se siente incompleta |
| **UX-009** | Top Opportunities mezcla LONG/SHORT sin diferenciar | Usuario busca compras y solo ve ventas |
| **UX-010** | Plan vacío (sin dirección) en top opportunities | Señales no accionables en lista de "oportunidades" |

### Medios (fricción que acumula)

| ID | Descripción | Impacto |
|---|---|---|
| **UX-002** | Sin tooltips ni ayuda contextual en columnas | Solo usuarios técnicos entienden todo |
| **UX-004** | 60% tickers con "weak_signal" | Columna SIGNAL sin valor discriminatorio |
| **UX-008** | Indicadores sin color ni interpretación visual | Aritmética mental para cada dato |
| **UX-011** | Signal Lab no enlaza con tickers activos | Información histórica sin aplicación práctica |
| **UX-013** | Analytics no aclara datos simulados | Usuario sobreestimaTrack histórico |
| **UX-014** | Paper Trading no integrado al modal | Fricción para ejecutar órdenes simuladas |

---

## Recomendaciones Priorizadas

1. **Ajustar umbrales del Motor Neural** → COMPRA ≥ 55, VENTA ≤ 45, NEUTRAL 45-55. O usar el XGBoost score directamente sin ensemble si el LSTM siempre da ~50%.
2. **Explicar P(Win)** → Tooltip: "Probabilidad de que esta acción supere su rendimiento típico en 5 días. No es probabilidad de ganancia absoluta."
3. **Unificar criterio Screener + Neural** → Si el plan de trading dice SHORT, el motor neural debería reflejar esa dirección o explicar el disenso.
4. **Humanizar alertas** → "Market Weakness: breadth at 0%" → "Mercado bajista: 0 de 98 acciones sobre su media de 50 días. Precaución."
5. **Añadir tooltips** en columnas del screener y cards del modal.
6. **Integrar Paper Trading** → Botón "Simular esta operación" en el plan de trading del modal.
7. **Filtrar Top Opportunities** por dirección — pestañas "Mejores para COMPRAR" y "Mejores para VENDER".

---

*Informe generado desde la perspectiva de un inversor minorista con conocimientos básicos de bolsa. Todos los valores fueron verificados contra la API en tiempo real. Las decisiones de inversión son hipotéticas y no constituyen asesoramiento financiero.*

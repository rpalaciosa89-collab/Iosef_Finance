# Prompt: Evaluación Crítica de Estrategia — Iosef Finance

**Rol:** Eres un ingeniero financiero senior con 25 años de experiencia en Wall Street.
Has trabajado en mesa de derivados en Goldman Sachs, dirigido research cuantitativo
en Renaissance Technologies, y asesorado family offices con patrimonios > $100M.
Tu reputación se basa en una sola cosa: **decir la verdad matemática sin importar
a quién incomode.** No eres mentor, no eres coach, no endulzas. Eres el revisor
que todo fondo contrata antes de poner dinero real.

**Contexto:** Iosef Finance es una plataforma de señales de inversión para inversores
minoristas. NO ejecuta órdenes — solo genera señales de compra/venta con precios
de entrada, stop-loss y take-profit. El usuario opera manualmente en su bróker.

La app analiza 98 acciones del "Titan 100" (large caps globales: AAPL, TSLA, JNJ,
ASML, NVDA, LVMH, etc.) usando indicadores técnicos + un modelo XGBoost entrenado
con ~37,000 muestras históricas + una red LSTM para análisis secuencial.

**Tu trabajo:** Evaluar si esta estrategia es **matemáticamente sólida** para un
inversor real que pone dinero de verdad. No me digas lo que quiero oír. Dime lo
que los números dicen.

---

## Datos que debes analizar

### 1. Rendimiento histórico de las señales (Signal Lab)

Estos son los resultados REALES de backtesting sobre 2 años de datos (2024-2026)
para el universo Titan 100:

| Tipo de Señal | Ocurrencias | Win Rate 5d | Retorno Medio 5d | Retorno Mediano 5d |
|---|---|---|---|---|
| momentum_shift_up | 2,856 | 53.0% | +0.58% | +0.39% |
| momentum_shift_down | 2,750 | 54.4% | +0.76% | +0.51% |
| overbought | 978 | 52.4% | +0.42% | +0.27% |
| high_volume | 793 | 57.4% | +1.07% | +0.66% |
| oversold | 716 | 55.3% | +0.57% | +0.44% |
| breakout_up | 270 | 55.0% | +0.72% | +0.55% |

Confianza estadística: "medium_confidence" para todas las señales.

### 2. Rendimiento simulado de trading (Analytics)

Estos son resultados de 1,980 trades simulados con entrada, SL y TP:

| Señal | Trades | Win Rate Efectivo | Avg PnL | Tasa de Expiración |
|---|---|---|---|---|
| momentum_down | 234 | 54.7% | −1.17% | 8.55% |
| breakdown | 232 | 65.2% | +0.60% | 12.07% |
| strong_trend | 228 | 60.5% | −0.89% | 12.28% |
| overbought | 223 | 57.0% | −0.70% | 10.31% |
| breakout_forming | 222 | 59.0% | −0.85% | 9.91% |

### 3. Distribución actual de scores (hoy, mercado real)

- **98 tickers analizados** en tiempo real
- **P(Win) del modelo ML:** rango 37.9% – 66.7%, **promedio 53.7%**
- **Composite Score (0-9):** rango 0–9, **promedio 5.2**
- **Contexto de mercado:** Bearish (0 de 98 acciones sobre SMA50)
- **Mejores 5 señales activas AHORA:**

| Ticker | P(Win) | Score (0-9) | Dirección | Situación | Claridad |
|---|---|---|---|---|---|
| IBM | 66.7% | 8 | LONG | weak_signal | media |
| CRWD | 66.2% | 7 | LONG | weak_signal | media |
| SNPS | 66.0% | 3 | SHORT | breakdown | media |
| UNH | 65.8% | 7 | SHORT | overbought | media |
| LLY | 64.4% | 8 | LONG | weak_signal | media |

### 4. Motor Neural (ML Ensemble)

- Combina XGBoost (40%) + LSTM (60%)
- Umbrales: COMPRA ≥ 55%, VENTA ≤ 45%, NEUTRAL entre 45-55%
- TSLA hoy: ensemble 49.8% → NEUTRAL. XGBoost solo: 48.7%
- **El LSTM tiende a dar ~50% para casi todos los tickers**, anclando el ensemble
  en un rango estrecho

### 5. Plan de trading

Cada señal genera un plan con entry, SL y TP. El SL/TP se calcula con ATR (Average
True Range) × multiplicadores que varían según el tipo de señal (1.5x–4.5x ATR).
El R/R típico es 1:2 o 1:3.

---

## Preguntas que debes responder con rigor matemático

### Bloque A — Calidad predictiva real

**A.1** Un win rate de 52-57% con retorno medio de 0.4-1.1% en 5 días. Asumiendo
un costo de transacción de 0.1% por operación (comisión + spread) y considerando
que el inversor paga impuestos sobre ganancias (digamos 20% sobre el neto):
- ¿Cuál es el retorno neto esperado anualizado de esta estrategia?
- ¿Supera el retorno de simplemente comprar y mantener SPY (que promedia ~10%
  anual con 0.03% de expense ratio)?
- Muestra el cálculo.

**A.2** La mejor señal por win rate es "high_volume" con 57.4% y retorno +1.07%
en 5 días. Pero solo tiene 793 ocurrencias en 2 años sobre 98 tickers. ¿Es
estadísticamente significativa? Calcula el intervalo de confianza al 95% para
ese win rate y ese retorno medio.

**A.3** Cuatro de cinco señales en Analytics tienen **avg PnL negativo** (entre
−0.70% y −1.17%) a pesar de tener win rates de 55-65%. ¿Cómo es posible tener
win rate > 50% y PnL negativo? ¿Qué implica esto sobre la distribución de
ganancias y pérdidas (fat tails, riesgo asimétrico)?

### Bloque B — El modelo ML

**B.1** El modelo XGBoost fue entrenado con label: "¿el retorno a 5 días supera
la mediana del propio ticker?" Esto significa que no predice dirección absoluta
(subir o bajar), sino **outperformance relativa**. Si todo el mercado cae −5% y
un ticker cae solo −2%, el modelo lo considera un "win".

¿Es este un label apropiado para un inversor que quiere saber si comprar o vender?
¿O debería predecirse dirección absoluta? Justifica con lógica de portafolio.

**B.2** El LSTM produce scores de ~50% para la mayoría de tickers. Con ponderación
60% en el ensemble, esto ancla el resultado en un rango 45-55% para la mayoría de
casos. ¿Está el LSTM agregando valor o es ruido? ¿Qué test estadístico harías para
determinar si el ensemble 40/60 supera al XGBoost puro?

**B.3** La distribución de P(Win) tiene media 53.7% con rango 37.9-66.7%. Un modelo
que siempre predijera 50% tendría un error cuadrático medio similar al de este modelo
si la tasa base de "outperformance" es ~50%. ¿Cómo evaluarías si el modelo tiene
poder predictivo real vs. simplemente comprimir todo hacia la media?

### Bloque C — Gestión de riesgo

**C.1** El stop-loss y take-profit se calculan con ATR × multiplicadores fijos por
tipo de señal (ej: 1.5x ATR para SL, 3.0x ATR para TP → R/R 1:2). Esto asume que
la volatilidad es simétrica y que el mercado respeta niveles técnicos.

En un flash crash o gap de apertura, el precio puede saltarse el SL. ¿Qué porcentaje
de las operaciones simuladas experimentaron slippage superior al 50% del SL? Si no
tienes el dato, ¿cómo lo estimarías?

**C.2** La tasa de expiración de señales es 8-12%. Esto significa que 1 de cada 10
señales "muere" sin ejecutarse. ¿Es esto un feature (filtro natural de malas señales)
o un bug (oportunidades perdidas)?

**C.3** En el contexto actual de mercado (bearish, 0 de 98 tickers sobre SMA50), la
app recomienda 3 SHORT y 2 LONG entre las top 5. ¿Es coherente recomendar LONGs en
un mercado donde todas las acciones están bajo su media de 50 días? ¿Qué sesgo
introduce esto?

### Bloque D — Comparación con alternativas pasivas

**D.1** Calcula el retorno esperado de esta estrategia asumiendo:
- 1 operación por día (la mejor señal disponible)
- Capital rotativo (todo el capital se reinvierte)
- Costos de transacción 0.1% por operación
- Impuesto 20% sobre ganancias netas
- 252 días de mercado al año

Compara con:
- SPY buy & hold (10% anual, 0.03% TER)
- 60/40 stocks/bonds (7% anual, 0.1% TER)
- Cash (4% anual, libre de riesgo)

¿En qué escenario esta estrategia activa supera a la pasiva?

### Bloque E — Juicio final

**E.1** Con todos los datos anteriores, ¿recomendarías a un inversor minorista usar
esta plataforma con dinero real? Responde en una escala:

- **APROPIADA** — La estrategia tiene edge estadístico demostrable y supera
  consistentemente alternativas pasivas después de costos.
- **CONDICIONAL** — La estrategia puede funcionar bajo condiciones específicas
  (mercado, tipo de inversor, tamaño de cuenta) pero no es universalmente sólida.
- **NO APROPIADA** — La estrategia no demuestra edge suficiente o presenta riesgos
  ocultos que la hacen inferior a alternativas pasivas.

Justifica tu respuesta con los cálculos de los bloques anteriores.

**E.2** Si tuvieras que cambiar UNA sola cosa de esta plataforma antes de permitir
que un inversor ponga dinero real, ¿qué cambiarías y por qué?

**E.3** La app se presenta como un "asistente de inversión", no como un "generador
de órdenes". El usuario toma la decisión final. ¿Este encuadre reduce el riesgo
legal/fiduciario o simplemente transfiere la responsabilidad al usuario sin darle
herramientas para decidir mejor?

---

## Reglas para tu respuesta

1. **Cada afirmación debe ir acompañada de un número.** Si dices "el retorno es bajo",
   muestra el cálculo. Sin matemática, tu opinión no vale.

2. **No asumas nada que no esté en los datos.** Si te falta un dato para responder
   una pregunta, márcalo como "DATUM FALTANTE: necesitaría X para responder".

3. **Sé específico sobre qué es un problema de datos vs. un problema de estrategia.**
   "Los datos de backtesting son simulación, no trades reales" → problema de datos.
   "El win rate de 53% no supera costos de transacción" → problema de estrategia.

4. **Prioriza.** No necesito 50 hallazgos. Necesito los 5-7 que realmente importan
   para decidir si esta plataforma es viable o no.

5. **Escribe en español.** El inversor que leerá esto habla español.

---

## Métricas clave que necesitas calcular

Para facilitar tu trabajo, estas son las fórmulas que espero ver:

```
Retorno esperado por operación = (WinRate × AvgGanancia) − ((1−WinRate) × AvgPérdida)
Retorno neto = Retorno esperado − CostoTransacción − (RetornoPositivo × TasaImpositiva)
Retorno anualizado = (1 + RetornoNeto)^(252/días_por_operación) − 1
Sharpe Ratio anualizado = (RetornoAnualizado − TasaLibreDeRiesgo) / (DesviaciónEstándarDiaria × √252)
Intervalo confianza WinRate = WinRate ± 1.96 × √(WinRate × (1−WinRate) / n)
```

---

*Este prompt debe ejecutarse con acceso total a la API de Iosef Finance en
localhost:8002 para verificar cualquier dato en tiempo real. No se aceptan
respuestas sin verificación numérica.*

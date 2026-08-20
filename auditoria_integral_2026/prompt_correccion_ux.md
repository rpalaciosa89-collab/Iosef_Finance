# Prompt: Plan de Corrección UX — Iosef Finance (6.2 → 10/10)

**Rol:** Eres un ingeniero de producto senior especializado en UX para plataformas
financieras. Tu misión es eliminar TODA la fricción entre el usuario y su decisión
de inversión. No construyes features nuevas — **pules lo que ya existe** hasta
que un inversor normal pueda tomar decisiones en < 3 minutos sin dudar.

**Objetivo:** Resolver los 14 hallazgos del informe de experiencia de usuario,
elevando la app de 6.2/10 a 10/10.

**Regla de oro:** El usuario NUNCA debe ver dos secciones de la app diciendo
cosas contradictorias sobre la misma acción. Si hay conflicto, la app debe
explicarlo o resolverlo. Si no puede resolverlo, debe ocultar la sección
conflictiva hasta que tenga certeza.

---

## Bloque A — Críticos: Eliminar contradicciones internas

### A.1 — Ajustar umbrales del Motor Neural (UX-005 + UX-012)

**Problema:** El ensemble siempre cae en 50-58% porque el LSTM tiende a dar ~50%.
Con umbrales COMPRA ≥ 60 y VENTA ≤ 40, el resultado es NEUTRAL para virtualmente
todos los tickers. El usuario aprende a ignorar esta sección.

**Archivo:** [server.py:L1173-L1176](file:///Users/raymondpalacios/Documents/Bootcamp Data Science/Iosef_Finance/backend/server.py#L1173-L1176)

**Fix:**
- Cambiar umbrales en `/api/neural-score/{ticker}`:
  - COMPRA: `composite >= 55.0`
  - VENTA: `composite <= 45.0`
  - NEUTRAL: `45.0 < composite < 55.0`
- Si incluso con estos umbrales más del 70% de los tickers caen en NEUTRAL, evaluar
  eliminar el LSTM del ensemble para inferencia y usar solo XGBoost puro.
- Alternativa: Ponderar 70% XGBoost + 30% LSTM en vez de 40/60 para dar más peso
  al modelo que realmente discrimina.

**Verificación:** Llamar `/api/neural-score` para 10 tickers aleatorios.
Al menos 3 deben dar COMPRA o VENTA. Si 8+ siguen en NEUTRAL, el fix no fue
suficiente.

---

### A.2 — Unificar criterio Screener + Motor Neural (UX-006)

**Problema:** El screener da un plan de trading explícito (SHORT TSLA, SL=$413, TP=$326,
R/R 1:2) pero el Motor Neural en el modal dice NEUTRAL. La contradicción destruye
la confianza.

**Archivos:**
- `frontend-v2/src/components/TickerModal.tsx` (donde se muestra el Neural Score)
- `backend/server.py` endpoint `/api/neural-score/{ticker}`

**Fix:** Agregar un campo `alignment` al endpoint neural-score:

```python
# En el endpoint neural-score, después de calcular composite:
plan_dir = _get_plan_direction_for_ticker(ticker)  # LONG, SHORT, o None

if composite >= 55.0 and plan_dir == "LONG":
    alignment = "CONFIRMADO"
elif composite <= 45.0 and plan_dir == "SHORT":
    alignment = "CONFIRMADO"
elif 45.0 < composite < 55.0:
    alignment = "NEUTRAL"
else:
    alignment = "DIVERGENTE"
```

En el frontend, mostrar visualmente:
- `CONFIRMADO` → badge verde: "✅ Consistente con el plan de trading"
- `NEUTRAL` → badge gris: "Sin dirección clara"
- `DIVERGENTE` → badge naranja: "⚠️ El modelo difiere del análisis técnico"

Y añadir una línea de explicación:
- DIVERGENTE: "El análisis técnico sugiere {LONG/SHORT}, pero el modelo ML no encuentra suficiente evidencia estadística. Considere reducir el tamaño de posición."
- NEUTRAL: "Ni el análisis técnico ni el modelo ML encuentran una dirección clara. Considere esperar."

**Verificación:** Abrir el modal de TSLA. El motor neural debe mostrar consistencia
con el plan SHORT del screener, o al menos explicar por qué difiere. Ya no debe
haber un "NEUTRAL" huérfano sin contexto.

---

### A.3 — Si el LSTM no discrimina, degradarlo o eliminarlo de la UI (UX-012 parte 2)

**Problema:** Si tras los fixes anteriores el LSTM sigue sin aportar discriminación
(>70% de tickers en NEUTRAL), mantenerlo visible degrada la experiencia.

**Fix condicional:**
- Monitorear durante 24h el % de tickers en cada categoría.
- Si NEUTRAL > 70%: quitar el LSTM del ensemble de inferencia (dejarlo solo para
  backtesting). Usar `p_win_xgb` como score principal.
- Simplificar la UI: mostrar solo "P(Win) XGBoost" sin las 3 barras de ensemble.
- El LSTM se conserva en backend para futura recalibración.

---

## Bloque B — Altos: Claridad y completitud

### B.1 — Explicar P(Win) con tooltip inequívoco (UX-001)

**Problema:** El usuario ve "P(Win) 66%" en una acción que cayó -14% este mes.
Su intuición dice "esto no puede ser". La app no explica qué mide realmente P(Win).

**Archivo:** `frontend-v2/src/components/TickerModal.tsx` (card de Prob. P(Win))

**Fix:** Añadir un tooltip o texto pequeño debajo del valor:

```
P(Win)
66.2%

Probabilidad de que esta acción supere
su rendimiento típico en los próximos 5 días.
No es probabilidad de que el precio suba.
```

O alternativamente, renombrar la etiqueta en la UI:
- Dashboard: `P(Win)` → `ML Score`
- Tooltip: "Score del modelo XGBoost. Mide probabilidad de rendimiento superior al promedio del activo en 5 días."

**Verificación:** Pasar el mouse sobre P(Win) en el dashboard y en el modal.
Debe aparecer un tooltip explicativo. Un usuario nuevo debe entender que 66%
no significa "66% de probabilidad de ganar dinero".

---

### B.2 — Humanizar las alertas del dashboard (UX-003)

**Problema:** "Market Weakness: breadth at 0%" usa jerga cuantitativa. La
alerta más visible de la app asusta sin informar.

**Archivo:** [server.py:L600-L606](file:///Users/raymondpalacios/Documents/Bootcamp Data Science/Iosef_Finance/backend/server.py#L600-L606)

**Fix:** Reescribir los mensajes de alerta en language natural:

Antes:
```python
alerts.append({"ticker": "MARKET", "type": "market_weakness",
    "message": f"Market Weakness: breadth at {market_breadth:.0%}",
    "strength": "high", "color": "yellow"})
```

Después:
```python
alerts.append({"ticker": "MARKET", "type": "market_weakness",
    "message": f"Mercado bajista: 0 de {total_valid} acciones sobre su media de 50 días. Precaución.",
    "strength": "high", "color": "yellow"})
```

Aplicar mismo patrón a todas las alertas:
- `"Breakdown below SMA50 at 201.68"` → `"NVDA rompió a la baja su media de 50 días en $201.68. Tendencia bajista."`
- `"Strong move down (-3.1%)"` → `"NVDA cae -3.1% hoy. Movimiento brusco."`
- `"RSI Oversold (28.5)"` → `"TM está en zona de sobreventa (RSI 28.5). Posible rebote técnico."`

**Verificación:** Refrescar el dashboard. Todas las alertas deben ser comprensibles
para una persona sin conocimientos técnicos. Cero jerga sin explicación.

---

### B.3 — Rellenar o eliminar pestañas vacías en el modal (UX-007)

**Problema:** El modal tiene pestañas "Salud Financiera" y "Backtesting Cuantitativo"
que están vacías o sin datos útiles. El usuario siente que la app está incompleta.

**Fix — Salud Financiera:**
- Verificar el endpoint `/api/ticker/{ticker}/financials`. Si devuelve datos,
  renderizarlos en una tabla simple: Revenue, Net Income, EPS, P/E, Debt/Equity,
  Margen bruto.
- Si el endpoint no devuelve datos para ese ticker, mostrar:
  "Datos fundamentales no disponibles para {ticker}. Solo tickers US."
  **No mostrar una pestaña vacía.**

**Fix — Backtesting Cuantitativo:**
- Verificar si existe lógica de backtesting para tickers individuales.
- Si existe: mostrar un resumen de rendimiento histórico simulado.
- Si no existe: **ocultar la pestaña** hasta que se implemente. Una pestaña
  vacía es peor que ninguna pestaña.

**Verificación:** Abrir el modal de AAPL. La pestaña "Salud Financiera" debe
mostrar datos o un mensaje claro de no disponibilidad. "Backtesting Cuantitativo"
solo debe aparecer si tiene contenido.

---

### B.4 — Corregir dirección vacía en plan de trading (UX-010)

**Problema:** SNPS y REGN están en Top 5 de oportunidades pero tienen `direction=""`
y plan de trading vacío. No son accionables.

**Archivo:** [server.py:L799-L814](file:///Users/raymondpalacios/Documents/Bootcamp Data Science/Iosef_Finance/backend/server.py#L799-L814) — filtro de new_candidates
y [server.py:L1100-L1108](file:///Users/raymondpalacios/Documents/Bootcamp Data Science/Iosef_Finance/backend/server.py#L1100-L1108) — endpoint /api/top

**Fix en `/api/top`:**
Agregar filtro adicional:
```python
actionable = [
    t for t in data
    if t.get("decision_clarity") != "baja"
    and t.get("trade_plan", {}).get("direction") in ("LONG", "SHORT")
    and t.get("trade_plan", {}).get("entry_price", 0) > 0
]
```

Esto asegura que solo tickers con plan de trading completo y dirección definida
aparezcan como oportunidades.

**Verificación:** `/api/top` debe devolver solo tickers con `direction` LONG o SHORT
y `entry_price > 0`. Ningún ticker con plan vacío.

---

### B.5 — Separar Top Opportunities LONG vs SHORT (UX-009)

**Problema:** El usuario busca "las mejores para comprar" y ve SHORTs.

**Fix en el frontend (`frontend-v2/src/tabs/TopOpportunities.tsx` o similar):**

Dividir la sección en dos columnas o dos tabs:
- **"Mejores para COMPRAR (LONG)"** — filtradas por `direction == "LONG"`
- **"Mejores para VENDER (SHORT)"** — filtradas por `direction == "SHORT"`

Cada una con su propio top 10. Encabezado contextual que cambia según el mercado:
- Bearish: "En mercado bajista, las oportunidades de VENTA dominan. Las de COMPRA son selectivas."
- Bullish: lo opuesto.

**Verificación:** En el mercado bearish actual, la columna SHORT debe ser más grande.
La columna LONG debe mostrar las pocas oportunidades de compra (como LLY).

---

## Bloque C — Medios: Reducir fricción

### C.1 — Añadir tooltips en columnas del screener y cards del modal (UX-002 + UX-008)

**Problema:** El usuario no sabe qué es REL VOL, SCORE, P(WIN) sin ir a Google.
Los indicadores no tienen color ni interpretación.

**Fix — Columnas del Dashboard (`frontend-v2/src/tabs/Dashboard.tsx` o tabla del screener):**

Agregar tooltip en cada encabezado de columna:
| Columna | Tooltip |
|---|---|
| RSI | "Índice de Fuerza Relativa (0-100). >70 = sobrecomprado, <30 = sobrevendido" |
| REL VOL | "Volumen hoy vs. promedio 20 días. >1.5x = volumen inusualmente alto" |
| MOM 1M | "Cambio de precio en el último mes (20 días)" |
| SCORE | "Puntuación técnica (0-9) basada en SMA, RSI, momentum y volumen" |
| P(WIN) | "Score del modelo ML. Mide probabilidad de rendimiento superior al promedio en 5 días" |

**Fix — Cards del Modal:**
Añadir color contextual a cada card de indicador:
- RSI > 70: fondo rojo claro + "Sobrecomprado"
- RSI < 30: fondo verde claro + "Sobrevendido"
- RSI 30-70: fondo neutro
- Momentum > 0: texto verde
- Momentum < 0: texto rojo
- Price > SMA20: badge "▲ Sobre media 20d" en verde
- Price < SMA20: badge "▼ Bajo media 20d" en rojo

**Verificación:** Cada columna del screener debe mostrar tooltip al pasar el mouse.
Cada card del modal debe tener color contextual que indique si el valor es
positivo, negativo o neutral.

---

### C.2 — Reducir ruido de "weak_signal" (UX-004)

**Problema:** 59 de 98 tickers muestran `situation: "weak_signal"`. La columna
SIGNAL del screener pierde valor discriminatorio.

**Archivo:** `app/services/human_layer.py:_detect_situation()`

**Fix:** Crear una categoría intermedia "neutral" que agrupe los casos sin señal clara
pero sin ser "no_signal". Cambiar el último `return "weak_signal"` por:

```python
if price > sma50:
    return "neutral_positive"
elif price > sma200:
    return "neutral_holding"
else:
    return "weak_signal"
```

En el frontend, para `neutral_positive` y `neutral_holding` mostrar un badge gris
sin ícono de alerta. Solo `weak_signal`, `breakdown`, `momentum_down` y `no_signal`
deberían activar atención visual.

**Verificación:** Refrescar el scan. La distribución de situaciones debe tener
menos de 30 tickers con "weak_signal". Las situaciones neutrales deben ser
visualmente menos intrusivas.

---

### C.3 — Conectar Signal Lab con el Screener (UX-011)

**Problema:** Signal Lab muestra que "momentum_shift_down tiene 54.4% win rate",
pero no dice qué tickers tienen esa señal AHORA.

**Fix en frontend (SignalLab.tsx):**
En cada fila de la tabla de señales, añadir un enlace o botón:
"[Ver tickers activos →]" que filtre el screener por ese tipo de señal.

Esto requiere:
- Que el endpoint `/api/scan` acepte un query param `?signal_type=momentum_shift_down`
  para filtrar server-side, O
- Que el frontend filtre client-side (ya tiene todos los datos del scan).

**Fix en backend (opcional):** Agregar query param `signal_type` a `/api/scan`:
```python
@app.get("/api/scan")
def get_scan(market: str = DEFAULT_MARKET, signal_type: str = None):
    ...
    if signal_type:
        data = [t for t in data if signal_type in t.get("active_signals", [])]
```

**Verificación:** En Signal Lab, hacer clic en "momentum_shift_down → Ver tickers activos".
Debe mostrar solo los tickers del screener que tienen esa señal activa.

---

### C.4 — Transparentar que Analytics usa datos simulados (UX-013)

**Problema:** El usuario lee "230 operaciones registradas" y asume que son reales.

**Archivo:** `frontend-v2/src/tabs/Analytics.tsx`

**Fix:** Añadir un banner informativo en la parte superior de la sección Analytics:

```
ℹ️ Los datos de rendimiento histórico provienen de simulación (backtesting).
No reflejan operaciones reales. Úselos como referencia, no como garantía.
```

O alternativamente, agregar un campo `data_source` en el endpoint `/api/analytics`
que indique `"simulated_backfill"` y mostrarlo en la UI.

**Verificación:** La sección Analytics debe mostrar visiblemente que los datos
son simulados.

---

### C.5 — Integrar Paper Trading al modal (UX-014)

**Problema:** Cuando el usuario ve el plan SHORT para TSLA en el modal, no hay
un botón para ejecutarlo en simulación. Tiene que navegar a otra pestaña.

**Archivo:** `frontend-v2/src/components/TickerModal.tsx`

**Fix:** Añadir un botón en la sección del Plan de Trading:

```
┌──────────────────────────────────────┐
│ 📋 PLAN DE TRADING — SHORT          │
│                                      │
│ ENTRY      $384.30                   │
│ STOP LOSS  $413.28 (+7.5%)          │
│ TAKE PROFIT $326.35 (-15%)          │
│ R/R RATIO  1:2                      │
│                                      │
│ [📝 Simular esta operación] ← NUEVO │
└──────────────────────────────────────┘
```

Al hacer clic:
1. Si el usuario no tiene cuenta paper trading → mostrar modal de creación rápida
2. Si ya tiene cuenta → ejecutar la orden paper inmediatamente con entry, SL, TP del plan
3. Confirmación visual: "✅ Orden simulada ejecutada para TSLA"

**Fix en backend:** Asegurar que el endpoint `POST /api/paper-trading/execute`
acepte los campos del plan de trading directamente:
```json
{
  "ticker": "TSLA",
  "direction": "SHORT",
  "quantity": 10,
  "entry_price": 384.30,
  "stop_loss": 413.28,
  "take_profit": 326.35
}
```

**Verificación:** Abrir modal de TSLA, hacer clic en "Simular esta operación".
La orden debe ejecutarse y reflejarse en Paper Trading sin salir del modal.

---

## Bloque D — Verificación Final

### D.1 — Re-ejecutar el prompt de experiencia de usuario

Después de aplicar todas las correcciones, volver a ejecutar el prompt original
de evaluación UX y verificar que:

- [ ] **Coherencia ≥ 9/10** — Ninguna sección contradice a otra. Si hay diferencia,
  se explica con badge de alineación.
- [ ] **Claridad ≥ 8/10** — Todos los términos técnicos tienen tooltip.
- [ ] **Confianza ≥ 8/10** — El usuario entiende qué mide cada número.
- [ ] **Accionabilidad ≥ 9/10** — El plan de trading es visible y accionable
  (incluye botón de simulación).
- [ ] **Completitud ≥ 8/10** — Sin pestañas vacías. Datos fundamentales visibles.
- [ ] **Nota global ≥ 8.5/10**

### D.2 — Prueba de las 2 decisiones

Abrir la app como inversor nuevo y responder:

1. ¿Puedo encontrar UNA acción para comprar en < 2 minutos?
2. ¿Puedo encontrar UNA acción para vender en < 2 minutos?
3. ¿Sé exactamente a qué precio, dónde poner el stop, y cuánto puedo ganar?
4. ¿El Motor Neural y el Screener dicen lo mismo (o se explica por qué no)?
5. ¿Puedo ejecutar la operación en simulación sin salir del modal?

### D.3 — Verificaciones técnicas

- [ ] `npm run build` exitoso en frontend
- [ ] `npx vitest run` — 4/4 tests frontend
- [ ] `python -m pytest tests/ -q` — 52/52 tests backend
- [ ] `npx tsc -b` — 0 nuevos errores TypeScript
- [ ] `/api/neural-score` para 10 tickers — al menos 3 devuelven COMPRA o VENTA
- [ ] `/api/top` — 0 tickers con plan vacío o direction=""
- [ ] `/api/scan` — alertas en lenguaje natural, no jerga cuantitativa

---

## Resumen de Archivos a Modificar

| Archivo | Bloques | Qué cambia |
|---|---|---|
| `backend/server.py` | A1, A2, B2, B4, C3 | Umbrales neural, alineación, alertas humanizadas, filtro top, filtro signal_type |
| `backend/app/services/human_layer.py` | C2 | Nuevas situaciones neutral_positive/neutral_holding |
| `frontend-v2/src/components/TickerModal.tsx` | A2, B1, C1, C5 | Badge alineación, tooltip P(Win), color cards, botón simular |
| `frontend-v2/src/tabs/Analytics.tsx` | C4 | Banner datos simulados |
| `frontend-v2/src/tabs/SignalLab.tsx` | C3 | Enlace a tickers activos |
| `frontend-v2/src/tabs/Dashboard.tsx` | C1 | Tooltips en columnas |
| `frontend-v2/src/tabs/TopOpportunities.tsx` | B5 | Separar LONG/SHORT |
| `frontend-v2/src/tabs/FinancialsTab.tsx` | B3 | Mostrar datos o mensaje, no pestaña vacía |

---

## Orden de Ejecución

1. **Backend first:** A1 (umbrales) + A2 (alineación) + B2 (alertas) + B4 (filtro top)
2. **Frontend core:** A2 (badge alineación) + B1 (tooltip PWin) + C2 (situaciones)
3. **Frontend completeness:** B3 (tabs vacías) + B5 (LONG/SHORT) + C4 (banner simulación)
4. **Frontend friction:** C1 (tooltips columnas + color cards) + C3 (link Signal Lab) + C5 (botón simular)
5. **Verificación:** D1 (re-ejecutar prompt UX) + D2 (2 decisiones) + D3 (tests)

**Al finalizar, documentar todos los cambios en un CHANGELOG de UX con formato:**
- ID del hallazgo resuelto
- Qué se cambió (archivo, línea, antes/después)
- Verificación (captura o evidencia)
- Impacto en el score

---

*Este prompt está diseñado para ejecución secuencial con verificación en cada paso.
Cada bloque es independiente y puede verificarse sin esperar a los demás.*

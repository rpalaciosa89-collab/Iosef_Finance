# Prompt: Gráficos con Capa de Señales — Iosef Finance

**Rol:** Eres un diseñador de producto especializado en plataformas de análisis
de inversión. Iosef Finance **no es una app de trading** — es un **asistente de
señales de inversión**. El usuario no ejecuta órdenes aquí; usa la app para
decidir cuándo y dónde invertir manualmente en su bróker. El gráfico debe ser
el lugar donde el usuario **entiende la señal, su evolución y su resultado** sin
leer cards ni saltar entre secciones.

**Contexto técnico:**
- El sistema genera señales mediante un motor de ciclo de vida (`signal_status`:
  `new` → `active` → `weakening` → `expired`).
- Cada señal tiene: timestamp de detección, tipo (`breakout_up`, `momentum_down`,
  etc.), score ML, precio de entrada, SL, TP, dirección (LONG/SHORT).
- Un mismo ticker puede acumular **múltiples señales en el tiempo**.
- El backend ya expone `/api/ticker/{ticker}/intraday?period=...` y
  `/api/neural-score/{ticker}`. Los datos de señales están en el cache del scan.

**Objetivo del gráfico:** Que el usuario vea **de un vistazo**:
1. ¿Hubo señales en este ticker? ¿Cuándo?
2. ¿Esa señal está viva, ganando, perdiendo o ya expiró?
3. ¿Hay una señal activa AHORA y qué me recomienda?

---

## Principio rector: El gráfico es un mapa de señales, no un panel de trading

A diferencia de una app de trading (donde el foco es ejecutar órdenes), aquí el
foco es **entender la calidad y evolución de las señales**. El precio es el
contexto; las señales son el contenido.

---

## Capa 1 — Toggle "Mostrar señales" (obligatorio, evita saturación)

**Problema:** Si un ticker tiene 15 señales en 6 meses, pintarlas todas satura
el gráfico y lo vuelve ilegible.

**Solución:** Un toggle en la parte superior derecha del gráfico:

```
[ 📍 Ver señales  ✓ ]   ← toggle on/off
```

- **OFF (default para timeframes largos):** Gráfico limpio, solo velas.
- **ON:** Se activan las capas de señal descritas abajo.

**Regla inteligente de visibilidad:**
- Si `total_señales_en_rango > 8` → mostrar solo las de los últimos 30 días +
  un resumen agregado de las antiguas (ver Capa 4).
- Si `total_señales_en_rango ≤ 8` → mostrar todas.

---

## Capa 2 — Marcadores de Señal (Signal Pins)

Cada señal detectada se representa con un **pin vertical** en la vela
correspondiente al timestamp `signal_detected_at`.

### Anatomía del pin

```
         ┌──────────┐
         │ 68% 🔻   │  ← dirección + score ML al detectarse
         └────┬─────┘
              │
──────────────┼──────────────  ← precio de entrada (línea horizontal corta)
              │
           ██████             ← vela del día de detección
```

### Colores por estado de ciclo de vida

| `signal_status` | Color del pin | Opacidad | Tamaño | Significado |
|---|---|---|---|---|
| `new` | 🟢 Verde brillante | 100% | Grande | "Acaba de aparecer — mírame" |
| `active` | 🟢 Verde | 80% | Normal | "Sigue vigente" |
| `weakening` | 🟡 Ámbar | 60% | Normal | "Perdiendo fuerza" |
| `expired` / `closed_win` | ⚪ Gris con ✅ | 30% | Pequeño | "Ya pasó, cerró con ganancia" |
| `expired` / `closed_loss` | ⚪ Gris con ❌ | 30% | Pequeño | "Ya pasó, cerró con pérdida" |
| `expired` (sin ejecución) | ⚪ Gris | 20% | Muy pequeño | "Expirada sin acción" |

### Tooltip al hover

```
━━━━━━━━━━━━━━━━━━━━━━━━
Señal: momentum_down
Detectada: 10 jun 2026 11:40
Dirección: SHORT
Score ML: 66.2%
Entrada: $384.30  |  SL: $413.28  |  TP: $326.35
Estado: ACTIVE · entry window: open
━━━━━━━━━━━━━━━━━━━━━━━━
```

### Regla anti-saturación para múltiples señales

Cuando hay varias señales cercanas en el tiempo (mismo día o días consecutivos),
se aplica **agrupación por proximidad**:

- Señales detectadas con ≤ 2 velas de diferencia → se agrupan en un solo pin
  "expandible".
- El pin agrupado muestra un badge con el conteo: `[3 señales]`.
- Al hacer clic en el pin agrupado, se despliega una mini-lista vertical con las
  señales individuales.

```
         ┌──────────┐
         │ [3 señales]│  ← agrupado
         └────┬─────┘
              │
    ┌─────────┼─────────┐
    │ 66% 🔻  │ 58% 🔻  │  ← expandido al hacer clic
    │ 55% 🔺  │         │
    └─────────┴─────────┘
```

---

## Capa 3 — Tracker de P&L para la señal activa

**Problema:** El usuario quiere saber si la señal que eligió seguir "va ganando
o perdiendo". Pero como no somos una app de trading, no tenemos P&L real — tenemos
**P&L teórico basado en el movimiento del precio desde la detección**.

**Solución para la señal activa más reciente (si `signal_status ∈ {new, active}`):**

Una **banda de rendimiento** desde el precio de entrada hasta el precio actual:

```
  ┌──────────────────────────────────────────────┐
  │  Señal activa: SHORT · Detectada hace 3h      │
  │                                               │
  │  ████████████████████░░░░░░  +0.82% (+$3.12) │  ← barra de progreso
  │                                               │
  │  Precio entrada: $384.30                      │
  │  Precio actual:  $381.18  🔻                  │
  │  Distancia a TP: 14.1% ($326.35)             │
  │  Distancia a SL: 8.3%  ($413.28)             │
  └──────────────────────────────────────────────┘
```

Esta banda:
- Es verde si el precio se mueve a favor de la dirección de la señal
- Es roja si el precio se mueve en contra
- Muestra % de avance hacia el TP (no hacia SL)
- Se actualiza con el precio en tiempo real
- Solo aparece si hay UNA señal activa. Si hay varias, mostrar un selector:
  `[Señal 1 ▼]` para elegir cuál trackear.

---

## Capa 4 — Resumen de señales históricas (para timeframes largos)

Cuando el timeframe es ≥ 3MO y hay muchas señales, en lugar de pintar pins
individuales que saturarían el gráfico, se muestra un **heatmap mensual**
en la parte inferior:

```
        Dic     Ene     Feb     Mar     Abr     May     Jun
SEÑALES  ▉▉     ▉       ▉▉▉     ▉▉      ▉      ▉▉▉     ▉▉
GANADAS  ▉      ▉       ▉▉      ▉       ▉      ▉▉      ▉▉
PERDIDAS ▉              ▉       ▉                        ▉
```

- Cada barra = cantidad de señales en ese mes
- Color = proporción de ganadas (verde) vs pérdidas (rojo)
- Tooltip al hover: "Marzo: 5 señales, 3 ganadas (60%), +1.2% avg return"
- Este heatmap reemplaza los pins individuales en timeframes ≥ 3MO
- En timeframes ≤ 1MO, se muestran los pins individuales

---

## Capa 5 — Panel lateral de señales (Signal Sidebar)

En vez de saturar el gráfico con datos, las líneas SL/TP y el detalle completo
se muestran en un **panel lateral colapsable** a la derecha del gráfico:

```
┌────────────────────┬──────────────┐
│                    │ 📋 Señales   │
│                    │              │
│    GRÁFICO         │ 🔻 SHORT     │
│    DE VELAS        │ 66.2% ML     │
│                    │ Active       │
│                    │              │
│                    │ Entry $384   │
│                    │ SL    $413   │
│                    │ TP    $326   │
│                    │ R/R   1:2    │
│                    │              │
│                    │ [Historial]  │
└────────────────────┴──────────────┘
```

- El panel se abre al hacer clic en un pin de señal
- Muestra el detalle completo de ESA señal
- Si hay múltiples señales, lista desplazable con la más reciente arriba
- Incluye las líneas SL/TP como mini-indicadores visuales
- Botón "Copiar datos al portapapeles" para pegarlos en el bróker

---

## Capa 6 — Indicador de tendencia (Background Band)

La única capa SIEMPRE visible (sin toggle):

Una banda de color semi-transparente detrás de las velas:

| Timeframe | Color si tendencia es alcista | Color si es bajista |
|---|---|---|
| 1D | Verde tenue (change > 0) | Rojo tenue |
| 5D-1MO | Verde (price > SMA20) | Rojo |
| 3MO-1Y | Verde (price > SMA50) | Rojo |

Implementación: `<rect>` SVG con `opacity: 0.04`.

---

## Plan de Implementación

### Backend (1 endpoint extendido)

**`GET /api/ticker/{ticker}/intraday?period=...`**

Agregar campo `signal_overlays` a la respuesta:

```json
{
  "candles": [...],
  "signal_overlays": [
    {
      "id": "sig_171",
      "detected_at": 1781123456,
      "direction": "SHORT",
      "signal_type": "momentum_down",
      "score_at_detection": 66.2,
      "entry_price": 384.30,
      "stop_loss": 413.28,
      "take_profit": 326.35,
      "status": "active",
      "entry_window": "open",
      "pnl_since_detection_pct": 0.82,
      "pnl_since_detection_usd": 3.12,
      "is_currently_winning": true
    }
  ]
}
```

Los datos se obtienen del Redis cache del scan (`scan:data:titan100`) + lifecycle
engine. Si el cache no tiene datos para ese ticker, `signal_overlays: []`.

**Endpoint para historial (opcional, fase 2):**
`GET /api/ticker/{ticker}/signal-history` → devuelve señales pasadas con resultado.

### Frontend (IosefChart.tsx)

| Capa | Componente | Prioridad |
|---|---|---|
| Toggle "Ver señales" | `<SignalToggle>` | 🔥 Fase 1 |
| Background band | `<rect>` overlay | 🔥 Fase 1 |
| Signal pins | `<SignalPin>` con ciclo de vida | 🔥 Fase 1 |
| Agrupación anti-saturación | `<SignalCluster>` | 🔥 Fase 1 |
| Tracker P&L señal activa | `<ActiveSignalTracker>` | 🔥 Fase 2 |
| Panel lateral | `<SignalSidebar>` | 🔥 Fase 2 |
| Heatmap mensual (≥3MO) | `<SignalHeatmap>` | Fase 3 |
| Historial de señales | Endpoint nuevo + pins ✅/❌ | Fase 3 |

---

## Reglas de visibilidad por timeframe

| Timeframe | ¿Mostrar señales? | ¿Pins individuales o heatmap? |
|---|---|---|
| 1D | Sí (default ON) | Pins individuales (máx las del día) |
| 5D | Sí (default ON) | Pins individuales |
| 1MO | Sí (default ON) | Pins individuales |
| 3MO | Sí (default OFF) | Heatmap mensual + pins solo de últimos 30 días |
| 6MO | Sí (default OFF) | Heatmap mensual |
| 1Y | Sí (default OFF) | Heatmap mensual |

---

## Verificación

Para 3 tickers (uno con señal activa, uno con historial, uno sin señales):

- [ ] Toggle "Ver señales" aparece y funciona (ON/OFF)
- [ ] Con toggle ON y timeframe ≤ 1MO: se ven pins individuales
- [ ] Señal `new` tiene pin más grande y brillante que `expired`
- [ ] Señal ganadora muestra ✅, perdedora muestra ❌
- [ ] P&L tracker muestra % correcto (verificar contra precio real)
- [ ] Con toggle ON y timeframe ≥ 3MO: se ve heatmap, no pins individuales
- [ ] Sin señales: el gráfico se ve normal, sin errores
- [ ] Múltiples señales en mismo día: se agrupan, no se saturan
- [ ] Click en pin → panel lateral con detalle
- [ ] `npm run build` exitoso
- [ ] `npx vitest run` — 4/4 tests

---

## Criterios de aceptación

Un usuario nuevo debe poder, **en < 15 segundos y sin leer documentación**:

1. Ver si el ticker tiene señales → ✅ toggle + pins visibles
2. Saber cuál es la señal más reciente → ✅ pin más brillante/grande
3. Saber si la señal va ganando o perdiendo → ✅ tracker P&L
4. Entender el historial sin saturación → ✅ heatmap mensual
5. Ver el detalle completo de una señal → ✅ clic en pin → panel lateral
6. Navegar entre timeframes sin que el gráfico se rompa → ✅ reglas por timeframe

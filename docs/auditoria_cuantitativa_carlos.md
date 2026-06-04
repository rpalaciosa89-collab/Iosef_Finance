# Auditoría Cuantitativa del Motor de Señales
## Iosef Finance — 2026-06-04
**Autor:** Carlos (Ingeniero Financiero Senior · Data Science & ML)

> "Sin alfa matemáticamente demostrado, no hay edge. Todo lo demás es folklore." — Carlos

---

## 1. Resumen Ejecutivo

Se auditaron 4 subsistemas cuantitativos del backend:
1. `compute_signal_score` (scoring.py)
2. `_generate_trade_plan` (server.py)
3. `composite_score` (server.py — scan loop)
4. `_ticker_composite_score` (signal_evaluation.py)

**Hallazgos principales:** Los algoritmos son razonables y funcionalmente correctos, pero todos los umbrales son **heurísticos fijos** no calibrados estadísticamente. El riesgo más crítico es el plan de trade sin ATR: los SL/TP en porcentaje fijo ignoran la volatilidad individual del activo.

---

## 2. Auditoría: `compute_signal_score` (scoring.py)

### Fórmula Actual
```
score = (wr - 0.45) / 0.20 × 40  +  exp / 1.0 × 30  +  (pf - 1.0) / 0.5 × 20  +  conf_bonus
```

### Análisis Matemático

| Componente | Rango Input | Peso | Justificación | Estado |
|---|---|---|---|---|
| Win Rate (5d) | 45% – 65% | 40 pts | Centrado en el rango estadísticamente relevante | ✅ Correcto |
| Expectancy (5d) | 0% – 1% | 30 pts | 1% de retorno medio en 5d es un benchmark razonable | ✅ Correcto |
| Profit Factor | 1.0 – 1.5 | 20 pts | PF=1.5 es un umbral conservador pero honesto | ✅ Correcto |
| Confidence | label | 10 pts | Penaliza muestras insuficientes | ✅ Correcto |

### Hallazgos

**CRÍTICO — Falta normalización por volatilidad:**
La expectancy (retorno medio %) es comparada de forma absoluta entre activos con volatilidades muy distintas. Un retorno del 0.5% en 5 días es muy diferente para NVDA (β≈1.7) que para KO (β≈0.55).

**Recomendación de Carlos:**
Normalizar la expectancy por la volatilidad histórica del activo (ej. `return_5d / volatility_20d`). Esto convierte la expectancy en un **ratio de información (IR)** ajustado por riesgo.

```python
# Propuesta: Information Ratio parcial como sustituto de expectancy bruta
volatility_20d = close_series.pct_change().rolling(20).std().iloc[-1]
if volatility_20d > 0:
    ir_proxy = avg_return_5d / (volatility_20d * sqrt(5))  # Sharpe parcial
else:
    ir_proxy = 0.0
```

**ADVERTENCIA — Pesos fijos sin validación estadística:**
Los pesos 40/30/20/10 son arbitrarios. No han sido derivados por regresión logística u optimización. Esto es aceptable como punto de partida, pero debe ser reemplazado en v2.0 con pesos aprendidos de los datos históricos de `trades.db`.

---

## 3. Auditoría: `_generate_trade_plan` (server.py)

### Fórmula Actual
```python
if situation == "oversold":     sl=-4%,  tp=+8%  (RR 1:2)
if situation == "breakout":     sl=-3%,  tp=+9%  (RR 1:3)
if situation == "momentum_up":  sl=-5%,  tp=+10% (RR 1:2)
if situation == "bearish":      sl=+3%,  tp=-6%  (RR 1:2)
```

### ⛔ Hallazgo CRÍTICO — SL/TP fijo ignora la volatilidad del activo

Este es el problema más grave del sistema. Un stop-loss del 4% en TSLA (volatilidad diaria ~3%) se activará en condiciones normales de mercado. El mismo 4% en MSFT (volatilidad diaria ~1.2%) es excesivamente amplio.

**Solución recomendada — SL/TP basado en ATR (Average True Range):**
```python
# ATR(14) es la métrica estándar de volatilidad de precio para sizing
def _compute_atr(close_series: pd.Series, high_series: pd.Series, 
                 low_series: pd.Series, period: int = 14) -> float:
    """Average True Range: volatilidad real de precio, no % fijo."""
    tr = pd.DataFrame({
        'hl': high_series - low_series,
        'hc': (high_series - close_series.shift(1)).abs(),
        'lc': (low_series - close_series.shift(1)).abs()
    }).max(axis=1)
    return float(tr.ewm(span=period, adjust=False).mean().iloc[-1])

# En el plan de trade:
atr = _compute_atr(close_series, high_series, low_series)
atr_multiplier_sl = 1.5   # 1.5× ATR como stop loss
atr_multiplier_tp = 3.0   # 3.0× ATR como take profit (RR 1:2)

plan["stop_loss"]   = round(entry_price - (atr * atr_multiplier_sl), 2)  # LONG
plan["take_profit"] = round(entry_price + (atr * atr_multiplier_tp), 2)
plan["sl_pct"]      = round(((plan["stop_loss"] - entry_price) / entry_price) * 100, 2)
plan["tp_pct"]      = round(((plan["take_profit"] - entry_price) / entry_price) * 100, 2)
```

**Impacto:** Esta mejora tiene el potencial de reducir los `closed_loss` prematuros causados por stops demasiado ajustados en activos de alta volatilidad.

---

## 4. Auditoría: `composite_score` (scan loop, server.py)

### Fórmula Actual
```python
score += 1  # price > sma20
score += 2  # price > sma50
score += 3  # price > sma200
score += 2  # rsi < 30
score -= 2  # rsi > 70
score += 2  # momentum > 0
score += 1  # rel_volume > 1.5
score += 1  # pct_change > 0
# Max teórico = 12, Min = -2
```

### Hallazgos

**ADVERTENCIA — Escala inconsistente con `signal_strength_score`:**
El `composite_score` va de -2 a +12 pero no está normalizado a 0-100. El `signal_strength_score` sí está normalizado. Esto puede confundir al usuario que compara ambas columnas.

**ADVERTENCIA — Peso de SMA200 (3pts) vs SMA20 (1pt):**
La ponderación mayor a la SMA200 tiene justificación técnica (tendencia primaria > tendencia corta), pero no está validada empíricamente. El sistema debería aprender estos pesos del historial de `trades.db`.

**ADVERTENCIA — `rsi < 30` suma puntos en cualquier contexto:**
Un RSI<30 en tendencia bajista fuerte NO es una señal alcista. Sin embargo, el sistema suma puntos incondicionalmente. Esto puede generar falsas señales alcistas en mercados bajistas.

**Recomendación:** Condicionar el bonus de RSI al contexto del mercado:
```python
if rsi < 30 and current_context != "bearish":
    score += 2   # Solo suma en contextos neutro/bullish
elif rsi > 70 and current_context != "bullish":
    score -= 2
```

---

## 5. Auditoría: `_ticker_composite_score` (signal_evaluation.py)

### Fórmula Actual
```
score = win_rate × 0.40  +  ((avg_return + 10) / 20) × 0.30  +  log2(count)/log2(100) × 0.30
```

### Análisis

| Componente | Evaluación |
|---|---|
| Win Rate (40%) | ✅ Peso correcto, principal driver |
| Avg Return normalizado (30%) | ✅ Cap en ±10% evita dominancia de outliers |
| Log-scale count (30%) | ✅ Excelente decisión. Penaliza muestras pequeñas sin castigarlas linealmente |

**Esta es la función mejor diseñada del sistema.** El uso de log2 para el conteo es estadísticamente sound: añadir la muestra 2 a 10 → beneficio de `log2(10)=3.32` pero añadir muestra 100 a 200 → beneficio marginal mucho menor. Refleja correctamente la ley de rendimientos decrecientes de la información estadística.

**MENOR — Avg return usa retorno bruto, no ajustado por riesgo:** Mismo comentario que en scoring.py.

---

## 6. Análisis de Sesgos Estadísticos

### ✅ Sin Look-Ahead Bias (Confirmado)

Revisión de `signal_evaluation.py`:
```python
ret_5d = closes.shift(-5) / closes - 1  # ← correcto: precio futuro / precio hoy
```
El forward return se calcula correctamente usando `shift(-5)`, que mira hacia adelante en la serie temporal. No existe look-ahead bias porque el signal es determinado por los precios ACTUALES (`mask`), y el retorno es calculado hacia ADELANTE.

### ⚠️ Riesgo de Survivorship Bias (Potencial)

El universo de tickers (`NASDAQ100_TICKERS`, `SP500_TICKERS`) refleja **la composición actual** de los índices. Los tickers delisted (WBA, SPLK, ANSS — ya corregidos) y los que fueron expulsados por mal rendimiento NO aparecen. Esto genera un sesgo de supervivencia en las métricas históricas de cualquier señal evaluada sobre estos universos.

**Impacto estimado:** Sobreestimación del win rate en 3-8% según la literatura académica en backtesting de índices.

**Acción recomendada:** Usar una lista de tickers con composición histórica puntual (ej. tickers del NASDAQ100 en 2022, no los de 2024).

---

## 7. Roadmap Cuantitativo — Fase 2 del Motor

| Prioridad | Mejora | Esfuerzo | Impacto |
|---|---|---|---|
| 🔴 Alta | SL/TP basado en ATR(14) en lugar de % fijo | Media | Elimina stops prematuros en activos volátiles |
| 🔴 Alta | Normalizar expectancy por volatilidad (IR proxy) | Baja | Comparación equitativa entre activos |
| 🟡 Media | RSI condicional al contexto de mercado | Baja | Reduce falsas señales alcistas en bear markets |
| 🟡 Media | Normalizar composite_score a 0-100 | Baja | UX más clara para el usuario |
| 🟢 Baja | Pesos aprendidos (regresión logística sobre trades.db) | Alta | Eliminación de arbitrariedad en weights |
| 🟢 Baja | Universo histórico puntual para evitar survivorship bias | Alta | Backtesting más honesto |

---

## 8. Dictamen Final de Carlos

El motor actual es **funcionalmente correcto y estadísticamente honesto** en lo fundamental: no hay look-ahead bias, el scoring penaliza muestras pequeñas, y el profit factor actúa como barrera mínima de calidad.

Los problemas son de **calibración y robustez**, no de diseño fundamental. El sistema está listo para producción con la corrección urgente del SL/TP basado en ATR. Las demás mejoras son iterativas.

**Veredicto:** ⚠️ APROBADO CON OBSERVACIONES — Corrección de ATR obligatoria antes de ir a producción con capital real.

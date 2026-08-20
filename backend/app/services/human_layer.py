"""
Iosef Finance — Human Layer
============================
Traduce la lógica cuantitativa a lenguaje natural comprensible
para cualquier usuario, sin contradicir el scoring real.

Campos generados por `translate_ticker`:
  human_signal       → etiqueta semántica de la señal
  situation          → categoría interna de la situación
  suggested_action   → qué hacer
  holding_period     → durante cuánto tiempo
  risk_level         → nivel de riesgo en texto
  explanation        → explicación en español sin jerga
  confidence_text    → traducción de confidence al español
  decision_clarity   → "alta" / "media" / "baja"
"""

from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
# Signal detection helpers
# ──────────────────────────────────────────────────────────────────────────────

def _detect_situation(t: dict) -> str:
    """Detect the primary technical situation for this ticker."""
    rsi       = t.get("rsi", 50.0)
    change    = t.get("change_pct", 0.0)
    ma_brk    = t.get("ma_breakout_signal", False)
    composite = t.get("composite_score", 0)
    score     = t.get("signal_strength_score", 0.0)
    price     = t.get("price", 0.0)
    sma50     = t.get("sma50", 0.0)
    sma200    = t.get("sma200", 0.0)
    mom       = t.get("momentum_1m", 0.0)
    context   = t.get("market_context_used", "neutral")

    # Priority order: strongest signals first
    if rsi < 30:
        return "oversold"
    if rsi > 70 and change > 0:
        return "overbought"
    if ma_brk and composite >= 6:
        return "breakout_strong"
    if ma_brk and composite < 6:
        return "breakout_forming"
    if change < -3.0:
        return "momentum_down"
    if change > 3.0:
        return "momentum_up"
    # Breakdown: price below key MAs and falling
    if price < sma50 and mom < -5.0:
        return "breakdown"
    if composite >= 6 and not ma_brk:
        return "weak_signal" if context == "bearish" else "strong_trend"
    if score < 10 or (composite == 0 and not ma_brk):
        return "no_signal"
    if price > sma50:
        return "neutral_positive"
    if price > sma200:
        return "neutral_holding"
    return "weak_signal"


def _human_signal_label(situation: str) -> tuple[str, str]:
    """Returns (human_signal_text, icon)."""
    MAP = {
        "oversold":          ("REBOTE PROBABLE",      "✅"),
        "overbought":        ("SUBIDA EXCESIVA",       "⚠️"),
        "breakout_strong":   ("RUPTURA ALCISTA",       "🔥"),
        "breakout_forming":  ("RUPTURA EN FORMACIÓN",  "👀"),
        "momentum_up":       ("COMPRAS AGRESIVAS",     "✅"),
        "momentum_down":     ("VENTAS AGRESIVAS",      "⚠️"),
        "breakdown":         ("PÉRDIDA DE SOPORTE",    "🚫"),
        "strong_trend":      ("TENDENCIA POSITIVA",    "✅"),
        "no_signal":         ("SIN SEÑAL CLARA",       "—"),
        "weak_signal":       ("SEÑAL DÉBIL",           "👀"),
        "neutral_positive":  ("NEUTRAL ALCISTA",       "📊"),
        "neutral_holding":   ("NEUTRAL ESTABLE",       "📊"),
    }
    return MAP.get(situation, ("SIN SEÑAL CLARA", "—"))


# ──────────────────────────────────────────────────────────────────────────────
# Suggested action — coherent with score, context-adjusted if adverse
# ──────────────────────────────────────────────────────────────────────────────

def _suggested_action(situation: str, score: float, ctx_adj: float) -> str:
    """
    Derive the human action recommendation.
    - ctx_adj == -0.15 → market is working against the signal → soften action
    - ctx_adj == +0.15 → market amplifies the signal → can be bolder
    """
    adverse_market = ctx_adj <= -0.15
    favorable_market = ctx_adj >= 0.15

    # ── Hard rules first ───────────────────────────────────────────────────
    if score < 10:
        return "Esperar"

    if situation == "breakdown":
        return "No comprar / Vender si tienes"

    if situation == "momentum_down":
        if score >= 40:
            return "Reducir posición"
        return "Evitar"

    # ── Bullish situations ─────────────────────────────────────────────────
    if situation == "oversold":
        if score >= 60:
            return "Vigilar antes de entrar" if adverse_market else "Comprar con precaución"
        if score >= 35:
            return "Vigilar antes de entrar" if adverse_market else "Vigilar"
        return "Esperar"

    if situation == "breakout_strong":
        if score >= 60:
            return "Vigilar antes de entrar" if adverse_market else "Comprar"
        if score >= 35:
            return "Vigilar antes de entrar" if adverse_market else "Comprar con precaución"
        return "Vigilar"

    if situation == "breakout_forming":
        if score >= 40:
            return "Vigilar antes de entrar" if adverse_market else "Vigilar"
        return "Esperar"

    if situation == "momentum_up":
        if score >= 50:
            return "Vigilar antes de entrar" if adverse_market else "Comprar con precaución"
        return "Vigilar"

    if situation == "strong_trend":
        if score >= 50:
            return "Vigilar antes de entrar" if adverse_market else "Comprar con precaución"
        return "Vigilar"

    if situation == "overbought":
        if score >= 50:
            return "Tomar ganancias"
        return "Precaución"

    if situation in ("neutral_positive", "neutral_holding"):
        if score >= 55:
            return "Vigilar"
        return "Esperar"

    # ── Generic fallback ───────────────────────────────────────────────────
    if score >= 50:
        return "Vigilar antes de entrar" if adverse_market else "Vigilar"
    if score >= 25:
        return "Vigilar"
    return "Esperar"


# ──────────────────────────────────────────────────────────────────────────────
# Holding period — derived from Strategy Lab stats when available
# ──────────────────────────────────────────────────────────────────────────────

def _holding_period(situation: str, signal_stats: Optional[dict]) -> str:
    """Use Lab stats to pick the best horizon; fall back to situation heuristics."""
    if signal_stats:
        wr1  = signal_stats.get("win_rate_1d")  or 0.0
        wr5  = signal_stats.get("win_rate_5d")  or 0.0
        wr10 = signal_stats.get("win_rate_10d") or 0.0
        wr20 = signal_stats.get("win_rate_20d") or 0.0
        best = max([(wr1, "1d"), (wr5, "5d"), (wr10, "10d"), (wr20, "20d")], key=lambda x: x[0])
        horizon = best[1]
        if horizon == "1d":
            return "1 a 3 días"
        if horizon == "5d":
            return "5 a 10 días"
        return "10 a 20 días"

    # Heuristics when no lab data
    HEURISTICS = {
        "oversold":         "5 a 10 días",
        "breakout_strong":  "5 a 10 días",
        "breakout_forming": "Corto plazo",
        "momentum_up":      "1 a 3 días",
        "momentum_down":    "1 a 3 días",
        "overbought":       "1 a 3 días",
        "strong_trend":     "10 a 20 días",
        "breakdown":        "Corto plazo",
        "neutral_positive": "5 a 10 días",
        "neutral_holding":  "10 a 20 días",
    }
    return HEURISTICS.get(situation, "Corto plazo")


# ──────────────────────────────────────────────────────────────────────────────
# Risk level
# ──────────────────────────────────────────────────────────────────────────────

def _risk_level(score: float, ctx_adj: float, situation: str) -> str:
    adverse = ctx_adj <= -0.15
    suffix = " (mercado en contra)" if adverse else ""

    if situation in ("breakdown", "momentum_down"):
        return "Alto" + suffix
    if score >= 75:
        return "Medio" + suffix
    if score >= 50:
        return "Medio-Alto" + suffix
    return "Alto" + suffix


# ──────────────────────────────────────────────────────────────────────────────
# Explanation — plain Spanish, no jargon
# ──────────────────────────────────────────────────────────────────────────────

def _explanation(situation: str, score: float, ctx_adj: float, t: dict) -> str:
    adverse = ctx_adj <= -0.15
    
    is_bullish = situation in ("oversold", "breakout_strong", "breakout_forming", "momentum_up", "strong_trend")
    is_bearish = situation in ("overbought", "breakdown", "momentum_down")
    
    if adverse and is_bullish:
        ctx_suffix = " Sin embargo, el mercado general está débil, lo que añade riesgo a esta oportunidad."
    elif adverse and is_bearish:
        ctx_suffix = " Sin embargo, el mercado general está fuerte, lo que reduce la probabilidad de caídas."
    else:
        ctx_suffix = ""

    rsi     = t.get("rsi", 50.0)
    change  = t.get("change_pct", 0.0)
    rvol    = t.get("relative_volume", 1.0)

    if situation == "oversold":
        base = "Esta acción ha caído muy rápido y el sistema detecta una posible oportunidad de rebote."
        return base + ctx_suffix

    if situation == "overbought":
        base = (
            "La acción lleva subiendo con fuerza y el sistema detecta señales de agotamiento. "
            "Puede ser buen momento para asegurar ganancias si tienes posición."
        )
        return base + ctx_suffix

    if situation == "breakout_strong":
        base = "La acción está rompiendo una zona de resistencia importante con fuerza compradora y buena señal técnica."
        return base + (" El mercado general favorece este tipo de movimientos." if ctx_adj >= 0.15 else ctx_suffix)

    if situation == "breakout_forming":
        return (
            "La acción muestra señales de inicio de ruptura, pero aún no está totalmente confirmada. "
            "Vale la pena seguirla de cerca antes de actuar."
        )

    if situation == "momentum_up":
        return (
            f"Esta acción registra una subida brusca ({change:+.1f}%) con mayor actividad de lo normal. "
            "El sistema detecta interés comprador inusual."
        )

    if situation == "momentum_down":
        base = (
            f"Esta acción cae con fuerza ({change:.1f}%) y el sistema no detecta señales claras de recuperación cercana. "
            "Es preferible esperar a que se estabilice."
        )
        return base + ctx_suffix

    if situation == "breakdown":
        base = (
            "La acción perdió niveles técnicos importantes y el sistema detecta debilidad estructural. "
            "No es un buen momento para entrar."
        )
        return base + ctx_suffix

    if situation == "strong_trend":
        return (
            "El sistema detecta una tendencia positiva sólida. "
            "No hay una señal de entrada específica, pero la acción muestra fortaleza general."
        )

    if situation == "no_signal":
        return (
            "No hay señales claras en este momento. "
            "La acción no presenta condiciones técnicas relevantes. Lo mejor es esperar."
        )

    if situation == "neutral_positive":
        return (
            "La acción se mantiene sobre su media de 50 días, lo cual es una señal técnica positiva. "
            "Sin embargo, no hay una señal de entrada específica. Observar de cerca."
        )

    if situation == "neutral_holding":
        return (
            "La acción se sostiene sobre su media de 200 días, pero por debajo de la de 50 días. "
            "Zona de consolidación. Esperar una señal más clara."
        )

    # weak_signal
    return (
        "El sistema detecta una señal leve, pero no lo suficientemente fuerte para actuar con confianza. "
        "Mejor esperar confirmación."
    )


# ──────────────────────────────────────────────────────────────────────────────
# Confidence text
# ──────────────────────────────────────────────────────────────────────────────

def _confidence_text(source: str, score: float, signal_stats: Optional[dict]) -> str:
    if source == "fallback" or signal_stats is None:
        return "Confianza limitada: sin suficiente historial para esta señal"
    conf = (signal_stats.get("confidence") or "low").lower()
    if conf == "high":
        return "Alta confianza: patrón bien respaldado por datos históricos"
    if conf == "medium":
        return "Confianza media: patrón con historial razonable de resultados"
    return "Baja confianza: patrón con poco historial o resultado débil"


# ──────────────────────────────────────────────────────────────────────────────
# Decision clarity
# ──────────────────────────────────────────────────────────────────────────────

def _decision_clarity(score: float, ctx_adj: float, situation: str, source: str) -> str:
    """
    'alta'  → señal fuerte, contexto favorable o neutro, fuente optimized
    'media' → señal presente pero con algún factor limitante
    'baja'  → señal débil, contexto adverso, o sin datos históricos
    """
    if situation in ("no_signal",) or source == "fallback":
        return "baja"
    if situation in ("weak_signal", "neutral_positive", "neutral_holding"):
        return "baja" if ctx_adj <= -0.15 else "media"
    if score >= 55 and ctx_adj >= 0 and source == "optimized":
        return "alta"
    if score >= 35 and ctx_adj >= -0.15:
        return "media"
    return "baja"


# ──────────────────────────────────────────────────────────────────────────────
# Signal Revalidation Note — Lifecycle-aware human message
# ──────────────────────────────────────────────────────────────────────────────

def _revalidation_note(signal_status: str, entry_window_status: str, signal_expired: bool) -> str:
    """Generate a short, friendly revalidation message based on lifecycle state."""
    if signal_expired or signal_status == "expired":
        return "Ya no es una entrada eficiente en este momento."

    if signal_status == "new":
        if entry_window_status == "open":
            return "Señal recién detectada. Ventana de entrada abierta."
        return "Señal nueva. Monitorear de cerca."

    if signal_status == "active":
        if entry_window_status == "open":
            return "Sigue vigente."
        if entry_window_status == "narrowing":
            return "Todavía válida, pero con menor claridad."
        if entry_window_status == "late":
            return "La oportunidad se está debilitando. Entrada menos eficiente."
        return "Señal activa."

    if signal_status == "weakening":
        if entry_window_status in ("late", "closed"):
            return "La oportunidad se está debilitando. Ya no es un punto de entrada eficiente."
        return "La señal está perdiendo fuerza. Vigilar antes de actuar."

    # No lifecycle state yet (no active signal for this ticker)
    return ""


# ──────────────────────────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────────────────────────

def translate_ticker(ticker_data: dict, opt_cache: Optional[dict]) -> dict:
    """
    Receives a fully-computed ticker dict from run_scan() and the
    optional strategy optimization cache from Redis.

    Returns a dict with human-readable fields to be merged into the ticker.
    Note: lifecycle fields (signal_status, entry_window_status, etc.) are
    already set by the Signal Lifecycle Engine before this function is called.
    """
    score     = ticker_data.get("signal_strength_score", 0.0) or 0.0
    ctx_adj   = ticker_data.get("signal_context_adjustment", 0.0) or 0.0
    source    = ticker_data.get("signal_strength_source", "fallback")
    rsi       = ticker_data.get("rsi", 50.0)
    ma_brk    = ticker_data.get("ma_breakout_signal", False)

    # Detect primary situation
    situation = _detect_situation(ticker_data)

    # Try to find the best matching signal stats from Strategy Lab cache
    signal_stats: Optional[dict] = None
    if opt_cache and isinstance(opt_cache, dict):
        ind = opt_cache.get("individual_signals", {})
        comb = opt_cache.get("combined_signals", {})

        # Map situation → preferred signal key in lab
        SIT_TO_SIG = {
            "oversold":        "oversold",
            "overbought":      "overbought",
            "breakout_strong": "breakout_up__composite_gte6",
            "breakout_forming":"ma_breakout_signal",
            "momentum_up":     "momentum_shift_up",
            "momentum_down":   "momentum_shift_down",
            "strong_trend":    "composite_score_high",
        }
        sig_key = SIT_TO_SIG.get(situation)
        if sig_key:
            signal_stats = comb.get(sig_key) or ind.get(sig_key)

    label, icon = _human_signal_label(situation)
    action      = _suggested_action(situation, score, ctx_adj)
    holding     = _holding_period(situation, signal_stats)
    risk        = _risk_level(score, ctx_adj, situation)
    explanation = _explanation(situation, score, ctx_adj, ticker_data)
    conf_text   = _confidence_text(source, score, signal_stats)
    clarity     = _decision_clarity(score, ctx_adj, situation, source)

    # Lifecycle revalidation note (reads fields injected by server.py lifecycle engine)
    sig_status   = ticker_data.get("signal_status", "")
    entry_window = ticker_data.get("entry_window_status", "")
    sig_expired  = ticker_data.get("signal_expired", False)
    reval_note   = _revalidation_note(sig_status, entry_window, sig_expired)

    return {
        "human_signal":    f"{icon} {label}",
        "situation":       situation,
        "suggested_action": action,
        "holding_period":  holding,
        "risk_level":      risk,
        "explanation":     explanation,
        "confidence_text": conf_text,
        "decision_clarity": clarity,
        "signal_revalidation_note": reval_note,
    }


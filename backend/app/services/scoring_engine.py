"""
Motor de scoring pluggable (SP-4.3).

Unifica la heuristica aditiva del screener (antes inline en server.py) con el
score ML (XGBoost), y ETIQUETA la fuente de cada score para que el frontend
nunca confunda heuristica con modelo:

  source: "heuristic" | "ml" | "ensemble"
  components: { heuristic: <n>, ml: <n>|null }
  auc_gate: "passed" | "failed"
"""

import logging
from typing import Optional

from app.services.scoring import compute_ml_score, _load_model_meta

logger = logging.getLogger(__name__)


def heuristic_score(features: dict) -> dict:
    """
    Score aditivo historico del screener (server.py:666-684):
      +1 close>SMA20, +2 close>SMA50, +3 close>SMA200,
      +2 RSI<30, -2 RSI>70, +2 momentum_1m>0, +1 rel_volume>1.5, +1 pct_change>0.
    Devuelve {value, source, components:{heuristic, ml}}.
    """
    value = 0
    if features.get("close", 0) > features.get("sma20", 0):
        value += 1
    if features.get("close", 0) > features.get("sma50", 0):
        value += 2
    if features.get("close", 0) > features.get("sma200", 0):
        value += 3
    rsi = features.get("rsi", 50)
    if rsi < 30:
        value += 2
    elif rsi > 70:
        value -= 2
    if features.get("momentum_1m", 0) > 0:
        value += 2
    if features.get("rel_volume", 0) > 1.5:
        value += 1
    if features.get("pct_change", 0) > 0:
        value += 1

    return {
        "value": value,
        "source": "heuristic",
        "components": {"heuristic": value, "ml": None},
    }


def _is_model_promoted() -> bool:
    """Lee el meta del modelo (SP-4.2): promoted=false -> modelo archivado."""
    try:
        meta = _load_model_meta()
        return bool(meta.get("promoted", True))  # backward compat
    except Exception:
        return True  # sin meta, no bloquear el flujo legacy


def score_ticker(features: dict) -> dict:
    """
    Score final de un ticker con etiqueta de fuente honesta.
    - Si el modelo ML esta promovido: ensemble (heuristica + ML normalizado).
    - Si no: solo heuristica, ml=None, auc_gate=failed.
    """
    h = heuristic_score(features)

    promoted = _is_model_promoted()
    if not promoted:
        return {
            "value": h["value"],
            "source": "heuristic",
            "components": {"heuristic": h["value"], "ml": None},
            "auc_gate": "failed",
        }

    ml_value = compute_ml_score(
        {
            "log_return": features.get("log_return", 0.0),
            "volatility_20": features.get("volatility_20", 0.0),
            "momentum_10": features.get("momentum_10", 0.0),
            "rsi_14": features.get("rsi_14", features.get("rsi", 50.0)),
            "macd_hist": features.get("macd_hist", 0.0),
        }
    )

    # Ensemble simple: 60% heuristica normalizada + 40% ML (0-100 -> 0-10)
    heur_norm = min(10.0, h["value"])
    ml_norm = ml_value / 10.0  # 0-100 -> 0-10
    ensemble = round(0.6 * heur_norm + 0.4 * ml_norm, 2)

    return {
        "value": ensemble,
        "source": "ensemble",
        "components": {"heuristic": h["value"], "ml": round(ml_value, 1)},
        "auc_gate": "passed",
    }


class ScoringEngine:
    """Interfaz estable del motor: score(features) -> (value, source, components)."""

    def score(self, features: dict) -> dict:
        return score_ticker(features)
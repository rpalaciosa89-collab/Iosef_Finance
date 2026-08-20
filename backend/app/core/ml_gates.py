"""
Gates de promocion de modelos ML (SP-4.2).

Este modulo NO importa torch ni xgboost: solo lee los reportes de validacion
walk-forward (JSON) y decide si un modelo esta promovido. Aislarlo permite
testear los gates sin cargar librerias pesadas (evita colision de inicializadores
OpenMP/threads que causa segfaults en macOS).
"""

import json
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

PROMOTION_AUC_THRESHOLD = 0.56

MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "models"
XGB_REPORT = MODEL_DIR / "xgboost_signal_scorer_meta.json"
LSTM_REPORT = MODEL_DIR / "lstm_walkforward_report.json"


def _read_report(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception as e:
        logger.warning(f"No se pudo leer reporte {path.name}: {e}")
    return {}


@lru_cache(maxsize=1)
def xgboost_is_promoted() -> bool:
    """XGBoost promovido solo si el meta lo indica explicitamente (gate AUC OOS)."""
    meta = _read_report(XGB_REPORT)
    promoted = meta.get("promoted")
    if promoted is False:
        return False
    if promoted is True:
        return True
    # Backward compat: reportes antiguos sin el campo promoted
    auc = meta.get("auc_oos_mean")
    if auc is not None:
        return float(auc) >= PROMOTION_AUC_THRESHOLD
    return True  # sin reporte, comportamiento legacy


@lru_cache(maxsize=1)
def lstm_is_promoted() -> bool:
    """LSTM promovido solo si el reporte walk-forward lo indica (AUC OOS >= 0.56)."""
    report = _read_report(LSTM_REPORT)
    promoted = report.get("promoted")
    if promoted is False:
        return False
    if promoted is True:
        return True
    auc = report.get("auc_oos")
    if auc is not None:
        return float(auc) >= PROMOTION_AUC_THRESHOLD
    return True  # sin reporte, comportamiento legacy


def invalidate_caches() -> None:
    xgboost_is_promoted.cache_clear()
    lstm_is_promoted.cache_clear()
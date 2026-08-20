import joblib
import json
import logging
import threading
import pandas as pd
from pathlib import Path
import xgboost as xgb

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).resolve().parent.parent.parent / "models" / "xgboost_signal_scorer.pkl"
META_PATH = Path(__file__).resolve().parent.parent.parent / "models" / "xgboost_signal_scorer_meta.json"

# Carga lazy: evita colision de inicializadores (torch+xgboost/OpenMP) y agiliza
# el arranque. El modelo se carga en el primer compute_ml_score.
_xgb_model = None
_model_lock = threading.Lock()
_model_loaded = False


def _load_xgb_model():
    """Carga el modelo XGBoost una sola vez (thread-safe)."""
    global _xgb_model, _model_loaded
    if _model_loaded:
        return _xgb_model
    with _model_lock:
        if not _model_loaded:
            try:
                _xgb_model = joblib.load(MODEL_PATH)
                logger.info("Modelo XGBoost cargado con éxito para inferencia.")
            except Exception as e:
                logger.warning(f"No se pudo cargar el modelo XGBoost: {e}")
                _xgb_model = None
            _model_loaded = True
    return _xgb_model


def _load_model_meta() -> dict:
    try:
        if META_PATH.exists():
            return json.loads(META_PATH.read_text())
    except Exception:
        pass
    return {}


def get_model_info() -> dict:
    meta = _load_model_meta()
    return {
        "model_source": meta.get("source", "synthetic"),
        "trained_at": meta.get("trained_at", ""),
        "n_samples": meta.get("n_samples", 0),
        "n_tickers": meta.get("n_tickers", 0),
        "roc_auc": meta.get("roc_auc", 0.0),
        "auc_oos_mean": meta.get("auc_oos_mean", None),
        "auc_oos_std": meta.get("auc_oos_std", None),
        "cv_folds": meta.get("cv_folds", 0),
        "embargo_days": meta.get("embargo_days", 0),
        "promoted": bool(meta.get("promoted", True)),  # backward compat: si no hay gate, asumir legacy
        "status": "promoted" if meta.get("promoted", True) else "archived",
    }

def compute_ml_score(features: dict) -> float:
    """
    Inferencia de Machine Learning: Calcula P(Win) usando XGBoost.
    SP-4.2: si el modelo no esta `promoted` (gate AUC OOS < 0.56), devuelve
    el fallback 50.0 (sin señal) en lugar de usar un modelo sin edge.
    """
    model = _load_xgb_model()
    if model is None:
        return 50.0  # Fallback si no hay modelo

    meta = _load_model_meta()
    if meta.get("promoted") is False:
        logger.info("Modelo archivado (gate AUC no superado); score ML desactivado.")
        return 50.0

    try:
        # Expected features: log_return, volatility_20, momentum_10, rsi_14, macd_hist
        df = pd.DataFrame([features])
        # Rellenar faltantes con 0 para evitar fallos si el dict viene incompleto
        for col in ['log_return', 'volatility_20', 'momentum_10', 'rsi_14', 'macd_hist']:
            if col not in df.columns:
                df[col] = 0.0
                
        # Predict probability of class 1 (Success)
        prob = model.predict_proba(df)[0, 1]
        return round(prob * 100, 1) # Return as percentage 0-100
    except Exception as e:
        logger.error(f"Error en inferencia ML: {e}")
        return 50.0

def get_confidence_label(total: int, win_rate_5d: float, profit_factor: float, expectancy: float) -> str:
    """
    Determine the confidence label for a signal based on historical metrics.
    Penalizes weak edge (negative expectancy or profit factor < 1.0) regardless of sample size.
    """
    # Strict penalty for weak/negative drift
    if profit_factor is not None and profit_factor < 1.0:
        return "low"
    if expectancy is not None and expectancy <= 0.0:
        return "low"

    if total < 15:
        return "insufficient_sample"
    if total >= 100 and win_rate_5d >= 0.60:
        return "high"
    if total >= 40:
        return "medium"
    return "low"

def compute_signal_score(stats: dict) -> float:
    """
    Compute a normalized signal strength score (0-100) based on historical metrics.
    Used by both the Real-Time Scoring Engine and Strategy Lab.
    """
    wr = stats.get("win_rate_5d") or 0.0
    # Carlos Audit: Use Information Ratio proxy if available, fallback to raw expectancy
    exp = stats.get("ir_proxy") if stats.get("ir_proxy") is not None else (stats.get("expectancy_5d") or 0.0)
    pf = stats.get("profit_factor") or 0.0
    conf = stats.get("confidence") or "low"

    # Base scale:
    # Win Rate: linearly scale from 45% to 65% (max 40 pts)
    # Expectancy (or IR): linearly scale from 0 to 1.0 (max 30 pts)
    # Profit Factor: linearly scale from 1.0 to 1.5 (max 20 pts)
    # Confidence: high=10, medium=5, low=0 (max 10 pts)
    
    score = min(100.0, (
        max(0.0, min((wr - 0.45) / 0.20, 1.0)) * 40.0 +
        max(0.0, min(exp / 1.0, 1.0)) * 30.0 +
        max(0.0, min((pf - 1.0) / 0.5, 1.0)) * 20.0 +
        {"high": 10, "medium": 5, "low": 0, "insufficient_sample": 0}.get(conf, 0)
    ))
    return round(score, 1)

"""
app/services/lstm_inference.py

Servicio de inferencia del Global LSTM Titan 100.
- Carga el modelo una sola vez en memoria RAM (Singleton).
- Genera el Neural Confidence Score P_lstm(Win) por ticker.
- Combina con XGBoost para un Score compuesto final.

Responsable: Javier (Infra) | Auditado por: Carlos (Quant)
Licencia de dependencias: PyTorch (BSD), Numpy (BSD)
"""

import sys
import logging
from pathlib import Path
from functools import lru_cache

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

logger = logging.getLogger(__name__)

BASE_DIR  = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = BASE_DIR / "models"
DATA_DIR  = BASE_DIR / "data" / "titan_parquet"

# ── Arquitectura LSTM (debe coincidir exactamente con el training) ────────────
class GlobalLSTM(nn.Module):
    def __init__(self):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=5,
            hidden_size=64,
            num_layers=2,
            batch_first=True,
            dropout=0.3,
        )
        self.norm = nn.LayerNorm(64)
        self.fc   = nn.Sequential(
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        out, _ = self.lstm(x)
        out = self.norm(out[:, -1, :])
        return self.fc(out)


# ── Singleton: carga el modelo una sola vez ───────────────────────────────────
@lru_cache(maxsize=1)
def _load_model() -> tuple[nn.Module, torch.device]:
    """Carga y cachea el modelo LSTM en memoria. Thread-safe gracias a lru_cache."""
    model_path = MODEL_DIR / "global_lstm_titan100.pth"
    if not model_path.exists():
        raise FileNotFoundError(f"Modelo no encontrado: {model_path}")

    # Device: MPS → CPU (inferencia en MPS puede tener limitaciones con batch=1)
    device = torch.device("cpu")  # CPU para inferencia single-sample es más rápido
    model = GlobalLSTM()
    model.load_state_dict(torch.load(model_path, map_location=device, weights_only=True))
    model.eval()
    logger.info("✓ Global LSTM Titan 100 cargado en memoria.")
    return model, device


SEQ_LEN      = 60
FEATURE_COLS = ["volume_norm", "log_return", "momentum_10", "rsi_14", "macd_hist"]


def _build_features(df: pd.DataFrame) -> pd.DataFrame | None:
    """Replica exactamente el feature engineering del training."""
    df = df.copy().sort_index()
    if len(df) < SEQ_LEN + 20:
        return None

    df["log_return"]    = np.log(df["close"] / df["close"].shift(1))
    df["volatility_20"] = df["log_return"].rolling(20).std()
    df["momentum_10"]   = df["close"].pct_change(10)

    # Volume normalizado
    df["volume_log"]  = np.log1p(df["volume"])
    df["volume_norm"] = (
        (df["volume_log"] - df["volume_log"].rolling(60).mean()) /
        (df["volume_log"].rolling(60).std() + 1e-9)
    )

    # RSI 14
    delta = df["close"].diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    df["rsi_14"] = 100 - (100 / (1 + gain / (loss + 1e-9)))

    # MACD Histogram
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    macd  = ema12 - ema26
    df["macd_hist"] = macd - macd.ewm(span=9, adjust=False).mean()

    df.dropna(inplace=True)
    return df


def get_lstm_score(ticker: str) -> float | None:
    """
    Retorna el Neural Confidence Score P_lstm(Win) ∈ [0, 1] para un ticker.
    Usa los últimos 60 días de historia almacenada en Parquet.
    Retorna None si el ticker no está en el Titan 100 o no hay datos suficientes.
    """
    parquet_path = DATA_DIR / f"{ticker.replace('/', '_')}.parquet"
    if not parquet_path.exists():
        return None

    try:
        df = pd.read_parquet(parquet_path)
        df = _build_features(df)
        if df is None or len(df) < SEQ_LEN:
            return None

        # Tomar los últimos SEQ_LEN días (la "memoria reciente")
        seq = df[FEATURE_COLS].values[-SEQ_LEN:]
        seq_tensor = torch.tensor(seq, dtype=torch.float32).unsqueeze(0)  # (1, 60, 5)

        model, device = _load_model()
        with torch.no_grad():
            prob = model(seq_tensor.to(device)).item()

        return round(prob, 4)

    except Exception as e:
        logger.error(f"[LSTM] Error en inferencia para {ticker}: {e}")
        return None


def get_composite_score(ticker: str, xgb_score: float) -> dict:
    """
    Combina XGBoost P(Win) con LSTM Neural Confidence para producir
    un Score Compuesto (Ensemble) más robusto.

    Ponderación:
      - XGBoost  (40%): Rápido, basado en indicadores técnicos puntuales.
      - LSTM     (60%): Memoriza 60 días de secuencia, capta momentum profundo.
    """
    lstm_score_val = get_lstm_score(ticker)

    if lstm_score_val is None:
        # Ticker fuera del Titan 100: usar solo XGBoost
        return {
            "p_win_xgb":      round(xgb_score, 4),
            "p_win_lstm":     None,
            "p_win_composite": round(xgb_score, 4),
            "model":          "xgboost_only",
        }

    # Escalar a porcentaje (0-100) para alinear con xgb_score
    lstm_pct = lstm_score_val * 100.0

    composite = 0.40 * xgb_score + 0.60 * lstm_pct
    return {
        "p_win_xgb":       round(xgb_score, 4),
        "p_win_lstm":      round(lstm_pct, 4),
        "p_win_composite": round(composite, 4),
        "model":           "ensemble",
    }

"""
scripts/retrain_global_lstm.py

Re-entrenamiento Continuo (Online Learning) — Modelo Titan 100.
Diseñado para ejecutarse como cron job diario (ej. cada noche a las 02:00 AM).

Estrategia:
  1. Descarga los últimos 30 días de datos frescos para todos los tickers del Titan 100.
  2. Carga el modelo existente (transfer learning desde el checkpoint actual).
  3. Entrena sólo sobre los datos recientes (fine-tuning), preservando el conocimiento histórico.
  4. Guarda el nuevo checkpoint, versionado por fecha.
  5. Genera informe de métricas para auditoría del equipo.

Principio: El modelo "vive" con el mercado. No se queda obsoleto.

Responsable: Javier (Infra/Scheduling) | Auditado por: Carlos (Quant)
"""

import sys
import logging
import time
import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

BASE_DIR  = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
from config.titan_universe import TITAN_100, SECTOR_MAP
from scripts.train_global_lstm import GlobalLSTM, FEATURE_COLS, SEQ_LEN, build_sequences, compute_features

MODEL_DIR   = BASE_DIR / "models"
RETRAIN_DIR = BASE_DIR / "models" / "checkpoints"
DATA_DIR    = BASE_DIR / "data" / "titan_parquet"
LOG_DIR     = BASE_DIR.parent / "artifacts" / "retraining_logs"

RETRAIN_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Hiperparámetros del fine-tuning (menos agresivo que el entrenamiento inicial)
FINE_TUNE_EPOCHS = 10
FINE_TUNE_LR     = 1e-4    # LR más pequeño para no "destruir" lo aprendido
BATCH_SIZE       = 512

DEVICE = torch.device("mps") if torch.backends.mps.is_available() else torch.device("cpu")


def download_recent_data(ticker: str, days: int = 30) -> pd.DataFrame | None:
    """Descarga los últimos N días de datos OHLCV para un ticker."""
    end   = datetime.today()
    start = end - timedelta(days=days + 30)  # Buffer extra para features rolling

    try:
        df = yf.download(ticker, start=start.strftime("%Y-%m-%d"),
                         end=end.strftime("%Y-%m-%d"), interval="1d",
                         auto_adjust=True, progress=False, timeout=20)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]
        df.index   = pd.to_datetime(df.index)
        df["sector"] = SECTOR_MAP.get(ticker, "UNKNOWN")
        df["ticker"] = ticker
        return df
    except Exception as e:
        logger.warning(f"[{ticker}] Error descargando datos recientes: {e}")
        return None


def run_retraining():
    run_date = datetime.now().strftime("%Y-%m-%d_%H-%M")
    logger.info("=" * 60)
    logger.info(f"RE-ENTRENAMIENTO CONTINUO — {run_date}")
    logger.info(f"Device: {DEVICE}")
    logger.info("=" * 60)

    # 1. Cargar modelo actual
    model_path = MODEL_DIR / "global_lstm_titan100.pth"
    if not model_path.exists():
        logger.error("Modelo base no encontrado. Ejecuta train_global_lstm.py primero.")
        return

    model = GlobalLSTM().to(DEVICE)
    model.load_state_dict(torch.load(model_path, map_location=DEVICE, weights_only=True))
    logger.info("✓ Checkpoint actual cargado.")

    # 2. Descargar datos frescos
    logger.info("Descargando datos de los últimos 30 días...")
    all_seqs, all_labels = [], []
    refreshed = 0

    for ticker in TITAN_100:
        df = download_recent_data(ticker, days=30)
        if df is None:
            continue
        df = compute_features(df, ticker)
        if df is None or len(df) < SEQ_LEN:
            continue
        seqs, labels = build_sequences(df)
        all_seqs  += seqs
        all_labels += labels
        refreshed += 1
        time.sleep(0.3)   # Rate limiting cortés

    if not all_seqs:
        logger.error("Sin datos frescos para re-entrenamiento.")
        return

    logger.info(f"✓ {refreshed} tickers actualizados | {len(all_seqs)} secuencias nuevas")

    # 3. Fine-tuning
    X = torch.tensor(np.array(all_seqs),   dtype=torch.float32)
    y = torch.tensor(np.array(all_labels), dtype=torch.float32).unsqueeze(1)
    loader    = DataLoader(TensorDataset(X, y), batch_size=BATCH_SIZE, shuffle=True)
    criterion = nn.BCELoss()
    optimizer = optim.AdamW(model.parameters(), lr=FINE_TUNE_LR, weight_decay=1e-4)

    losses = []
    model.train()
    for epoch in range(1, FINE_TUNE_EPOCHS + 1):
        epoch_loss = 0.0
        for xb, yb in loader:
            xb, yb = xb.to(DEVICE), yb.to(DEVICE)
            optimizer.zero_grad()
            pred = model(xb)
            loss = criterion(pred, yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            epoch_loss += loss.item() * len(xb)
        epoch_loss /= len(all_seqs)
        losses.append(epoch_loss)
        logger.info(f"Fine-tune Epoch {epoch:>2}/{FINE_TUNE_EPOCHS} | Loss: {epoch_loss:.5f}")

    # 4. Guardar checkpoint versionado + sobreescribir el principal
    checkpoint_path = RETRAIN_DIR / f"global_lstm_{run_date}.pth"
    torch.save(model.state_dict(), checkpoint_path)
    torch.save(model.state_dict(), model_path)   # El servidor FastAPI cargará el nuevo
    logger.info(f"✓ Checkpoint guardado: {checkpoint_path}")
    logger.info(f"✓ Modelo principal actualizado: {model_path}")

    # 5. Informe de métricas (JSON para auditoría)
    report = {
        "run_date":          run_date,
        "tickers_refreshed": refreshed,
        "sequences_trained": len(all_seqs),
        "fine_tune_epochs":  FINE_TUNE_EPOCHS,
        "initial_loss":      round(losses[0], 6),
        "final_loss":        round(losses[-1], 6),
        "delta_loss":        round(losses[0] - losses[-1], 6),
        "device":            str(DEVICE),
    }
    report_path = LOG_DIR / f"retrain_{run_date}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info("=" * 60)
    logger.info(f"✓ Re-entrenamiento completo | Delta Loss: {report['delta_loss']:.5f}")
    logger.info(f"  Informe guardado: {report_path}")
    logger.info("=" * 60)


if __name__ == "__main__":
    run_retraining()

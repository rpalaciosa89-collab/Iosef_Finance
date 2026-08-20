"""
Validación temporal del Global LSTM (gate SP-4.2 aplicado a LSTM).
========================================================================
Entrena el LSTM global en la primera parte de la serie temporal y valida
en la parte FINAL (sin overlap, con embargo). Reporta AUC OOS.

Decision de negocio: si AUC OOS < 0.56, el LSTM queda ARCHIVADO
(promoted=false) y `get_lstm_score` devuelve None (sin senal), al igual
que el XGBoost.

Uso: cd backend && python scripts/validate_lstm_walkforward.py
"""
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.titan_universe import TITAN_100
from scripts.train_global_lstm import (
    FEATURE_COLS, SEQ_LEN, compute_features, build_sequences,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "titan_parquet"
MODEL_DIR = BASE_DIR / "models"
PROMOTION_AUC = 0.56


class GlobalLSTM(nn.Module):
    def __init__(self, hidden=64, layers=2, dropout=0.3):
        super().__init__()
        self.lstm = nn.LSTM(len(FEATURE_COLS), hidden, layers, batch_first=True, dropout=dropout)
        self.norm = nn.LayerNorm(hidden)
        self.fc = nn.Sequential(
            nn.Linear(hidden, 32), nn.ReLU(), nn.Dropout(0.2), nn.Linear(32, 1), nn.Sigmoid(),
        )

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(self.norm(out[:, -1, :]))


def load_all_sequences():
    """Retorna (secuencias, labels, fechas) concatenando todos los tickers."""
    seqs, labels, dates = [], [], []
    for ticker in TITAN_100:
        path = DATA_DIR / f"{ticker.replace('/', '_')}.parquet"
        if not path.exists():
            continue
        try:
            df = pd.read_parquet(path)
        except Exception:
            continue
        df = compute_features(df, ticker)
        if df is None:
            continue
        s, l = build_sequences(df)
        seqs.extend(s)
        labels.extend(l)
        # Fecha de cada secuencia = fecha de la ultima vela de la secuencia
        dates.extend(df.index[SEQ_LEN:].tolist())
    return np.array(seqs), np.array(labels, dtype=float), np.array(dates)


def train_model(seqs, labels, device, epochs=8):
    model = GlobalLSTM().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.BCELoss()
    X = torch.tensor(seqs, dtype=torch.float32)
    y = torch.tensor(labels, dtype=torch.float32).unsqueeze(1)

    dataset = torch.utils.data.TensorDataset(X, y)
    loader = torch.utils.data.DataLoader(dataset, batch_size=1024, shuffle=True)
    model.train()
    for epoch in range(epochs):
        total_loss = 0.0
        for bx, by in loader:
            opt.zero_grad()
            out = model(bx.to(device))
            loss = loss_fn(out, by.to(device))
            loss.backward()
            opt.step()
            total_loss += loss.item()
        if epoch % 4 == 0:
            logger.info(f"  epoch {epoch}: loss={total_loss / len(loader):.4f}")
    return model


def main():
    logger.info("Cargando secuencias de todos los tickers (esto tarda)...")
    seqs, labels, dates = load_all_sequences()
    logger.info(f"Secuencias totales: {len(seqs)} | positives: {labels.mean():.3f}")

    if len(seqs) < 5000:
        raise RuntimeError("Datos insuficientes")

    # Split temporal: 60% train (inicio), 40% valid (final), con embargo de 5 dias
    cutoff = int(len(seqs) * 0.6)
    train_seq, train_y = seqs[:cutoff], labels[:cutoff]
    valid_seq, valid_y = seqs[cutoff:], labels[cutoff:]

    # Embargo: descartar las validaciones dentro de la ventana forward del ultimo train
    last_train_date = dates[cutoff - 1]
    embargo = np.array([pd.Timestamp(d) > pd.Timestamp(last_train_date) + pd.Timedelta(days=5) for d in dates[cutoff:]])
    valid_seq, valid_y = valid_seq[embargo], valid_y[embargo]

    logger.info(f"Train: {len(train_seq)} | Valid (post embargo): {len(valid_seq)}")

    device = torch.device("cpu")
    model = train_model(train_seq, train_y, device, epochs=8)

    model.eval()
    with torch.no_grad():
        proba = model(torch.tensor(valid_seq, dtype=torch.float32)).squeeze().numpy()

    auc = roc_auc_score(valid_y, proba)
    promoted = auc >= PROMOTION_AUC
    logger.info(f"AUC OOS (walk-forward LSTM): {auc:.4f} | promoted={promoted}")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": "global_lstm_titan100",
        "method": "walk_forward_60_40_purged_5d",
        "n_train": len(train_seq),
        "n_valid": len(valid_seq),
        "auc_oos": round(auc, 4),
        "promotion_threshold": PROMOTION_AUC,
        "promoted": promoted,
    }
    out = MODEL_DIR / "lstm_walkforward_report.json"
    out.write_text(json.dumps(report, indent=2))
    logger.info(f"Reporte: {out}")

    if promoted:
        logger.info("Gate superado: LSTM puede promoverse a produccion.")
    else:
        logger.info("Gate NO superado: recomendar archivar el LSTM (get_lstm_score -> None).")


if __name__ == "__main__":
    main()
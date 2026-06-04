"""
scripts/train_global_lstm.py

Motor de entrenamiento LSTM Global — Titan 100.
- Procesa TODOS los tickers en un único modelo "Cross-Asset".
- Ventana temporal de 60 días (suficiente para swing/momentum).
- Features: [Volume_norm, LogReturn, Momentum_10, RSI, MACD_hist, Sector_embed].
- Genera gráficos de convergencia y mapa de importancia de features.

Responsable: Carlos (Quant) | Auditado por: Javier (Infra) | Sign-off: Raymond (Lead)
"""

import sys
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import matplotlib
matplotlib.use("Agg")   # Sin GUI — compatible con servidor headless
import matplotlib.pyplot as plt
import seaborn as sns

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
from config.titan_universe import TITAN_100, SECTOR_MAP

DATA_DIR   = BASE_DIR / "data" / "titan_parquet"
MODEL_DIR  = BASE_DIR / "models"
PLOT_DIR   = BASE_DIR.parent / "artifacts" / "plots"
MODEL_DIR.mkdir(exist_ok=True)
PLOT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)

# ── Hiperparámetros ──────────────────────────────────────────────────────────────
SEQ_LEN     = 60        # 60 días de memoria secuencial (Swing Multi-Timeframe)
BATCH_SIZE  = 128
EPOCHS      = 100
LR          = 1e-3
HIDDEN_SIZE = 64
NUM_LAYERS  = 2

SECTOR_ENCODE = {s: i for i, s in enumerate(set(SECTOR_MAP.values()))}  # One-hot


# ── Feature Engineering ─────────────────────────────────────────────────────────
def compute_features(df: pd.DataFrame, ticker: str) -> pd.DataFrame | None:
    df = df.copy().sort_index()
    if len(df) < SEQ_LEN + 20:
        return None

    df["log_return"]   = np.log(df["close"] / df["close"].shift(1))
    df["volatility_20"]= df["log_return"].rolling(20).std()
    df["momentum_10"]  = df["close"].pct_change(10)

    # Volume normalizado (log-vol para reducir skew extremo)
    df["volume_log"]   = np.log1p(df["volume"])
    df["volume_norm"]  = (df["volume_log"] - df["volume_log"].rolling(60).mean()) / \
                         (df["volume_log"].rolling(60).std() + 1e-9)

    # RSI 14
    delta = df["close"].diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / (loss + 1e-9)
    df["rsi_14"] = 100 - (100 / (1 + rs))

    # MACD Histogram
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    macd  = ema12 - ema26
    signal= macd.ewm(span=9, adjust=False).mean()
    df["macd_hist"] = macd - signal

    # Target: retorno positivo en T+5 (5 días forward)
    df["target"] = (df["close"].shift(-5) > df["close"]).astype(int)

    # Sector embedding (scalar int)
    sector = SECTOR_MAP.get(ticker, "MOAT")
    df["sector_id"] = SECTOR_ENCODE.get(sector, 0)

    df.dropna(inplace=True)
    return df


# ── Dataset de PyTorch ───────────────────────────────────────────────────────────
FEATURE_COLS = ["volume_norm", "log_return", "momentum_10", "rsi_14", "macd_hist"]
N_FEATURES   = len(FEATURE_COLS)

class TitanDataset(Dataset):
    def __init__(self, sequences: list, labels: list):
        self.X = torch.tensor(np.array(sequences), dtype=torch.float32)
        self.y = torch.tensor(np.array(labels),    dtype=torch.float32).unsqueeze(1)

    def __len__(self):   return len(self.y)
    def __getitem__(self, i): return self.X[i], self.y[i]


def build_sequences(df: pd.DataFrame) -> tuple[list, list]:
    seqs, labels = [], []
    arr = df[FEATURE_COLS].values
    tgt = df["target"].values
    for i in range(len(df) - SEQ_LEN):
        seqs.append(arr[i : i + SEQ_LEN])
        labels.append(tgt[i + SEQ_LEN])
    return seqs, labels


# ── Arquitectura LSTM Global ─────────────────────────────────────────────────────
class GlobalLSTM(nn.Module):
    def __init__(self):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=N_FEATURES,
            hidden_size=HIDDEN_SIZE,
            num_layers=NUM_LAYERS,
            batch_first=True,
            dropout=0.3,
        )
        self.norm = nn.LayerNorm(HIDDEN_SIZE)
        self.fc   = nn.Sequential(
            nn.Linear(HIDDEN_SIZE, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        out, _ = self.lstm(x)
        out = self.norm(out[:, -1, :])   # Último estado oculto + normalización
        return self.fc(out)


# ── Pipeline Principal ───────────────────────────────────────────────────────────
def run():
    logger.info("=" * 60)
    logger.info("GLOBAL LSTM TITAN 100 — Entrenamiento Cross-Asset")
    logger.info("=" * 60)

    all_seqs, all_labels = [], []
    loaded = 0

    for ticker in TITAN_100:
        path = DATA_DIR / f"{ticker.replace('/', '_')}.parquet"
        if not path.exists():
            logger.warning(f"[{ticker}] Sin datos locales, omitiendo.")
            continue
        df = pd.read_parquet(path)
        df = compute_features(df, ticker)
        if df is None:
            logger.warning(f"[{ticker}] Datos insuficientes tras feature engineering.")
            continue
        seqs, labels = build_sequences(df)
        all_seqs  += seqs
        all_labels+= labels
        loaded += 1
        logger.info(f"[{ticker}] {len(seqs)} secuencias cargadas.")

    logger.info(f"\nTotal tickers cargados: {loaded} | Secuencias totales: {len(all_seqs)}")
    if not all_seqs:
        logger.error("Sin datos para entrenar. Ejecuta primero download_titan_history.py")
        return

    dataset    = TitanDataset(all_seqs, all_labels)
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

    model     = GlobalLSTM()
    criterion = nn.BCELoss()
    optimizer = optim.AdamW(model.parameters(), lr=LR, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

    losses = []
    logger.info("\nIniciando entrenamiento...")
    for epoch in range(1, EPOCHS + 1):
        model.train()
        epoch_loss = 0.0
        for X_batch, y_batch in dataloader:
            optimizer.zero_grad()
            pred = model(X_batch)
            loss = criterion(pred, y_batch)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            epoch_loss += loss.item() * len(X_batch)

        epoch_loss /= len(dataset)
        scheduler.step()
        losses.append(epoch_loss)

        if epoch % 10 == 0:
            logger.info(f"Epoch {epoch:>3}/{EPOCHS} | Loss: {epoch_loss:.5f} | LR: {scheduler.get_last_lr()[0]:.6f}")

    # ── Guardar Modelo ──────────────────────────────────────────────────────────
    model_path = MODEL_DIR / "global_lstm_titan100.pth"
    torch.save(model.state_dict(), model_path)
    logger.info(f"\n✓ Modelo guardado: {model_path}")

    # ── Gráficos (Innegociable) ─────────────────────────────────────────────────
    sns.set_style("darkgrid")
    plt.figure(figsize=(12, 5))
    plt.plot(losses, color="#9B59B6", linewidth=2, label="Train Loss (BCE)")
    plt.title("Global LSTM Titan 100 — Convergencia del Aprendizaje", fontsize=14, fontweight="bold")
    plt.xlabel("Epoch"), plt.ylabel("Loss")
    plt.legend()
    plt.tight_layout()
    plot_path = PLOT_DIR / "global_lstm_convergence.png"
    plt.savefig(plot_path, dpi=150)
    plt.close()
    logger.info(f"✓ Gráfico generado: {plot_path}")


if __name__ == "__main__":
    run()

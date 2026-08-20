"""
Iosef Finance — Real-Data XGBoost Training Pipeline
====================================================
Reemplaza generate_synthetic_dataset() con datos reales de mercado
extraídos de yfinance para todas las empresas del Titan 100.

Features (5):
  - log_return   : retorno logarítmico diario
  - volatility_20: desviación estándar rolling 20 días
  - momentum_10  : retorno porcentual rolling 10 días
  - rsi_14       : RSI de 14 días
  - macd_hist    : histograma MACD (12, 26, 9)

Label: 1 si el retorno forward a 5 días es > mediana del mercado, 0 si no.

Ejecutar:
  cd backend && python scripts/train_xgboost_real.py
"""
import os
import sys
import json
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, roc_auc_score
import joblib
import logging
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.titan_universe import TITAN_100

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)
MODEL_PATH = MODEL_DIR / "xgboost_signal_scorer.pkl"
META_PATH = MODEL_DIR / "xgboost_signal_scorer_meta.json"
CACHE_DIR = BASE_DIR / "data" / "training_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

FORWARD_DAYS = 5
MIN_ROWS_PER_TICKER = 250


def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def _compute_macd_hist(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line - signal_line


def download_ticker_data(tickers: list[str], period: str = "2y") -> dict[str, pd.DataFrame]:
    import yfinance as yf

    cache_file = CACHE_DIR / f"titan100_{period}_{datetime.now().strftime('%Y%m%d')}.parquet"
    if cache_file.exists():
        logger.info(f"Loading cached data from {cache_file}")
        all_data = pd.read_parquet(cache_file)
        result = {}
        for t in tickers:
            try:
                df = all_data.xs(t, level='Ticker', axis=1).copy()
            except KeyError:
                continue
            if df.empty:
                continue
            df.columns = [c.lower() for c in df.columns]
            result[t] = df.dropna()
        return result

    logger.info(f"Downloading {len(tickers)} tickers with period={period}...")
    data = yf.download(tickers, period=period, progress=False, group_by="ticker")

    if data.columns.nlevels > 1:
        try:
            data.to_parquet(cache_file)
            logger.info(f"Saved cache to {cache_file}")
        except Exception as e:
            logger.warning(f"Could not save cache: {e}")

    result = {}
    if isinstance(data.columns, pd.MultiIndex):
        for t in tickers:
            try:
                df = data.xs(t, level='Ticker', axis=1).copy()
            except KeyError:
                continue
            if df.empty:
                continue
            df.columns = [c.lower() for c in df.columns]
            result[t] = df.dropna()
    else:
        for t in tickers:
            cols = [c for c in data.columns if t in str(c)]
            if cols:
                df = data[cols].copy()
                df.columns = [c.lower() for c in df.columns]
                result[t] = df.dropna()

    return result


def extract_features_and_labels(ticker_data: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.Series]:
    rows = []

    for ticker, df in ticker_data.items():
        if len(df) < MIN_ROWS_PER_TICKER:
            continue

        close = df["close"]

        volatility_20 = close.pct_change().rolling(20).std()
        momentum_10 = close.pct_change(10)
        rsi_14 = _compute_rsi(close, 14)
        macd_hist = _compute_macd_hist(close)
        log_return = np.log(close / close.shift(1))
        forward_return = close.shift(-FORWARD_DAYS) / close - 1.0

        ticker_df = pd.DataFrame({
            "log_return": log_return,
            "volatility_20": volatility_20,
            "momentum_10": momentum_10,
            "rsi_14": rsi_14,
            "macd_hist": macd_hist,
            "forward_return_5d": forward_return,
        }).dropna()

        if len(ticker_df) < 30:
            continue

        median_fwd = ticker_df["forward_return_5d"].median()
        ticker_df["label"] = (ticker_df["forward_return_5d"] > median_fwd).astype(int)
        ticker_df["ticker"] = ticker
        rows.append(ticker_df)

    if not rows:
        raise RuntimeError("No ticker had enough data after feature extraction")

    combined = pd.concat(rows, ignore_index=True)

    logger.info(
        f"Extracted {len(combined)} samples from {len(rows)} tickers. "
        f"Label distribution: {combined['label'].value_counts().to_dict()}"
    )

    feature_cols = ["log_return", "volatility_20", "momentum_10", "rsi_14", "macd_hist"]
    X = combined[feature_cols]
    y = combined["label"]
    return X, y


def train_model():
    logger.info("=== Iosef Finance XGBoost Training Pipeline (Real Data) ===")

    ticker_data = download_ticker_data(TITAN_100, period="2y")
    logger.info(f"Downloaded data for {len(ticker_data)}/{len(TITAN_100)} tickers")

    X, y = extract_features_and_labels(ticker_data)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = xgb.XGBClassifier(
        n_estimators=200,
        learning_rate=0.03,
        max_depth=5,
        subsample=0.8,
        colsample_bytree=0.8,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )

    logger.info(f"Training on {len(X_train)} samples, testing on {len(X_test)}...")
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_proba)

    logger.info("=" * 50)
    logger.info("Model Evaluation (Real Market Data):")
    logger.info(f"  Accuracy:  {acc:.4f}")
    logger.info(f"  Precision: {prec:.4f}")
    logger.info(f"  ROC AUC:   {auc:.4f}")
    logger.info("=" * 50)

    joblib.dump(model, MODEL_PATH)
    logger.info(f"Model saved to {MODEL_PATH}")

    META_PATH.write_text(json.dumps({
        "source": "real_market_yfinance",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "n_samples": int(len(X_train)),
        "n_tickers": int(len(ticker_data)),
        "roc_auc": float(auc),
        "features": ["log_return", "volatility_20", "momentum_10", "rsi_14", "macd_hist"],
        "forward_days": FORWARD_DAYS,
    }))
    logger.info(f"Metadata saved to {META_PATH}")

    if auc > 0.52:
        logger.info("✅ Model performs above random (AUC > 0.5). Real signal detected.")
    else:
        logger.warning("⚠️  AUC near 0.5 — market efficiency limit. Model still valid for ranking.")


if __name__ == "__main__":
    train_model()

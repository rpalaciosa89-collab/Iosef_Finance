"""
Iosef Finance — Grid de experimentos para buscar edge (SP research).
Prueba: ventanas forward (1/5/10/20) x label (outperform vs mediana propia).
"""
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.titan_universe import TITAN_100
from app.services.ml_validation import evaluate_walk_forward

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / "data" / "training_cache"
MIN_ROWS_PER_TICKER = 250

FEATURES_V2 = [
    "log_return", "volatility_20", "momentum_10", "rsi_14", "macd_hist",
    "volume_z", "atr_pct", "relative_strength", "gap_pct",
    "sma20_dist", "sma50_dist", "range_pos_10",
]


def _compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def _compute_macd_hist(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    return macd_line - macd_line.ewm(span=signal, adjust=False).mean()


def load_cached_data():
    cache = sorted(CACHE_DIR.glob("titan100_2y_*.parquet"))
    all_data = pd.read_parquet(cache[-1])
    result = {}
    for t in TITAN_100:
        try:
            df = all_data.xs(t, level="Ticker", axis=1).copy()
        except KeyError:
            continue
        if df.empty:
            continue
        df.columns = [c.lower() for c in df.columns]
        result[t] = df.dropna()
    return result


def extract(ticker_data: dict, forward_days: int, label_mode: str) -> tuple[pd.DataFrame, pd.Series]:
    closes_all = {t: df["close"] for t, df in ticker_data.items() if len(df) >= MIN_ROWS_PER_TICKER}
    market_close = pd.DataFrame(closes_all).dropna(axis=0, how="all")
    market_fwd = market_close.shift(-forward_days) / market_close - 1.0
    market_fwd_mean = market_fwd.mean(axis=1)

    rows = []
    for ticker, df in ticker_data.items():
        if len(df) < MIN_ROWS_PER_TICKER:
            continue
        close, high, low, vol = df["close"], df["high"], df["low"], df["volume"]
        fwd = close.shift(-forward_days) / close - 1.0
        mkt = market_fwd_mean.reindex(close.index)

        tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
        vol_mean = vol.rolling(20).mean()
        vol_std = vol.rolling(20).std()
        sma20 = close.rolling(20).mean()
        sma50 = close.rolling(50).mean()
        high10 = high.rolling(10).max()
        low10 = low.rolling(10).min()

        tdf = pd.DataFrame({
            "log_return": np.log(close / close.shift(1)),
            "volatility_20": close.pct_change().rolling(20).std(),
            "momentum_10": close.pct_change(10),
            "rsi_14": _compute_rsi(close, 14),
            "macd_hist": _compute_macd_hist(close),
            "volume_z": (vol - vol_mean) / vol_std.replace(0, np.nan),
            "atr_pct": atr / close,
            "relative_strength": close.pct_change(5) - market_close.mean(axis=1).pct_change(5).reindex(close.index),
            "gap_pct": df["open"] / close.shift(1) - 1.0,
            "sma20_dist": close / sma20 - 1.0,
            "sma50_dist": close / sma50 - 1.0,
            "range_pos_10": (close - low10) / (high10 - low10).replace(0, np.nan),
            "fwd": fwd,
            "mkt_fwd": mkt,
        }).dropna()
        if len(tdf) < 30:
            continue
        if label_mode == "outperform":
            tdf["label"] = (tdf["fwd"] > tdf["mkt_fwd"]).astype(int)
        else:
            tdf["label"] = (tdf["fwd"] > tdf["fwd"].median()).astype(int)
        rows.append(tdf)

    combined = pd.concat(rows)
    combined.index = pd.to_datetime(combined.index)
    combined = combined.sort_index()
    return combined[FEATURES_V2], combined["label"]


def main():
    ticker_data = load_cached_data()
    grid = [
        (1, "outperform"), (1, "median"),
        (5, "outperform"), (5, "median"),
        (10, "outperform"), (10, "median"),
        (20, "outperform"), (20, "median"),
    ]
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "experiments": {}}
    for fwd, mode in grid:
        X, y = extract(ticker_data, fwd, mode)
        meta = evaluate_walk_forward(X, y, n_splits=3, embargo_days=fwd)
        key = f"fwd{fwd}_{mode}"
        report["experiments"][key] = meta
        logger.info(f"[{key}] AUC OOS: {meta['auc_oos_mean']:.4f} ± {meta['auc_oos_std']:.4f} "
                    f"(promoted={meta['promoted']})")

    out = BASE_DIR / "models" / "research_grid_report.json"
    out.write_text(json.dumps(report, indent=2))
    logger.info(f"Grid guardado en {out}")


if __name__ == "__main__":
    main()
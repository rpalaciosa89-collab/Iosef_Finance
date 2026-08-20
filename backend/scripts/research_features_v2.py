"""
Iosef Finance — XGBoost v2: Feature Engineering Research (SP post-Ola 7)
=========================================================================
Objetivo: buscar edge REAL (AUC OOS >= 0.56) con features adicionales y un
label cross-seccional (outperform del mercado equal-weight, no la mediana
propia del ticker).

Features v2 (10):
  - log_return, volatility_20, momentum_10, rsi_14, macd_hist   (v1)
  - volume_z         : z-score del volumen 20d
  - atr_pct          : ATR(14) / close
  - relative_strength: retorno 5d del ticker - retorno 5d del mercado equal-weight
  - gap_pct          : gap overnight (open/prev_close - 1)
  - sma20_dist       : (close/sma20 - 1)
  - sma50_dist       : (close/sma50 - 1)
  - range_pos_10     : posicion del close en el rango 10d [0,1]

Label v2: 1 si forward_return_5d > forward_return_5d del mercado equal-weight.

Uso: cd backend && python scripts/research_features_v2.py
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
FORWARD_DAYS = 5
MIN_ROWS_PER_TICKER = 250

FEATURES_V1 = ["log_return", "volatility_20", "momentum_10", "rsi_14", "macd_hist"]
FEATURES_V2 = [
    "log_return", "volatility_20", "momentum_10", "rsi_14", "macd_hist",
    "volume_z", "atr_pct", "relative_strength", "gap_pct",
    "sma20_dist", "sma50_dist", "range_pos_10",
]


def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def _compute_macd_hist(series: pd.Series, fast=12, slow=26, signal=9) -> pd.Series:
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    return macd_line - macd_line.ewm(span=signal, adjust=False).mean()


def load_cached_data() -> dict[str, pd.DataFrame]:
    cache = sorted(CACHE_DIR.glob("titan100_2y_*.parquet"))
    if not cache:
        raise RuntimeError("No hay cache de datos; ejecutar download primero")
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
    logger.info(f"Cargados {len(result)}/{len(TITAN_100)} tickers desde {cache[-1].name}")
    return result


def extract_v2(ticker_data: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.Series]:
    closes_all = {}
    dfs = {}

    for ticker, df in ticker_data.items():
        if len(df) < MIN_ROWS_PER_TICKER:
            continue
        closes_all[ticker] = df["close"]
        dfs[ticker] = df

    # Mercado equal-weight (retorno medio diario cross-seccional)
    market_close = pd.DataFrame(closes_all).dropna(axis=0, how="all")
    market_fwd = market_close.shift(-FORWARD_DAYS) / market_close - 1.0
    market_fwd_mean = market_fwd.mean(axis=1)

    rows = []
    for ticker, df in dfs.items():
        close = df["close"]
        high, low, vol = df["high"], df["low"], df["volume"]

        fwd = close.shift(-FORWARD_DAYS) / close - 1.0
        mkt = market_fwd_mean.reindex(close.index)

        rsi_14 = _compute_rsi(close, 14)
        macd = _compute_macd_hist(close)
        log_ret = np.log(close / close.shift(1))

        tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1 / 14, adjust=False).mean()

        vol_mean = vol.rolling(20).mean()
        vol_std = vol.rolling(20).std()

        sma20 = close.rolling(20).mean()
        sma50 = close.rolling(50).mean()
        high10 = high.rolling(10).max()
        low10 = low.rolling(10).min()

        mkt_ret_5d = market_close[ticker].pct_change(5)  # no usado; ver abajo
        rel_strength = close.pct_change(5) - market_close.mean(axis=1).pct_change(5).reindex(close.index)

        ticker_df = pd.DataFrame({
            "log_return": log_ret,
            "volatility_20": close.pct_change().rolling(20).std(),
            "momentum_10": close.pct_change(10),
            "rsi_14": rsi_14,
            "macd_hist": macd,
            "volume_z": (vol - vol_mean) / vol_std.replace(0, np.nan),
            "atr_pct": atr / close,
            "relative_strength": rel_strength,
            "gap_pct": df["open"] / close.shift(1) - 1.0,
            "sma20_dist": close / sma20 - 1.0,
            "sma50_dist": close / sma50 - 1.0,
            "range_pos_10": (close - low10) / (high10 - low10).replace(0, np.nan),
            "fwd_5d": fwd,
            "mkt_fwd_5d": mkt,
        }).dropna()

        if len(ticker_df) < 30:
            continue

        # Label v2: outperform del mercado equal-weight
        ticker_df["label"] = (ticker_df["fwd_5d"] > ticker_df["mkt_fwd_5d"]).astype(int)
        rows.append(ticker_df)

    if not rows:
        raise RuntimeError("No data extracted")

    combined = pd.concat(rows)
    combined.index = pd.to_datetime(combined.index)
    combined = combined.sort_index()

    logger.info(
        f"v2: {len(combined)} muestras, {combined['label'].value_counts().to_dict()} "
        f"({len(rows)} tickers)"
    )
    return combined[FEATURES_V2], combined["label"]


def main():
    ticker_data = load_cached_data()
    X, y = extract_v2(ticker_data)

    # Comparativa v1 vs v2 con el MISMO walk-forward
    results = {}
    for name, feats in [("v1", FEATURES_V1), ("v2", FEATURES_V2)]:
        meta = evaluate_walk_forward(X[feats], y, n_splits=3, embargo_days=FORWARD_DAYS)
        results[name] = meta
        logger.info(f"[{name}] AUC OOS: {meta['auc_oos_mean']:.4f} ± {meta['auc_oos_std']:.4f} "
                    f"(promoted={meta['promoted']})")

    # Guardar reporte
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "label": "outperform_equal_weight_market",
        "features": {"v1": FEATURES_V1, "v2": FEATURES_V2},
        "results": results,
    }
    out = BASE_DIR / "models" / "research_v2_report.json"
    out.write_text(json.dumps(report, indent=2))
    logger.info(f"Reporte guardado en {out}")


if __name__ == "__main__":
    main()
"""
Backtest del ranking heuristico del screener (recomendacion #4 del reporte de edge).
==================================================================================
Pregunta: ¿seleccionar los top-N tickers por score heuristico del screener
(SP-4.3) genera retorno superior al mercado equal-weight a 5 dias?

Diseno:
- Cada semana (5 dias), se calcula el score heuristico de TODOS los tickers
  con los datos hasta t (sin lookahead).
- Se forma una cartera equal-weight con los top-N.
- Se mide el retorno de la cartera a 5 dias vs el mercado equal-weight.
- Metricas: hit rate (cartera > mercado), retorno medio de exceso, Information
  Ratio, y significancia (t-stat del exceso diario).
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
from app.services.scoring_engine import heuristic_score

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / "data" / "training_cache"
MIN_HISTORY = 210  # velas minimas para calcular sma200/sma50


def _rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def load_data():
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


def compute_scores_at(ticker_data: dict, date: pd.Timestamp) -> dict[str, float]:
    """Score heuristico de cada ticker usando datos hasta `date` (sin lookahead)."""
    scores = {}
    for ticker, df in ticker_data.items():
        hist = df.loc[:date]
        if len(hist) < MIN_HISTORY:
            continue
        close = hist["close"]
        latest = float(close.iloc[-1])
        if latest <= 0:
            continue
        sma20 = float(close.rolling(20).mean().iloc[-1])
        sma50 = float(close.rolling(50).mean().iloc[-1])
        sma200 = float(close.rolling(200).mean().iloc[-1])
        rsi = float(_rsi(close).iloc[-1])
        momentum_1m = (latest / float(close.iloc[-20]) - 1) * 100 if len(close) > 20 else 0.0
        rel_volume = float(hist["volume"].iloc[-1] / hist["volume"].rolling(20).mean().iloc[-1]) if len(hist) > 20 else 1.0
        pct_change = (latest / float(close.iloc[-2]) - 1) * 100 if len(close) > 1 else 0.0

        res = heuristic_score({
            "close": latest, "sma20": sma20, "sma50": sma50, "sma200": sma200,
            "rsi": rsi, "momentum_1m": momentum_1m, "rel_volume": rel_volume,
            "pct_change": pct_change,
        })
        scores[ticker] = res["value"]
    return scores


def main():
    ticker_data = load_data()
    closes_all = {t: df["close"] for t, df in ticker_data.items()}
    prices = pd.DataFrame(closes_all).dropna(axis=0, how="all").ffill()

    dates = list(prices.index)
    top_n = 10
    holding = 5
    rebal = holding
    excess_returns = []
    portfolio_log = []

    for i in range(0, len(dates) - holding, rebal):
        rebal_date = dates[i]
        future_date = dates[i + holding]

        scores = compute_scores_at(ticker_data, rebal_date)
        if len(scores) < 30:
            continue
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        top = [t for t, _ in ranked[:top_n]]

        # Retorno de la cartera top-N y del mercado equal-weight
        rets = prices.loc[future_date] / prices.loc[rebal_date] - 1.0
        port_ret = rets[top].mean()
        mkt_ret = rets.mean()
        excess = port_ret - mkt_ret
        excess_returns.append(excess)
        portfolio_log.append({
            "rebal_date": str(rebal_date.date()),
            "top_score_min": ranked[top_n - 1][1] if len(ranked) >= top_n else None,
            "portfolio_return": round(float(port_ret), 5),
            "market_return": round(float(mkt_ret), 5),
            "excess": round(float(excess), 5),
        })

    excess = np.array(excess_returns)
    n = len(excess)
    mean_excess = float(excess.mean())
    std_excess = float(excess.std(ddof=1)) if n > 1 else 0.0
    t_stat = float(mean_excess / (std_excess / np.sqrt(n))) if std_excess > 0 else 0.0
    hit_rate = float((excess > 0).mean())
    total_excess_pct = float((1 + excess).prod() - 1) * 100

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "design": {
            "top_n": top_n, "holding_days": holding, "rebalance_days": rebal,
            "score": "heuristic_screener_v1",
            "universe": "Titan 100",
        },
        "results": {
            "periods": n,
            "mean_excess_per_period": round(mean_excess * 100, 3),
            "hit_rate_excess": round(hit_rate, 4),
            "t_stat_excess": round(t_stat, 3),
            "cumulative_excess_pct": round(total_excess_pct, 2),
            "verdict": "alfa positivo" if t_stat > 2.0 else
                       ("sin evidencia" if abs(t_stat) <= 2.0 else "alfa negativo"),
        },
        "log": portfolio_log,
    }

    out = BASE_DIR / "models" / "research_screener_ranking.json"
    out.write_text(json.dumps(report, indent=2))
    logger.info(f"Periodos: {n} | Exceso medio: {mean_excess*100:.3f}%/periodo | "
                f"Hit rate: {hit_rate:.1%} | t-stat: {t_stat:.2f} | "
                f"Exceso acumulado: {total_excess_pct:.2f}%")
    logger.info(f"Reporte: {out}")


if __name__ == "__main__":
    main()
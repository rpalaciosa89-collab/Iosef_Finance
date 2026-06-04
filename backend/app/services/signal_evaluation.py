import numpy as np
import pandas as pd
import yfinance as yf
import logging

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
MIN_TICKER_SAMPLE = 3          # Minimum occurrences for a ticker to appear in top/worst
MIN_TICKER_CONFIDENT = 5       # Minimum for a ticker to appear without warning
MIN_SIGNAL_DISPLAY = 10        # Minimum for a signal to generate insights
SAMPLE_SUFFICIENT = 40         # >= this → "sufficient"
SAMPLE_LIMITED_LOW = 10        # >= this → "limited"
# < SAMPLE_LIMITED_LOW → "insufficient"


def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def _sample_quality(count: int) -> str:
    """Classify sample size quality."""
    if count >= SAMPLE_SUFFICIENT:
        return "sufficient"
    elif count >= SAMPLE_LIMITED_LOW:
        return "limited"
    return "insufficient"


def _ticker_composite_score(win_rate: float, avg_return: float, count: int) -> float:
    """
    Composite score for ranking tickers, weighting:
    - win_rate (0-1): 40%
    - avg_return (normalized): 30%
    - count (log-scaled): 30%
    Avoids a ticker with high win rate but tiny sample or negative returns dominating.
    """
    wr_component = win_rate * 0.40
    # Normalize avg_return: cap at ±10% to avoid outlier dominance
    capped_return = max(-10.0, min(10.0, avg_return))
    ret_component = ((capped_return + 10.0) / 20.0) * 0.30
    # Log-scale count: log2(count) / log2(100) capped at 1.0
    count_component = min(1.0, np.log2(max(1, count)) / np.log2(100)) * 0.30
    return wr_component + ret_component + count_component


def generate_insight(name: str, stats: dict) -> str:
    """Generate a strictly descriptive, data-driven insight. No marketing, no recommendations."""
    if not stats or stats["total_signals"] < MIN_SIGNAL_DISPLAY:
        return "Datos insuficientes para generar una conclusión estadística fiable."

    parts = []
    total = stats["total_signals"]
    quality = stats["sample_quality"]
    wr5 = stats["win_rate_5d"] * 100
    avg5 = stats["avg_return_5d"]

    # 1. Core stat
    parts.append(f"Win rate del {wr5:.0f}% sobre {total} ocurrencias ({quality}).")

    # 2. PnL direction
    if avg5 > 0:
        parts.append(f"Retorno medio a 5 días: +{avg5:.1f}%.")
    elif avg5 < 0:
        parts.append(f"Retorno medio a 5 días: {avg5:.1f}%.")
    else:
        parts.append("Retorno medio a 5 días: 0.0%.")

    # 3. Context comparison
    ctx = stats.get("context", {})
    bull_ctx = ctx.get("bullish", {})
    bear_ctx = ctx.get("bearish", {})

    if bull_ctx.get("count", 0) >= 5 and bear_ctx.get("count", 0) >= 5:
        bull_wr = bull_ctx["win_rate"] * 100
        bear_wr = bear_ctx["win_rate"] * 100
        diff = abs(bull_wr - bear_wr)
        if diff >= 8:
            if bear_wr > bull_wr:
                parts.append(f"Rendimiento superior en contexto bearish ({bear_wr:.0f}%) vs bullish ({bull_wr:.0f}%).")
            else:
                parts.append(f"Rendimiento superior en contexto bullish ({bull_wr:.0f}%) vs bearish ({bear_wr:.0f}%).")
        else:
            parts.append(f"Rendimiento similar en ambos contextos (bullish {bull_wr:.0f}%, bearish {bear_wr:.0f}%).")

    # 4. Top/worst ticker mention
    top = stats.get("top_tickers", [])
    worst = stats.get("worst_tickers", [])
    if top:
        top_names = ", ".join(t["ticker"] for t in top[:3])
        parts.append(f"Mejor comportamiento en: {top_names}.")
    if worst:
        worst_names = ", ".join(t["ticker"] for t in worst[:2])
        parts.append(f"Peor comportamiento en: {worst_names}.")

    return " ".join(parts)


def evaluate_signals(tickers: list[str], period: str = "2y") -> dict:
    """
    Signal Intelligence Lab — evaluates historical signal probabilities
    with per-ticker breakdown, per-context desglose, and composite rankings.
    """
    # 1. Fetch data
    data = yf.download(tickers, period=period, progress=False)
    if "Close" not in data:
        return {"universe": {"tickers": 0, "period": period}, "signals": {}}

    closes = data["Close"]
    volumes = data["Volume"]

    # Handle single-ticker edge case
    if isinstance(closes, pd.Series):
        closes = closes.to_frame(name=tickers[0])
        volumes = volumes.to_frame(name=tickers[0])

    universe_size = len(closes.columns)

    # 2. Indicators
    sma50 = closes.rolling(50).mean()
    sma200 = closes.rolling(200).mean()
    avg_vol_20 = volumes.rolling(20).mean()
    rsi = closes.apply(calc_rsi)
    pct_change = closes.pct_change() * 100

    prev_close = closes.shift(1)
    prev_sma50 = sma50.shift(1)
    prev_sma200 = sma200.shift(1)

    # 3. Market Context (breadth-based)
    stocks_above_sma50 = (closes > sma50).sum(axis=1)
    total_stocks = closes.notna().sum(axis=1)
    breadth = stocks_above_sma50 / total_stocks

    bullish_days = breadth > 0.6
    bearish_days = breadth < 0.4
    neutral_days = ~bullish_days & ~bearish_days

    # Expand context masks to match closes shape
    def expand_mask(day_mask):
        m = pd.DataFrame(index=closes.index, columns=closes.columns)
        for col in m.columns:
            m[col] = day_mask
        return m.astype(bool)

    bullish_mask = expand_mask(bullish_days)
    bearish_mask = expand_mask(bearish_days)
    neutral_mask = expand_mask(neutral_days)

    # 4. Signal Masks (Edge-triggered for de-duplication)
    masks = {}

    masks["breakout_up"] = (prev_close < prev_sma50) & (closes > sma50)
    masks["breakdown_down"] = (prev_close > prev_sma50) & (closes < sma50)
    masks["ma_breakout_signal"] = masks["breakout_up"] | ((prev_close < prev_sma200) & (closes > sma200))

    # Volume spike
    masks["high_volume"] = volumes > (2.0 * avg_vol_20)

    # RSI
    is_overbought = rsi > 70
    masks["overbought"] = is_overbought & (~is_overbought.shift(1).fillna(False))
    is_oversold = rsi < 30
    masks["oversold"] = is_oversold & (~is_oversold.shift(1).fillna(False))

    # Momentum Shift
    masks["momentum_shift_up"] = pct_change > 3.0
    masks["momentum_shift_down"] = pct_change < -3.0

    # Composite Signals
    masks["breakout_vol_1_5"] = masks["breakout_up"] & (volumes > (1.5 * avg_vol_20))
    masks["breakout_bullish"] = masks["breakout_up"] & bullish_mask
    masks["high_vol_mom_2"] = masks["high_volume"] & (pct_change > 2.0)
    masks["oversold_bullish"] = masks["oversold"] & bullish_mask

    # 5. Forward Returns
    ret_1d = closes.shift(-1) / closes - 1
    ret_5d = closes.shift(-5) / closes - 1
    ret_20d = closes.shift(-20) / closes - 1

    # 6. Evaluation Function (enriched)
    def eval_mask(mask: pd.DataFrame) -> dict:
        total = int(mask.sum().sum())
        if total == 0:
            return None

        # ── Global metrics ────────────────────────────────────────────────
        r1 = ret_1d[mask].values
        r5 = ret_5d[mask].values
        r20 = ret_20d[mask].values

        r1 = r1[~np.isnan(r1)]
        r5 = r5[~np.isnan(r5)]
        r20 = r20[~np.isnan(r20)]

        wr1 = float((r1 > 0).mean()) if len(r1) > 0 else 0
        wr5 = float((r5 > 0).mean()) if len(r5) > 0 else 0
        wr20 = float((r20 > 0).mean()) if len(r20) > 0 else 0

        # ── Per-context breakdown ─────────────────────────────────────────
        context_data = {}
        for ctx_name, ctx_mask in [("bullish", bullish_mask), ("bearish", bearish_mask), ("neutral", neutral_mask)]:
            combined = mask & ctx_mask
            ctx_count = int(combined.sum().sum())
            if ctx_count > 0:
                ctx_r5 = ret_5d[combined].values
                ctx_r5 = ctx_r5[~np.isnan(ctx_r5)]
                ctx_wr = float((ctx_r5 > 0).mean()) if len(ctx_r5) > 0 else 0
                ctx_avg = float(np.mean(ctx_r5) * 100) if len(ctx_r5) > 0 else 0
                context_data[ctx_name] = {
                    "win_rate": round(ctx_wr, 4),
                    "avg_return": round(ctx_avg, 2),
                    "count": ctx_count
                }

        # Determine best/worst context (by win_rate, min 5 samples)
        valid_contexts = {k: v for k, v in context_data.items() if v["count"] >= 5}
        best_context = max(valid_contexts, key=lambda k: valid_contexts[k]["win_rate"]) if valid_contexts else None
        worst_context = min(valid_contexts, key=lambda k: valid_contexts[k]["win_rate"]) if valid_contexts else None

        # ── Per-ticker breakdown ──────────────────────────────────────────
        ticker_stats = []
        for col in mask.columns:
            col_mask = mask[col]
            col_count = int(col_mask.sum())
            if col_count >= MIN_TICKER_SAMPLE:
                col_r5 = ret_5d.loc[col_mask, col].dropna().values
                if len(col_r5) > 0:
                    col_wr = float((col_r5 > 0).mean())
                    col_avg = float(np.mean(col_r5) * 100)
                    composite = _ticker_composite_score(col_wr, col_avg, col_count)
                    ticker_stats.append({
                        "ticker": col,
                        "win_rate": round(col_wr, 4),
                        "avg_return": round(col_avg, 2),
                        "count": col_count,
                        "sample_warning": col_count < MIN_TICKER_CONFIDENT,
                        "composite_score": round(composite, 4)
                    })

        # Sort by composite score
        ticker_stats.sort(key=lambda x: x["composite_score"], reverse=True)
        top_tickers = ticker_stats[:5]
        worst_tickers = sorted(ticker_stats, key=lambda x: x["composite_score"])[:3] if len(ticker_stats) > 3 else []

        # ── Confidence / sample quality ───────────────────────────────────
        quality = _sample_quality(total)

        if total >= 100 and wr5 > 0.60:
            confidence = "high_confidence"
        elif total >= SAMPLE_SUFFICIENT:
            confidence = "medium_confidence"
        else:
            confidence = "low_confidence"

        return {
            "total_signals": total,
            "sample_quality": quality,
            "win_rate_1d": round(wr1, 4),
            "win_rate_5d": round(wr5, 4),
            "win_rate_20d": round(wr20, 4),
            "avg_return_1d": round(float(np.mean(r1) * 100), 2) if len(r1) else 0,
            "avg_return_5d": round(float(np.mean(r5) * 100), 2) if len(r5) else 0,
            "avg_return_20d": round(float(np.mean(r20) * 100), 2) if len(r20) else 0,
            "median_return_5d": round(float(np.median(r5) * 100), 2) if len(r5) else 0,
            "context": context_data,
            "best_context": best_context,
            "worst_context": worst_context,
            "top_tickers": top_tickers,
            "worst_tickers": worst_tickers,
            "confidence": confidence
        }

    # 7. Build Results
    signals = {}
    for name, m in masks.items():
        stats = eval_mask(m)
        if stats:
            stats["insight"] = generate_insight(name, stats)
            signals[name] = stats

    return {
        "universe": {
            "tickers": universe_size,
            "period": period,
            "min_ticker_sample": MIN_TICKER_SAMPLE,
            "min_signal_display": MIN_SIGNAL_DISPLAY,
            "sample_sufficient_threshold": SAMPLE_SUFFICIENT,
        },
        "signals": signals
    }


if __name__ == "__main__":
    import json
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
    print("Evaluating signals for test universe...")
    res = evaluate_signals(tickers, "2y")
    print(json.dumps(res, indent=2))

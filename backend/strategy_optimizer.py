"""
Iosef Finance — Strategy Optimizer
====================================
Motor de análisis estadístico de señales en 6 fases.

Anti-lookahead guarantee:
  - Señales generadas con datos hasta t (inclusive)
  - Retornos medidos con cierre de t+N (futuro, solo para evaluación)
  - Deduplicación: ventana de 3 días por ticker para evitar señales repetidas
"""

import numpy as np
import pandas as pd
import yfinance as yf
from typing import Optional

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def _confidence_label(total: int, win_rate_5d: float) -> str:
    if total < 15:
        return "insufficient_sample"
    if total >= 100 and win_rate_5d >= 0.60:
        return "high"
    if total >= 40:
        return "medium"
    return "low"


def _deduplicate_mask(mask: pd.DataFrame, window: int = 3) -> pd.DataFrame:
    """
    Per-ticker deduplication: if a signal fired within the last `window`
    trading days for the same ticker, suppress it to avoid double-counting
    the same event.
    """
    result = mask.copy().astype(bool)
    for col in mask.columns:
        vals = mask[col].fillna(False).astype(bool).values
        out = vals.copy()
        last_i = -9999
        for i, v in enumerate(vals):
            if v:
                if (i - last_i) <= window:
                    out[i] = False
                else:
                    last_i = i
        result[col] = pd.Series(out, index=mask.index)
    return result


def _safe_arr(ret_df: pd.DataFrame, mask_df: pd.DataFrame) -> np.ndarray:
    """Extract non-NaN return values where mask is True."""
    vals = ret_df.where(mask_df).values.flatten()
    return vals[~np.isnan(vals)]


# ──────────────────────────────────────────────────────────────────────────────
# Core metrics computation
# ──────────────────────────────────────────────────────────────────────────────

def _compute_metrics(
    mask: pd.DataFrame,
    closes: pd.DataFrame,
    ret_1d: pd.DataFrame,
    ret_5d: pd.DataFrame,
    ret_10d: pd.DataFrame,
    ret_20d: pd.DataFrame,
    bullish_mask: pd.DataFrame,
    bearish_mask: pd.DataFrame,
    deduplicate: bool = True,
) -> Optional[dict]:
    """
    Compute full statistical metrics for a signal mask.

    Parameters
    ----------
    mask : bool DataFrame — True where signal fired (on day t)
    closes : price DataFrame
    ret_Nd : forward return DataFrames (t → t+N), pre-computed
    bullish/bearish_mask : market regime DataFrames
    """
    if deduplicate:
        mask = _deduplicate_mask(mask, window=3)

    mask = mask.fillna(False).astype(bool)
    total = int(mask.sum().sum())
    if total == 0:
        return None

    r1  = _safe_arr(ret_1d,  mask)
    r5  = _safe_arr(ret_5d,  mask)
    r10 = _safe_arr(ret_10d, mask)
    r20 = _safe_arr(ret_20d, mask)

    # Context breakdown
    bull_mask = mask & bullish_mask.fillna(False).astype(bool)
    bear_mask = mask & bearish_mask.fillna(False).astype(bool)
    neut_mask = mask & ~bullish_mask.fillna(False).astype(bool) & ~bearish_mask.fillna(False).astype(bool)

    r5_bull = _safe_arr(ret_5d, bull_mask)
    r5_bear = _safe_arr(ret_5d, bear_mask)
    r5_neut = _safe_arr(ret_5d, neut_mask)

    def wr(arr):
        return round(float((arr > 0).mean()), 4) if len(arr) > 0 else None

    def avg(arr):
        return round(float(np.mean(arr)), 3) if len(arr) > 0 else None

    def med(arr):
        return round(float(np.median(arr)), 3) if len(arr) > 0 else None

    def expectancy(arr):
        """(win_rate × avg_win) − (loss_rate × avg_loss)  in %"""
        if len(arr) < 5:
            return None
        wins   = arr[arr > 0]
        losses = arr[arr <= 0]
        if len(wins) == 0 or len(losses) == 0:
            return None
        wr_    = len(wins) / len(arr)
        lr_    = 1 - wr_
        return round(float(wr_ * np.mean(wins) - lr_ * abs(np.mean(losses))), 3)

    def profit_factor(arr):
        """Sum of gains / abs(sum of losses)"""
        if len(arr) < 5:
            return None
        wins   = arr[arr > 0]
        losses = arr[arr <= 0]
        if len(losses) == 0 or abs(losses.sum()) < 1e-6:
            return None
        return round(float(wins.sum() / abs(losses.sum())), 3)

    def max_dd(arr):
        """Worst individual outcome in this horizon (approximate drawdown)."""
        if len(arr) == 0:
            return None
        return round(float(np.min(arr)), 3)

    wr5 = wr(r5)
    conf = _confidence_label(total, wr5 if wr5 else 0.0)

    return {
        "total_signals":    total,
        "win_rate_1d":      wr(r1),
        "win_rate_5d":      wr5,
        "win_rate_10d":     wr(r10),
        "win_rate_20d":     wr(r20),
        "avg_return_1d":    avg(r1),
        "avg_return_5d":    avg(r5),
        "avg_return_10d":   avg(r10),
        "avg_return_20d":   avg(r20),
        "median_return_5d": med(r5),
        "expectancy_5d":    expectancy(r5),
        "profit_factor":    profit_factor(r5),
        "max_drawdown_5d":  max_dd(r5),
        "confidence":       conf,
        "context": {
            "bullish": {
                "total":          int(bull_mask.sum().sum()),
                "win_rate_5d":    wr(r5_bull),
                "avg_return_5d":  avg(r5_bull),
            },
            "bearish": {
                "total":          int(bear_mask.sum().sum()),
                "win_rate_5d":    wr(r5_bear),
                "avg_return_5d":  avg(r5_bear),
            },
            "neutral": {
                "total":          int(neut_mask.sum().sum()),
                "win_rate_5d":    wr(r5_neut),
                "avg_return_5d":  avg(r5_neut),
            },
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# Exit Rule Backtest
# ──────────────────────────────────────────────────────────────────────────────

def _backtest_exit_rule(
    entry_mask: pd.DataFrame,
    closes: pd.DataFrame,
    stop_loss: float = -0.05,
    take_profit: float = 0.10,
    max_days: int = 5,
    trailing: bool = False,
    partial_exit: bool = False,
) -> dict:
    """
    Simulate per-signal entries and apply a defined exit rule.
    Returns trade-level statistics.

    Model A: Fixed SL/TP, max 5d
    Model B: Fixed SL/TP, max 10d
    Model C: Fixed SL, trailing stop (no fixed TP), max 20d
    Model D: 50% at +5%, rest at SL or max 10d
    """
    trades: list[float] = []

    price_idx = {col: closes[col].values for col in closes.columns}
    date_index = list(closes.index)
    n = len(date_index)

    for col in closes.columns:
        if col not in entry_mask.columns:
            continue

        prices = price_idx[col]
        signals = entry_mask[col].fillna(False).astype(bool).values

        in_pos       = False
        entry_i      = 0
        entry_price  = 0.0
        hwm          = 0.0   # high-water mark for trailing stop
        partial_done = False

        for i in range(n):
            price = prices[i]
            if np.isnan(price):
                continue

            if in_pos:
                days_held = i - entry_i
                ret = (price - entry_price) / entry_price

                exit_now = False
                trade_ret = ret

                if trailing:
                    # Model C: trailing stop 5% below high-water mark
                    hwm = max(hwm, price)
                    trailing_stop_price = hwm * (1 + stop_loss)  # stop_loss is negative
                    if price <= trailing_stop_price or days_held >= max_days:
                        trade_ret = ret
                        exit_now = True

                elif partial_exit:
                    # Model D: take 50% at +5%, let rest run to max_days or SL
                    if not partial_done and ret >= 0.05:
                        partial_done = True
                    if days_held >= max_days or ret <= stop_loss:
                        if partial_done:
                            # Blended: 50% closed at +5%, 50% closed now
                            trade_ret = 0.5 * 0.05 + 0.5 * ret
                        else:
                            trade_ret = ret
                        exit_now = True

                else:
                    # Models A & B: fixed SL / TP / max_days
                    if ret >= take_profit or ret <= stop_loss or days_held >= max_days:
                        trade_ret = ret
                        exit_now = True

                if exit_now:
                    trades.append(trade_ret * 100)
                    in_pos = False
                    partial_done = False

            # Entry (only if not already in position)
            if not in_pos and signals[i] and not np.isnan(price):
                in_pos       = True
                entry_i      = i
                entry_price  = price
                hwm          = price
                partial_done = False

    if not trades:
        return {"total_trades": 0, "win_rate": None, "avg_return": None,
                "expectancy": None, "profit_factor": None, "max_drawdown": None}

    arr    = np.array(trades)
    wins   = arr[arr > 0]
    losses = arr[arr <= 0]

    wr      = round(float(len(wins) / len(arr)), 4) if len(arr) > 0 else None
    avg_ret = round(float(np.mean(arr)), 3)

    exp = None
    if len(wins) > 0 and len(losses) > 0:
        exp = round(float(
            (len(wins) / len(arr)) * np.mean(wins) -
            (len(losses) / len(arr)) * abs(np.mean(losses))
        ), 3)

    pf = None
    if len(losses) > 0 and abs(losses.sum()) > 1e-6:
        pf = round(float(wins.sum() / abs(losses.sum())), 3)

    return {
        "total_trades":  len(arr),
        "win_rate":      wr,
        "avg_return":    avg_ret,
        "expectancy":    exp,
        "profit_factor": pf,
        "max_drawdown":  round(float(np.min(arr)), 3) if len(arr) > 0 else None,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Ranking
# ──────────────────────────────────────────────────────────────────────────────

def _generate_ranking(individual: dict, combined: dict) -> dict:
    """
    Score every signal/combination and split into top / low_quality lists.

    Score formula (100 pts max):
      40% → win_rate_5d
      30% → expectancy_5d (normalized to 5%)
      20% → profit_factor (normalized to 3.0)
      10% → confidence bonus (high=10, medium=5, low=0)
    """
    all_signals = {}
    for k, v in individual.items():
        if v and v.get("confidence") != "insufficient_sample":
            all_signals[k] = {"stats": v, "kind": "individual"}
    for k, v in combined.items():
        if v and v.get("confidence") != "insufficient_sample":
            all_signals[k] = {"stats": v, "kind": "combined"}

    scores = {}
    for name, entry in all_signals.items():
        s = entry["stats"]
        wr  = s.get("win_rate_5d")  or 0.0
        exp = s.get("expectancy_5d") or 0.0
        pf  = s.get("profit_factor") or 0.0
        conf = s.get("confidence", "low")

        score = (
            wr  * 40 +
            min(max(exp, 0) / 5.0, 1.0) * 30 +
            min(max(pf,  0) / 3.0, 1.0) * 20 +
            {"high": 10, "medium": 5, "low": 2}.get(conf, 0)
        )

        scores[name] = {
            "score":          round(score, 2),
            "kind":           entry["kind"],
            "win_rate_5d":    wr,
            "expectancy_5d":  exp,
            "profit_factor":  pf,
            "confidence":     conf,
            "total_signals":  s.get("total_signals", 0),
        }

    ranked = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)
    top       = [{"name": k, **v} for k, v in ranked[:5]]
    low_quality = [{"name": k, **v} for k, v in ranked if v["score"] < 15]

    return {"top": top, "low_quality": low_quality}


# ──────────────────────────────────────────────────────────────────────────────
# Natural language summary
# ──────────────────────────────────────────────────────────────────────────────

def _generate_summary(
    individual: dict,
    combined: dict,
    exit_rules: dict,
    ranking: dict,
) -> str:
    lines = []

    # Best individual signal by expectancy
    ind_valid = [(k, v) for k, v in individual.items()
                 if v and v.get("expectancy_5d") is not None]
    if ind_valid:
        best_k, best_v = max(ind_valid, key=lambda x: x[1]["expectancy_5d"])
        wr5  = (best_v.get("win_rate_5d") or 0) * 100
        exp5 = best_v.get("expectancy_5d") or 0
        lines.append(
            f"La señal individual con mayor expectativa es '{best_k.replace('_', ' ')}' "
            f"con un win rate del {wr5:.1f}% y expectativa de {exp5:.2f}% a 5 días."
        )

    # Best improvement from combined vs individual
    best_delta_name, best_delta_val = None, 0.0
    for k, v in combined.items():
        if not v:
            continue
        delta = v.get("delta_win_rate_5d") or 0.0
        if delta > best_delta_val:
            best_delta_val = delta
            best_delta_name = k
            base_wr = (individual.get(v.get("base_signal") or "", {}) or {}).get("win_rate_5d", 0) * 100
            new_wr  = (v.get("win_rate_5d") or 0) * 100

    if best_delta_name and best_delta_val > 0.02:
        lines.append(
            f"La combinación '{best_delta_name.replace('__', ' + ').replace('_', ' ')}' "
            f"mejora el win rate en {best_delta_val*100:.1f} puntos porcentuales respecto a la señal base."
        )

    # Best exit model
    best_model_name, best_model_exp = None, -999.0
    for model, stats in exit_rules.items():
        exp = stats.get("expectancy")
        if exp is not None and exp > best_model_exp:
            best_model_exp  = exp
            best_model_name = model

    if best_model_name:
        label = exit_rules[best_model_name].get("label", best_model_name)
        lines.append(
            f"El modelo de salida con mejor expectativa es {best_model_name} "
            f"('{label}', expectativa: {best_model_exp:.2f}%)."
        )

    # Market context advice
    breakout_ind = individual.get("breakout_up") or {}
    ctx = breakout_ind.get("context", {})
    bull_wr = (ctx.get("bullish", {}).get("win_rate_5d") or 0) * 100
    bear_wr = (ctx.get("bearish", {}).get("win_rate_5d") or 0) * 100
    if bull_wr and bear_wr and (bull_wr - bear_wr) > 8:
        lines.append(
            f"Los breakouts muestran mayor efectividad en contexto alcista ({bull_wr:.0f}% win rate) "
            f"vs contexto bajista ({bear_wr:.0f}% win rate) — se recomienda filtrar por breadth de mercado."
        )

    lines.append(
        "Los breakouts sin confirmación de volumen presentan mayor tasa de falsos positivos. "
        "Siempre se recomienda filtrar con volumen relativo ≥ 1.5x."
    )

    return " ".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────────────────────────

def run_strategy_optimization(tickers: list, period: str = "2y") -> dict:
    """
    Full 6-phase signal optimization pipeline.

    Returns a structured dict with:
      individual_signals, combined_signals, exit_rules, ranking, summary,
      market_context
    """
    print(f"[optimizer] Downloading {len(tickers)} tickers, period={period}…")
    data = yf.download(tickers, period=period, progress=False)

    if "Close" not in data:
        return {}

    closes  = data["Close"].dropna(how="all", axis=1)
    volumes = data["Volume"].reindex(columns=closes.columns).fillna(0)

    valid_tickers = closes.columns.tolist()
    print(f"[optimizer] {len(valid_tickers)} tickers with valid data.")

    # ── Indicators (using only data available at t) ────────────────────────────
    sma50       = closes.rolling(50).mean()
    sma200      = closes.rolling(200).mean()
    avg_vol_20  = volumes.rolling(20).mean().replace(0, np.nan)
    rsi         = closes.apply(_calc_rsi)
    pct_change  = closes.pct_change() * 100

    prev_close  = closes.shift(1)
    prev_sma50  = sma50.shift(1)
    prev_sma200 = sma200.shift(1)

    # Composite score (matches existing scanner logic)
    score_raw = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    score_raw += (closes > sma50).astype(float)  * 2
    score_raw += (closes > sma200).astype(float) * 3
    score_raw += (rsi < 30).astype(float)        * 2
    score_raw -= (rsi > 70).astype(float)        * 2
    score_raw += (pct_change > 0).astype(float)
    score_raw += (volumes > 1.5 * avg_vol_20).fillna(False).astype(float)

    # ── Market Context (breadth) ───────────────────────────────────────────────
    stocks_above_sma50 = (closes > sma50).sum(axis=1)
    total_stocks       = closes.notna().sum(axis=1)
    breadth            = stocks_above_sma50 / total_stocks.replace(0, np.nan)

    bullish_days = breadth > 0.6
    bearish_days = breadth < 0.4
    neutral_days = ~bullish_days & ~bearish_days

    # Broadcast day-level series to full DataFrame (same columns as closes)
    def broadcast(series: pd.Series) -> pd.DataFrame:
        arr = np.tile(series.values.reshape(-1, 1), (1, len(closes.columns)))
        return pd.DataFrame(arr, index=closes.index, columns=closes.columns, dtype=bool)

    bullish_mask = broadcast(bullish_days)
    bearish_mask = broadcast(bearish_days)

    # ── Forward returns (no lookahead in signal generation) ────────────────────
    ret_1d  = (closes.shift(-1)  / closes - 1) * 100
    ret_5d  = (closes.shift(-5)  / closes - 1) * 100
    ret_10d = (closes.shift(-10) / closes - 1) * 100
    ret_20d = (closes.shift(-20) / closes - 1) * 100

    # ── Phase 1: Individual Signal Masks ──────────────────────────────────────
    is_oversold   = rsi < 30
    is_overbought = rsi > 70
    hv_2x         = (volumes > 2.0 * avg_vol_20).fillna(False)
    hv_15x        = (volumes > 1.5 * avg_vol_20).fillna(False)

    # Edge-triggered oversold/overbought (first day entering zone only)
    oversold_entry   = is_oversold   & ~(is_oversold.shift(1).fillna(False).astype(bool))
    overbought_entry = is_overbought & ~(is_overbought.shift(1).fillna(False).astype(bool))

    breakout_up     = (prev_close < prev_sma50)  & (closes >= sma50)
    breakdown_down  = (prev_close > prev_sma50)  & (closes < sma50)
    ma_breakout     = breakout_up | ((prev_close < prev_sma200) & (closes >= sma200))

    individual_masks = {
        "breakout_up":          breakout_up,
        "breakdown_down":       breakdown_down,
        "high_volume":          hv_2x,
        "oversold":             oversold_entry,
        "overbought":           overbought_entry,
        "momentum_shift_up":    pct_change > 3.0,
        "momentum_shift_down":  pct_change < -3.0,
        "ma_breakout_signal":   ma_breakout,
        "composite_score_high": score_raw >= 6,
    }

    # ── Phase 2: Combined Signal Masks ────────────────────────────────────────
    combined_defs = {
        "breakout_up__high_volume":             (breakout_up & hv_15x,                      "breakout_up"),
        "breakout_up__bullish_context":         (breakout_up & bullish_mask,                 "breakout_up"),
        "breakout_up__rsi_lt70":                (breakout_up & (rsi < 70),                   "breakout_up"),
        "breakout_up__composite_gte6":          (breakout_up & (score_raw >= 6),             "breakout_up"),
        "oversold__bullish_context":            (oversold_entry & bullish_mask,               "oversold"),
        "oversold__high_volume":                (oversold_entry & hv_15x,                    "oversold"),
        "momentum_shift_up__bullish_context":   ((pct_change > 3.0) & bullish_mask,          "momentum_shift_up"),
        "breakout_up__high_vol__composite6":    (breakout_up & hv_15x & (score_raw >= 6),    "breakout_up"),
        "oversold__bullish__composite6":        (oversold_entry & bullish_mask & (score_raw >= 6), "oversold"),
    }

    # ── Evaluate individual signals ────────────────────────────────────────────
    print("[optimizer] Evaluating individual signals…")
    individual_results: dict = {}
    for name, mask in individual_masks.items():
        stats = _compute_metrics(
            mask, closes, ret_1d, ret_5d, ret_10d, ret_20d,
            bullish_mask, bearish_mask, deduplicate=True
        )
        individual_results[name] = stats

    # ── Evaluate combined signals ──────────────────────────────────────────────
    print("[optimizer] Evaluating combined signals…")
    combined_results: dict = {}
    for name, (mask, base_key) in combined_defs.items():
        stats = _compute_metrics(
            mask, closes, ret_1d, ret_5d, ret_10d, ret_20d,
            bullish_mask, bearish_mask, deduplicate=True
        )
        if stats:
            stats["base_signal"] = base_key
            # Delta vs base individual signal
            base = individual_results.get(base_key) or {}
            wr_base  = base.get("win_rate_5d")  or 0.0
            wr_comb  = stats.get("win_rate_5d") or 0.0
            exp_base = base.get("expectancy_5d") or 0.0
            exp_comb = stats.get("expectancy_5d") or 0.0
            stats["delta_win_rate_5d"]    = round(wr_comb  - wr_base,  4)
            stats["delta_expectancy_5d"]  = round(exp_comb - exp_base, 3)
        combined_results[name] = stats

    # ── Phase 4: Exit Rule Backtest (using breakout_up as entry) ──────────────
    print("[optimizer] Backtesting exit rules…")
    entry_for_exit = _deduplicate_mask(breakout_up.fillna(False).astype(bool), window=3)

    exit_results = {
        "model_A": {
            "label": "SL 5% | TP 10% | Máx 5 días",
            **_backtest_exit_rule(
                entry_for_exit, closes,
                stop_loss=-0.05, take_profit=0.10, max_days=5
            ),
        },
        "model_B": {
            "label": "SL 5% | TP 10% | Máx 10 días",
            **_backtest_exit_rule(
                entry_for_exit, closes,
                stop_loss=-0.05, take_profit=0.10, max_days=10
            ),
        },
        "model_C": {
            "label": "SL 5% | Trailing stop | Máx 20 días",
            **_backtest_exit_rule(
                entry_for_exit, closes,
                stop_loss=-0.05, take_profit=0.10, max_days=20, trailing=True
            ),
        },
        "model_D": {
            "label": "50% salida en +5% | Resto SL 5% o 10 días",
            **_backtest_exit_rule(
                entry_for_exit, closes,
                stop_loss=-0.05, take_profit=0.05, max_days=10, partial_exit=True
            ),
        },
    }

    # ── Phase 5: Ranking ──────────────────────────────────────────────────────
    print("[optimizer] Generating ranking…")
    ranking = _generate_ranking(individual_results, combined_results)

    # ── Summary text ──────────────────────────────────────────────────────────
    summary = _generate_summary(individual_results, combined_results, exit_results, ranking)

    print("[optimizer] ✓ Done.")
    return {
        "individual_signals": individual_results,
        "combined_signals":   combined_results,
        "exit_rules":         exit_results,
        "ranking":            ranking,
        "summary":            summary,
        "market_context": {
            "description":      "Bullish si breadth > 60% | Neutral 40–60% | Bearish < 40%",
            "bullish_days_pct": round(float(bullish_days.mean()) * 100, 1),
            "bearish_days_pct": round(float(bearish_days.mean()) * 100, 1),
            "neutral_days_pct": round(float(neutral_days.mean()) * 100, 1),
        },
    }


# ── Quick smoke test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    test_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "ADBE", "COST"]
    print("Running optimizer on 10 tickers…")
    res = run_strategy_optimization(test_tickers, period="2y")
    # Print only lightweight parts
    summary_view = {
        "ranking":        res.get("ranking"),
        "exit_rules":     res.get("exit_rules"),
        "market_context": res.get("market_context"),
        "summary":        res.get("summary"),
    }
    print(json.dumps(summary_view, indent=2, default=str))

def get_confidence_label(total: int, win_rate_5d: float, profit_factor: float, expectancy: float) -> str:
    """
    Determine the confidence label for a signal based on historical metrics.
    Penalizes weak edge (negative expectancy or profit factor < 1.0) regardless of sample size.
    """
    # Strict penalty for weak/negative drift
    if profit_factor is not None and profit_factor < 1.0:
        return "low"
    if expectancy is not None and expectancy <= 0.0:
        return "low"

    if total < 15:
        return "insufficient_sample"
    if total >= 100 and win_rate_5d >= 0.60:
        return "high"
    if total >= 40:
        return "medium"
    return "low"

def compute_signal_score(stats: dict) -> float:
    """
    Compute a normalized signal strength score (0-100) based on historical metrics.
    Used by both the Real-Time Scoring Engine and Strategy Lab.
    """
    wr = stats.get("win_rate_5d") or 0.0
    exp = stats.get("expectancy_5d") or 0.0
    pf = stats.get("profit_factor") or 0.0
    conf = stats.get("confidence") or "low"

    # Base scale:
    # Win Rate: linearly scale from 45% to 65% (max 40 pts)
    # Expectancy: linearly scale from 0% to 1.0% (max 30 pts)
    # Profit Factor: linearly scale from 1.0 to 1.5 (max 20 pts)
    # Confidence: high=10, medium=5, low=0 (max 10 pts)
    
    score = min(100.0, (
        max(0.0, min((wr - 0.45) / 0.20, 1.0)) * 40.0 +
        max(0.0, min(exp / 1.0, 1.0)) * 30.0 +
        max(0.0, min((pf - 1.0) / 0.5, 1.0)) * 20.0 +
        {"high": 10, "medium": 5, "low": 0, "insufficient_sample": 0}.get(conf, 0)
    ))
    return round(score, 1)

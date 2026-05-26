import numpy as np
import pandas as pd
import yfinance as yf

def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def generate_insight(name: str, stats: dict) -> str:
    if not stats or stats["total_signals"] < 10:
        return "Insufficient historical data for reliable insight."
        
    wr5 = stats["win_rate_5d"] * 100
    wr_bull = stats["bullish_context_win_rate"] * 100
    wr_bear = stats["bearish_context_win_rate"] * 100
    avg5 = stats["avg_return_5d"]
    
    insight = []
    
    if wr5 > 60:
        insight.append(f"Shows strong overall reliability ({wr5:.1f}% win rate at 5 days).")
    elif wr5 < 45:
        insight.append(f"Struggles to maintain positive drift ({wr5:.1f}% win rate at 5 days).")
    else:
        insight.append(f"Demonstrates average reliability ({wr5:.1f}% win rate at 5 days).")
        
    if abs(wr_bull - wr_bear) > 10:
        if wr_bull > wr_bear:
            insight.append("Significantly more effective during bullish market regimes.")
        else:
            insight.append("Surprisingly more effective during bearish market regimes.")
            
    if avg5 > 2.0:
        insight.append(f"Tends to produce outsized average returns (+{avg5:.1f}%).")
    elif avg5 < 0:
        insight.append(f"Often results in negative average returns ({avg5:.1f}%).")
        
    return " ".join(insight)

def evaluate_signals(tickers: list[str], period: str = "2y") -> dict:
    # 1. Fetch data
    data = yf.download(tickers, period=period, progress=False)
    if "Close" not in data:
        return {}
        
    closes = data["Close"]
    volumes = data["Volume"]
    
    # 2. Indicators
    sma50 = closes.rolling(50).mean()
    sma200 = closes.rolling(200).mean()
    avg_vol_20 = volumes.rolling(20).mean()
    rsi = closes.apply(calc_rsi)
    pct_change = closes.pct_change() * 100
    
    prev_close = closes.shift(1)
    prev_sma50 = sma50.shift(1)
    prev_sma200 = sma200.shift(1)
    
    # 3. Market Context
    stocks_above_sma50 = (closes > sma50).sum(axis=1)
    total_stocks = closes.notna().sum(axis=1)
    breadth = stocks_above_sma50 / total_stocks
    
    bullish_days = breadth > 0.6
    bearish_days = breadth < 0.4
    
    bullish_mask = pd.DataFrame(index=closes.index, columns=closes.columns)
    for col in bullish_mask.columns:
        bullish_mask[col] = bullish_days
        
    bearish_mask = pd.DataFrame(index=closes.index, columns=closes.columns)
    for col in bearish_mask.columns:
        bearish_mask[col] = bearish_days
        
    # 4. Signal Masks (Edge-triggered for de-duplication)
    masks = {}
    
    masks["breakout_up"] = (prev_close < prev_sma50) & (closes > sma50)
    masks["breakdown_down"] = (prev_close > prev_sma50) & (closes < sma50)
    
    masks["ma_breakout_signal"] = masks["breakout_up"] | ((prev_close < prev_sma200) & (closes > sma200))
    
    # Volume spike (allow consecutive)
    masks["high_volume"] = volumes > (2.0 * avg_vol_20)
    
    # RSI
    is_overbought = rsi > 70
    masks["overbought"] = is_overbought & (~is_overbought.shift(1).fillna(False))
    
    is_oversold = rsi < 30
    masks["oversold"] = is_oversold & (~is_oversold.shift(1).fillna(False))
    
    # Momentum Shift
    masks["momentum_shift_up"] = pct_change > 3.0
    masks["momentum_shift_down"] = pct_change < -3.0

    # Composite Signals (Combinations)
    masks["breakout_vol_1_5"] = masks["breakout_up"] & (volumes > (1.5 * avg_vol_20))
    masks["breakout_bullish"] = masks["breakout_up"] & bullish_mask
    masks["high_vol_mom_2"] = masks["high_volume"] & (pct_change > 2.0)
    masks["oversold_bullish"] = masks["oversold"] & bullish_mask

    
    # 5. Forward Returns
    ret_1d = closes.shift(-1) / closes - 1
    ret_5d = closes.shift(-5) / closes - 1
    ret_20d = closes.shift(-20) / closes - 1
    
    # 6. Evaluation Function
    def eval_mask(mask: pd.DataFrame) -> dict:
        total = int(mask.sum().sum())
        if total == 0:
            return None
            
        r1 = ret_1d[mask].values
        r5 = ret_5d[mask].values
        r20 = ret_20d[mask].values
        
        r1 = r1[~np.isnan(r1)]
        r5 = r5[~np.isnan(r5)]
        r20 = r20[~np.isnan(r20)]
        
        mask_bull = mask & bullish_mask
        mask_bear = mask & bearish_mask
        
        r5_bull = ret_5d[mask_bull].values
        r5_bull = r5_bull[~np.isnan(r5_bull)]
        
        r5_bear = ret_5d[mask_bear].values
        r5_bear = r5_bear[~np.isnan(r5_bear)]
        
        wr1 = (r1 > 0).mean() if len(r1) > 0 else 0
        wr5 = (r5 > 0).mean() if len(r5) > 0 else 0
        wr20 = (r20 > 0).mean() if len(r20) > 0 else 0
        
        wr_bull = (r5_bull > 0).mean() if len(r5_bull) > 0 else 0
        wr_bear = (r5_bear > 0).mean() if len(r5_bear) > 0 else 0
        
        # Confidence logic
        if total >= 100 and wr5 > 0.60:
            confidence = "high_confidence"
        elif total >= 40:
            confidence = "medium_confidence"
        else:
            confidence = "low_confidence"
            
        return {
            "total_signals": total,
            "win_rate_1d": round(float(wr1), 4),
            "win_rate_5d": round(float(wr5), 4),
            "win_rate_20d": round(float(wr20), 4),
            "avg_return_1d": round(float(np.mean(r1) * 100), 2) if len(r1) else 0,
            "avg_return_5d": round(float(np.mean(r5) * 100), 2) if len(r5) else 0,
            "avg_return_20d": round(float(np.mean(r20) * 100), 2) if len(r20) else 0,
            "median_return_5d": round(float(np.median(r5) * 100), 2) if len(r5) else 0,
            "bullish_context_win_rate": round(float(wr_bull), 4),
            "bearish_context_win_rate": round(float(wr_bear), 4),
            "confidence": confidence
        }

    # 7. Build Results
    results = {}
    for name, m in masks.items():
        stats = eval_mask(m)
        if stats:
            stats["insight"] = generate_insight(name, stats)
            results[name] = stats
            
    return results

if __name__ == "__main__":
    # Quick test
    import json
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
    print("Evaluating signals for test universe...")
    res = evaluate_signals(tickers, "2y")
    print(json.dumps(res, indent=2))

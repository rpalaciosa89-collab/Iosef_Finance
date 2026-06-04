"""
Iosef Finance – FastAPI Backend
================================
Architecture:
  - yf.download por lotes  → scan principal (rápido, sin .info)
  - background_sector_sync → carga sector/industry en segundo plano con rate limiting
  - background_scanner     → scan completo cada 60 s → Redis + snapshot file
  - Redis                  → capa principal de velocidad (TTL por tipo de dato)
"""

import asyncio
import json
import os
import time
from typing import Optional

import numpy as np
import pandas as pd
import redis
import yfinance as yf
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from app.services.signal_evaluation import evaluate_signals
from app.services.strategy_optimizer import run_strategy_optimization
from app.services import analytics
from app.services.scoring import compute_signal_score, compute_ml_score
from app.services.human_layer import translate_ticker, _detect_situation
from app.services import persistence
# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SNAPSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "snapshots")
SNAPSHOT_FILE = os.path.join(SNAPSHOT_DIR, "latest.json")

# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT  = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB    = int(os.getenv("REDIS_DB",   0))

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

# ---------------------------------------------------------------------------
# TTLs (seconds)
# ---------------------------------------------------------------------------
TTL_SCAN        = 60
TTL_TICKER      = 30
TTL_INTRADAY    = 10
TTL_FINANCIALS  = 86_400       # 1 day
TTL_SECTOR      = 60 * 60 * 24 * 30   # 30 days (virtually persistent)

# Sector sync rate limiting
SECTOR_FETCH_DELAY   = 0.8   # seconds between .info calls
SECTOR_MAX_RETRIES   = 3
SECTOR_BACKOFF_BASE  = 2.0   # exponential backoff base (seconds)

# ---------------------------------------------------------------------------
# Tickers to scan – per-market universes
# ---------------------------------------------------------------------------
NASDAQ100_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "ADBE", "COST",
    "PEP",  "CSCO", "NFLX",  "CMCSA","INTC", "AMD",  "TXN",  "QCOM", "INTU", "AMGN",
    "ISRG", "AMAT", "BKNG",  "SBUX", "GILD", "MDLZ", "ADI",  "LRCX", "VRTX", "REGN",
    "PANW", "SNPS", "CDNS",  "KLAC", "ABNB", "MELI", "PYPL", "CRWD", "MAR",  "MNST",
    "ORLY", "FTNT", "CSX",   "DASH", "DXCM", "MRVL", "NXPI", "ADSK", "ROP",  "PCAR",
    "CTAS", "ODFL", "CPRT",  "ADP",  "FANG", "KDP",  "ROST", "FAST", "MCHP", "KHC",
    "PAYX", "AEP",  "GEHC",  "VRSK", "EXC",  "IDXX", "EA",   "CTSH", "XEL",  "BIIB",
    "ON",   "ZS",   "TTWO",  "DDOG", "CSGP", "CDW",  "ILMN", "MDB",
    "WBD",  "TEAM", "CEG",   "BKR",  "LULU", "WDAY", "TTD",  "SIRI", "DLTR",
    "ALGN", "ENPH", "LCID",  "RIVN", "ZM",   "OKTA", "JD",   "PDD",  "DKNG",
    # Eliminados 2026-06-04 (delisted / sin datos en yfinance): SPLK, ANSS, WBA
]

SP500_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "JPM", "JNJ",
    "V",    "PG",   "UNH",   "HD",   "MA",   "DIS",  "PYPL", "BAC",   "VZ",  "ADBE",
    "NFLX", "INTC", "CMCSA", "PFE",  "CSCO", "PEP",  "KO",   "WMT",   "T",   "MRK",
    "ABT",  "CRM",  "AVGO",  "TXN",  "QCOM", "NKE",  "MCD",  "MDT",   "HON", "IBM",
    "GE",   "CAT",  "BA",    "GS",   "LMT",  "AXP",  "SBUX", "BLK",   "MMM", "CVX",
    "XOM",  "COP",  "SLB",   "EOG",  "MPC",  "PSX",  "VLO",  "OXY",   "HAL", "DVN",
    "LLY",  "TMO",  "DHR",   "BMY",  "ABBV", "GILD", "VRTX", "REGN",  "ZTS", "SYK",
    "ISRG", "BDX",  "CI",    "HUM",  "ELV",  "MCK",  "CAH",  "DXCM",  "A",   "BSX",
    "DE",   "EMR",  "ITW",   "APD",  "SHW",  "ECL",  "NSC",  "UNP",   "CSX", "WM",
    "ADP",  "PAYX", "FIS",   "FISV", "AJG",  "AON",  "MMC",  "TRV",   "CB",  "PGR",
]

EUROPE_TICKERS = [
    "ASML", "MC.PA",  "SAP",   "SIE.DE", "OR.PA",  "SAN.PA", "TTE",   "NESN.SW", "NOVN.SW", "ROG.SW",
    "AZN",  "SHEL",   "HSBA.L","ULVR.L", "BP.L",   "GSK",   "RIO.L", "BHP.L",   "DGE.L",   "BATS.L",
    "AIR.PA","BNP.PA","CS.PA", "SU.PA",  "AI.PA",  "DTE.DE","BAS.DE","ALV.DE",  "MBG.DE",  "BMW.DE",
    "VOW3.DE","ADS.DE","IFX.DE","MUV2.DE","DB1.DE","ENEL.MI","ISP.MI","UCG.MI", "RACE.MI", "ENI.MI",
    "INGA.AS","PHIA.AS","AD.AS","WKL.AS", "DSM.AS","NOVO-B.CO","CARL-B.CO","MAERSK-B.CO","VWS.CO","NZYM-B.CO",
]

# Market lookup
MARKET_TICKERS = {
    "nasdaq100": NASDAQ100_TICKERS,
    "sp500":     SP500_TICKERS,
    "europe":    EUROPE_TICKERS,
}

DEFAULT_MARKET = "nasdaq100"

# Union of all tickers (for sector sync)
ALL_TICKERS = sorted(set(NASDAQ100_TICKERS + SP500_TICKERS + EUROPE_TICKERS))

# Legacy alias so existing helpers keep working
TICKERS_TO_SCAN = NASDAQ100_TICKERS

# Sector metadata map (populated by background task, read without blocking scan)
SECTOR_META_CACHE: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Redis helpers
# ---------------------------------------------------------------------------
def redis_get(key: str) -> Optional[dict]:
    try:
        cached = r.get(key)
        if cached:
            return json.loads(cached)
    except redis.ConnectionError:
        pass
    return None

def redis_set(key: str, value, ttl: int) -> None:
    try:
        r.setex(key, ttl, json.dumps(value))
    except redis.ConnectionError:
        pass

def redis_set_no_expire(key: str, value) -> None:
    """Store without expiry (effectively persistent)."""
    try:
        r.set(key, json.dumps(value))
    except redis.ConnectionError:
        pass

def redis_delete(key: str) -> None:
    try:
        r.delete(key)
    except redis.ConnectionError:
        pass

# ---------------------------------------------------------------------------
# Calculations
# ---------------------------------------------------------------------------
def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain  = (delta.where(delta > 0, 0)).ewm(alpha=1 / period, adjust=False).mean()
    loss  = (-delta.where(delta < 0, 0)).ewm(alpha=1 / period, adjust=False).mean()
    rs    = gain / loss
    return 100 - (100 / (1 + rs))

# ---------------------------------------------------------------------------
# Signal Lifecycle Engine
# ---------------------------------------------------------------------------
from datetime import datetime, timezone

def _flatten_trade_data(ticker_entry: dict, market: str) -> dict:
    """Flattens a ticker entry to match the persistence SQLite schema."""
    plan = ticker_entry.get("trade_plan", {})
    tracking = ticker_entry.get("trade_tracking", {})
    
    return {
        "ticker": ticker_entry.get("ticker"),
        "market": market,
        "signal_type": ticker_entry.get("situation"),
        "human_signal": ticker_entry.get("human_signal"),
        "score_at_detection": ticker_entry.get("signal_strength_score", 0.0),
        "signal_detected_at": ticker_entry.get("signal_detected_at"),
        "trade_opened_at": tracking.get("trade_opened_at") or ticker_entry.get("signal_detected_at"),
        "trade_closed_at": tracking.get("trade_closed_at"),
        "signal_status_at_detection": ticker_entry.get("signal_status"),
        "entry_window_status_at_detection": ticker_entry.get("entry_window_status"),
        "market_context_used": ticker_entry.get("market_context_used"),
        "signal_context_adjustment": ticker_entry.get("signal_context_adjustment", 0.0),
        "entry_price": plan.get("entry_price", 0.0),
        "stop_loss": plan.get("stop_loss", 0.0),
        "take_profit": plan.get("take_profit", 0.0),
        "risk_reward_ratio": plan.get("risk_reward", ""),
        "trade_direction": plan.get("direction", ""),
        "trade_status": tracking.get("trade_status", ""),
        "trade_result": tracking.get("trade_result", ""),
        "pnl_percentage": tracking.get("pnl_percentage", 0.0),
        "pnl_absolute": tracking.get("pnl_absolute", 0.0),
        "trade_duration_seconds": tracking.get("trade_duration_seconds", 0),
        "exit_reason": tracking.get("exit_reason", ""),
        "signal_invalid_reason": ticker_entry.get("signal_invalid_reason", ""),
        "confidence_text": ticker_entry.get("confidence_text", ""),
        "decision_clarity": ticker_entry.get("decision_clarity", ""),
        "suggested_action": ticker_entry.get("suggested_action", ""),
        "holding_period": ticker_entry.get("holding_period", "")
    }

def _compute_atr(close_series: pd.Series, high_series: pd.Series, low_series: pd.Series, period: int = 14) -> float:
    """Average True Range (ATR) para sizing basado en volatilidad real."""
    if len(close_series) < period + 1:
        return 0.0
    tr = pd.DataFrame({
        'hl': high_series - low_series,
        'hc': (high_series - close_series.shift(1)).abs(),
        'lc': (low_series - close_series.shift(1)).abs()
    }).max(axis=1)
    return float(tr.ewm(span=period, adjust=False).mean().iloc[-1])

def _generate_trade_plan(situation: str, entry_price: float, atr: float = 0.0) -> dict:
    """Generate Trade Plan based on signal situation and ATR volatility."""
    if entry_price <= 0:
        return {}

    plan = {
        "direction": "LONG",
        "entry_price": entry_price,
        "stop_loss": 0.0,
        "take_profit": 0.0,
        "sl_pct": 0.0,
        "tp_pct": 0.0,
        "risk_reward": ""
    }

    if atr <= 0:
        atr = entry_price * 0.02 # fallback a 2%

    atr_multiplier_sl = 1.5
    atr_multiplier_tp = 3.0

    if situation == "oversold":
        atr_multiplier_sl = 2.0
        atr_multiplier_tp = 4.0
        plan["risk_reward"] = "1:2"
    elif situation in ("breakout_strong", "breakout_forming"):
        atr_multiplier_sl = 1.5
        atr_multiplier_tp = 4.5
        plan["risk_reward"] = "1:3"
    elif situation in ("momentum_up", "strong_trend"):
        atr_multiplier_sl = 2.0
        atr_multiplier_tp = 4.0
        plan["risk_reward"] = "1:2"
    elif situation in ("breakdown", "momentum_down", "overbought"):
        plan["direction"] = "SHORT"
        atr_multiplier_sl = 1.5
        atr_multiplier_tp = 3.0
        plan["risk_reward"] = "1:2"
    else:
        atr_multiplier_sl = 2.0
        atr_multiplier_tp = 4.0
        plan["risk_reward"] = "1:2"

    if plan["direction"] == "LONG":
        plan["stop_loss"] = round(entry_price - (atr * atr_multiplier_sl), 2)
        plan["take_profit"] = round(entry_price + (atr * atr_multiplier_tp), 2)
    else:
        plan["stop_loss"] = round(entry_price + (atr * atr_multiplier_sl), 2)
        plan["take_profit"] = round(entry_price - (atr * atr_multiplier_tp), 2)

    plan["sl_pct"] = round(((plan["stop_loss"] - entry_price) / entry_price) * 100, 2)
    plan["tp_pct"] = round(((plan["take_profit"] - entry_price) / entry_price) * 100, 2)

    return plan

def _update_trade_simulation(state: dict, current_price: float, now: float, market_status: str):
    tracking = state.get("trade_tracking")
    if not tracking or tracking.get("trade_status") != "open":
        return
        
    if market_status == "closed":
        tracking["trading_paused"] = True
        return
    else:
        tracking["trading_paused"] = False
        
    plan = state.get("trade_plan", {})
    if not plan:
        return
        
    entry = plan.get("entry_price", 0.0)
    tp = plan.get("take_profit", 0.0)
    sl = plan.get("stop_loss", 0.0)
    direction = plan.get("direction", "LONG")
    opened_at = tracking.get("trade_opened_at", now)
    
    # Update duration
    duration = int(now - opened_at)
    tracking["trade_duration_seconds"] = duration
    
    # Calculate floating PnL
    if entry > 0:
        if direction == "LONG":
            pct = ((current_price - entry) / entry) * 100.0
            abs_pnl = current_price - entry
        else:
            pct = ((entry - current_price) / entry) * 100.0
            abs_pnl = entry - current_price
            
        tracking["pnl_percentage"] = round(pct, 2)
        tracking["pnl_absolute"] = round(abs_pnl, 2)
        
    # Check Exits
    # 1. Target or Stop
    if direction == "LONG":
        if current_price >= tp and tp > 0:
            tracking["trade_status"] = "closed_win"
            tracking["trade_result"] = "win"
            tracking["trade_closed_at"] = now
            tracking["exit_reason"] = "target hit"
        elif current_price <= sl and sl > 0:
            tracking["trade_status"] = "closed_loss"
            tracking["trade_result"] = "loss"
            tracking["trade_closed_at"] = now
            tracking["exit_reason"] = "stop loss hit"
    else: # SHORT
        if current_price <= tp and tp > 0:
            tracking["trade_status"] = "closed_win"
            tracking["trade_result"] = "win"
            tracking["trade_closed_at"] = now
            tracking["exit_reason"] = "target hit"
        elif current_price >= sl and sl > 0:
            tracking["trade_status"] = "closed_loss"
            tracking["trade_result"] = "loss"
            tracking["trade_closed_at"] = now
            tracking["exit_reason"] = "stop loss hit"
            
    # 2. Invalidation (Grace Period exceeded)
    if tracking["trade_status"] == "open" and state.get("signal_expired"):
        tracking["trade_status"] = "closed_invalidated"
        tracking["trade_result"] = "expired"  # Mantenemos 'expired' o 'invalidated' para Analytics
        tracking["trade_closed_at"] = now
        tracking["exit_reason"] = "signal invalidated"
        
    state["trade_tracking"] = tracking

def _format_lifecycle_output(state: dict, now: float) -> dict:
    age_seconds = int(now - state.get("signal_detected_at", now))
    def format_ts(ts):
        if not ts: return ""
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

    return {
        "signal_detected_at": format_ts(state.get("signal_detected_at")),
        "signal_last_validated_at": format_ts(state.get("signal_last_validated_at")),
        "signal_status": state.get("signal_status", ""),
        "signal_age_seconds": age_seconds,
        "entry_window_status": state.get("entry_window_status", ""),
        "signal_expired": state.get("signal_expired", False),
        "signal_invalid_reason": state.get("signal_invalid_reason", ""),
        "trade_plan": state.get("trade_plan", {}),
        "trade_tracking": state.get("trade_tracking", {})
    }

def update_signal_lifecycle(ticker: str, strength_score: float, active_signals: list, current_price: float, ticker_entry: dict, market_status: str, atr: float = 0.0, commit_new: bool = False) -> tuple[dict, bool]:
    key = f"lifecycle:{ticker}"
    cached = redis_get(key)
    now = time.time()
    
    is_valid_signal = strength_score >= 40.0 and len(active_signals) > 0
    situation = _detect_situation(ticker_entry)
    
    if not cached:
        if is_valid_signal:
            trade_plan = _generate_trade_plan(situation, current_price, atr)
            state = {
                "signal_detected_at": now,
                "signal_last_validated_at": now,
                "signal_status": "new",
                "detection_price": current_price,
                "entry_window_status": "open",
                "signal_expired": False,
                "signal_invalid_reason": "",
                "missed_cycles": 0,
                "trade_plan": trade_plan,
                "trade_tracking": {
                    "trade_status": "open",
                    "trade_opened_at": now,
                    "trade_closed_at": None,
                    "trade_result": "",
                    "pnl_percentage": 0.0,
                    "pnl_absolute": 0.0,
                    "trade_duration_seconds": 0,
                    "exit_reason": "",
                    "trading_paused": market_status == "closed"
                }
            }
            if commit_new:
                redis_set(key, state, 7200) # 2 hours TTL
            return _format_lifecycle_output(state, now), True
        else:
            # No active signal — return null-safe skeleton so frontend never crashes
            return {
                "signal_detected_at": "",
                "signal_last_validated_at": "",
                "signal_status": "",
                "signal_age_seconds": 0,
                "entry_window_status": "",
                "signal_expired": False,
                "signal_invalid_reason": "",
                "trade_plan": {
                    "direction": "",
                    "entry_price": 0.0,
                    "stop_loss": 0.0,
                    "take_profit": 0.0,
                    "sl_pct": 0.0,
                    "tp_pct": 0.0,
                    "risk_reward": "N/A"
                },
                "trade_tracking": {
                    "trade_status": "",
                    "trade_opened_at": None,
                    "trade_closed_at": None,
                    "trade_result": "",
                    "pnl_percentage": 0.0,
                    "pnl_absolute": 0.0,
                    "trade_duration_seconds": 0,
                    "exit_reason": "",
                    "trading_paused": False
                }
            }, False
    else:
        # EXISTING SIGNAL
        state = cached
        detected_at = state.get("signal_detected_at", now)
        detection_price = state.get("detection_price", current_price)
        age = now - detected_at
        
        if is_valid_signal:
            # Signal continues to be valid
            state["missed_cycles"] = 0
            state["signal_last_validated_at"] = now
            state["signal_expired"] = False
            state["signal_invalid_reason"] = ""
            
            if age < 300: # 5 minutes
                state["signal_status"] = "new"
            else:
                if strength_score < 50:
                    state["signal_status"] = "weakening"
                else:
                    state["signal_status"] = "active"
                    
            dev = abs(current_price - detection_price) / (detection_price if detection_price > 0 else 1) * 100
            if dev < 1.0:
                state["entry_window_status"] = "open"
            elif dev < 3.0:
                state["entry_window_status"] = "narrowing"
            else:
                state["entry_window_status"] = "late"
                
            redis_set(key, state, 7200)
        else:
            # SIGNAL NO LONGER VALID (Grace period check)
            if market_status != "closed":
                missed_cycles = state.get("missed_cycles", 0) + 1
                state["missed_cycles"] = missed_cycles
                
                if missed_cycles >= 3 and not state.get("signal_expired"):
                    state["signal_status"] = "expired"
                    state["entry_window_status"] = "closed"
                    state["signal_expired"] = True
                    state["signal_invalid_reason"] = "La señal técnica desapareció por 3 ciclos consecutivos."
                    state["signal_last_validated_at"] = now

        # Run tracking update regardless of valid signal (to close out if needed)
        _update_trade_simulation(state, current_price, now, market_status)
        redis_set(key, state, 7200)
    
        return _format_lifecycle_output(state, now), False

# ---------------------------------------------------------------------------
# Sector / Industry background sync
# Condition 1 & 2: runs outside scan loop, never blocks /api/scan
# Condition 4: stored in Redis with 30-day TTL
# Condition 5: rate limiting + exponential backoff
# Condition 6: stores update timestamp per ticker and global marker
# ---------------------------------------------------------------------------
async def _fetch_single_sector(ticker: str) -> Optional[dict]:
    """Fetch sector/industry for a single ticker with retries + backoff."""
    for attempt in range(SECTOR_MAX_RETRIES):
        try:
            t = yf.Ticker(ticker)
            info = await asyncio.to_thread(lambda: t.info)
            result = {
                "sector":    info.get("sector")   or "Unknown",
                "industry":  info.get("industry") or "Unknown",
                "updated_at": time.time(),
            }
            return result
        except Exception as e:
            wait = SECTOR_BACKOFF_BASE ** attempt
            print(f"[sector_sync] {ticker} attempt {attempt + 1}/{SECTOR_MAX_RETRIES} failed: {e}. Retrying in {wait:.1f}s")
            await asyncio.sleep(wait)
    return None

async def background_sector_sync():
    """
    Runs once at startup (and every 12 h thereafter).
    Fetches sector/industry for each ticker with rate limiting.
    Populates SECTOR_META_CACHE in memory AND persists to Redis.
    Updates global timestamp marker: meta:sector_sync_ts
    """
    while True:
        print("[sector_sync] Starting sector/industry sync cycle …")
        sync_start = time.time()

        for ticker in ALL_TICKERS:
            redis_key = f"meta:sector:{ticker}"

            # Skip if already cached in Redis (avoids redundant .info calls)
            cached = redis_get(redis_key)
            if cached:
                SECTOR_META_CACHE[ticker] = cached
                await asyncio.sleep(0)   # yield control
                continue

            # Rate limit: sleep between calls
            await asyncio.sleep(SECTOR_FETCH_DELAY)

            result = await _fetch_single_sector(ticker)
            if result:
                SECTOR_META_CACHE[ticker] = result
                redis_set_no_expire(redis_key, result)
                print(f"[sector_sync] ✓ {ticker}: {result['sector']} / {result['industry']}")
            else:
                print(f"[sector_sync] ✗ {ticker}: failed after {SECTOR_MAX_RETRIES} attempts")

        sync_end = time.time()
        elapsed  = sync_end - sync_start

        # Condition 6: global update marker
        try:
            r.set("meta:sector_sync_ts", json.dumps({
                "completed_at": sync_end,
                "elapsed_seconds": round(elapsed, 2),
                "tickers_synced": len(SECTOR_META_CACHE),
            }))
        except redis.ConnectionError:
            pass

        print(f"[sector_sync] Cycle complete in {elapsed:.1f}s. Next in 12 h.")
        await asyncio.sleep(60 * 60 * 12)   # re-sync every 12 hours

# ---------------------------------------------------------------------------
# Main scanner
# Condition 1 & 2: uses yf.download batch, does NOT call .info
# Condition 3: sector/industry fetched from in-memory cache, defaults to null/Unknown
# Condition 7: breakout as internal signal (ma_breakout_signal), not absolute truth
# ---------------------------------------------------------------------------
def _check_market_hours(market: str) -> dict:
    # TODO: Implement actual market hours logic per market.
    # For now, default to "open" so tracking works.
    return {"state": "open"}

def run_scan(market: str = DEFAULT_MARKET) -> tuple[list, list]:
    tickers = MARKET_TICKERS.get(market, MARKET_TICKERS[DEFAULT_MARKET])
    data = yf.download(tickers, period="1y", progress=False)

    if "Close" not in data:
        return [], []

    closes  = data["Close"]
    highs   = data["High"]
    lows    = data["Low"]
    volumes = data["Volume"]
    results = []
    alerts = []
    new_candidates = []

    # --- Pre-calculate Market Breadth ---
    # We do this before iterating over tickers to have context ready.
    sma50_all = closes.rolling(50).mean()
    latest_closes = closes.iloc[-1]
    latest_sma50 = sma50_all.iloc[-1]
    stocks_above_sma50 = (latest_closes > latest_sma50).sum()
    total_valid = latest_closes.notna().sum()
    market_breadth = stocks_above_sma50 / total_valid if total_valid > 0 else 0.0

    if market_breadth > 0.6:
        current_context = "bullish"
    elif market_breadth < 0.4:
        current_context = "bearish"
    else:
        current_context = "neutral"

    if current_context == "bearish":
        alerts.append({"ticker": "MARKET", "type": "market_weakness", "message": f"Market Weakness: breadth at {market_breadth:.0%}", "strength": "high", "color": "yellow"})
    elif current_context == "bullish":
        alerts.append({"ticker": "MARKET", "type": "market_strength", "message": f"Market Strength: breadth at {market_breadth:.0%}", "strength": "high", "color": "green"})

    opt_cache = redis_get(f"meta:strategy_optimization:{market}")

    for ticker in tickers:
        if ticker not in closes.columns:
            continue

        close_series  = closes[ticker].dropna()
        volume_series = volumes[ticker].dropna()

        if len(close_series) < 200:
            continue

        latest_close = float(close_series.iloc[-1])
        prev_close   = float(close_series.iloc[-2])
        pct_change   = ((latest_close - prev_close) / prev_close) * 100

        rsi   = float(calculate_rsi(close_series).iloc[-1])
        sma20 = float(close_series.rolling(20).mean().iloc[-1])
        sma50 = float(close_series.rolling(50).mean().iloc[-1])
        sma200= float(close_series.rolling(200).mean().iloc[-1])

        momentum   = ((latest_close - float(close_series.iloc[-20])) / float(close_series.iloc[-20])) * 100
        avg_vol_20 = float(volume_series.rolling(20).mean().iloc[-1])
        latest_vol = float(volume_series.iloc[-1])
        rel_volume = latest_vol / avg_vol_20 if avg_vol_20 > 0 else 1.0

        high_series = highs[ticker].dropna()
        low_series  = lows[ticker].dropna()
        atr = _compute_atr(close_series, high_series, low_series)

        # --- Composite Score ---
        # Carlos Audit: score RSI is conditional to market context
        score = 0
        if latest_close > sma20:   score += 1
        if latest_close > sma50:   score += 2
        if latest_close > sma200:  score += 3
        if rsi < 30 and current_context != "bearish":
            score += 2   # oversold
        elif rsi > 70 and current_context != "bullish":
            score -= 2   # overbought
        if momentum > 0:           score += 2
        if rel_volume > 1.5:       score += 1
        if pct_change > 0:         score += 1

        # --- Condition 7: Breakout signal (internal indicator, not ground truth) ---
        # Price crosses above SMA50 or SMA200 – useful as attention signal
        prev50  = float(close_series.rolling(50).mean().iloc[-2])
        prev200 = float(close_series.rolling(200).mean().iloc[-2])
        ma_breakout_signal = (
            (float(close_series.iloc[-2]) < prev50  and latest_close >= sma50)  or
            (float(close_series.iloc[-2]) < prev200 and latest_close >= sma200)
        )

        # --- Real-Time Prioritization Scoring Engine ---
        active_signals = []
        is_breakout_up = (prev_close < prev50) and (latest_close >= sma50)
        is_breakdown_down = (prev_close > prev50) and (latest_close < sma50)
        is_oversold = rsi < 30
        is_overbought = rsi > 70
        is_high_volume = rel_volume > 2.0
        is_momentum_shift_up = pct_change > 3.0
        is_momentum_shift_down = pct_change < -3.0
        is_composite_score_high = score >= 6
        
        if is_breakout_up:
            active_signals.append("breakout_up")
        if is_breakdown_down:
            active_signals.append("breakdown_down")
        if is_oversold:
            active_signals.append("oversold")
        if is_overbought:
            active_signals.append("overbought")
        if is_high_volume:
            active_signals.append("high_volume")
        if is_momentum_shift_up:
            active_signals.append("momentum_shift_up")
        if is_momentum_shift_down:
            active_signals.append("momentum_shift_down")
        if ma_breakout_signal:
            active_signals.append("ma_breakout_signal")
        if is_composite_score_high:
            active_signals.append("composite_score_high")
            
        if is_breakout_up and rel_volume > 1.5:
            active_signals.append("breakout_up__high_volume")
        if is_breakout_up and is_composite_score_high:
            active_signals.append("breakout_up__composite_gte6")
        if is_breakout_up and rsi < 70:
            active_signals.append("breakout_up__rsi_lt70")
        if is_oversold and rel_volume > 1.5:
            active_signals.append("oversold__high_volume")

        # --- ML Inferencia (XGBoost) ---
        features = {
            'log_return': pct_change / 100.0 if pct_change else 0.0,
            'volatility_20': atr / latest_close if latest_close > 0 else 0.0,
            'momentum_10': momentum if momentum else 0.0,
            'rsi_14': rsi if rsi else 50.0,
            'macd_hist': ind.get("MACD_hist", 0.0) if ind else 0.0
        }
        
        strength_score = compute_ml_score(features)
        strength_source = "xgboost_ml"
        best_adj = 0.0


        # --- Condition 3: sector/industry from in-memory cache, never blocks scan ---
        meta     = SECTOR_META_CACHE.get(ticker, {})
        sector   = meta.get("sector")   or None   # None → frontend shows "–"
        industry = meta.get("industry") or None

        ticker_entry = {
            "ticker":            ticker,
            "price":             round(latest_close, 2),
            "change_pct":        round(pct_change, 2),
            "rsi":               round(rsi, 2),
            "sma20":             round(sma20, 2),
            "sma50":             round(sma50, 2),
            "sma200":            round(sma200, 2),
            "momentum_1m":       round(momentum, 2),
            "relative_volume":   round(rel_volume, 2),
            "composite_score":   score,
            "ma_breakout_signal": ma_breakout_signal,
            "signal_strength_score": strength_score,
            "signal_strength_source": strength_source,
            "signal_context_adjustment": best_adj,
            "market_context_used": current_context,
            "sector":            sector,
            "industry":          industry,
        }
        
        # --- Human Layer: translate to plain language ---
        human_fields = translate_ticker(ticker_entry, opt_cache)
        ticker_entry.update(human_fields)
        
        # --- Signal Lifecycle Engine ---
        # First pass: we evaluate all, update existing, and mark new candidates
        market_hours = _check_market_hours(market)
        market_status = market_hours["state"]
        
        lifecycle_fields, is_new = update_signal_lifecycle(ticker, strength_score, active_signals, latest_close, ticker_entry, market_status, atr=atr, commit_new=False)
        ticker_entry.update(lifecycle_fields)
        
        if is_new:
            # TOP OPPORTUNITIES BASE FILTER
            if strength_score >= 60.0 and ticker_entry.get("decision_clarity") != "baja":
                # Check for contradictory context
                plan_dir = ticker_entry.get("trade_plan", {}).get("direction", "LONG")
                contradiction = False
                if plan_dir == "LONG" and current_context == "bearish":
                    contradiction = True
                elif plan_dir == "SHORT" and current_context == "bullish":
                    contradiction = True
                
                # Exclude weak/ambiguous signal types
                sig_type = active_signals[0] if active_signals else ""
                weak_types = ["rsi_oversold_weak", "weak_trend", "consolidation"]
                if not contradiction and not any(wt in sig_type for wt in weak_types):
                    new_candidates.append(ticker_entry)
        else:
            # Append existing trades to results immediately
            results.append(ticker_entry)
            
            # --- Persistence Layer for EXISTING trades ---
            tracking = ticker_entry.get("trade_tracking", {})
            if tracking.get("trade_status", "").startswith("closed_"):
                persistence.save_closed_trade(_flatten_trade_data(ticker_entry, market))
                redis_delete(f"lifecycle:{ticker}")

        # --- Alerts Generation ---
        # 1. Breakout
        if prev_close < prev50 and latest_close > sma50:
            alerts.append({"ticker": ticker, "type": "breakout_up", "message": f"Breakout above SMA50 at {latest_close:.2f}", "strength": "high", "color": "green"})
        elif prev_close > prev50 and latest_close < sma50:
            alerts.append({"ticker": ticker, "type": "breakdown_down", "message": f"Breakdown below SMA50 at {latest_close:.2f}", "strength": "high", "color": "red"})
        
        # 2. Volume Spike
        if rel_volume > 2.0:
            vol_color = "green" if pct_change > 0 else "red"
            alerts.append({"ticker": ticker, "type": "high_volume", "message": f"Volume Spike ({rel_volume:.1f}x avg)", "strength": "medium", "color": vol_color})
            
        # 3. RSI Extreme
        if rsi > 70:
            alerts.append({"ticker": ticker, "type": "overbought", "message": f"RSI Overbought ({rsi:.1f})", "strength": "medium", "color": "red"})
        elif rsi < 30:
            alerts.append({"ticker": ticker, "type": "oversold", "message": f"RSI Oversold ({rsi:.1f})", "strength": "medium", "color": "green"})
            
        # 4. Momentum Shift
        if pct_change > 3.0:
            alerts.append({"ticker": ticker, "type": "momentum_shift", "message": f"Strong move up (+{pct_change:.1f}%)", "strength": "high", "color": "green"})
        elif pct_change < -3.0:
            alerts.append({"ticker": ticker, "type": "momentum_shift", "message": f"Strong move down ({pct_change:.1f}%)", "strength": "high", "color": "red"})

    # --- Top Opportunities Selection ---
    # Sort candidates by total quality (score)
    new_candidates.sort(key=lambda x: x.get("signal_strength_score", 0), reverse=True)
    top_candidates = new_candidates[:3] # TOP 3 per market
    
    # Commit the top candidates to Redis
    for cand in top_candidates:
        # Re-run update_signal_lifecycle with commit_new=True
        # We need the active signals list, let's just extract it or mock it since it's already generated
        # Actually it's easier to just redis_set directly!
        key = f"lifecycle:{cand['ticker']}"
        state = {
            "signal_detected_at": cand.get("signal_detected_at"),
            "signal_last_validated_at": cand.get("signal_last_validated_at"),
            "signal_status": cand.get("signal_status"),
            "detection_price": cand.get("price"),
            "entry_window_status": cand.get("entry_window_status"),
            "signal_expired": cand.get("signal_expired"),
            "signal_invalid_reason": cand.get("signal_invalid_reason"),
            "missed_cycles": 0,
            "trade_plan": cand.get("trade_plan"),
            "trade_tracking": cand.get("trade_tracking")
        }
        # Parse ISO timestamps back to float for Redis storage
        def parse_ts(ts_str):
            if not ts_str: return time.time()
            try:
                return datetime.fromisoformat(ts_str).timestamp()
            except:
                return time.time()
                
        state["signal_detected_at"] = parse_ts(cand.get("signal_detected_at"))
        state["signal_last_validated_at"] = parse_ts(cand.get("signal_last_validated_at"))
        if "trade_tracking" in state and "trade_opened_at" in state["trade_tracking"]:
             # trade_opened_at is stored as float in Redis
             if isinstance(state["trade_tracking"]["trade_opened_at"], str):
                 state["trade_tracking"]["trade_opened_at"] = parse_ts(state["trade_tracking"]["trade_opened_at"])
                 
        redis_set(key, state, 7200)
        results.append(cand)

    # 5. Market Context was pre-calculated at the beginning of the function
    return results, alerts

# ---------------------------------------------------------------------------
# Background scanner – every 60 s, scans ALL markets
# ---------------------------------------------------------------------------
async def background_scanner():
    while True:
        for market in MARKET_TICKERS:
            try:
                results, alerts = await asyncio.to_thread(run_scan, market)
                if results:
                    payload = {"timestamp": time.time(), "market": market, "data": results, "alerts": alerts}
                    redis_set(f"scan:data:{market}", payload, TTL_SCAN)
                    # Also keep legacy key updated for default market
                    if market == DEFAULT_MARKET:
                        redis_set("scan:data", payload, TTL_SCAN)
                    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
                    snap_file = os.path.join(SNAPSHOT_DIR, f"latest_{market}.json")
                    with open(snap_file, "w") as f:
                        json.dump(payload, f)
                    # Also write Parquet cache for faster cold-start reload
                    _write_parquet_cache(market, payload)
                    print(f"[scanner] ✓ {market}: {len(results)} tickers scanned")
            except Exception as e:
                print(f"[scanner] Error scanning {market}: {e}")
        await asyncio.sleep(60)

# ---------------------------------------------------------------------------
# Parquet-based disk cache for yfinance data (faster than JSON fallback)
# ---------------------------------------------------------------------------
PARQUET_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cache", "parquet")
os.makedirs(PARQUET_CACHE_DIR, exist_ok=True)
PARQUET_CACHE_TTL = 60  # seconds, same as scan interval

def _parquet_cache_path(market: str) -> str:
    return os.path.join(PARQUET_CACHE_DIR, f"scan_{market}.parquet")

def _write_parquet_cache(market: str, payload: dict) -> None:
    """Write scan results as Parquet + metadata JSON for fast reload."""
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
        data = payload.get("data", [])
        if data:
            table = pa.Table.from_pydict({k: [d[k] for d in data] for k in data[0].keys()})
            pq.write_table(table, _parquet_cache_path(market))
        meta_path = _parquet_cache_path(market).replace(".parquet", "_meta.json")
        with open(meta_path, "w") as f:
            json.dump({"timestamp": payload["timestamp"], "market": payload["market"], "alerts": payload.get("alerts", [])}, f)
    except ImportError:
        pass  # pyarrow not installed, skip parquet
    except Exception as e:
        print(f"[parquet] Write error for {market}: {e}")

def _read_parquet_cache(market: str) -> Optional[dict]:
    """Restore scan results from Parquet cache (much faster than JSON for large datasets)."""
    try:
        import pyarrow.parquet as pq
        parq_path = _parquet_cache_path(market)
        meta_path = parq_path.replace(".parquet", "_meta.json")
        if os.path.exists(parq_path) and os.path.exists(meta_path):
            cache_mtime = os.path.getmtime(parq_path)
            if time.time() - cache_mtime < PARQUET_CACHE_TTL:
                table = pq.read_table(parq_path)
                data = table.to_pylist()
                with open(meta_path) as f:
                    meta = json.load(f)
                return {**meta, "data": data}
    except ImportError:
        pass
    except Exception as e:
        print(f"[parquet] Read error for {market}: {e}")
    return None

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Iosef Finance Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_cache_control_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        if request.url.path == "/api/strategy-optimization":
            response.headers["Cache-Control"] = "no-cache"
        else:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
    return response

@app.on_event("startup")
async def startup_event():
    persistence.init_db()
    # Start both background tasks independently
    asyncio.create_task(background_scanner())
    asyncio.create_task(background_sector_sync())

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/scan")
def get_scan(market: str = DEFAULT_MARKET):
    """Return latest scan from Redis (primary) → snapshot file (fallback)."""
    market = market.lower()
    if market not in MARKET_TICKERS:
        market = DEFAULT_MARKET

    cached = redis_get(f"scan:data:{market}")
    if cached:
        return cached

    # Fallback: Parquet cache (fastest disk read)
    parquet_data = _read_parquet_cache(market)
    if parquet_data:
        return parquet_data

    # Fallback: snapshot JSON file
    snap_file = os.path.join(SNAPSHOT_DIR, f"latest_{market}.json")
    if os.path.exists(snap_file):
        with open(snap_file) as f:
            return json.load(f)
    return {"timestamp": None, "market": market, "data": []}

@app.get("/api/top")
def get_top(market: str = DEFAULT_MARKET):
    """Top 20 tickers by signal_strength_score."""
    scan  = get_scan(market)
    data  = scan.get("data", [])
    if not data:
        return {"timestamp": None, "market": market, "data": []}
    top20 = sorted(data, key=lambda x: (x.get("signal_strength_score", 0.0), x.get("composite_score", 0)), reverse=True)[:20]
    return {"timestamp": scan.get("timestamp"), "market": market, "data": top20}

@app.get("/api/history")
def get_history(limit: int = 100, offset: int = 0):
    """Endpoint to list persisted trades."""
    return {"data": persistence.get_closed_trades_history(limit, offset)}

from fastapi import Path

@app.get("/api/ticker/{ticker}")
def get_ticker_detail(ticker: str = Path(..., pattern=r"^[A-Za-z0-9\.\-]{1,10}$")):
    ticker = ticker.upper()
    cache_key = f"ticker:{ticker}"

    cached = redis_get(cache_key)
    if cached:
        return {"cached": True, "data": cached}

    try:
        info = yf.Ticker(ticker).fast_info
        detail_data = {
            "currency":           info.currency,
            "dayHigh":            info.day_high,
            "dayLow":             info.day_low,
            "exchange":           info.exchange,
            "fiftyDayAverage":    info.fifty_day_average,
            "lastPrice":          info.last_price,
            "lastVolume":         info.last_volume,
            "marketCap":          info.market_cap,
            "quoteType":          info.quote_type,
            "timezone":           info.timezone,
            "twoHundredDayAverage": info.two_hundred_day_average,
            "yearHigh":           info.year_high,
            "yearLow":            info.year_low,
        }
        redis_set(cache_key, detail_data, TTL_TICKER)
        return {"cached": False, "data": detail_data}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Ticker {ticker} not found: {e}")

@app.get("/api/ticker/{ticker}/intraday")
def get_ticker_intraday(ticker: str = Path(..., pattern=r"^[A-Za-z0-9\.\-]{1,10}$"), period: str = "1d", interval: str = "1m"):
    ticker = ticker.upper()
    
    # Normalize timeframe inputs
    period_map = {
        "1d": "1d",
        "5d": "5d",
        "1m": "1mo",
        "1mo": "1mo",
        "3m": "3mo",
        "3mo": "3mo",
        "1y": "1y"
    }
    p = period_map.get(period.lower(), "1d")
    
    interval_map = {
        "1m": "1m",
        "2m": "2m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "60m": "60m",
        "1h": "1h",
        "1d": "1d"
    }
    i = interval_map.get(interval.lower(), "1m")
    
    # Valida y restringe combinaciones recomendadas para evitar consultas inválidas en yfinance
    if p == "1d":
        i = "1m"
    elif p == "5d":
        i = "5m"
    elif p == "1mo":
        if i not in {"30m", "60m", "1h"}:
            i = "30m"
    elif p in {"3mo", "1y"}:
        i = "1d"
        
    cache_key = f"intraday:{ticker}:{p}:{i}"
    
    # Determinar TTL dinámico por period
    ttl = TTL_INTRADAY  # 10s default para 1d
    if p == "5d":
        ttl = 60       # 1 min para 5d
    elif p in {"1mo", "3mo", "1y"}:
        ttl = 300      # 5 min para timeframes superiores
        
    cached = redis_get(cache_key)
    if cached:
        return {"cached": True, "data": cached}
        
    try:
        data = yf.download(tickers=ticker, period=p, interval=i, progress=False)
        if data.empty:
            return {"data": []}
            
        data_reset = data.reset_index()
        data_reset.columns = [str(c[0]) if isinstance(c, tuple) else str(c) for c in data_reset.columns]
        
        records = []
        for _, row in data_reset.iterrows():
            time_col = None
            for col in ["Datetime", "Date", "index"]:
                if col in row:
                    time_col = col
                    break
                    
            if not time_col or pd.isnull(row[time_col]):
                continue
                
            ts = int(row[time_col].timestamp())
            
            try:
                open_p  = float(row["Open"])
                high_p  = float(row["High"])
                low_p   = float(row["Low"])
                close_p = float(row["Close"])
            except KeyError:
                continue
                
            if pd.isna(close_p):
                continue
                
            vol = int(row.get("Volume", 0))
            
            records.append({
                "time": ts,
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "volume": vol
            })
            
        records = sorted(records, key=lambda x: x["time"])
        unique_records = []
        last_time = 0
        for r in records:
            if r["time"] > last_time:
                unique_records.append(r)
                last_time = r["time"]
                
        redis_set(cache_key, unique_records, ttl)
        return {"cached": False, "data": unique_records}
    except Exception as e:
        print(f"[Intraday] Error fetching {ticker} ({p}/{i}): {e}")
        return {"data": []}

@app.get("/api/ticker/{ticker}/financials")
def get_ticker_financials(ticker: str):
    ticker = ticker.upper()
    cache_key = f"financials:{ticker}"

    cached = redis_get(cache_key)
    if cached:
        return {"cached": True, "data": cached}

    try:
        q_fin = yf.Ticker(ticker).quarterly_financials
        if q_fin.empty:
            return {"data": {}}

        q_fin     = q_fin.replace({np.nan: None})
        data_dict = {str(k): v.to_dict() for k, v in q_fin.items()}
        redis_set(cache_key, data_dict, TTL_FINANCIALS)
        return {"cached": False, "data": data_dict}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/meta/sector_sync")
def get_sector_sync_status():
    """Returns last sector sync timestamp and coverage from Redis."""
    try:
        ts_raw = r.get("meta:sector_sync_ts")
        ts     = json.loads(ts_raw) if ts_raw else None
        coverage = {
            t: bool(r.exists(f"meta:sector:{t}")) for t in ALL_TICKERS
        }
        cached_count = sum(coverage.values())
        return {
            "last_sync":      ts,
            "total_tickers":  len(ALL_TICKERS),
            "cached_count":   cached_count,
            "coverage":       coverage,
        }
    except redis.ConnectionError:
        return {"error": "Redis not reachable"}

@app.get("/api/signal-evaluation")
def get_signal_evaluation(market: str = DEFAULT_MARKET):
    """
    Evaluates signal probabilities historically.
    This uses a heavy background calculation, so we cache it for 24 hours.
    """
    market = market.lower()
    if market not in MARKET_TICKERS:
        market = DEFAULT_MARKET
        
    cache_key = f"meta:signal_evaluation:{market}"
    
    cached = redis_get(cache_key)
    if cached:
        return {"cached": True, "market": market, "data": cached}
        
    try:
        tickers = MARKET_TICKERS[market]
        # This will block the event loop for a few seconds since we don't await to_thread, 
        # but it only runs once per market per 24 hours.
        results = evaluate_signals(tickers, period="2y")
        
        # Cache for 24 hours (86400 seconds)
        redis_set(cache_key, results, 86400)
        
        return {"cached": False, "market": market, "data": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error evaluating signals: {str(e)}")

@app.get("/api/strategy-optimization")
def get_strategy_optimization(market: str = DEFAULT_MARKET):
    """
    Advanced statistical optimization of signals. 
    Heavy blocking operation, cached for 6 hours.
    """
    market = market.lower()
    if market not in MARKET_TICKERS:
        market = DEFAULT_MARKET
        
    cache_key = f"meta:strategy_optimization:{market}"
    
    cached = redis_get(cache_key)
    if cached:
        return {"cached": True, "market": market, "data": cached}
        
    try:
        tickers = MARKET_TICKERS[market]
        # Runs synchronously taking 30-60s on first fetch. 
        # Caching prevents repeated blocking.
        results = run_strategy_optimization(tickers, period="2y")
        
        # Cache for 6 hours (21600 seconds)
        redis_set(cache_key, results, 21600)
        
        return {"cached": False, "market": market, "data": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running strategy optimization: {str(e)}")

@app.get("/api/analytics")
def get_system_analytics():
    """
    Returns mathematical analytics over the SQLite dataset of closed trades.
    Cached for 5 minutes (300 seconds) to prevent heavy DB load.
    """
    cache_key = "system:analytics"
    cached = redis_get(cache_key)
    if cached:
        return {"cached": True, "data": cached}
        
    try:
        data = analytics.build_analytics_payload()
        redis_set(cache_key, data, 300)
        return {"cached": False, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating analytics: {str(e)}")

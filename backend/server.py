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
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.services.signal_evaluation import evaluate_signals
from app.services.strategy_optimizer import run_strategy_optimization
from app.services import analytics
from app.services.scoring import compute_signal_score, compute_ml_score, get_model_info
from app.services.human_layer import translate_ticker, _detect_situation
from app.services import persistence
from app.services.lstm_inference import get_composite_score, get_lstm_score
from config.titan_universe import TITAN_100

from app.api import auth, backtest, paper_trading as pt_router
from app.api.llm_router import router as llm_router
from app.db.database import engine, Base, SessionLocal
from app.models import paper_trading as _pt_models  # noqa: ensure tables registered
from app.models.user import User  # noqa: ensure User registered for foreign keys
from app.services.paper_trading import execute_trade, refresh_positions
from app.schemas.paper_trading import ExecuteTradeRequest
from app.models.paper_trading import TradeDirection
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
# Tickers to scan – Universo Titan 100 (Exclusivo)
# Filosofía: Solo operamos las 100 empresas que pasaron por nuestro modelo
# de ML (XGBoost + Global LSTM Titan 100). Cero ruido, máxima eficiencia.
# ---------------------------------------------------------------------------

# Market lookup — un solo universo institucional
MARKET_TICKERS = {
    "titan100": TITAN_100,
}

DEFAULT_MARKET = "titan100"

# Union of all tickers (for sector sync)
ALL_TICKERS = sorted(set(TITAN_100))

# Legacy alias so existing helpers keep working
TICKERS_TO_SCAN = TITAN_100

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
    def _parse_ts(ts) -> float:
        """Accept a Unix float OR an ISO string and return a Unix float."""
        if ts is None:
            return now
        if isinstance(ts, (int, float)):
            return float(ts)
        if isinstance(ts, str) and ts:
            try:
                return datetime.fromisoformat(ts.replace('Z', '+00:00')).timestamp()
            except Exception:
                pass
        return now

    def format_ts(ts):
        if not ts: return ""
        ts_float = _parse_ts(ts)
        return datetime.fromtimestamp(ts_float, tz=timezone.utc).isoformat()

    detected_ts = _parse_ts(state.get("signal_detected_at"))
    age_seconds = max(0, int(now - detected_ts))

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

from datetime import datetime

def update_signal_lifecycle(ticker: str, strength_score: float, active_signals: list, current_price: float, ticker_entry: dict, market_status: str, atr: float = 0.0, commit_new: bool = False) -> tuple[dict, bool]:
    key = f"lifecycle:{ticker}"
    cached = redis_get(key)
    now = time.time()
    iso_now = datetime.utcnow().isoformat() + "Z"
    
    # NUEVA REGLA ESTRICTA (Sprint 12):
    # La señal es válida si el ML está MUY seguro (>= 70 o <= 30) O si hay una señal tradicional fuerte activa.
    is_ml_strong_buy = strength_score >= 70.0
    is_ml_strong_sell = strength_score <= 30.0
    is_valid_signal = (is_ml_strong_buy or is_ml_strong_sell) or (len(active_signals) > 0)
    
    # Forzar la situación direccional si fue disparada puramente por ML
    situation = _detect_situation(ticker_entry)
    if is_ml_strong_buy and not situation.endswith("up"):
        situation = "momentum_shift_up" # Override para ML
    elif is_ml_strong_sell and not situation.endswith("down"):
        situation = "momentum_shift_down" # Override para ML
        
    if not cached:
        if is_valid_signal:
            trade_plan = _generate_trade_plan(situation, current_price, atr)
            # Add detection price to trade plan for charts
            trade_plan["detection_price"] = current_price
            state = {
                "signal_detected_at": iso_now,
                "signal_last_validated_at": iso_now,
                "signal_status": "new",
                "detection_price": current_price,
                "entry_window_status": "open",
                "signal_expired": False,
                "signal_invalid_reason": "",
                "missed_cycles": 0,
                "trade_plan": trade_plan,
                "trade_tracking": {
                    "trade_status": "open",
                    "trade_opened_at": iso_now,
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
        # Tolerate both float and ISO string timestamps (backward compat)
        raw_detected = state.get("signal_detected_at", now)
        if isinstance(raw_detected, str) and raw_detected:
            try:
                detected_at = datetime.fromisoformat(raw_detected.replace('Z', '+00:00')).timestamp()
            except Exception:
                detected_at = now
        else:
            detected_at = float(raw_detected) if raw_detected else now
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
        alerts.append({"ticker": "MARKET", "type": "market_weakness", "message": f"Mercado bajista: {stocks_above_sma50} de {total_valid} acciones sobre su media de 50 días. Precaución.", "strength": "high", "color": "yellow"})
    elif current_context == "bullish":
        alerts.append({"ticker": "MARKET", "type": "market_strength", "message": f"Mercado alcista: {stocks_above_sma50} de {total_valid} acciones sobre su media de 50 días.", "strength": "high", "color": "green"})

    opt_cache = redis_get(f"meta:strategy_optimization:{market}")

    for ticker in tickers:
        if ticker not in closes.columns:
            continue

        close_series  = closes[ticker].dropna()
        volume_series = volumes[ticker].dropna()

        if len(close_series) < 200:
            # We must still return it so the frontend shows all 100 tickers
            sector = redis_get(f"meta:sector:{ticker}") or {}
            dummy_entry = {
                "ticker": ticker,
                "price": float(close_series.iloc[-1]) if len(close_series) > 0 else 0.0,
                "change_pct": 0.0,
                "rsi": 0.0,
                "sma20": 0.0,
                "sma50": 0.0,
                "sma200": 0.0,
                "momentum_1m": 0.0,
                "relative_volume": 0.0,
                "composite_score": 0,
                "ma_breakout_signal": False,
                "signal_strength_score": 0.0,
                "signal_strength_source": "fallback",
                "signal_context_adjustment": 0.0,
                "market_context_used": "neutral",
                "sector": sector.get("sector", ""),
                "industry": sector.get("industry", ""),
                "situation": "Insuficientes velas históricas (<200)",
                "human_signal": "Esperando historial completo",
                "confidence_text": "N/A",
                "decision_clarity": "baja",
                "suggested_action": "Mantener al margen",
                "holding_period": "-",
                "signal_detected_at": "",
                "signal_last_validated_at": "",
                "signal_status": "",
                "signal_age_seconds": 0,
                "entry_window_status": "",
                "signal_expired": False,
                "signal_invalid_reason": "No data",
                "trade_plan": {
                    "direction": "", "entry_price": 0.0, "stop_loss": 0.0, "take_profit": 0.0,
                    "sl_pct": 0.0, "tp_pct": 0.0, "risk_reward": ""
                },
                "trade_tracking": {}
            }
            results.append(dummy_entry)
            continue

        latest_close = float(close_series.iloc[-1])
        prev_close   = float(close_series.iloc[-2])
        pct_change   = ((latest_close - prev_close) / prev_close) * 100

        rsi   = float(calculate_rsi(close_series).iloc[-1])
        sma20 = float(close_series.rolling(20).mean().iloc[-1])
        sma50 = float(close_series.rolling(50).mean().iloc[-1])
        sma200= float(close_series.rolling(200).mean().iloc[-1])

        momentum_1m = ((latest_close - float(close_series.iloc[-20])) / float(close_series.iloc[-20])) * 100
        momentum_10 = float(close_series.pct_change(10).iloc[-1]) * 100 if len(close_series) > 10 else momentum_1m
        avg_vol_20 = float(volume_series.rolling(20).mean().iloc[-1])
        latest_vol = float(volume_series.iloc[-1])
        rel_volume = latest_vol / avg_vol_20 if avg_vol_20 > 0 else 1.0

        high_series = highs[ticker].dropna()
        low_series  = lows[ticker].dropna()
        atr = _compute_atr(close_series, high_series, low_series)

        # MACD histogram for XGBoost feature (BUG-001 fix)
        ema12 = close_series.ewm(span=12, adjust=False).mean()
        ema26 = close_series.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        macd_hist = float((macd_line - macd_line.ewm(span=9, adjust=False).mean()).iloc[-1])

        # --- Composite Score ---
        # BUG-008 fix: oversold bonus always applies; overbought penalty always applies
        score = 0
        if latest_close > sma20:   score += 1
        if latest_close > sma50:   score += 2
        if latest_close > sma200:  score += 3
        if rsi < 30:
            score += 2   # oversold
        elif rsi > 70:
            score -= 2   # overbought
        if momentum_1m > 0:        score += 2
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
            'momentum_10': momentum_10 if momentum_10 else 0.0,
            'rsi_14': rsi if rsi else 50.0,
            'macd_hist': macd_hist if macd_hist else 0.0
        }
        
        strength_score = float(compute_ml_score(features))
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
            "momentum_1m":       round(momentum_1m, 2),
            "relative_volume":   round(rel_volume, 2),
            "atr":               round(atr, 4),
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
        
        # Siempre agregamos al resultado final para no esconder acciones del screener
        results.append(ticker_entry)
        
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
            # --- Persistence Layer for EXISTING trades ---
            tracking = ticker_entry.get("trade_tracking", {})
            if tracking.get("trade_status", "").startswith("closed_"):
                persistence.save_closed_trade(_flatten_trade_data(ticker_entry, market))
                redis_delete(f"lifecycle:{ticker}")

        # --- Alerts Generation ---
        # 1. Breakout
        if prev_close < prev50 and latest_close > sma50:
            alerts.append({"ticker": ticker, "type": "breakout_up", "message": f"{ticker} rompió al alza su media de 50 días en ${latest_close:.2f}. Tendencia alcista.", "strength": "high", "color": "green"})
        elif prev_close > prev50 and latest_close < sma50:
            alerts.append({"ticker": ticker, "type": "breakdown_down", "message": f"{ticker} rompió a la baja su media de 50 días en ${latest_close:.2f}. Tendencia bajista.", "strength": "high", "color": "red"})
        
        # 2. Volume Spike
        if rel_volume > 2.0:
            vol_color = "green" if pct_change > 0 else "red"
            alerts.append({"ticker": ticker, "type": "high_volume", "message": f"{ticker} con volumen inusualmente alto ({rel_volume:.1f}x el promedio).", "strength": "medium", "color": vol_color})
            
        # 3. RSI Extreme
        if rsi > 70:
            alerts.append({"ticker": ticker, "type": "overbought", "message": f"{ticker} en zona de sobrecompra (RSI {rsi:.1f}). Posible corrección.", "strength": "medium", "color": "red"})
        elif rsi < 30:
            alerts.append({"ticker": ticker, "type": "oversold", "message": f"{ticker} en zona de sobreventa (RSI {rsi:.1f}). Posible rebote técnico.", "strength": "medium", "color": "green"})
            
        # 4. Momentum Shift
        if pct_change > 3.0:
            alerts.append({"ticker": ticker, "type": "momentum_shift", "message": f"{ticker} sube con fuerza (+{pct_change:.1f}%). Impulso alcista.", "strength": "high", "color": "green"})
        elif pct_change < -3.0:
            alerts.append({"ticker": ticker, "type": "momentum_shift", "message": f"{ticker} cae con fuerza ({pct_change:.1f}%). Impulso bajista.", "strength": "high", "color": "red"})

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
        # cand is already in results list, so we don't append it again
        
        # --- Auto-Trading Engine (Sprint 12) ---
        if cand.get("signal_status") == "new" and cand.get("trade_plan", {}).get("direction"):
            p_win = cand.get("signal_strength_score", 50.0)
            trade_dir = cand["trade_plan"]["direction"]
            
            # Filtro institucional estricto: Solo auto-ejecutar si el modelo ML tiene altísima confianza (>70% o <30%)
            # AUTO-TRADING DESHABILITADO POR PETICIÓN DEL USUARIO
            if False and ((trade_dir == "LONG" and p_win >= 70.0) or (trade_dir == "SHORT" and p_win <= 30.0)):
                db = SessionLocal()
                try:
                    # 10 shares por defecto para simulación
                    default_qty = 10 
                    direction = TradeDirection.LONG if trade_dir == "LONG" else TradeDirection.SHORT
                    req = ExecuteTradeRequest(
                        ticker=cand["ticker"],
                        direction=direction,
                        quantity=default_qty,
                        entry_price=cand["price"],
                        stop_loss=cand["trade_plan"].get("stop_loss", 0),
                        take_profit=cand["trade_plan"].get("take_profit", 0),
                        signal_source="IOSEF_ML"
                    )
                    try:
                        execute_trade(user_id=1, payload=req, db=db)
                    except ValueError as e:
                        # Error (ej. falta balance, o no cuenta) -> pass
                        pass
                finally:
                    db.close()

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
                    # Broadcast to WebSocket clients
                    asyncio.create_task(_broadcast_scan(payload))
                    print(f"[scanner] ✓ {market}: {len(results)} tickers scanned")
            except Exception as e:
                print(f"[scanner] Error scanning {market}: {e}")
                
        # --- Auto-Close TP/SL Check (Sprint 12) ---
        db = SessionLocal()
        try:
            # Revisa las posiciones de la cuenta sim 1 y cierra si toca SL/TP
            refresh_positions(user_id=1, db=db)
        except Exception as e:
            print(f"[scanner] Error in auto-trading refresh: {e}")
        finally:
            db.close()

        await asyncio.sleep(60)

# ---------------------------------------------------------------------------
# Parquet-based disk cache for yfinance data (faster than JSON fallback)
# Implementación en app/services/parquet_cache.py (fix SP-3.1)
# ---------------------------------------------------------------------------
from app.services.parquet_cache import (
    PARQUET_CACHE_DIR, PARQUET_CACHE_TTL,
    write_parquet_cache as _write_parquet_cache,
    read_parquet_cache as _read_parquet_cache,
)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Iosef Finance Backend")

cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
cors_origins = [o.strip() for o in cors_origins_str.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,      prefix="/api/auth",          tags=["auth"])
app.include_router(backtest.router,  prefix="/api/backtest",      tags=["backtest"])
app.include_router(pt_router.router, prefix="/api/paper-trading", tags=["paper-trading"])
app.include_router(llm_router,       prefix="/api/llm",           tags=["llm"])

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
    Base.metadata.create_all(bind=engine)
    asyncio.create_task(background_scanner())
    asyncio.create_task(background_sector_sync())

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "iosef-backend"}

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

@app.post("/api/scan/refresh")
async def force_refresh_scan(market: str = DEFAULT_MARKET):
    """Force a fresh scan immediately, bypassing all caches. Useful for dev/debug."""
    market = market.lower()
    if market not in MARKET_TICKERS:
        market = DEFAULT_MARKET
    try:
        results, alerts = await asyncio.to_thread(run_scan, market)
        payload = {"timestamp": time.time(), "market": market, "data": results, "alerts": alerts}
        redis_set(f"scan:data:{market}", payload, TTL_SCAN)
        if market == DEFAULT_MARKET:
            redis_set("scan:data", payload, TTL_SCAN)
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        snap_file = os.path.join(SNAPSHOT_DIR, f"latest_{market}.json")
        with open(snap_file, "w") as f:
            json.dump(payload, f)
        _write_parquet_cache(market, payload)
        return {"status": "ok", "market": market, "tickers": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/top")
def get_top(market: str = DEFAULT_MARKET):
    """Top 20 tickers by signal_strength_score, filtered for actionable clarity."""
    scan  = get_scan(market)
    data  = scan.get("data", [])
    if not data:
        return {"timestamp": None, "market": market, "data": []}
    actionable = [t for t in data
                   if t.get("decision_clarity", "baja") != "baja"
                   and t.get("trade_plan", {}).get("direction") in ("LONG", "SHORT")
                   and t.get("trade_plan", {}).get("entry_price", 0) > 0]
    top20 = sorted(actionable, key=lambda x: (x.get("signal_strength_score", 0.0), x.get("composite_score", 0)), reverse=True)[:20]
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

@app.get("/api/neural-score/{ticker}")
def get_neural_score(ticker: str = Path(..., pattern=r"^[A-Za-z0-9\.\-]{1,10}$")):
    """
    Retorna el score compuesto del Ensemble (XGBoost + Global LSTM Titan 100).
    - p_win_xgb:       Probabilidad de éxito XGBoost (indicadores técnicos puntuales)
    - p_win_lstm:      Confianza neural LSTM (60 días de secuencia histórica)
    - p_win_composite: Score final del Ensemble (40% XGBoost + 60% LSTM)
    """
    ticker = ticker.upper()
    cache_key = f"neural_score:{ticker}"

    cached = redis_get(cache_key)
    if cached:
        return {"cached": True, "data": cached}

    try:
        # BUG-002 fix: compute XGBoost score from real features instead of stale cache
        xgb_score = 50.0
        try:
            hist = yf.Ticker(ticker).history(period="2mo")
            if len(hist) >= 30:
                close = hist["Close"]
                high = hist["High"]
                low  = hist["Low"]
                price_now = float(close.iloc[-1])
                rsi_val = float(calculate_rsi(close).iloc[-1])
                atr_val = _compute_atr(close, high, low)
                momentum_10d = float(close.pct_change(10).iloc[-1]) * 100 if len(close) > 10 else 0.0

                ema12 = close.ewm(span=12, adjust=False).mean()
                ema26 = close.ewm(span=26, adjust=False).mean()
                macd_h = float((ema12 - ema26 - (ema12 - ema26).ewm(span=9, adjust=False).mean()).iloc[-1])

                features = {
                    'log_return': 0.0,
                    'volatility_20': atr_val / price_now if price_now > 0 else 0.0,
                    'momentum_10': momentum_10d,
                    'rsi_14': rsi_val,
                    'macd_hist': macd_h,
                }
                xgb_score = float(compute_ml_score(features))
        except Exception as e:
            logger.warning(f"neural-score: could not compute features for {ticker}: {e}")

        # 2. Obtener Composite Score (XGBoost + LSTM)
        composite = get_composite_score(ticker, xgb_score)

        xgb_val = composite["p_win_xgb"]
        composite_val = composite["p_win_composite"]

        if composite_val >= 55.0:
            signal = "COMPRA"
        elif composite_val <= 45.0:
            signal = "VENTA"
        else:
            signal = "NEUTRAL"

        scan = redis_get(f"scan:data:titan100")
        plan_dir = None
        if scan and "data" in scan:
            for t in scan["data"]:
                if t.get("ticker") == ticker:
                    plan_dir = t.get("trade_plan", {}).get("direction")
                    break

        if signal != "NEUTRAL" and plan_dir:
            alignment = "CONFIRMADO" if (
                (signal == "COMPRA" and plan_dir == "LONG") or
                (signal == "VENTA" and plan_dir == "SHORT")
            ) else "DIVERGENTE"
        else:
            alignment = "NEUTRAL"

        result = {
            "ticker":          ticker,
            "p_win_xgb":       composite["p_win_xgb"],
            "p_win_lstm":      composite["p_win_lstm"],
            "p_win_composite": composite["p_win_composite"],
            "model":           composite["model"],
            "signal":          signal,
            "alignment":       alignment,
        }
        redis_set(cache_key, result, 60)
        return {"cached": False, "data": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculando score neural: {e}")

def _build_signal_overlays(ticker: str) -> list[dict]:
    """
    Construye los overlays de señales para el gráfico intraday.
    Busca en el cache del scan los datos de lifecycle del ticker.
    Retorna lista vacia si no hay senales.
    """
    overlays = []
    try:
        scan_data = redis_get("scan:data:titan100")
        if not scan_data or "data" not in scan_data:
            return []

        for t in scan_data["data"]:
            if t.get("ticker") != ticker:
                continue

            tracking = t.get("trade_tracking", {})
            plan = t.get("trade_plan", {})
            det_ts = t.get("signal_detected_at")
            status = t.get("signal_status", "")

            if not det_ts:
                return []

            overlay = {
                "detected_at": det_ts,
                "direction": plan.get("direction", ""),
                "entry_price": plan.get("entry_price", 0),
                "stop_loss": plan.get("stop_loss", 0),
                "take_profit": plan.get("take_profit", 0),
                "score_at_detection": t.get("signal_strength_score", 0),
                "signal_type": t.get("situation", ""),
                "status": status,
                "entry_window": t.get("entry_window_status", ""),
                "signal_expired": t.get("signal_expired", False),
                "human_signal": t.get("human_signal", ""),
                "suggested_action": t.get("suggested_action", ""),
                "pnl_since_detection_pct": 0.0,
                "pnl_since_detection_usd": 0.0,
                "is_currently_winning": False,
            }

            entry = overlay["entry_price"]
            current = t.get("price", 0)
            if entry > 0 and current > 0:
                direction = overlay["direction"]
                if direction == "LONG":
                    pnl_pct = ((current - entry) / entry) * 100
                elif direction == "SHORT":
                    pnl_pct = ((entry - current) / entry) * 100
                else:
                    pnl_pct = 0.0
                overlay["pnl_since_detection_pct"] = round(pnl_pct, 2)
                overlay["pnl_since_detection_usd"] = round(pnl_pct * entry / 100, 2)
                overlay["is_currently_winning"] = pnl_pct > 0

            overlays.append(overlay)
            break

    except Exception:
        pass

    return overlays


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
        "6m": "6mo",
        "6mo": "6mo",
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
    elif p in {"3mo", "6mo", "1y"}:
        i = "1d"
        
    cache_key = f"intraday:{ticker}:{p}:{i}"
    
    # Determinar TTL dinámico por period
    ttl = TTL_INTRADAY  # 10s default para 1d
    if p == "5d":
        ttl = 60       # 1 min para 5d
    elif p in {"1mo", "3mo", "6mo", "1y"}:
        ttl = 300      # 5 min para timeframes superiores
        
    cached = redis_get(cache_key)
    if cached:
        overlays = _build_signal_overlays(ticker)
        return {"cached": True, "data": cached, "signal_overlays": overlays}
        
    try:
        data = yf.download(tickers=ticker, period=p, interval=i, progress=False)
        if data.empty:
            return {"data": [], "signal_overlays": []}
            
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
        overlays = _build_signal_overlays(ticker)
        return {"cached": False, "data": unique_records, "signal_overlays": overlays}
    except Exception as e:
        print(f"[Intraday] Error fetching {ticker} ({p}/{i}): {e}")
        return {"data": [], "signal_overlays": []}

@app.get("/api/ticker/{ticker}/financials")
def get_ticker_financials(ticker: str = Path(..., pattern=r"^[A-Za-z0-9\.\-]{1,10}$")):
    ticker = ticker.upper()
    cache_key = f"financials:{ticker}"

    cached = redis_get(cache_key)
    if cached:
        return {"cached": True, "data": cached}

    try:
        t = yf.Ticker(ticker)
        
        def safe_extract(df):
            if df is None or df.empty: return {}
            df = df.replace({np.nan: None})
            # Limitar a los 4 años más recientes para claridad en UI
            cols = df.columns[:4]
            return {str(k)[:10]: df[k].to_dict() for k in cols}
            
        data_dict = {
            "income": safe_extract(t.financials),
            "balance": safe_extract(t.balance_sheet),
            "cashflow": safe_extract(t.cashflow)
        }
        
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
async def get_signal_evaluation(market: str = DEFAULT_MARKET):
    """
    Evaluates signal probabilities historically.
    Heavy calculation runs in thread pool to avoid blocking the event loop.
    Cached for 24 hours.
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
        results = await asyncio.to_thread(evaluate_signals, tickers, "2y")
        
        # Cache for 24 hours (86400 seconds)
        redis_set(cache_key, results, 86400)
        
        return {"cached": False, "market": market, "data": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error evaluating signals: {str(e)}")

@app.get("/api/strategy-optimization")
async def get_strategy_optimization(market: str = DEFAULT_MARKET):
    """
    Advanced statistical optimization of signals. 
    Heavy blocking operation runs in thread pool, cached for 6 hours.
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
        results = await asyncio.to_thread(run_strategy_optimization, tickers, "2y")
        
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

# ---------------------------------------------------------------------------
# Model Info
# ---------------------------------------------------------------------------
@app.get("/api/model-info")
def get_xgboost_model_info():
    """Returns metadata about the XGBoost model (provenance, metrics, training date)."""
    return get_model_info()

# ---------------------------------------------------------------------------
# WebSocket — Real-Time Market Data
# ---------------------------------------------------------------------------
_ws_clients: set[WebSocket] = set()


@app.websocket("/ws/market")
async def websocket_market(ws: WebSocket):
    await ws.accept()
    _ws_clients.add(ws)
    scan_data = redis_get("scan:data:titan100") or redis_get("scan:data")
    if scan_data:
        await ws.send_json(scan_data)
    try:
        while True:
            try:
                await ws.receive_text()
            except WebSocketDisconnect:
                break
    finally:
        _ws_clients.discard(ws)


async def _broadcast_scan(data: dict):
    dead: list[WebSocket] = []
    for ws in _ws_clients:
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.discard(ws)

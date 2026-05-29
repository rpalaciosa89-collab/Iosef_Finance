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

from signal_evaluation import evaluate_signals
from strategy_optimizer import run_strategy_optimization
from scoring import compute_signal_score
from human_layer import translate_ticker
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
    "ON",   "ZS",   "TTWO",  "DDOG", "ANSS", "CSGP", "GFS",  "CDW",  "ILMN", "MDB",
    "WBD",  "TEAM", "CEG",   "BKR",  "LULU", "WDAY", "TTD",  "SPLK", "SIRI", "DLTR",
    "ALGN", "ENPH", "LCID",  "RIVN", "ZM",   "OKTA", "WBA",  "JD",   "PDD",  "DKNG",
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
def run_scan(market: str = DEFAULT_MARKET) -> tuple[list, list]:
    tickers = MARKET_TICKERS.get(market, MARKET_TICKERS[DEFAULT_MARKET])
    data = yf.download(tickers, period="1y", progress=False)

    if "Close" not in data:
        return [], []

    closes  = data["Close"]
    volumes = data["Volume"]
    results = []
    alerts = []

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

        # --- Composite Score ---
        score = 0
        if latest_close > sma20:   score += 1
        if latest_close > sma50:   score += 2
        if latest_close > sma200:  score += 3
        if rsi < 30:               score += 2   # oversold
        elif rsi > 70:             score -= 2   # overbought
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

        strength_score = 0.0
        strength_source = "fallback"
        best_adj = 0.0
        
        if opt_cache and isinstance(opt_cache, dict):
            ind_stats = opt_cache.get("individual_signals", {})
            comb_stats = opt_cache.get("combined_signals", {})
            max_score = 0.0
            found_any = False
            
            for sig in active_signals:
                if sig == "high_volume":
                    continue
                
                stats = comb_stats.get(sig) if "__" in sig else ind_stats.get(sig)
                if stats and isinstance(stats, dict):
                    sig_score = compute_signal_score(stats)
                    
                    # Context adjustment
                    base_wr = stats.get("win_rate_5d") or 0.0
                    ctx_stats = stats.get("context", {}).get(current_context, {})
                    ctx_wr = ctx_stats.get("win_rate_5d") if ctx_stats.get("win_rate_5d") is not None else base_wr
                    
                    adj = 0.0
                    if ctx_wr > base_wr + 0.05:
                        sig_score *= 1.15
                        adj = 0.15
                    elif ctx_wr < base_wr - 0.05:
                        sig_score *= 0.85
                        adj = -0.15
                        
                    sig_score = min(100.0, max(0.0, sig_score))

                    if sig_score > max_score:
                        max_score = sig_score
                        best_adj = adj
                        found_any = True
            if found_any:
                strength_score = round(max_score, 1)
                strength_source = "optimized"

        if strength_source == "fallback":
            fallback_val = (score * 5.0)
            if ma_breakout_signal:
                fallback_val += 30.0
            if rel_volume > 1.5:
                fallback_val += 15.0
            if rsi < 30:
                fallback_val += 15.0
            elif rsi > 70:
                fallback_val -= 15.0
            strength_score = round(max(0.0, min(100.0, float(fallback_val))), 1)

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
        results.append(ticker_entry)

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

@app.get("/api/ticker/{ticker}")
def get_ticker_detail(ticker: str):
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
def get_ticker_intraday(ticker: str, period: str = "1d", interval: str = "1m"):
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

"""
Acceso a datos de mercado (SP-5.1).

Problema: yfinance es sincrono y bloquea el event loop cuando se llama dentro
de endpoints async (paper_trading, signal_evaluation, backtest).

Solucion:
- bulk_fetch_live_prices(): UNA llamada por ticker, tolerante a fallos, con cache
  en memoria (TTL 15s) para evitar repetir llamadas dentro de la ventana.
- async_fetch_live_price(): wrapper async que delega en un thread pool executor,
  garantizando que el event loop nunca se bloquea.
"""

import asyncio
import time
from typing import Dict, Optional

import yfinance as yf

# ── Cache en memoria (simple, sin Redis para no acoplar) ─────────────────────
_PRICE_CACHE: Dict[str, tuple[float, float]] = {}  # ticker -> (precio, ts)
_PRICE_CACHE_TTL = 15.0  # segundos

_BULK_CACHE: Dict[str, tuple[Dict[str, float], float]] = {}
_BULK_CACHE_TTL = 15.0


def _fetch_single(ticker: str) -> Optional[float]:
    """Una sola consulta a yfinance (sincrono; usese dentro de executor)."""
    try:
        t = yf.Ticker(ticker)
        hist = t.fast_info
        return round(float(hist.last_price), 4)
    except Exception:
        return None


def bulk_fetch_live_prices(tickers: list[str]) -> Dict[str, float]:
    """Fetch de precios por ticker (sincrono, tolerante a fallos)."""
    result: Dict[str, float] = {}
    for t in tickers:
        price = _fetch_single(t)
        if price is not None:
            result[t] = price
    return result


def get_cached_bulk_prices(tickers: list[str]) -> Dict[str, float]:
    """Precios en lote con cache en memoria de 15s."""
    now = time.time()
    key = tuple(sorted(tickers))
    cached = _BULK_CACHE.get(key)
    if cached and (now - cached[1]) < _BULK_CACHE_TTL:
        return cached[0]

    prices = bulk_fetch_live_prices(list(tickers))
    _BULK_CACHE[key] = (prices, now)
    return prices


def fetch_live_price(ticker: str) -> Optional[float]:
    """Precio individual con cache en memoria (delega en el lote)."""
    prices = get_cached_bulk_prices([ticker])
    return prices.get(ticker)


async def async_fetch_live_price(ticker: str) -> Optional[float]:
    """Version async: corre el fetch en un thread pool (no bloquea el loop)."""
    return await asyncio.to_thread(fetch_live_price, ticker)


async def async_bulk_fetch_live_prices(tickers: list[str]) -> Dict[str, float]:
    """Version async del lote: corre en executor sin bloquear el event loop."""
    return await asyncio.to_thread(get_cached_bulk_prices, tickers)
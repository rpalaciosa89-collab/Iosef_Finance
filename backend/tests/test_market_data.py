import asyncio
import time
from typing import Optional

import yfinance as yf
import pytest

from app.services.market_data import (
    bulk_fetch_live_prices,
    fetch_live_price,
    get_cached_bulk_prices,
)


@pytest.fixture(autouse=True)
def clear_price_cache():
    """Aisla la cache en memoria entre tests."""
    import app.services.market_data as md
    md._BULK_CACHE.clear()
    md._PRICE_CACHE.clear()
    yield
    md._BULK_CACHE.clear()
    md._PRICE_CACHE.clear()


def test_bulk_fetch_returns_prices(monkeypatch):
    """bulk_fetch_live_prices devuelve un dict ticker->precio (lote)."""

    class FakeTicker:
        def __init__(self, t):
            self.t = t

        @property
        def fast_info(self):
            class FI:
                last_price = 100.0 if self.t == "AAPL" else 200.0
            return FI()

    monkeypatch.setattr(yf, "Ticker", FakeTicker)
    result = bulk_fetch_live_prices(["AAPL", "MSFT"])
    assert result == {"AAPL": 100.0, "MSFT": 200.0}


def test_bulk_fetch_tolerates_failures(monkeypatch):
    """Si un ticker falla, no rompe el lote (devuelve los que pudo)."""

    class FlakyTicker:
        def __init__(self, t):
            self.t = t

        @property
        def fast_info(self):
            raise RuntimeError("rate limited")

    monkeypatch.setattr(yf, "Ticker", FlakyTicker)
    result = bulk_fetch_live_prices(["AAPL", "MSFT"])
    assert result == {}


def test_fetch_live_price_uses_bulk(monkeypatch):
    """fetch_live_price delega en el lote y cachea en memoria (TTL corto)."""
    calls = []

    def fake_bulk(tickers):
        calls.append(list(tickers))
        return {t: 10.0 for t in tickers}

    monkeypatch.setattr("app.services.market_data.bulk_fetch_live_prices", fake_bulk)
    p1 = fetch_live_price("AAPL")
    p2 = fetch_live_price("AAPL")
    assert p1 == p2 == 10.0
    assert len(calls) == 1, "debe cachear en memoria: una sola llamada al lote"


def test_get_cached_bulk_prices(monkeypatch):
    """get_cached_bulk_prices usa cache (una llamada al proveedor por ventana TTL)."""
    calls = []

    def fake_bulk(tickers):
        calls.append(1)
        return {t: 5.0 for t in tickers}

    monkeypatch.setattr("app.services.market_data.bulk_fetch_live_prices", fake_bulk)
    r1 = get_cached_bulk_prices(["A", "B"])
    r2 = get_cached_bulk_prices(["A", "B"])
    assert r1 == {"A": 5.0, "B": 5.0}
    assert r2 == {"A": 5.0, "B": 5.0}
    assert len(calls) == 1


def test_fetch_is_async_safe():
    """La API no bloquea el event loop: expone version async."""
    from app.services.market_data import async_fetch_live_price
    assert asyncio.iscoroutinefunction(async_fetch_live_price)
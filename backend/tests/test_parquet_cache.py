import json
import os
import time

import pytest

from app.services.parquet_cache import (
    write_parquet_cache,
    read_parquet_cache,
)


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    from app.services import parquet_cache

    monkeypatch.setattr(parquet_cache, "PARQUET_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(parquet_cache, "PARQUET_CACHE_TTL", 60)
    return tmp_path


def _real_scan_payload():
    """Replica el payload real del scan con tipos mixtos que rompía pyarrow."""
    return {
        "timestamp": "2026-08-20T06:57:54.871572Z",
        "market": "titan100",
        "alerts": [
            {"ticker": "MARKET", "type": "market_strength", "message": "Mercado alcista"},
        ],
        "data": [
            {
                "ticker": "XYZ",
                "price": 0.0,
                "rsi": 0.0,
                "composite_score": 0,
                "change_pct": 0.0,
                "signal_detected_at": "",
                "trade_plan": {},
                "trade_tracking": {},
                "active": True,
            },
            {
                "ticker": "AAPL",
                "price": 232.65,
                "rsi": 55.32,
                "composite_score": 8,
                "change_pct": 1.24,
                "signal_detected_at": "2026-08-20T06:57:54.871572Z",
                "trade_plan": {"direction": "LONG", "entry_price": 232.65},
                "trade_tracking": {"status": "open"},
                "active": True,
            },
        ],
    }


def test_round_trip_mixed_types(cache_dir):
    payload = _real_scan_payload()
    write_parquet_cache("test_market", payload)
    result = read_parquet_cache("test_market")
    assert result == payload


def test_write_no_error_on_mixed(cache_dir):
    payload = _real_scan_payload()
    write_parquet_cache("test_market", payload)
    assert os.path.exists(os.path.join(str(cache_dir), "scan_test_market.parquet"))


def test_mixed_type_column_with_number_then_string(cache_dir):
    payload = _real_scan_payload()
    payload["data"][0]["signal_age_seconds"] = 0
    payload["data"][1]["signal_age_seconds"] = "2026-08-20T06:57:54Z"
    write_parquet_cache("test_market", payload)
    assert read_parquet_cache("test_market") == payload


def test_read_ignores_stale(cache_dir):
    payload = _real_scan_payload()
    write_parquet_cache("test_market", payload)
    path = os.path.join(str(cache_dir), "scan_test_market.parquet")
    old = time.time() - 99999
    os.utime(path, (old, old))
    assert read_parquet_cache("test_market") is None


def test_no_payload_returns_none():
    assert read_parquet_cache("inexistente") is None
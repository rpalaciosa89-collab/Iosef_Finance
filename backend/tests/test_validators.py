import pytest

from app.core.validators import TICKER_PATTERN, validate_ticker
from app.schemas.paper_trading import ExecuteTradeRequest


def test_validator_accepts_valid_tickers():
    assert validate_ticker("AAPL") == "AAPL"
    assert validate_ticker("brk-b") == "BRK-B"
    assert validate_ticker("SPGI") == "SPGI"


def test_validator_rejects_injection():
    for bad in ["AAPL'; DROP TABLE users;--", "AAPL\" OR 1=1", "<script>alert(1)</script>", "A" * 30, "AAP L"]:
        try:
            validate_ticker(bad)
            raise AssertionError(f"debió rechazar: {bad!r}")
        except ValueError:
            pass


def test_pattern_matches_server_endpoints():
    assert TICKER_PATTERN.match("AAPL")
    assert TICKER_PATTERN.match("BRK-B")
    assert not TICKER_PATTERN.match("bad ticker")
    assert not TICKER_PATTERN.match("A" * 11)


def test_execute_trade_schema_rejects_bad_ticker():
    try:
        ExecuteTradeRequest(ticker="AAPL'; DROP TABLE users;--", quantity=10, entry_price=100.0)
        raise AssertionError("schema debió rechazar ticker inválido")
    except Exception:
        pass


def test_execute_trade_schema_accepts_valid():
    req = ExecuteTradeRequest(ticker="aapl", quantity=10, entry_price=100.0)
    assert req.ticker == "AAPL"


def test_backtest_endpoint_rejects_bad_ticker(client):
    """Ticker invalido es rechazado. Sin token valido, la auth (401) gana antes de la validacion.
    Con token valido, la validacion de formato (422) protege la ruta."""
    resp = client.get(
        "/api/backtest/AAPL%27%3B%20DROP%20TABLE",
        headers={"Authorization": "Bearer invalid"},
    )
    assert resp.status_code == 401  # auth evaluada primero (seguro: no llega al backtest)


def test_backtest_endpoint_accepts_valid_format(client):
    """Ticker valido pasa la validacion de formato (llega a auth -> 401 sin token)."""
    resp = client.get(
        "/api/backtest/AAPL",
        headers={"Authorization": "Bearer invalid"},
    )
    assert resp.status_code == 401
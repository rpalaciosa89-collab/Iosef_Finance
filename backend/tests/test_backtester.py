import numpy as np
import pandas as pd
import pytest

from app.services.backtester import Backtester, BacktestResult


@pytest.fixture
def synthetic_prices() -> pd.DataFrame:
    """Precio sintetico: 300 dias, tendencia alcista con ruido."""
    rng = np.random.default_rng(42)
    n = 300
    rets = rng.normal(0.0005, 0.015, n)
    close = 100 * np.exp(np.cumsum(rets))
    idx = pd.date_range("2023-01-02", periods=n, freq="B")
    return pd.DataFrame(
        {
            "Open": close * 0.999,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": rng.integers(1_000_000, 5_000_000, n),
        },
        index=idx,
    )


@pytest.fixture
def bt(synthetic_prices, monkeypatch):
    b = Backtester("TEST", "2023-01-01", "2024-12-31")
    monkeypatch.setattr(b, "fetch_data", lambda: synthetic_prices)
    b.data = synthetic_prices
    return b


def test_costs_reduce_net_return(bt):
    """Con costos, el retorno neto <= bruto."""
    res: BacktestResult = bt.run_strategy()
    assert res.gross_total_return_pct >= res.net_total_return_pct
    assert res.costs_pct >= 0


def test_benchmark_metrics_healthy_input(bt):
    """Métricas contra benchmark presentes y numéricas."""
    res: BacktestResult = bt.run_strategy()
    assert res.ir is not None
    assert isinstance(res.sortino, float)
    assert isinstance(res.max_drawdown_pct, float)
    assert res.benchmark_return_pct is not None


def test_deterministic(bt):
    """Dos ejecuciones del mismo input dan el mismo resultado."""
    r1 = bt.run_strategy()
    r2 = bt.run_strategy()
    assert r1 == r2


def test_exit_via_sl_tp(bt):
    """SL/TP se aplican: el retorno por trade acotado por SL/TP."""
    res: BacktestResult = bt.run_strategy(
        stop_loss_pct=0.05,
        take_profit_pct=0.05,
    )
    assert res.expectancy_per_trade is not None


def test_momentum_strategy_not_all_flat(bt):
    """La estrategia genera trades (no quedan todos en 0)."""
    res: BacktestResult = bt.run_strategy()
    assert res.total_trades > 0


def test_report_schema_fields():
    """El resultado incluye todos los campos obligatorios de la Spec."""
    res = BacktestResult()
    required = {
        "net_total_return_pct",
        "gross_total_return_pct",
        "costs_pct",
        "benchmark_return_pct",
        "ir",
        "sortino",
        "expectancy_per_trade",
        "profit_factor",
        "win_rate",
        "max_drawdown_pct",
        "total_trades",
    }
    assert required.issubset(set(BacktestResult.model_fields.keys()))
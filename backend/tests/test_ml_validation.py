import numpy as np
import pandas as pd
import pytest

from app.services.ml_validation import (
    WalkForwardSplit,
    evaluate_walk_forward,
    should_promote,
)


@pytest.fixture
def timeseries_data():
    """X con indice temporal ascendente, y binario."""
    n = 500
    dates = pd.date_range("2023-01-02", periods=n, freq="B")
    rng = np.random.default_rng(7)
    X = pd.DataFrame(
        {
            "log_return": rng.normal(0, 0.01, n),
            "volatility_20": rng.uniform(0.005, 0.03, n),
            "momentum_10": rng.normal(0, 0.02, n),
            "rsi_14": rng.uniform(10, 90, n),
            "macd_hist": rng.normal(0, 0.5, n),
        },
        index=dates,
    )
    # Label con algo de señal temporal para que no sea puro ruido
    y = pd.Series((X["momentum_10"].shift(1) > 0).astype(int).values, index=dates)
    return X, y


def test_walk_forward_split_chronological(timeseries_data):
    """Los folds de validacion son SIEMPRE posteriores al train (cronologico)."""
    X, y = timeseries_data
    wf = WalkForwardSplit(n_splits=3, embargo_days=5)
    for train_idx, valid_idx in wf.split(X, y):
        assert (train_idx < valid_idx.min()).all(), "leak temporal: train >= valid"


def test_embargo_removes_overlap(timeseries_data):
    """Ninguna fila de validacion comparte ventana ± embargo con train."""
    X, y = timeseries_data
    wf = WalkForwardSplit(n_splits=3, embargo_days=10)
    for train_idx, valid_idx in wf.split(X, y):
        train_dates = X.index[train_idx]
        valid_dates = X.index[valid_idx]
        for vd in valid_dates:
            assert not ((train_dates >= vd - pd.Timedelta(days=10)) & (train_dates <= vd)).any(), (
                f"fila de validacion {vd} comparte ventana con train"
            )


def test_gate_promotion_threshold():
    """AUC OOS >= 0.56 promueve; por debajo no."""
    assert should_promote(0.58) is True
    assert should_promote(0.55) is False
    assert should_promote(0.50) is False


def test_evaluate_walk_forward_reports_meta(timeseries_data):
    """El evaluador devuelve AUC OOS medio, std, folds y embargo."""
    X, y = timeseries_data
    result = evaluate_walk_forward(X, y, n_splits=3, embargo_days=5)
    assert "auc_oos_mean" in result
    assert "auc_oos_std" in result
    assert "cv_folds" in result
    assert result["cv_folds"] == 3
    assert result["embargo_days"] == 5
    assert 0.0 <= result["auc_oos_mean"] <= 1.0


def test_meta_includes_promoted(timeseries_data):
    """El meta reporte incluye promoted segun el gate."""
    X, y = timeseries_data
    result = evaluate_walk_forward(X, y, n_splits=3, embargo_days=5)
    assert "promoted" in result
    assert result["promoted"] == should_promote(result["auc_oos_mean"])
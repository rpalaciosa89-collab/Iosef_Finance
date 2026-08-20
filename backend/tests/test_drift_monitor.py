"""
SP-7.1: drift monitor para modelos ML (PSI sobre distribuciones de features).
"""
import numpy as np
import pytest

from app.services.drift_monitor import (
    compute_psi,
    classify_drift,
    compute_feature_drifts,
    check_model_drift,
)


def test_psi_identical_distributions_is_zero():
    """PSI de la misma distribucion debe ser ~0."""
    rng = np.random.default_rng(1)
    a = rng.normal(0, 1, 1000)
    psi = compute_psi(a, a)
    assert abs(psi) < 0.05


def test_psi_detects_shift():
    """Distribuciones muy distintas -> PSI alto."""
    rng = np.random.default_rng(2)
    a = rng.normal(0, 1, 1000)
    b = rng.normal(3, 1, 1000)
    psi = compute_psi(a, b)
    assert psi > 0.2


def test_classify_drift_levels():
    assert classify_drift(0.05) == "stable"
    assert classify_drift(0.2) == "watch"
    assert classify_drift(0.5) == "alert"


def test_compute_feature_drifts():
    """Devuelve PSI por feature."""
    rng = np.random.default_rng(3)
    ref = {
        "log_return": rng.normal(0, 1, 500),
        "volatility_20": rng.uniform(0.005, 0.03, 500),
    }
    live = {
        "log_return": rng.normal(2, 1, 500),
        "volatility_20": rng.uniform(0.005, 0.03, 500),
    }
    drifts = compute_feature_drifts(ref, live)
    assert "log_return" in drifts
    assert "volatility_20" in drifts
    assert drifts["log_return"] > drifts["volatility_20"]


def test_check_model_drift_reports_alert(monkeypatch):
    """Con shift fuerte en un feature, el estado es alert."""
    rng = np.random.default_rng(4)
    ref = {"rsi_14": rng.normal(50, 10, 1000)}
    live = {"rsi_14": rng.normal(90, 5, 1000)}

    monkeypatch.setattr(
        "app.services.drift_monitor.load_reference_distributions",
        lambda: ref,
    )
    monkeypatch.setattr(
        "app.services.drift_monitor.collect_live_distributions",
        lambda: live,
    )
    result = check_model_drift()
    assert result["drift"] == "alert"
    assert "rsi_14" in result["psi"]


def test_check_model_drift_stable(monkeypatch):
    """Sin shift, el estado es stable."""
    rng = np.random.default_rng(5)
    ref = {"rsi_14": rng.normal(50, 10, 1000)}
    live = {"rsi_14": rng.normal(50, 10, 1000)}

    monkeypatch.setattr(
        "app.services.drift_monitor.load_reference_distributions",
        lambda: ref,
    )
    monkeypatch.setattr(
        "app.services.drift_monitor.collect_live_distributions",
        lambda: live,
    )
    result = check_model_drift()
    assert result["drift"] == "stable"
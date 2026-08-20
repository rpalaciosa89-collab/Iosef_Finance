"""
SP-4.2: los gates de promocion (XGBoost y LSTM) leen los reportes walk-forward.
Este modulo no importa torch/xgboost -> seguro en cualquier orden de la suite.
"""
import json

import pytest

from app.core import ml_gates


@pytest.fixture(autouse=True)
def clear_gate_caches():
    ml_gates.invalidate_caches()
    yield
    ml_gates.invalidate_caches()


def test_lstm_gate_archived(tmp_path, monkeypatch):
    monkeypatch.setattr(ml_gates, "LSTM_REPORT", tmp_path / "lstm.json")
    (tmp_path / "lstm.json").write_text(json.dumps({"promoted": False, "auc_oos": 0.5155}))
    assert ml_gates.lstm_is_promoted() is False


def test_lstm_gate_promoted(tmp_path, monkeypatch):
    monkeypatch.setattr(ml_gates, "LSTM_REPORT", tmp_path / "lstm.json")
    (tmp_path / "lstm.json").write_text(json.dumps({"promoted": True, "auc_oos": 0.58}))
    assert ml_gates.lstm_is_promoted() is True


def test_lstm_gate_auc_based(tmp_path, monkeypatch):
    """Sin campo promoted, el gate usa AUC >= 0.56."""
    monkeypatch.setattr(ml_gates, "LSTM_REPORT", tmp_path / "lstm.json")
    (tmp_path / "lstm.json").write_text(json.dumps({"auc_oos": 0.60}))
    assert ml_gates.lstm_is_promoted() is True
    (tmp_path / "lstm.json").write_text(json.dumps({"auc_oos": 0.50}))
    ml_gates.invalidate_caches()
    assert ml_gates.lstm_is_promoted() is False


def test_lstm_gate_backward_compat(tmp_path, monkeypatch):
    """Sin reporte, comportamiento legacy (activado)."""
    monkeypatch.setattr(ml_gates, "LSTM_REPORT", tmp_path / "no_existe.json")
    assert ml_gates.lstm_is_promoted() is True


def test_xgboost_gate_archived(tmp_path, monkeypatch):
    monkeypatch.setattr(ml_gates, "XGB_REPORT", tmp_path / "xgb.json")
    (tmp_path / "xgb.json").write_text(json.dumps({"promoted": False, "auc_oos_mean": 0.5037}))
    assert ml_gates.xgboost_is_promoted() is False


def test_xgboost_gate_promoted(tmp_path, monkeypatch):
    monkeypatch.setattr(ml_gates, "XGB_REPORT", tmp_path / "xgb.json")
    (tmp_path / "xgb.json").write_text(json.dumps({"promoted": True, "auc_oos_mean": 0.57}))
    assert ml_gates.xgboost_is_promoted() is True


def test_xgboost_gate_auc_based(tmp_path, monkeypatch):
    monkeypatch.setattr(ml_gates, "XGB_REPORT", tmp_path / "xgb.json")
    (tmp_path / "xgb.json").write_text(json.dumps({"auc_oos_mean": 0.58}))
    assert ml_gates.xgboost_is_promoted() is True


def test_lstm_inference_respects_gate():
    """lstm_inference delega en el gate central (sin duplicar logica)."""
    from app.services import lstm_inference
    assert lstm_inference._lstm_is_promoted is ml_gates.lstm_is_promoted
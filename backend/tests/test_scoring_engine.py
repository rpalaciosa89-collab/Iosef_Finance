import pytest

from app.services.scoring_engine import (
    ScoringEngine,
    heuristic_score,
    score_ticker,
)


def test_heuristica_etiquetada():
    """La heuristica devuelve score + fuente 'heuristic'."""
    features = {
        "close": 110.0, "sma20": 100.0, "sma50": 95.0, "sma200": 90.0,
        "rsi": 55.0, "momentum_1m": 2.0, "rel_volume": 1.6, "pct_change": 0.5,
    }
    result = heuristic_score(features)
    assert result["source"] == "heuristic"
    assert "value" in result
    assert result["components"]["ml"] is None


def test_ml_cuando_promoted(monkeypatch):
    """Con modelo promoted, el engine incluye el score ML."""
    def fake_meta():
        return {"promoted": True}
    monkeypatch.setattr("app.services.scoring_engine._load_model_meta", fake_meta)

    result = score_ticker(
        {
            "close": 110.0, "sma20": 100.0, "sma50": 95.0, "sma200": 90.0,
            "rsi": 55.0, "momentum_1m": 2.0, "rel_volume": 1.6, "pct_change": 0.5,
            "log_return": 0.01, "volatility_20": 0.02, "momentum_10": 0.05,
            "rsi_14": 55.0, "macd_hist": 0.1,
        }
    )
    assert result["source"] in ("ml", "ensemble")
    assert result["components"]["ml"] is not None


def test_ml_null_sin_promoted(monkeypatch):
    """Con modelo no promovido, el ML aparece como null y la fuente es heuristic."""
    def fake_meta():
        return {"promoted": False}
    monkeypatch.setattr("app.services.scoring_engine._load_model_meta", fake_meta)

    result = score_ticker(
        {
            "close": 110.0, "sma20": 100.0, "sma50": 95.0, "sma200": 90.0,
            "rsi": 55.0, "momentum_1m": 2.0, "rel_volume": 1.6, "pct_change": 0.5,
        }
    )
    assert result["source"] == "heuristic"
    assert result["components"]["ml"] is None
    assert result["auc_gate"] == "failed"


def test_ensemble_combina_ambos(monkeypatch):
    """Cuando ML esta promovido, el score es combinacion heuristic+ml (ensemble)."""
    def fake_meta():
        return {"promoted": True}
    monkeypatch.setattr("app.services.scoring_engine._load_model_meta", fake_meta)

    h = heuristic_score(
        {
            "close": 110.0, "sma20": 100.0, "sma50": 95.0, "sma200": 90.0,
            "rsi": 55.0, "momentum_1m": 2.0, "rel_volume": 1.6, "pct_change": 0.5,
        }
    )
    result = score_ticker(
        {
            "close": 110.0, "sma20": 100.0, "sma50": 95.0, "sma200": 90.0,
            "rsi": 55.0, "momentum_1m": 2.0, "rel_volume": 1.6, "pct_change": 0.5,
            "log_return": 0.01, "volatility_20": 0.02, "momentum_10": 0.05,
            "rsi_14": 55.0, "macd_hist": 0.1,
        }
    )
    assert result["components"]["heuristic"] == h["value"]
    assert result["source"] == "ensemble"
    assert "ml" in result["components"]


def test_scoring_engine_interface():
    """ScoringEngine expone score(features) -> (value, source, components)."""
    engine = ScoringEngine()
    result = engine.score(
        {
            "close": 110.0, "sma20": 100.0, "sma50": 95.0, "sma200": 90.0,
            "rsi": 55.0, "momentum_1m": 2.0, "rel_volume": 1.6, "pct_change": 0.5,
        }
    )
    assert {"value", "source", "components"} <= set(result.keys())
    assert isinstance(result["value"], (int, float))
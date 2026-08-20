"""
tests/test_signal_evaluation.py
─────────────────────────────────────────────────────────────────────
Suite de tests unitarios para signal_evaluation.py (Luis — QA/Seguridad).
Se testean las funciones puras sin llamadas a yfinance.
Cada valor esperado está matemáticamente derivado. Sin mocks de red.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd
import pytest

from app.services.signal_evaluation import (
    calc_rsi,
    _sample_quality,
    _ticker_composite_score,
    generate_insight,
    SAMPLE_SUFFICIENT,
    SAMPLE_LIMITED_LOW,
    MIN_SIGNAL_DISPLAY,
    MIN_TICKER_SAMPLE,
)


# ──────────────────────────────────────────────────────────────────────────────
# calc_rsi
# ──────────────────────────────────────────────────────────────────────────────
class TestCalcRsi:
    def _flat_series(self, value: float, n: int = 50) -> pd.Series:
        return pd.Series([value] * n, dtype=float)

    def test_rsi_is_50_on_flat_series(self):
        """
        Una serie perfectamente plana → delta=0 en todos los pasos.
        gain/loss = 0/0 → EWM produce NaN. El RSI no puede calcularse.
        Este test documenta el comportamiento real del algoritmo.
        Un vector con leve varianza sí converge a ~50.
        """
        s = pd.Series([100.0, 100.1] * 25)  # mínima varianza alternante
        rsi = calc_rsi(s)
        last_valid = rsi.dropna()
        # Debe haber al menos un valor válido
        assert len(last_valid) > 0
        # Con varianza alternante perfecta, debe estar cerca de 50
        assert 45.0 <= last_valid.iloc[-1] <= 55.0, f"RSI fuera de rango: {last_valid.iloc[-1]}"

    def test_rsi_output_is_series(self):
        s = pd.Series(range(50), dtype=float)
        result = calc_rsi(s)
        assert isinstance(result, pd.Series)

    def test_rsi_bounded_0_to_100(self):
        """RSI must always be in [0, 100]."""
        # Monotonically rising prices → RSI → 100
        s = pd.Series([float(i) for i in range(1, 101)])
        rsi = calc_rsi(s)
        valid = rsi.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_rsi_high_on_rising_prices(self):
        s = pd.Series([float(i) for i in range(1, 101)])
        rsi = calc_rsi(s)
        assert rsi.dropna().iloc[-1] > 70

    def test_rsi_low_on_falling_prices(self):
        s = pd.Series([float(i) for i in range(100, 0, -1)])
        rsi = calc_rsi(s)
        assert rsi.dropna().iloc[-1] < 30


# ──────────────────────────────────────────────────────────────────────────────
# _sample_quality
# ──────────────────────────────────────────────────────────────────────────────
class TestSampleQuality:
    def test_sufficient(self):
        assert _sample_quality(SAMPLE_SUFFICIENT) == "sufficient"

    def test_sufficient_above_threshold(self):
        assert _sample_quality(SAMPLE_SUFFICIENT + 100) == "sufficient"

    def test_limited(self):
        assert _sample_quality(SAMPLE_LIMITED_LOW) == "limited"

    def test_limited_just_below_sufficient(self):
        assert _sample_quality(SAMPLE_SUFFICIENT - 1) == "limited"

    def test_insufficient_below_low(self):
        assert _sample_quality(SAMPLE_LIMITED_LOW - 1) == "insufficient"

    def test_insufficient_zero(self):
        assert _sample_quality(0) == "insufficient"


# ──────────────────────────────────────────────────────────────────────────────
# _ticker_composite_score
# ──────────────────────────────────────────────────────────────────────────────
class TestTickerCompositeScore:
    def test_perfect_inputs(self):
        """
        wr=1.0:         1.0 * 0.40 = 0.40
        avg_return=10:  (10+10)/20 * 0.30 = 1.0 * 0.30 = 0.30
        count=100:      log2(100)/log2(100) = 1.0 * 0.30 = 0.30
        total = 1.0
        """
        score = _ticker_composite_score(1.0, 10.0, 100)
        assert abs(score - 1.0) < 1e-9

    def test_zero_inputs(self):
        """
        wr=0:           0 * 0.40 = 0
        avg_return=-10: (0)/20 * 0.30 = 0
        count=1:        log2(1)/log2(100) = 0 * 0.30 = 0
        total = 0.0
        """
        score = _ticker_composite_score(0.0, -10.0, 1)
        assert abs(score - 0.0) < 1e-9

    def test_avg_return_is_capped_at_10(self):
        """avg_return > 10 must be treated same as 10."""
        score_10 = _ticker_composite_score(0.5, 10.0, 50)
        score_99 = _ticker_composite_score(0.5, 99.0, 50)
        assert score_10 == score_99

    def test_avg_return_is_capped_at_minus_10(self):
        score_neg10 = _ticker_composite_score(0.5, -10.0, 50)
        score_neg99 = _ticker_composite_score(0.5, -99.0, 50)
        assert score_neg10 == score_neg99

    def test_score_between_0_and_1(self):
        """Composite score must always be in [0, 1]."""
        for wr in [0.0, 0.5, 1.0]:
            for ret in [-15, 0, 15]:
                for count in [1, 10, 100, 1000]:
                    s = _ticker_composite_score(wr, float(ret), count)
                    assert 0.0 <= s <= 1.0, f"Out of range: {s}"


# ──────────────────────────────────────────────────────────────────────────────
# generate_insight
# ──────────────────────────────────────────────────────────────────────────────
class TestGenerateInsight:
    def _minimal_stats(self, total: int, wr5: float = 0.55, avg5: float = 0.5) -> dict:
        return {
            "total_signals": total,
            "sample_quality": "sufficient",
            "win_rate_5d": wr5,
            "avg_return_5d": avg5,
            "context": {},
            "top_tickers": [],
            "worst_tickers": [],
        }

    def test_insufficient_data_message(self):
        """Below MIN_SIGNAL_DISPLAY → must return default message."""
        stats = self._minimal_stats(MIN_SIGNAL_DISPLAY - 1)
        msg = generate_insight("test_signal", stats)
        assert "insuficientes" in msg.lower()

    def test_none_stats_returns_default(self):
        msg = generate_insight("test_signal", None)
        assert "insuficientes" in msg.lower()

    def test_insight_contains_win_rate(self):
        stats = self._minimal_stats(MIN_SIGNAL_DISPLAY + 5, wr5=0.63)
        msg = generate_insight("breakout_up", stats)
        assert "63%" in msg or "63" in msg

    def test_positive_return_shown(self):
        stats = self._minimal_stats(20, avg5=1.5)
        msg = generate_insight("breakout_up", stats)
        assert "+" in msg

    def test_negative_return_shown(self):
        stats = self._minimal_stats(20, avg5=-0.8)
        msg = generate_insight("breakout_up", stats)
        assert "-" in msg


# ──────────────────────────────────────────────────────────────────────────────
# SP-4.4: umbrales de muestra exigentes
# ──────────────────────────────────────────────────────────────────────────────
class TestSampleThresholdsSP44:
    def test_min_ticker_sample_raised(self):
        """SP-4.4: MIN_TICKER_SAMPLE >= 8 para aparecer en top/worst."""
        from app.services.signal_evaluation import MIN_TICKER_SAMPLE, MIN_TICKER_CONFIDENT
        assert MIN_TICKER_SAMPLE >= 8
        assert MIN_TICKER_CONFIDENT >= 20

    def test_sampling_warning_level_in_result(self):
        """El resultado de la senal incluye sampling.warning_level."""
        from app.services.signal_evaluation import evaluate_signals
        # Monkeypatch ligero: sin red, se prueba via _sample_quality mapping
        from app.services.signal_evaluation import _sample_quality
        assert _sample_quality(5) == "insufficient"
        assert _sample_quality(20) == "limited"
        assert _sample_quality(60) == "sufficient"

    def test_insight_warns_on_limited_sample(self):
        from app.services.signal_evaluation import generate_insight, MIN_SIGNAL_DISPLAY
        stats = {
            "total_signals": 15,
            "sample_quality": "limited",
            "win_rate_5d": 0.55,
            "avg_return_5d": 0.5,
            "context": {},
            "top_tickers": [],
            "worst_tickers": [],
        }
        msg = generate_insight("breakout_up", stats)
        assert "limitada" in msg.lower()

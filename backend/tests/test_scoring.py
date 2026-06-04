"""
tests/test_scoring.py
─────────────────────────────────────────────────────
Suite de pruebas unitarias para el motor de scoring (Luis).
Todos los valores esperados están derivados matemáticamente
de las fórmulas en scoring.py. Sin mocks, sin poesía.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.services.scoring import compute_signal_score, get_confidence_label


# ─────────────────────────────────────────────────────
# get_confidence_label
# ─────────────────────────────────────────────────────
class TestGetConfidenceLabel:
    def test_low_when_profit_factor_below_one(self):
        assert get_confidence_label(200, 0.70, 0.9, 0.5) == "low"

    def test_low_when_expectancy_zero(self):
        assert get_confidence_label(200, 0.70, 1.5, 0.0) == "low"

    def test_low_when_expectancy_negative(self):
        assert get_confidence_label(200, 0.70, 1.5, -0.1) == "low"

    def test_insufficient_sample_below_15(self):
        assert get_confidence_label(14, 0.70, 1.5, 0.5) == "insufficient_sample"

    def test_high_when_100_trades_60pct_wr(self):
        assert get_confidence_label(100, 0.60, 1.5, 0.5) == "high"

    def test_medium_when_40_trades(self):
        assert get_confidence_label(40, 0.55, 1.2, 0.3) == "medium"

    def test_low_when_enough_sample_but_low_wr(self):
        # 100 trades but win_rate < 0.60 → not high; 40+ → medium
        result = get_confidence_label(100, 0.55, 1.2, 0.3)
        assert result == "medium"


# ─────────────────────────────────────────────────────
# compute_signal_score
# ─────────────────────────────────────────────────────
class TestComputeSignalScore:
    def test_perfect_score(self):
        """
        wr=0.65 → 40 pts
        exp=1.0  → 30 pts
        pf=1.5   → 20 pts
        conf=high→ 10 pts
        = 100.0
        """
        stats = {"win_rate_5d": 0.65, "expectancy_5d": 1.0,
                 "profit_factor": 1.5, "confidence": "high"}
        assert compute_signal_score(stats) == 100.0

    def test_zero_score_on_empty_stats(self):
        """All zero inputs → score must be 0."""
        assert compute_signal_score({}) == 0.0

    def test_score_capped_at_100(self):
        """Super-stats must not exceed 100."""
        stats = {"win_rate_5d": 0.99, "expectancy_5d": 10.0,
                 "profit_factor": 5.0, "confidence": "high"}
        assert compute_signal_score(stats) == 100.0

    def test_partial_score(self):
        """
        wr=0.55: (0.55-0.45)/0.20 = 0.5 * 40 = 20 pts
        exp=0.5: 0.5/1.0 = 0.5 * 30 = 15 pts
        pf=1.25: (1.25-1.0)/0.5 = 0.5 * 20 = 10 pts
        conf=medium: 5 pts
        Total = 50.0
        """
        stats = {"win_rate_5d": 0.55, "expectancy_5d": 0.5,
                 "profit_factor": 1.25, "confidence": "medium"}
        assert compute_signal_score(stats) == 50.0

    def test_score_never_negative(self):
        stats = {"win_rate_5d": 0.10, "expectancy_5d": -5.0,
                 "profit_factor": 0.1, "confidence": "low"}
        assert compute_signal_score(stats) >= 0.0

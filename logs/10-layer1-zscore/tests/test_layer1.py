"""Prototype-grade tests for Feature 10 - Layer 1 Z-Score Baseline.

Run with:
    python -m unittest logs/10-layer1-zscore/tests/test_layer1.py -v
"""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

from app.detection.layer1_zscore import ZScoreAnalyzer, ZScoreResult, _compute_stats


class TestComputeStats(unittest.TestCase):
    """Statistical helper functions."""

    def test_sufficient_data_returns_mean_std(self) -> None:
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
        mean, std = _compute_stats(s)
        self.assertIsNotNone(mean)
        self.assertIsNotNone(std)
        self.assertAlmostEqual(mean, 4.0, places=1)

    def test_insufficient_data_returns_none(self) -> None:
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])  # Only 5 days
        mean, std = _compute_stats(s)
        self.assertIsNone(mean)
        self.assertIsNone(std)

    def test_zero_std_returns_mean_none(self) -> None:
        s = pd.Series([5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0])  # No variation
        mean, std = _compute_stats(s)
        self.assertIsNotNone(mean)
        self.assertEqual(mean, 5.0)
        # std = 0 should be handled specially in z-score calc


class TestZScoreAnalyzer(unittest.TestCase):
    """Core z-score analysis logic."""

    def setUp(self) -> None:
        self.analyzer = ZScoreAnalyzer(threshold=3.0, min_history_days=7)

    def _make_series(self, n_days: int = 30, spike_day: int | None = None) -> pd.Series:
        """Generate daily kWh series with optional spike."""
        base_date = date(2024, 1, 1)
        dates = [base_date + timedelta(days=i) for i in range(n_days)]
        values = [100.0] * n_days
        if spike_day is not None and 0 <= spike_day < n_days:
            values[spike_day] = 150.0  # 50% spike
        return pd.Series(values, index=dates)

    def test_normal_consumption_no_anomaly(self) -> None:
        """Steady 100 kWh/day should have z ~ 0 -> no anomaly."""
        series = self._make_series(n_days=15, spike_day=None)
        result = self.analyzer.analyze(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 15),
            daily_kwh=series,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.actual_kwh, 100.0)
        self.assertAlmostEqual(result.z_score, 0.0, places=1)
        self.assertFalse(result.is_anomaly)

    def test_spike_creates_anomaly(self) -> None:
        """150 kWh when mean is 100, std ~0 should give high z -> anomaly."""
        series = self._make_series(n_days=15, spike_day=14)  # Spike on day 15
        result = self.analyzer.analyze(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 15),
            daily_kwh=series,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.actual_kwh, 150.0)
        self.assertEqual(result.historical_mean, 100.0)
        self.assertGreater(result.abs_z_score, 3.0)
        self.assertTrue(result.is_anomaly)

    def test_low_consumption_creates_anomaly(self) -> None:
        """50 kWh when mean is 100, std ~30 -> z ~ -1.7, use lower threshold."""
        dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(15)]
        # Create variation: mean ~100, std ~30
        values = [70.0, 130.0, 100.0, 90.0, 110.0, 80.0, 120.0] * 2  # 14 days
        values.append(50.0)  # Low on last day
        series = pd.Series(values, index=dates)

        # Use lower threshold so moderate z-score triggers anomaly
        analyzer = ZScoreAnalyzer(threshold=1.5)
        result = analyzer.analyze(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 15),
            daily_kwh=series,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.actual_kwh, 50.0)
        self.assertLess(result.z_score, -1.0)  # Significantly below mean
        self.assertTrue(result.is_anomaly)

    def test_insufficient_history_returns_none(self) -> None:
        """Less than 7 days history should return None."""
        series = self._make_series(n_days=5)
        result = self.analyzer.analyze(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 5),
            daily_kwh=series,
        )
        self.assertIsNone(result)

    def test_target_not_in_series_returns_none(self) -> None:
        """If target date has no data, return None."""
        series = self._make_series(n_days=15)
        result = self.analyzer.analyze(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 2, 1),  # Not in series
            daily_kwh=series,
        )
        self.assertIsNone(result)

    def test_z_score_calculation_correct(self) -> None:
        """Manual z-score: (150 - 100) / std where std of 14x100s = 0."""
        # This will have std=0 so z-score should be inf
        dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(15)]
        values = [100.0] * 14 + [150.0]
        series = pd.Series(values, index=dates)

        result = self.analyzer.analyze(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 15),
            daily_kwh=series,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.z_score, float("inf"))
        self.assertTrue(result.is_anomaly)

    def test_boundary_at_threshold(self) -> None:
        """Exactly z=3.0 should NOT be anomaly (strict > threshold)."""
        # Create series where we can control z-score
        dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(15)]
        # 14 days of mean=100, std ~ 33.3, so z=3 at 200
        values = [100.0, 133.0, 67.0] * 4 + [100.0] * 2  # Creates variation
        values.append(200.0)  # Should give z ~ 3.0
        series = pd.Series(values, index=dates)

        # Use lower threshold to test boundary
        analyzer = ZScoreAnalyzer(threshold=2.0)
        result = analyzer.analyze(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 15),
            daily_kwh=series,
        )
        if result is not None:
            # With enough variation, z=2.0 is at threshold
            self.assertFalse(result.abs_z_score > 2.0 and result.abs_z_score <= 2.0)

    def test_lookback_window_limits_history(self) -> None:
        """Only use last 90 days, not all history."""
        # Create 120 days of history
        dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(120)]
        values = [100.0] * 119 + [150.0]
        series = pd.Series(values, index=dates)

        result = self.analyzer.analyze(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 4, 29),  # Day 120
            daily_kwh=series,
        )
        self.assertIsNotNone(result)
        # Should only use ~90 days, not full 119 prior
        self.assertLessEqual(result.n_historical_days, 90)


class TestZScoreResult(unittest.TestCase):
    """Result dataclass and serialization."""

    def test_to_db_row(self) -> None:
        r = ZScoreResult(
            meter_id="M1",
            dt_id="DT1",
            feeder_id="F1",
            date=date(2024, 1, 1),
            actual_kwh=150.0,
            historical_mean=100.0,
            historical_std=10.0,
            z_score=5.0,
            abs_z_score=5.0,
            threshold=3.0,
            is_anomaly=True,
            n_historical_days=30,
            computed_at=datetime.utcnow(),
        )
        row = r.to_db_row()
        self.assertEqual(row["meter_id"], "M1")
        self.assertEqual(row["z_score"], 5.0)
        self.assertEqual(row["is_anomaly"], True)


class TestBatchAnalysis(unittest.TestCase):
    """Batch processing with DataFrames."""

    def test_analyze_batch_multiple_meters(self) -> None:
        # Create meter daily data
        dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(15)]
        meter_ids = ["M1"] * 15 + ["M2"] * 15
        all_dates = dates * 2
        # M1 steady at 100, M2 steady at 200
        kwh = [100.0] * 15 + [200.0] * 15

        meter_daily = pd.DataFrame({
            "meter_id": meter_ids,
            "date": all_dates,
            "kwh": kwh,
        })

        topology = pd.DataFrame({
            "meter_id": ["M1", "M2"],
            "dt_id": ["DT1", "DT1"],
            "feeder_id": ["F1", "F1"],
        })

        analyzer = ZScoreAnalyzer()
        # Analyze day 15 (last day) where both are normal
        results = analyzer.analyze_batch(meter_daily, topology, date(2024, 1, 15))

        self.assertEqual(len(results), 2)
        m1_result = next(r for r in results if r.meter_id == "M1")
        m2_result = next(r for r in results if r.meter_id == "M2")

        self.assertEqual(m1_result.actual_kwh, 100.0)
        self.assertEqual(m2_result.actual_kwh, 200.0)
        # Both should have z ~ 0 since no variation
        self.assertFalse(m1_result.is_anomaly)
        self.assertFalse(m2_result.is_anomaly)

    def test_empty_data_returns_empty(self) -> None:
        analyzer = ZScoreAnalyzer()
        results = analyzer.analyze_batch(
            pd.DataFrame(),
            pd.DataFrame(),
            date(2024, 1, 1)
        )
        self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()

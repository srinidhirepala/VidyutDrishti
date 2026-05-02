"""Prototype-grade tests for Feature 07 - Forecast Backtest & Baselines.

Run with:
    python -m unittest logs/07-forecast-backtest/tests/test_evaluation.py -v
"""

from __future__ import annotations

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

from app.evaluation.baselines import NaiveBaseline, baseline_comparison
from app.evaluation.backtest import BacktestReport, Backtester, day7_match_accuracy, horizon_mapes
from app.evaluation.metrics import bias, mae, mape, rmse


class TestMetrics(unittest.TestCase):
    """Core metric calculations."""

    def test_mape_basic(self) -> None:
        y_true = np.array([100.0, 100.0, 100.0])
        y_pred = np.array([90.0, 100.0, 110.0])
        # Errors: 10%, 0%, 10% -> mean 6.67%
        result = mape(y_true, y_pred)
        self.assertAlmostEqual(result, 20.0 / 3.0, places=1)

    def test_mape_ignores_zero_actuals(self) -> None:
        y_true = np.array([0.0, 100.0, 100.0])
        y_pred = np.array([50.0, 90.0, 110.0])
        # First row ignored, remaining: 10%, 10% -> 10%
        result = mape(y_true, y_pred)
        self.assertAlmostEqual(result, 10.0, places=1)

    def test_mape_all_zeros_returns_inf(self) -> None:
        y_true = np.array([0.0, 0.0])
        y_pred = np.array([10.0, 20.0])
        result = mape(y_true, y_pred)
        self.assertEqual(result, float("inf"))

    def test_rmse(self) -> None:
        y_true = np.array([100.0, 100.0, 100.0])
        y_pred = np.array([90.0, 100.0, 110.0])
        # Squared errors: 100, 0, 100 -> mean 66.67 -> sqrt = 8.16
        result = rmse(y_true, y_pred)
        self.assertAlmostEqual(result, np.sqrt(200 / 3), places=1)

    def test_mae(self) -> None:
        y_true = np.array([100.0, 100.0, 100.0])
        y_pred = np.array([90.0, 100.0, 110.0])
        result = mae(y_true, y_pred)
        self.assertEqual(result, 20.0 / 3.0)

    def test_bias_positive_over_forecast(self) -> None:
        y_true = np.array([100.0, 100.0])
        y_pred = np.array([110.0, 110.0])
        result = bias(y_true, y_pred)
        self.assertEqual(result, 10.0)

    def test_bias_negative_under_forecast(self) -> None:
        y_true = np.array([100.0, 100.0])
        y_pred = np.array([90.0, 90.0])
        result = bias(y_true, y_pred)
        self.assertEqual(result, -10.0)


class TestNaiveBaseline(unittest.TestCase):
    """Yesterday = Today baseline."""

    def test_predict_returns_yesterday(self) -> None:
        dates = pd.date_range("2024-01-01", periods=5, freq="D")
        df = pd.DataFrame({"ds": dates, "y": [100.0, 110.0, 120.0, 130.0, 140.0]})
        baseline = NaiveBaseline(df)

        # Predict 2024-01-03 should return 2024-01-02's value (110)
        result = baseline.predict(date(2024, 1, 3))
        self.assertEqual(result, 110.0)

    def test_predict_missing_date_returns_none(self) -> None:
        dates = pd.date_range("2024-01-01", periods=3, freq="D")
        df = pd.DataFrame({"ds": dates, "y": [100.0, 110.0, 120.0]})
        baseline = NaiveBaseline(df)

        # Predict 2024-01-10 (no previous day in data)
        result = baseline.predict(date(2024, 1, 10))
        self.assertIsNone(result)

    def test_forecast_all_adds_baseline_column(self) -> None:
        dates = pd.date_range("2024-01-01", periods=5, freq="D")
        df = pd.DataFrame({"ds": dates, "y": [100.0, 110.0, 120.0, 130.0, 140.0]})
        baseline = NaiveBaseline(df)
        result = baseline.forecast_all()

        self.assertIn("yhat_baseline", result.columns)
        # First row has NaN baseline (no previous day), rest shifted
        self.assertTrue(pd.isna(result["yhat_baseline"].iloc[0]))
        self.assertEqual(result["yhat_baseline"].iloc[1], 100.0)
        self.assertEqual(result["yhat_baseline"].iloc[2], 110.0)


class TestBaselineComparison(unittest.TestCase):
    """Model vs baseline comparison."""

    def test_model_beats_baseline(self) -> None:
        # Model perfect on trending data, baseline lags behind
        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        y = [100.0 + i * 10 for i in range(10)]  # Trend: 100, 110, 120, ..., 190
        df = pd.DataFrame({
            "ds": dates,
            "y": y,
            "yhat": y,  # Perfect model follows trend exactly
        })
        result = baseline_comparison(df)
        # Baseline (yesterday's value) will be ~5-10% off on this steep trend
        self.assertTrue(result.beats_baseline)
        self.assertEqual(result.model_mape, 0.0)
        self.assertGreater(result.improvement_percent, 0.0)

    def test_baseline_beats_model(self) -> None:
        # Flat data where baseline (persistence) is perfect but model has error
        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        df = pd.DataFrame({
            "ds": dates,
            "y": [100.0] * 10,  # Flat series
            "yhat": [110.0] * 10,  # Model 10% too high
        })
        result = baseline_comparison(df)
        # On flat data, baseline (yesterday = today) is perfect
        self.assertFalse(result.beats_baseline)
        self.assertEqual(result.baseline_mape, 0.0)
        self.assertLess(result.improvement_percent, 0.0)

    def test_insufficient_data_returns_inf(self) -> None:
        df = pd.DataFrame({
            "ds": [pd.Timestamp("2024-01-01")],
            "y": [100.0],
            "yhat": [100.0],
        })
        result = baseline_comparison(df)
        self.assertEqual(result.model_mape, float("inf"))


class TestDay7MatchAccuracy(unittest.TestCase):
    """Day-7 within ±10% accuracy (eval target: 85%)."""

    def test_all_within_tolerance_meets_target(self) -> None:
        # 10 forecasts, all within ±10%
        df = pd.DataFrame({
            "y": [100.0] * 10,
            "yhat": [105.0] * 10,  # 5% error
            "horizon_days": [7] * 10,
        })
        result = day7_match_accuracy(df)
        self.assertEqual(result.total_forecasts, 10)
        self.assertEqual(result.within_tolerance, 10)
        self.assertEqual(result.match_percent, 100.0)
        self.assertTrue(result.meets_target)

    def test_half_within_tolerance_fails_target(self) -> None:
        # 10 forecasts, 5 within ±10%, 5 outside
        df = pd.DataFrame({
            "y": [100.0] * 10,
            "yhat": [105.0, 105.0, 105.0, 105.0, 105.0,  # 5% error (within)
                     120.0, 120.0, 120.0, 120.0, 120.0],  # 20% error (outside)
            "horizon_days": [7] * 10,
        })
        result = day7_match_accuracy(df)
        self.assertEqual(result.within_tolerance, 5)
        self.assertEqual(result.match_percent, 50.0)
        self.assertFalse(result.meets_target)

    def test_boundary_within_tolerance(self) -> None:
        # Exactly 10% error should be within tolerance
        df = pd.DataFrame({
            "y": [100.0],
            "yhat": [110.0],  # Exactly 10% error
            "horizon_days": [7],
        })
        result = day7_match_accuracy(df)
        self.assertEqual(result.within_tolerance, 1)

    def test_just_outside_tolerance(self) -> None:
        # 10.1% error should be outside
        df = pd.DataFrame({
            "y": [100.0],
            "yhat": [110.1],  # 10.1% error
            "horizon_days": [7],
        })
        result = day7_match_accuracy(df, tolerance=0.10)
        self.assertEqual(result.within_tolerance, 0)


class TestHorizonMapes(unittest.TestCase):
    """MAPE by horizon day."""

    def test_calculates_per_horizon(self) -> None:
        df = pd.DataFrame({
            "y": [100.0, 100.0, 100.0, 100.0],
            "yhat": [100.0, 110.0, 120.0, 130.0],  # 0%, 10%, 20%, 30% errors
            "horizon_days": [1, 2, 3, 4],
        })
        result = horizon_mapes(df)
        self.assertEqual(result[1], 0.0)
        self.assertEqual(result[2], 10.0)
        self.assertEqual(result[3], 20.0)
        self.assertEqual(result[4], 30.0)
        self.assertTrue(np.isnan(result[5]))  # No data


class TestBacktester(unittest.TestCase):
    """End-to-end backtest report."""

    def test_full_backtest_report(self) -> None:
        dates = pd.date_range("2024-01-01", periods=14, freq="D")
        # Model slightly better than naive baseline
        df = pd.DataFrame({
            "ds": dates,
            "y": [100.0 + i * 10 for i in range(14)],  # Trend: 100, 110, 120...
            "yhat": [105.0 + i * 10 for i in range(14)],  # Model: slight overprediction
        })

        backtester = Backtester(
            df=df,
            feeder_id="F1",
            model_version="v1",
            day7_target=85.0,
            day7_tolerance=0.10,
        )
        report = backtester.run()

        self.assertIsInstance(report, BacktestReport)
        self.assertEqual(report.feeder_id, "F1")
        self.assertEqual(report.model_version, "v1")
        self.assertEqual(report.total_rows, 14)
        self.assertGreater(report.overall_mape, 0.0)
        self.assertIsNotNone(report.baseline_result)
        self.assertIsNotNone(report.day7_match)

    def test_missing_columns_raises(self) -> None:
        df = pd.DataFrame({"wrong_column": [1, 2, 3]})
        backtester = Backtester(df, "F1", "v1")
        with self.assertRaises(ValueError):
            backtester.run()


if __name__ == "__main__":
    unittest.main()

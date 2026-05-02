"""Prototype-grade tests for Feature 05 - Prophet Forecasting.

Run with:
    python -m unittest logs/05-prophet-forecasting/tests/test_forecasting.py -v

Tests are skipped if Prophet is not installed.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

from app.forecasting.models import PROPHET_AVAILABLE, ForecastModel, ForecastResult
from app.forecasting.service import ForecastService


# Skip all tests if Prophet not available
@unittest.skipUnless(PROPHET_AVAILABLE, "Prophet not installed")
class TestForecastService(unittest.TestCase):
    """End-to-end forecasting tests with Prophet."""

    def _synthetic_daily(self, n_days: int = 90, seed: int = 42) -> pd.DataFrame:
        """Generate synthetic daily feeder load with weekly seasonality."""
        rng = np.random.default_rng(seed)
        base = datetime(2024, 1, 1)
        dates = [base + timedelta(days=i) for i in range(n_days)]
        # Weekly pattern: higher on weekdays, lower on weekends
        weekday_factor = [1.0 if d.weekday() < 5 else 0.7 for d in dates]
        trend = np.linspace(1000, 1200, n_days)
        noise = rng.normal(0, 50, n_days)
        y = (np.array(weekday_factor) * trend) + noise
        return pd.DataFrame({"ds": dates, "y": y})

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.service = ForecastService(Path(self.tmpdir.name))

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_train_creates_model(self) -> None:
        df = self._synthetic_daily(60)
        model = self.service.train("F1", df)
        self.assertIsNotNone(model)
        self.assertEqual(model.feeder_id, "F1")
        self.assertEqual(model.training_rows, 60)
        self.assertIsNotNone(model.model_version)

    def test_model_save_and_load(self) -> None:
        df = self._synthetic_daily(60)
        model = self.service.train("F1", df)
        assert model is not None
        path = self.service.save(model)
        self.assertTrue(path.exists())

        loaded = self.service.load("F1", model.model_version)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.feeder_id, model.feeder_id)
        self.assertEqual(loaded.model_version, model.model_version)
        self.assertEqual(loaded.training_rows, model.training_rows)

    def test_forecast_returns_results(self) -> None:
        df = self._synthetic_daily(90)
        model = self.service.train("F1", df)
        assert model is not None

        future = [date(2024, 4, 1) + timedelta(days=i) for i in range(7)]
        results = self.service.forecast(model, future)
        self.assertEqual(len(results), 7)

        for r in results:
            self.assertEqual(r.feeder_id, "F1")
            self.assertGreater(r.yhat, 0)
            self.assertLess(r.yhat_lower, r.yhat)
            self.assertGreater(r.yhat_upper, r.yhat)

    def test_forecast_result_to_db_row(self) -> None:
        r = ForecastResult(
            feeder_id="F1",
            forecast_date=date(2024, 4, 1),
            yhat=1000.0,
            yhat_lower=900.0,
            yhat_upper=1100.0,
            model_version="abc123",
            generated_at=datetime.utcnow(),
        )
        row = r.to_db_row()
        self.assertEqual(row["feeder_id"], "F1")
        self.assertEqual(row["yhat"], 1000.0)

    def test_backtest_returns_metrics(self) -> None:
        df = self._synthetic_daily(120)  # Need more data for CV
        metrics = self.service.backtest(df, initial="60 days", period="30 days", horizon="7 days")
        self.assertIsNotNone(metrics)
        self.assertIn("mape", metrics.columns)

        mape = self.service.mape(metrics)
        self.assertIsNotNone(mape)
        self.assertGreater(mape, 0)
        self.assertLess(mape, 50)  # Should be reasonable for synthetic data

    def test_mape_stored_in_model(self) -> None:
        df = self._synthetic_daily(120)
        model = self.service.train("F1", df)
        assert model is not None

        metrics = self.service.backtest(df, initial="60 days", period="30 days", horizon="7 days")
        model.mape = self.service.mape(metrics)

        self.assertIsNotNone(model.mape)
        self.assertGreater(model.mape, 0)

    def test_version_is_deterministic(self) -> None:
        df1 = self._synthetic_daily(60, seed=1)
        df2 = self._synthetic_daily(60, seed=1)  # Same seed
        df3 = self._synthetic_daily(60, seed=2)  # Different seed

        m1 = self.service.train("F1", df1)
        m2 = self.service.train("F1", df2)
        m3 = self.service.train("F1", df3)

        assert m1 is not None and m2 is not None and m3 is not None
        self.assertEqual(m1.model_version, m2.model_version)
        self.assertNotEqual(m1.model_version, m3.model_version)


@unittest.skipUnless(PROPHET_AVAILABLE, "Prophet not installed")
class TestForecastModelPersistence(unittest.TestCase):
    """Model save/load edge cases."""

    def test_load_missing_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = ForecastService(Path(tmp))
            loaded = service.load("F99", "nonexistent")
            self.assertIsNone(loaded)

    def test_list_models_empty_when_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = ForecastService(Path(tmp))
            models = service.list_models("F99")
            self.assertEqual(models, [])


class TestWithoutProphet(unittest.TestCase):
    """Tests that work even without Prophet installed."""

    def test_result_dataclass_works(self) -> None:
        r = ForecastResult(
            feeder_id="F1",
            forecast_date=date(2024, 4, 1),
            yhat=1000.0,
            yhat_lower=900.0,
            yhat_upper=1100.0,
            model_version="v1",
            generated_at=datetime.utcnow(),
        )
        self.assertEqual(r.yhat, 1000.0)

    def test_model_save_without_prophet(self) -> None:
        """Model.save should work even if Prophet model is None."""
        with tempfile.TemporaryDirectory() as tmp:
            model = ForecastModel(
                feeder_id="F1",
                model=None,
                trained_at=datetime.utcnow(),
                training_rows=0,
                model_version="test",
            )
            path = model.save(Path(tmp))
            self.assertTrue(path.exists())

            loaded = ForecastModel.load(path)
            self.assertEqual(loaded.feeder_id, "F1")
            self.assertIsNone(loaded.model)


if __name__ == "__main__":
    unittest.main()

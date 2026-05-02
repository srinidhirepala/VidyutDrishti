"""Prototype-grade tests for Feature 12 - Layer 3 Isolation Forest.

Run with:
    python -m unittest logs/12-layer3-isoforest/tests/test_layer3.py -v

Tests are skipped if scikit-learn is not installed.
"""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

from app.detection.layer3_isoforest import (
    SKLEARN_AVAILABLE,
    IsoForestAnalyzer,
    IsoForestResult,
)


@unittest.skipUnless(SKLEARN_AVAILABLE, "scikit-learn not installed")
class TestIsoForestAnalyzer(unittest.TestCase):
    """Isolation Forest training and scoring."""

    def _make_train_data(self, n: int = 100) -> pd.DataFrame:
        """Generate normal training data."""
        np.random.seed(42)
        return pd.DataFrame({
            "meter_id": [f"M{i}" for i in range(n)],
            "dt_id": ["DT1"] * n,
            "feeder_id": ["F1"] * n,
            "date": [date(2024, 1, 1)] * n,
            "total_kwh": np.random.normal(100, 10, n),
            "rolling7_kwh": np.random.normal(100, 10, n),
            "peak_hour_kwh": np.random.normal(5, 1, n),
            "trough_hour_kwh": np.random.normal(1, 0.2, n),
            "diurnal_mean": np.random.normal(2, 0.5, n),
            "temp_ratio": np.random.normal(1.0, 0.1, n),
            "meter_health_score": np.random.uniform(0.8, 1.0, n),
        })

    def test_train_creates_model(self) -> None:
        train_df = self._make_train_data(100)
        analyzer = IsoForestAnalyzer()
        success = analyzer.train(train_df)
        self.assertTrue(success)
        self.assertIsNotNone(analyzer.model)
        self.assertIsNotNone(analyzer.model_version)

    def test_analyze_returns_result(self) -> None:
        train_df = self._make_train_data(100)
        analyzer = IsoForestAnalyzer()
        analyzer.train(train_df)

        features = pd.Series({
            "total_kwh": 150.0,
            "rolling7_kwh": 150.0,
            "peak_hour_kwh": 10.0,
            "trough_hour_kwh": 0.5,
            "diurnal_mean": 3.0,
            "temp_ratio": 1.5,
            "meter_health_score": 0.9,
        })

        result = analyzer.analyze(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 2),
            features=features,
        )
        self.assertIsNotNone(result)
        self.assertIsInstance(result, IsoForestResult)
        self.assertEqual(result.meter_id, "M1")
        self.assertIn("anomaly_score", result.to_db_row())

    def test_normal_data_not_anomaly(self) -> None:
        """Data similar to training should not be anomaly."""
        train_df = self._make_train_data(100)
        analyzer = IsoForestAnalyzer()
        analyzer.train(train_df)

        # Features close to training distribution
        features = pd.Series({
            "total_kwh": 100.0,
            "rolling7_kwh": 100.0,
            "peak_hour_kwh": 5.0,
            "trough_hour_kwh": 1.0,
            "diurnal_mean": 2.0,
            "temp_ratio": 1.0,
            "meter_health_score": 0.9,
        })

        result = analyzer.analyze(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 2),
            features=features,
        )
        self.assertIsNotNone(result)
        # Normal data should have score > threshold
        self.assertFalse(result.is_anomaly)

    def test_extreme_data_is_anomaly(self) -> None:
        """Data far from training distribution should be anomaly."""
        train_df = self._make_train_data(100)
        analyzer = IsoForestAnalyzer(contamination=0.1)
        analyzer.train(train_df)

        # Extreme features
        features = pd.Series({
            "total_kwh": 500.0,  # Way above normal ~100
            "rolling7_kwh": 500.0,
            "peak_hour_kwh": 50.0,
            "trough_hour_kwh": 10.0,
            "diurnal_mean": 10.0,
            "temp_ratio": 5.0,
            "meter_health_score": 0.1,
        })

        result = analyzer.analyze(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 2),
            features=features,
        )
        self.assertIsNotNone(result)
        # Extreme data should be flagged
        self.assertTrue(result.is_anomaly)

    def test_insufficient_train_data_returns_false(self) -> None:
        """Need at least 10 samples to train."""
        train_df = self._make_train_data(5)
        analyzer = IsoForestAnalyzer()
        success = analyzer.train(train_df)
        self.assertFalse(success)

    def test_untrained_analyze_returns_none(self) -> None:
        analyzer = IsoForestAnalyzer()
        features = pd.Series({"total_kwh": 100.0})
        result = analyzer.analyze(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 1),
            features=features,
        )
        self.assertIsNone(result)

    def test_missing_features_returns_none(self) -> None:
        train_df = self._make_train_data(100)
        analyzer = IsoForestAnalyzer()
        analyzer.train(train_df)

        # Features with none of the expected columns
        features = pd.Series({"wrong_column": 100.0})
        result = analyzer.analyze(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 1),
            features=features,
        )
        self.assertIsNone(result)


@unittest.skipUnless(SKLEARN_AVAILABLE, "scikit-learn not installed")
class TestIsoForestBatch(unittest.TestCase):
    """Batch processing."""

    def test_analyze_batch(self) -> None:
        train_df = pd.DataFrame({
            "meter_id": [f"M{i}" for i in range(100)],
            "dt_id": ["DT1"] * 100,
            "feeder_id": ["F1"] * 100,
            "date": [date(2024, 1, 1)] * 100,
            "total_kwh": [100.0] * 100,
            "rolling7_kwh": [100.0] * 100,
        })

        analyzer = IsoForestAnalyzer()
        analyzer.train(train_df)

        analyze_df = pd.DataFrame({
            "meter_id": ["M1", "M2", "M3"],
            "dt_id": ["DT1"] * 3,
            "feeder_id": ["F1"] * 3,
            "date": [date(2024, 1, 2)] * 3,
            "total_kwh": [100.0, 200.0, 100.0],
            "rolling7_kwh": [100.0, 200.0, 100.0],
        })

        results = analyzer.analyze_batch(analyze_df)
        self.assertEqual(len(results), 3)

    def test_empty_batch_returns_empty(self) -> None:
        train_df = pd.DataFrame({
            "meter_id": ["M1"],
            "dt_id": ["DT1"],
            "feeder_id": ["F1"],
            "date": [date(2024, 1, 1)],
            "total_kwh": [100.0],
            "rolling7_kwh": [100.0],
        })

        analyzer = IsoForestAnalyzer()
        analyzer.train(train_df)

        results = analyzer.analyze_batch(pd.DataFrame())
        self.assertEqual(len(results), 0)


@unittest.skipUnless(SKLEARN_AVAILABLE, "scikit-learn not installed")
class TestIsoForestResult(unittest.TestCase):
    """Result dataclass and serialization."""

    def test_to_db_row(self) -> None:
        r = IsoForestResult(
            meter_id="M1",
            dt_id="DT1",
            feeder_id="F1",
            date=date(2024, 1, 1),
            anomaly_score=-0.8,
            is_anomaly=True,
            feature_names=["total_kwh", "rolling7_kwh"],
            feature_values=[150.0, 150.0],
            model_version="abc123",
            computed_at=datetime.utcnow(),
        )
        row = r.to_db_row()
        self.assertEqual(row["meter_id"], "M1")
        self.assertEqual(row["anomaly_score"], -0.8)
        self.assertEqual(row["is_anomaly"], True)
        self.assertEqual(row["feature_names"], ["total_kwh", "rolling7_kwh"])


class TestWithoutSklearn(unittest.TestCase):
    """Tests that work even without sklearn installed."""

    def test_result_dataclass_works(self) -> None:
        r = IsoForestResult(
            meter_id="M1",
            dt_id="DT1",
            feeder_id="F1",
            date=date(2024, 1, 1),
            anomaly_score=-0.5,
            is_anomaly=True,
            feature_names=["total_kwh"],
            feature_values=[100.0],
            model_version="v1",
            computed_at=datetime.utcnow(),
        )
        self.assertEqual(r.anomaly_score, -0.5)


if __name__ == "__main__":
    unittest.main()

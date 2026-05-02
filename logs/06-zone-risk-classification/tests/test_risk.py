"""Prototype-grade tests for Feature 06 - Zone Risk Classification.

Run with:
    python -m unittest logs/06-zone-risk-classification/tests/test_risk.py -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

from app.risk.classifier import (
    DEFAULT_HIGH_THRESHOLD,
    DEFAULT_MEDIUM_THRESHOLD,
    FeederCapacity,
    ZoneRiskClassifier,
    classify_zones,
)
from app.risk.models import RiskLevel, ZoneRiskResult


class TestRiskLevelEnum(unittest.TestCase):
    """RiskLevel ordering and comparison."""

    def test_high_is_most_severe(self) -> None:
        self.assertLess(RiskLevel.HIGH, RiskLevel.MEDIUM)
        self.assertLess(RiskLevel.MEDIUM, RiskLevel.LOW)
        self.assertLess(RiskLevel.HIGH, RiskLevel.LOW)

    def test_high_greater_than_medium(self) -> None:
        self.assertGreater(RiskLevel.MEDIUM, RiskLevel.HIGH)
        self.assertGreater(RiskLevel.LOW, RiskLevel.MEDIUM)

    def test_string_values(self) -> None:
        self.assertEqual(RiskLevel.HIGH.value, "HIGH")
        self.assertEqual(RiskLevel.MEDIUM.value, "MEDIUM")
        self.assertEqual(RiskLevel.LOW.value, "LOW")


class TestZoneRiskResult(unittest.TestCase):
    """Result dataclass and serialization."""

    def test_to_db_row(self) -> None:
        r = ZoneRiskResult(
            feeder_id="F1",
            forecast_date=date(2024, 4, 1),
            level=RiskLevel.HIGH,
            predicted_peak_kw=1500.0,
            capacity_kva=2000.0,
            headroom_percent=10.0,
            computed_at=datetime.utcnow(),
        )
        row = r.to_db_row()
        self.assertEqual(row["feeder_id"], "F1")
        self.assertEqual(row["level"], "HIGH")
        self.assertEqual(row["predicted_peak_kw"], 1500.0)
        self.assertIn("ts", row)


class TestZoneRiskClassifier(unittest.TestCase):
    """Core classification logic."""

    def setUp(self) -> None:
        self.clf = ZoneRiskClassifier()

    def test_high_risk_when_headroom_below_10_percent(self) -> None:
        # capacity 1000 kW, predicted 950 kW -> 5% headroom -> HIGH
        cap = FeederCapacity("F1", capacity_kva=1111.0, historical_peak_kw=None)  # ~1000 kW at 0.9 PF
        result = self.clf.classify("F1", date(2024, 4, 1), 950.0, cap)
        self.assertEqual(result.level, RiskLevel.HIGH)
        self.assertLess(result.headroom_percent, DEFAULT_HIGH_THRESHOLD)

    def test_medium_risk_when_headroom_between_10_and_25_percent(self) -> None:
        # capacity 1000 kW, predicted 850 kW -> 15% headroom -> MEDIUM
        cap = FeederCapacity("F1", capacity_kva=1111.0, historical_peak_kw=None)
        result = self.clf.classify("F1", date(2024, 4, 1), 850.0, cap)
        self.assertEqual(result.level, RiskLevel.MEDIUM)
        self.assertGreaterEqual(result.headroom_percent, DEFAULT_HIGH_THRESHOLD)
        self.assertLess(result.headroom_percent, DEFAULT_MEDIUM_THRESHOLD)

    def test_low_risk_when_headroom_above_25_percent(self) -> None:
        # capacity 1000 kW, predicted 700 kW -> 30% headroom -> LOW
        cap = FeederCapacity("F1", capacity_kva=1111.0, historical_peak_kw=None)
        result = self.clf.classify("F1", date(2024, 4, 1), 700.0, cap)
        self.assertEqual(result.level, RiskLevel.LOW)
        self.assertGreaterEqual(result.headroom_percent, DEFAULT_MEDIUM_THRESHOLD)

    def test_high_risk_when_overloaded(self) -> None:
        # capacity 1000 kW, predicted 1100 kW -> negative headroom -> HIGH
        cap = FeederCapacity("F1", capacity_kva=1111.0, historical_peak_kw=None)
        result = self.clf.classify("F1", date(2024, 4, 1), 1100.0, cap)
        self.assertEqual(result.level, RiskLevel.HIGH)
        self.assertLess(result.headroom_percent, 0)

    def test_uses_historical_peak_when_capacity_kva_missing(self) -> None:
        # historical peak 800 kW -> capacity 960 kW (800 * 1.2)
        cap = FeederCapacity("F1", capacity_kva=None, historical_peak_kw=800.0)
        result = self.clf.classify("F1", date(2024, 4, 1), 900.0, cap)
        # 960 capacity, 900 predicted -> ~6% headroom -> HIGH
        self.assertEqual(result.level, RiskLevel.HIGH)
        self.assertIsNone(result.capacity_kva)  # Original preserved in result

    def test_assumes_high_when_no_capacity_data(self) -> None:
        cap = FeederCapacity("F1", capacity_kva=None, historical_peak_kw=None)
        result = self.clf.classify("F1", date(2024, 4, 1), 1000.0, cap)
        self.assertEqual(result.level, RiskLevel.HIGH)
        self.assertEqual(result.headroom_percent, -50.0)  # Default worst case

    def test_custom_thresholds(self) -> None:
        clf = ZoneRiskClassifier(high_threshold=5.0, medium_threshold=15.0)
        cap = FeederCapacity("F1", capacity_kva=1000.0, historical_peak_kw=None)
        # 950 predicted on 900 kW capacity (1000 * 0.9) -> ~-5.5% headroom
        # Actually with capacity_kva=1000 and pf=0.9 -> capacity_kw=900
        result = clf.classify("F1", date(2024, 4, 1), 950.0, cap)
        self.assertEqual(result.level, RiskLevel.HIGH)

    def test_invalid_thresholds_raise(self) -> None:
        with self.assertRaises(ValueError):
            ZoneRiskClassifier(high_threshold=30.0, medium_threshold=20.0)

    def test_classify_forecast_df_batch(self) -> None:
        forecasts = pd.DataFrame({
            "feeder_id": ["F1", "F1", "F2"],
            "ds": pd.to_datetime(["2024-04-01", "2024-04-02", "2024-04-01"]),
            "yhat": [800.0, 900.0, 500.0],
        })
        capacities = {
            "F1": FeederCapacity("F1", capacity_kva=1111.0, historical_peak_kw=None),  # ~1000 kW
            "F2": FeederCapacity("F2", capacity_kva=555.0, historical_peak_kw=None),   # ~500 kW
        }
        results = self.clf.classify_forecast_df(forecasts, capacities)
        self.assertEqual(len(results), 3)
        # F1 day 1: 800/1000 -> 20% headroom -> MEDIUM
        self.assertEqual(results[0].level, RiskLevel.MEDIUM)
        # F1 day 2: 900/1000 -> 10% headroom -> HIGH (boundary)
        self.assertEqual(results[1].level, RiskLevel.HIGH)
        # F2 day 1: 500/500 -> 0% headroom -> HIGH
        self.assertEqual(results[2].level, RiskLevel.HIGH)


class TestClassifyZonesCSV(unittest.TestCase):
    """End-to-end CSV roundtrip."""

    def test_csv_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            # Write forecast CSV
            forecast = pd.DataFrame({
                "feeder_id": ["F1", "F1"],
                "ds": ["2024-04-01", "2024-04-02"],
                "yhat": [800.0, 700.0],
            })
            forecast.to_csv(root / "forecast.csv", index=False)

            # Write capacity CSV
            capacity = pd.DataFrame({
                "feeder_id": ["F1"],
                "capacity_kva": [1111.0],
                "historical_peak_kw": [None],
            })
            capacity.to_csv(root / "capacity.csv", index=False)

            # Run classification
            classify_zones(
                root / "forecast.csv",
                root / "capacity.csv",
                root / "risk.csv",
            )

            # Verify output
            result = pd.read_csv(root / "risk.csv")
            self.assertEqual(len(result), 2)
            self.assertIn("level", result.columns)
            self.assertIn("predicted_peak_kw", result.columns)


if __name__ == "__main__":
    unittest.main()

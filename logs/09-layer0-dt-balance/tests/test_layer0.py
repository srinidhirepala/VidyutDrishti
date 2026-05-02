"""Prototype-grade tests for Feature 09 - Layer 0 DT Energy Balance.

Run with:
    python -m unittest logs/09-layer0-dt-balance/tests/test_layer0.py -v
"""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

from app.detection.layer0_balance import BalanceAnalyzer, BalanceResult, analyze_balance_csv


class TestBalanceResult(unittest.TestCase):
    """Result dataclass and serialization."""

    def test_to_db_row(self) -> None:
        r = BalanceResult(
            dt_id="DT1",
            feeder_id="F1",
            date=date(2024, 1, 1),
            dt_in_kwh=1000.0,
            meters_sum_kwh=920.0,
            technical_loss_pct=6.0,
            expected_consumption=940.0,
            imbalance_kwh=-20.0,
            imbalance_pct=-2.0,
            threshold_pct=3.0,
            is_anomaly=False,
            n_meters=30,
            n_meters_missing=0,
            computed_at=datetime.utcnow(),
        )
        row = r.to_db_row()
        self.assertEqual(row["dt_id"], "DT1")
        self.assertEqual(row["imbalance_pct"], -2.0)
        self.assertEqual(row["is_anomaly"], False)


class TestBalanceAnalyzer(unittest.TestCase):
    """Core balance analysis logic."""

    def setUp(self) -> None:
        self.analyzer = BalanceAnalyzer(threshold_pct=3.0, default_technical_loss=6.0)

    def test_perfect_balance_no_anomaly(self) -> None:
        """DT in 1000, 6% losses, meters sum 940 -> 0% imbalance -> no anomaly."""
        dt_reading = {"kwh_in": 1000.0, "losses": 6.0}
        meter_readings = [{"meter_id": "M1", "kwh": 940.0}]

        result = self.analyzer.analyze(
            dt_id="DT1", feeder_id="F1", target_date=date(2024, 1, 1),
            dt_reading=dt_reading, meter_readings=meter_readings,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.dt_in_kwh, 1000.0)
        self.assertEqual(result.meters_sum_kwh, 940.0)
        self.assertEqual(result.expected_consumption, 940.0)  # 1000 * 0.94
        self.assertAlmostEqual(result.imbalance_kwh, 0.0, places=1)
        self.assertAlmostEqual(result.imbalance_pct, 0.0, places=1)
        self.assertFalse(result.is_anomaly)

    def test_under_reporting_anomaly(self) -> None:
        """Meters report 800 when expected 940 -> -14% imbalance -> anomaly."""
        dt_reading = {"kwh_in": 1000.0, "losses": 6.0}
        meter_readings = [{"meter_id": "M1", "kwh": 800.0}]

        result = self.analyzer.analyze(
            dt_id="DT1", feeder_id="F1", target_date=date(2024, 1, 1),
            dt_reading=dt_reading, meter_readings=meter_readings,
        )

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.imbalance_pct, -14.0, places=0)  # (800-940)/1000
        self.assertTrue(result.is_anomaly)  # | -14% | > 3%

    def test_over_reporting_anomaly(self) -> None:
        """Meters report 1000 when expected 940 -> +6% imbalance -> anomaly."""
        dt_reading = {"kwh_in": 1000.0, "losses": 6.0}
        meter_readings = [{"meter_id": "M1", "kwh": 1000.0}]

        result = self.analyzer.analyze(
            dt_id="DT1", feeder_id="F1", target_date=date(2024, 1, 1),
            dt_reading=dt_reading, meter_readings=meter_readings,
        )

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.imbalance_pct, 6.0, places=0)  # (1000-940)/1000
        self.assertTrue(result.is_anomaly)

    def test_within_threshold_not_anomaly(self) -> None:
        """Meters report 920 when expected 940 -> -2% imbalance -> no anomaly."""
        dt_reading = {"kwh_in": 1000.0, "losses": 6.0}
        meter_readings = [{"meter_id": "M1", "kwh": 920.0}]

        result = self.analyzer.analyze(
            dt_id="DT1", feeder_id="F1", target_date=date(2024, 1, 1),
            dt_reading=dt_reading, meter_readings=meter_readings,
        )

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.imbalance_pct, -2.0, places=0)
        self.assertFalse(result.is_anomaly)  # | -2% | < 3%

    def test_boundary_at_threshold(self) -> None:
        """Exactly 3% imbalance should NOT be anomaly (strict > threshold)."""
        dt_reading = {"kwh_in": 1000.0, "losses": 6.0}
        # Expected 940, 3% of 1000 is 30 kWh
        meter_readings = [{"meter_id": "M1", "kwh": 910.0}]  # -30 kWh = -3%

        result = self.analyzer.analyze(
            dt_id="DT1", feeder_id="F1", target_date=date(2024, 1, 1),
            dt_reading=dt_reading, meter_readings=meter_readings,
        )

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.imbalance_pct, -3.0, places=0)
        self.assertFalse(result.is_anomaly)  # Strictly > threshold, not >=

    def test_just_over_threshold_is_anomaly(self) -> None:
        """3.1% imbalance should be anomaly."""
        dt_reading = {"kwh_in": 1000.0, "losses": 6.0}
        meter_readings = [{"meter_id": "M1", "kwh": 909.0}]  # -31 kWh = -3.1%

        result = self.analyzer.analyze(
            dt_id="DT1", feeder_id="F1", target_date=date(2024, 1, 1),
            dt_reading=dt_reading, meter_readings=meter_readings,
        )

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.imbalance_pct, -3.1, places=0)
        self.assertTrue(result.is_anomaly)

    def test_missing_dt_reading_returns_none(self) -> None:
        result = self.analyzer.analyze(
            dt_id="DT1", feeder_id="F1", target_date=date(2024, 1, 1),
            dt_reading=None, meter_readings=[],
        )
        self.assertIsNone(result)

    def test_zero_dt_in_returns_none(self) -> None:
        dt_reading = {"kwh_in": 0.0, "losses": 6.0}
        result = self.analyzer.analyze(
            dt_id="DT1", feeder_id="F1", target_date=date(2024, 1, 1),
            dt_reading=dt_reading, meter_readings=[{"meter_id": "M1", "kwh": 100.0}],
        )
        self.assertIsNone(result)

    def test_default_technical_loss_applied(self) -> None:
        """When losses not in dt_reading, default 6% is used."""
        dt_reading = {"kwh_in": 1000.0}  # No losses field
        meter_readings = [{"meter_id": "M1", "kwh": 940.0}]

        result = self.analyzer.analyze(
            dt_id="DT1", feeder_id="F1", target_date=date(2024, 1, 1),
            dt_reading=dt_reading, meter_readings=meter_readings,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.technical_loss_pct, 6.0)
        self.assertEqual(result.expected_consumption, 940.0)

    def test_multiple_meters_aggregated(self) -> None:
        dt_reading = {"kwh_in": 1000.0, "losses": 6.0}
        meter_readings = [
            {"meter_id": "M1", "kwh": 400.0},
            {"meter_id": "M2", "kwh": 300.0},
            {"meter_id": "M3", "kwh": 240.0},  # Sum = 940
        ]

        result = self.analyzer.analyze(
            dt_id="DT1", feeder_id="F1", target_date=date(2024, 1, 1),
            dt_reading=dt_reading, meter_readings=meter_readings,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.meters_sum_kwh, 940.0)
        self.assertEqual(result.n_meters, 3)


class TestBatchAnalysis(unittest.TestCase):
    """Batch processing with DataFrames."""

    def test_analyze_batch_multiple_dts(self) -> None:
        dt_daily = pd.DataFrame({
            "dt_id": ["DT1", "DT2"],
            "date": [date(2024, 1, 1), date(2024, 1, 1)],
            "kwh_in": [1000.0, 2000.0],
            "feeder_id": ["F1", "F1"],
            "losses": [6.0, 6.0],
        })

        meter_daily = pd.DataFrame({
            "meter_id": ["M1", "M2", "M3", "M4"],
            "date": [date(2024, 1, 1)] * 4,
            "kwh": [470.0, 470.0, 940.0, 940.0],  # DT1: 940, DT2: 1880
        })

        topology = pd.DataFrame({
            "meter_id": ["M1", "M2", "M3", "M4"],
            "dt_id": ["DT1", "DT1", "DT2", "DT2"],
            "feeder_id": ["F1", "F1", "F1", "F1"],
        })

        analyzer = BalanceAnalyzer()
        results = analyzer.analyze_batch(dt_daily, meter_daily, topology, date(2024, 1, 1))

        self.assertEqual(len(results), 2)
        dt_ids = [r.dt_id for r in results]
        self.assertIn("DT1", dt_ids)
        self.assertIn("DT2", dt_ids)

        # Find DT1 result
        dt1 = next(r for r in results if r.dt_id == "DT1")
        self.assertEqual(dt1.meters_sum_kwh, 940.0)
        self.assertEqual(dt1.n_meters, 2)

    def test_analyze_batch_no_data_returns_empty(self) -> None:
        dt_daily = pd.DataFrame()  # Empty
        meter_daily = pd.DataFrame()
        topology = pd.DataFrame()

        analyzer = BalanceAnalyzer()
        results = analyzer.analyze_batch(dt_daily, meter_daily, topology, date(2024, 1, 1))

        self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()

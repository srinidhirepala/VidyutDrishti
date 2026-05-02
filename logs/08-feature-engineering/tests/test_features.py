"""Prototype-grade tests for Feature 08 - Daily Feature Engineering.

Run with:
    python -m unittest logs/08-feature-engineering/tests/test_features.py -v
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

from app.features.engineer import FeatureEngineer, _compute_diurnal_features, _health_score, build_features
from app.features.models import MeterFeatures


class TestDiurnalFeatures(unittest.TestCase):
    """Core diurnal feature calculations."""

    def test_peak_trough_mean_from_slots(self) -> None:
        df = pd.DataFrame({
            "ts": pd.date_range("2024-01-01", periods=96, freq="15min"),
            "kwh": [1.0] * 48 + [5.0] * 48,  # Low morning, high evening
        })
        peak, trough, mean = _compute_diurnal_features(df)
        self.assertEqual(peak, 5.0)
        self.assertEqual(trough, 1.0)
        self.assertEqual(mean, 3.0)

    def test_empty_data_returns_none(self) -> None:
        df = pd.DataFrame({"ts": [], "kwh": []})
        peak, trough, mean = _compute_diurnal_features(df)
        self.assertIsNone(peak)
        self.assertIsNone(trough)
        self.assertIsNone(mean)

    def test_all_nan_returns_none(self) -> None:
        df = pd.DataFrame({
            "ts": pd.date_range("2024-01-01", periods=4, freq="15min"),
            "kwh": [np.nan, np.nan, np.nan, np.nan],
        })
        peak, trough, mean = _compute_diurnal_features(df)
        self.assertIsNone(peak)


class TestHealthScore(unittest.TestCase):
    """Synthetic health score computation."""

    def test_perfect_data_high_score(self) -> None:
        # All 96 slots, voltage in range, PF in range
        df = pd.DataFrame({
            "ts": pd.date_range("2024-01-01", periods=96, freq="15min"),
            "kwh": [1.0] * 96,
            "voltage": [230.0] * 96,
            "pf": [0.95] * 96,
        })
        score = _health_score(df, expected_slots=96)
        self.assertGreaterEqual(score, 0.8)
        self.assertLessEqual(score, 1.0)

    def test_missing_slots_reduces_score(self) -> None:
        # Only 48 slots (half missing)
        df = pd.DataFrame({
            "ts": pd.date_range("2024-01-01", periods=48, freq="15min"),
            "kwh": [1.0] * 48,
            "voltage": [230.0] * 48,
            "pf": [0.95] * 48,
        })
        score = _health_score(df, expected_slots=96)
        self.assertLess(score, 0.8)  # Missing penalty applied

    def test_out_of_range_voltage_reduces_score(self) -> None:
        # All slots but voltage out of range
        df = pd.DataFrame({
            "ts": pd.date_range("2024-01-01", periods=96, freq="15min"),
            "kwh": [1.0] * 96,
            "voltage": [180.0] * 96,  # Too low
            "pf": [0.95] * 96,
        })
        score = _health_score(df, expected_slots=96)
        self.assertLess(score, 0.9)  # Voltage penalty applied

    def test_empty_data_zero_score(self) -> None:
        df = pd.DataFrame()
        score = _health_score(df, expected_slots=96)
        self.assertEqual(score, 0.0)


class TestFeatureEngineer(unittest.TestCase):
    """End-to-end feature engineering."""

    def setUp(self) -> None:
        self.engineer = FeatureEngineer()

    def _make_history(self, days: int = 10, meter_id: str = "M1") -> pd.DataFrame:
        """Generate synthetic meter history."""
        records = []
        base = datetime(2024, 1, 1)
        for d in range(days):
            for h in range(24):
                for m in [0, 15, 30, 45]:
                    ts = base + timedelta(days=d, hours=h, minutes=m)
                    records.append({
                        "meter_id": meter_id,
                        "ts": ts,
                        "kwh": 1.0 + d * 0.1,  # Slight daily increase
                        "voltage": 230.0,
                        "pf": 0.95,
                    })
        return pd.DataFrame(records)

    def test_engineer_day_returns_features(self) -> None:
        df = self._make_history(days=10)
        target = date(2024, 1, 10)

        features = self.engineer.engineer_day(
            meter_id="M1",
            dt_id="DT1",
            feeder_id="F1",
            target_date=target,
            df_history=df,
        )

        self.assertIsNotNone(features)
        self.assertIsInstance(features, MeterFeatures)
        self.assertEqual(features.meter_id, "M1")
        self.assertEqual(features.dt_id, "DT1")
        self.assertEqual(features.feeder_id, "F1")
        self.assertEqual(features.date, target)

    def test_total_kwh_sum_correct(self) -> None:
        df = self._make_history(days=1)
        target = date(2024, 1, 1)

        features = self.engineer.engineer_day(
            meter_id="M1",
            dt_id="DT1",
            feeder_id="F1",
            target_date=target,
            df_history=df,
        )

        self.assertIsNotNone(features)
        # 96 slots * 1.0 kWh each = 96 kWh
        self.assertAlmostEqual(features.total_kwh, 96.0, places=0)

    def test_rolling7_computed_with_sufficient_history(self) -> None:
        df = self._make_history(days=10)  # 9 prior days for day 10
        target = date(2024, 1, 10)

        features = self.engineer.engineer_day(
            meter_id="M1",
            dt_id="DT1",
            feeder_id="F1",
            target_date=target,
            df_history=df,
        )

        self.assertIsNotNone(features)
        self.assertIsNotNone(features.rolling7_kwh)
        self.assertGreater(features.rolling7_kwh, 0.0)

    def test_rolling7_none_with_insufficient_history(self) -> None:
        df = self._make_history(days=3)  # Only 2 prior days for day 3
        target = date(2024, 1, 3)

        features = self.engineer.engineer_day(
            meter_id="M1",
            dt_id="DT1",
            feeder_id="F1",
            target_date=target,
            df_history=df,
        )

        self.assertIsNotNone(features)
        self.assertIsNone(features.rolling7_kwh)  # Need 7 prior days

    def test_temp_ratio_computed(self) -> None:
        df = self._make_history(days=35)  # 30+ days for rolling30
        target = date(2024, 2, 4)  # Day 35 from Jan 1

        features = self.engineer.engineer_day(
            meter_id="M1",
            dt_id="DT1",
            feeder_id="F1",
            target_date=target,
            df_history=df,
        )

        self.assertIsNotNone(features)
        self.assertIsNotNone(features.temp_ratio)
        self.assertGreater(features.temp_ratio, 0.0)

    def test_weekday_isin_correct(self) -> None:
        # Jan 1, 2024 was Monday (weekday)
        df = self._make_history(days=1)
        features = self.engineer.engineer_day(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 1),
            df_history=df,
        )
        self.assertIsNotNone(features)
        self.assertEqual(features.weekday_isin, 1)
        self.assertEqual(features.day_of_week, 0)  # Monday = 0

        # Jan 6, 2024 was Saturday (weekend)
        df = self._make_history(days=6)
        features = self.engineer.engineer_day(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 6),
            df_history=df,
        )
        self.assertIsNotNone(features)
        self.assertEqual(features.weekday_isin, 0)
        self.assertEqual(features.day_of_week, 5)  # Saturday = 5

    def test_holiday_detection(self) -> None:
        holidays = {date(2024, 1, 1)}  # New Year
        engineer = FeatureEngineer(holidays=holidays)
        df = engineer._make_history(days=1) if hasattr(engineer, '_make_history') else self._make_history(days=1)

        features = engineer.engineer_day(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 1),
            df_history=df,
        )
        self.assertIsNotNone(features)
        self.assertEqual(features.is_holiday, 1)

    def test_inspection_days_computed(self) -> None:
        inspections = {"M1": date(2024, 1, 1)}
        engineer = FeatureEngineer(inspections=inspections)
        df = self._make_history(days=10)

        features = engineer.engineer_day(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 10),
            df_history=df,
        )
        self.assertIsNotNone(features)
        self.assertEqual(features.last_inspection_days, 9)  # 10 - 1 = 9 days

    def test_no_inspection_returns_none(self) -> None:
        df = self._make_history(days=1)
        features = self.engineer.engineer_day(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 1),
            df_history=df,
        )
        self.assertIsNotNone(features)
        self.assertIsNone(features.last_inspection_days)

    def test_empty_history_returns_none(self) -> None:
        features = self.engineer.engineer_day(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 1),
            df_history=pd.DataFrame(),
        )
        self.assertIsNone(features)


class TestMeterFeaturesDataclass(unittest.TestCase):
    """Serialization and dataclass behavior."""

    def test_to_db_row(self) -> None:
        f = MeterFeatures(
            meter_id="M1",
            dt_id="DT1",
            feeder_id="F1",
            date=date(2024, 1, 1),
            total_kwh=100.0,
            rolling7_kwh=95.0,
            peak_hour_kwh=5.0,
            trough_hour_kwh=0.5,
            diurnal_mean=2.0,
            weekday_isin=1,
            is_holiday=0,
            day_of_week=0,
            temp_ratio=1.05,
            meter_health_score=0.95,
            voltage_variability=2.5,
            pf_mean=0.95,
            last_inspection_days=30,
            computed_at=datetime.utcnow(),
            slots_missing=0,
            slots_total=96,
        )
        row = f.to_db_row()
        self.assertEqual(row["meter_id"], "M1")
        self.assertEqual(row["total_kwh"], 100.0)
        self.assertIn("computed_at", row)


if __name__ == "__main__":
    unittest.main()

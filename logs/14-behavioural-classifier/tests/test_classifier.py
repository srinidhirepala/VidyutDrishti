"""Prototype-grade tests for Feature 14 - Behavioural Classifier.

Run with:
    python C:\Hackathon\VidyutDrishti\logs\14-behavioural-classifier\tests\test_classifier.py -v
"""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

from app.detection.classifier import (
    BehaviouralClassifier,
    ClassificationResult,
    AnomalyType,
)


class TestAnomalyType(unittest.TestCase):
    """Anomaly type enum."""

    def test_enum_values(self) -> None:
        self.assertEqual(AnomalyType.SUDDEN_DROP.value, "sudden_drop")
        self.assertEqual(AnomalyType.SPIKE.value, "spike")
        self.assertEqual(AnomalyType.FLATLINE.value, "flatline")
        self.assertEqual(AnomalyType.ERRATIC.value, "erratic")
        self.assertEqual(AnomalyType.NORMAL_PATTERN.value, "normal_pattern")


class TestBehaviouralClassifier(unittest.TestCase):
    """Classification logic."""

    def setUp(self) -> None:
        self.classifier = BehaviouralClassifier()

    def _make_day_data(self, kwh_values: list[float], day: date | None = None) -> pd.DataFrame:
        """Create 15-min slot data for a single day."""
        day = day or date(2024, 1, 15)
        base_ts = datetime.combine(day, datetime.min.time())
        timestamps = [base_ts + timedelta(minutes=15*i) for i in range(len(kwh_values))]
        df = pd.DataFrame({
            "ts": timestamps,
            "kwh": kwh_values,
        })
        df["date"] = day
        return df.set_index("date")

    def _make_prior_data(self, daily_totals: list[float]) -> pd.DataFrame:
        """Create prior days data from daily totals."""
        frames = []
        target = date(2024, 1, 15)
        for day_offset, total in enumerate(daily_totals, start=1):
            day = target - timedelta(days=day_offset)
            base_ts = datetime.combine(day, datetime.min.time())
            # Distribute total across 96 slots (15-min intervals)
            kwh_per_slot = total / 96
            timestamps = [base_ts + timedelta(minutes=15*i) for i in range(96)]
            df = pd.DataFrame({
                "ts": timestamps,
                "kwh": [kwh_per_slot] * 96,
            })
            df["date"] = day
            frames.append(df)
        result = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if not result.empty:
            result = result.set_index("date")
        return result

    def test_normal_pattern(self) -> None:
        """Steady consumption should be classified as normal."""
        df_day = self._make_day_data([4.0] * 96)  # 4 kWh per slot = 384 kWh/day
        df_prior = self._make_prior_data([380, 385, 390])  # Similar prior days

        result = self.classifier.classify(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 15),
            df_day=df_day,
            df_prior=df_prior,
        )

        self.assertEqual(result.anomaly_type, AnomalyType.NORMAL_PATTERN)
        self.assertEqual(result.confidence, 0.5)
        self.assertIn("Normal", result.description)

    def test_sudden_drop(self) -> None:
        """40% drop from prior day should trigger sudden_drop."""
        # Prior day: 100 kWh total (distributed evenly)
        df_prior = self._make_prior_data([100])
        # Today: 50 kWh total (40% drop)
        df_day = self._make_day_data([0.52] * 96)  # ~50 kWh

        result = self.classifier.classify(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 15),
            df_day=df_day,
            df_prior=df_prior,
        )

        self.assertEqual(result.anomaly_type, AnomalyType.SUDDEN_DROP)
        self.assertGreater(result.confidence, 0.3)
        self.assertIn("drop", result.description.lower())

    def test_flatline(self) -> None:
        """95% zero slots should trigger flatline."""
        kwh_values = [0.0] * 90 + [4.0] * 6  # 94% zero
        df_day = self._make_day_data(kwh_values)
        df_prior = self._make_prior_data([100])

        result = self.classifier.classify(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 15),
            df_day=df_day,
            df_prior=df_prior,
        )

        self.assertEqual(result.anomaly_type, AnomalyType.FLATLINE)
        self.assertGreater(result.confidence, 0.9)
        self.assertIn("flatline", result.description.lower())

    def test_spike(self) -> None:
        """60% increase from prior day should trigger spike."""
        # Prior day: 100 kWh
        df_prior = self._make_prior_data([100])
        # Today: 160 kWh (60% increase)
        df_day = self._make_day_data([1.67] * 96)

        result = self.classifier.classify(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 15),
            df_day=df_day,
            df_prior=df_prior,
        )

        self.assertEqual(result.anomaly_type, AnomalyType.SPIKE)
        self.assertGreater(result.confidence, 0.5)
        self.assertIn("spike", result.description.lower())

    def test_erratic(self) -> None:
        """High volatility with stable total should trigger erratic."""
        # Alternating moderate values (high CV but stable total ~similar to prior)
        kwh_values = [2.0, 0.5] * 48  # CV ~60%, total ~120 kWh
        df_day = self._make_day_data(kwh_values)
        df_prior = self._make_prior_data([120])  # Similar total to avoid spike

        result = self.classifier.classify(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 15),
            df_day=df_day,
            df_prior=df_prior,
        )

        self.assertEqual(result.anomaly_type, AnomalyType.ERRATIC)
        self.assertGreater(result.cv_daily or 0, 0.5)

    def test_flatline_takes_precedence_over_drop(self) -> None:
        """Flatline should be detected even with large drop."""
        # 95% zeros (flatline) but also huge drop
        kwh_values = [0.0] * 91 + [0.5] * 5  # 95% near-zero
        df_day = self._make_day_data(kwh_values)
        df_prior = self._make_prior_data([1000])  # Huge prior

        result = self.classifier.classify(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 15),
            df_day=df_day,
            df_prior=df_prior,
        )

        # Flatline detected
        self.assertEqual(result.anomaly_type, AnomalyType.FLATLINE)


class TestClassificationResult(unittest.TestCase):
    """Result dataclass and serialization."""

    def test_to_db_row(self) -> None:
        r = ClassificationResult(
            meter_id="M1",
            dt_id="DT1",
            feeder_id="F1",
            date=date(2024, 1, 1),
            anomaly_type=AnomalyType.SUDDEN_DROP,
            confidence=0.85,
            daily_change_pct=-40.0,
            rolling_mean_ratio=0.6,
            zero_slots_ratio=0.05,
            cv_daily=0.1,
            description="Sudden drop: 40% decrease",
        )
        row = r.to_db_row()
        self.assertEqual(row["meter_id"], "M1")
        self.assertEqual(row["anomaly_type"], "sudden_drop")
        self.assertEqual(row["confidence"], 0.85)
        self.assertEqual(row["daily_change_pct"], -40.0)


class TestBatchClassification(unittest.TestCase):
    """Batch processing."""

    def test_classify_batch_multiple_meters(self) -> None:
        """Classify multiple meters in one batch."""
        # Create readings for 2 meters on target day
        base_ts = datetime(2024, 1, 15, 0, 0)
        timestamps = [base_ts + timedelta(minutes=15*i) for i in range(96)]

        # M1: 95% zeros (flatline), M2: normal consumption
        m1_kwh = [0.0] * 91 + [0.1] * 5  # 95% zeros
        m2_kwh = [4.0] * 96  # Normal

        readings_df = pd.DataFrame({
            "meter_id": ["M1"] * 96 + ["M2"] * 96,
            "ts": timestamps * 2,
            "kwh": m1_kwh + m2_kwh,
        })

        topology_df = pd.DataFrame({
            "meter_id": ["M1", "M2"],
            "dt_id": ["DT1", "DT1"],
            "feeder_id": ["F1", "F1"],
        })

        classifier = BehaviouralClassifier()
        results = classifier.classify_batch(
            readings_df, topology_df, date(2024, 1, 15)
        )

        self.assertEqual(len(results), 2)

        m1 = next(r for r in results if r.meter_id == "M1")
        m2 = next(r for r in results if r.meter_id == "M2")

        self.assertEqual(m1.anomaly_type, AnomalyType.FLATLINE)
        self.assertEqual(m2.anomaly_type, AnomalyType.NORMAL_PATTERN)

    def test_empty_data_returns_empty(self) -> None:
        classifier = BehaviouralClassifier()
        results = classifier.classify_batch(
            pd.DataFrame(), pd.DataFrame(), date(2024, 1, 1)
        )
        self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()

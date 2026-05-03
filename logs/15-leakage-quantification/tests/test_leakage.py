"""Prototype-grade tests for Feature 15 - Leakage Quantification.

Run with:
    python C:\Hackathon\VidyutDrishti\logs\15-leakage-quantification\tests\test_leakage.py -v
"""

from __future__ import annotations

import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

from app.evaluation.leakage import LeakageQuantifier, LeakageEstimate


class TestLeakageEstimate(unittest.TestCase):
    """Dataclass and serialization."""

    def test_to_db_row(self) -> None:
        e = LeakageEstimate(
            meter_id="M1",
            dt_id="DT1",
            feeder_id="F1",
            date=date(2024, 1, 1),
            anomaly_type="sudden_drop",
            confidence=0.85,
            estimated_kwh_lost=50.0,
            tariff_rate_per_kwh=Decimal("7.50"),
            estimated_inr_lost=Decimal("375.00"),
            basis="peer_deviation",
        )
        row = e.to_db_row()
        self.assertEqual(row["meter_id"], "M1")
        self.assertEqual(row["estimated_kwh_lost"], 50.0)
        self.assertEqual(row["estimated_inr_lost"], 375.00)
        self.assertEqual(row["basis"], "peer_deviation")


class TestLeakageQuantifier(unittest.TestCase):
    """Quantification logic."""

    def setUp(self) -> None:
        self.quantifier = LeakageQuantifier(default_tariff_per_kwh=Decimal("7.50"))

    def test_peer_deviation_calculation(self) -> None:
        """Loss = peer_mean - actual when actual < peer_mean."""
        estimate = self.quantifier.quantify(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 1),
            anomaly_type="sudden_drop",
            confidence=0.8,
            actual_kwh=50.0,
            peer_mean=100.0,  # Peers use 100
        )

        self.assertEqual(estimate.estimated_kwh_lost, 50.0)  # 100 - 50
        self.assertEqual(estimate.basis, "peer_deviation")
        self.assertEqual(estimate.estimated_inr_lost, Decimal("375.00"))  # 50 * 7.50

    def test_no_loss_when_actual_exceeds_expected(self) -> None:
        """If actual > expected, loss should be 0."""
        estimate = self.quantifier.quantify(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 1),
            anomaly_type="normal_pattern",
            confidence=0.5,
            actual_kwh=150.0,
            peer_mean=100.0,  # Peers use 100, but actual is higher
        )

        self.assertEqual(estimate.estimated_kwh_lost, 0.0)
        self.assertIn("no_loss", estimate.basis)

    def test_z_score_fallback_when_no_peers(self) -> None:
        """Use historical mean/std when peer data unavailable."""
        estimate = self.quantifier.quantify(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 1),
            anomaly_type="sudden_drop",
            confidence=0.8,
            actual_kwh=70.0,  # Loss = 30, within 3 std (3 * 15 = 45)
            peer_mean=None,  # No peer data
            historical_mean=100.0,
            historical_std=15.0,
        )

        self.assertEqual(estimate.estimated_kwh_lost, 30.0)  # 100 - 70
        self.assertEqual(estimate.basis, "z_score_extrapolation")

    def test_z_score_caps_at_3_std(self) -> None:
        """Loss capped at 3 std devs to avoid extreme outliers."""
        estimate = self.quantifier.quantify(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 1),
            anomaly_type="flatline",
            confidence=0.9,
            actual_kwh=0.0,  # Extreme low
            peer_mean=None,
            historical_mean=100.0,
            historical_std=10.0,
        )

        # Loss capped at 3 * 10 = 30 kWh, not full 100
        self.assertEqual(estimate.estimated_kwh_lost, 30.0)

    def test_insufficient_data_returns_none(self) -> None:
        """If no peer or historical data, kwh_lost should be None."""
        estimate = self.quantifier.quantify(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 1),
            anomaly_type="spike",
            confidence=0.6,
            actual_kwh=150.0,
            peer_mean=None,
            historical_mean=None,
        )

        self.assertIsNone(estimate.estimated_kwh_lost)
        self.assertIsNone(estimate.estimated_inr_lost)
        self.assertEqual(estimate.basis, "insufficient_data")

    def test_custom_tariff(self) -> None:
        """Allow custom tariff rate per meter."""
        estimate = self.quantifier.quantify(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 1),
            anomaly_type="sudden_drop",
            confidence=0.8,
            actual_kwh=50.0,
            peer_mean=100.0,
            tariff_per_kwh=Decimal("10.00"),  # Custom tariff
        )

        self.assertEqual(estimate.estimated_inr_lost, Decimal("500.00"))  # 50 * 10
        self.assertEqual(estimate.tariff_rate_per_kwh, Decimal("10.00"))

    def test_peer_method_preferred_over_z_score(self) -> None:
        """Peer deviation used when both methods available."""
        estimate = self.quantifier.quantify(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 1),
            anomaly_type="sudden_drop",
            confidence=0.8,
            actual_kwh=50.0,
            peer_mean=100.0,  # Peer method should be used
            historical_mean=80.0,
            historical_std=5.0,
        )

        self.assertEqual(estimate.basis, "peer_deviation")
        self.assertEqual(estimate.estimated_kwh_lost, 50.0)  # 100 - 50


class TestLeakageBatch(unittest.TestCase):
    """Batch processing."""

    def test_quantify_batch(self) -> None:
        detections_df = pd.DataFrame({
            "meter_id": ["M1", "M2"],
            "anomaly_type": ["sudden_drop", "spike"],
            "confidence": [0.8, 0.6],
            "actual_kwh": [50.0, 150.0],
            "peer_mean": [100.0, 100.0],
        })

        topology_df = pd.DataFrame({
            "meter_id": ["M1", "M2"],
            "dt_id": ["DT1", "DT1"],
            "feeder_id": ["F1", "F1"],
        })

        quantifier = LeakageQuantifier()
        results = quantifier.quantify_batch(detections_df, topology_df, date(2024, 1, 1))

        self.assertEqual(len(results), 2)

        # M1: loss = 100 - 50 = 50 kWh
        m1 = next(r for r in results if r.meter_id == "M1")
        self.assertEqual(m1.estimated_kwh_lost, 50.0)

        # M2: actual > peer_mean, no loss
        m2 = next(r for r in results if r.meter_id == "M2")
        self.assertEqual(m2.estimated_kwh_lost, 0.0)

    def test_empty_data_returns_empty(self) -> None:
        quantifier = LeakageQuantifier()
        results = quantifier.quantify_batch(pd.DataFrame(), pd.DataFrame(), date(2024, 1, 1))
        self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()

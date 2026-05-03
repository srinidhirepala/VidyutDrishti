"""Prototype-grade tests for Feature 13 - Confidence Engine.

Run with:
    python -m unittest logs/13-confidence-engine/tests/test_confidence.py -v
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

from app.detection.confidence import ConfidenceEngine, ConfidenceResult, LayerSignals


class TestLayerSignals(unittest.TestCase):
    """Layer signals dataclass."""

    def test_default_signals(self) -> None:
        s = LayerSignals()
        self.assertIsNone(s.l0_dt_imbalance_pct)
        self.assertFalse(s.l0_is_anomaly)
        self.assertFalse(s.l1_is_anomaly)
        self.assertFalse(s.l2_is_anomaly)
        self.assertFalse(s.l3_is_anomaly)

    def test_custom_signals(self) -> None:
        s = LayerSignals(
            l0_dt_imbalance_pct=-10.0,
            l0_is_anomaly=True,
            l1_z_score=4.0,
            l1_is_anomaly=True,
            l2_deviation_pct=-20.0,
            l2_is_anomaly=True,
            l3_anomaly_score=-0.6,
            l3_is_anomaly=True,
        )
        self.assertEqual(s.l0_dt_imbalance_pct, -10.0)
        self.assertTrue(s.l0_is_anomaly)
        self.assertEqual(s.l1_z_score, 4.0)


class TestConfidenceEngine(unittest.TestCase):
    """Confidence score computation."""

    def setUp(self) -> None:
        self.engine = ConfidenceEngine()

    def test_no_anomalies_zero_confidence(self) -> None:
        """When no layers detect anomaly, confidence should be 0."""
        signals = LayerSignals(
            l0_is_anomaly=False,
            l1_is_anomaly=False,
            l2_is_anomaly=False,
            l3_is_anomaly=False,
        )
        result = self.engine.compute(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 1),
            signals=signals,
        )
        self.assertEqual(result.confidence, 0.0)
        self.assertEqual(result.rank, 0)  # Will be assigned in batch

    def test_single_layer_anomaly(self) -> None:
        """One layer anomaly should give weighted confidence."""
        signals = LayerSignals(
            l0_is_anomaly=False,
            l1_is_anomaly=True,
            l1_z_score=4.0,  # 4/3 = 1.33 ratio
            l2_is_anomaly=False,
            l3_is_anomaly=False,
        )
        result = self.engine.compute(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 1),
            signals=signals,
        )
        # L1 weight 0.30, score ~ min(1.0, 1.33/3) = 0.44
        self.assertGreater(result.confidence, 0.0)
        self.assertLess(result.confidence, 1.0)
        # All contribution from L1
        self.assertGreater(result.l1_contrib, 0.8)

    def test_all_layers_anomaly_max_confidence(self) -> None:
        """All layers flagging anomaly with extreme magnitudes -> confidence ~1.0."""
        signals = LayerSignals(
            l0_is_anomaly=True,
            l0_dt_imbalance_pct=-20.0,  # Very high imbalance
            l1_is_anomaly=True,
            l1_z_score=10.0,  # Very high z-score
            l2_is_anomaly=True,
            l2_deviation_pct=-50.0,  # Very high deviation
            l3_is_anomaly=True,
            l3_anomaly_score=-2.0,  # Very anomalous
        )
        result = self.engine.compute(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 1),
            signals=signals,
        )
        # All maxed out, should be close to 1.0
        self.assertGreater(result.confidence, 0.8)
        self.assertLessEqual(result.confidence, 1.0)

    def test_layer_weights_sum_to_one(self) -> None:
        """Verify weights sum to 1.0."""
        total = sum(ConfidenceEngine.WEIGHTS.values())
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_confidence_range_0_to_1(self) -> None:
        """Confidence should always be in [0, 1]."""
        signals = LayerSignals(
            l1_is_anomaly=True,
            l1_z_score=100.0,  # Extreme
        )
        result = self.engine.compute(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 1),
            signals=signals,
        )
        self.assertGreaterEqual(result.confidence, 0.0)
        self.assertLessEqual(result.confidence, 1.0)

    def test_anomaly_without_magnitude(self) -> None:
        """Layer reports anomaly but no magnitude -> default score 0.5."""
        signals = LayerSignals(
            l1_is_anomaly=True,
            l1_z_score=None,  # No magnitude
        )
        result = self.engine.compute(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 1),
            signals=signals,
        )
        # L1 score = 0.5 (default when no magnitude)
        # Confidence = 0.30 * 0.5 = 0.15
        self.assertAlmostEqual(result.confidence, 0.15, places=2)

    def test_contributions_sum_to_one(self) -> None:
        """When there are signals, contributions should sum to 1.0."""
        signals = LayerSignals(
            l0_is_anomaly=True,
            l1_is_anomaly=True,
            l2_is_anomaly=True,
            l3_is_anomaly=True,
        )
        result = self.engine.compute(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 1),
            signals=signals,
        )
        total = result.l0_contrib + result.l1_contrib + result.l2_contrib + result.l3_contrib
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_no_signals_equal_contributions(self) -> None:
        """When no signals, contributions default to equal 0.25 each."""
        signals = LayerSignals(
            l0_is_anomaly=False,
            l1_is_anomaly=False,
            l2_is_anomaly=False,
            l3_is_anomaly=False,
        )
        result = self.engine.compute(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            target_date=date(2024, 1, 1),
            signals=signals,
        )
        self.assertEqual(result.l0_contrib, 0.25)
        self.assertEqual(result.l1_contrib, 0.25)
        self.assertEqual(result.l2_contrib, 0.25)
        self.assertEqual(result.l3_contrib, 0.25)


class TestConfidenceBatch(unittest.TestCase):
    """Batch processing with ranking."""

    def test_compute_batch_assigns_ranks(self) -> None:
        """Higher confidence should get lower rank number (rank 1 = highest)."""
        df = pd.DataFrame({
            "meter_id": ["M1", "M2", "M3"],
            "dt_id": ["DT1"] * 3,
            "feeder_id": ["F1"] * 3,
            "date": [date(2024, 1, 1)] * 3,
            # M1: all anomalies (highest confidence)
            "l0_is_anomaly": [True, False, False],
            "l1_is_anomaly": [True, True, False],
            "l2_is_anomaly": [True, False, False],
            "l3_is_anomaly": [True, False, False],
            "l1_z_score": [5.0, 3.0, 0.0],
        })

        engine = ConfidenceEngine()
        results = engine.compute_batch(df)

        self.assertEqual(len(results), 3)
        # M1 should be rank 1 (all layers)
        m1 = next(r for r in results if r.meter_id == "M1")
        self.assertEqual(m1.rank, 1)

        # M2 should be rank 2 (one layer)
        m2 = next(r for r in results if r.meter_id == "M2")
        self.assertEqual(m2.rank, 2)

        # M3 should be rank 3 (no anomalies)
        m3 = next(r for r in results if r.meter_id == "M3")
        self.assertEqual(m3.rank, 3)

    def test_results_sorted_by_confidence(self) -> None:
        """Results should be sorted by confidence descending."""
        df = pd.DataFrame({
            "meter_id": ["M1", "M2"],
            "dt_id": ["DT1"] * 2,
            "feeder_id": ["F1"] * 2,
            "date": [date(2024, 1, 1)] * 2,
            "l0_is_anomaly": [False, True],
            "l1_is_anomaly": [False, True],
            "l2_is_anomaly": [False, True],
            "l3_is_anomaly": [False, True],
        })

        engine = ConfidenceEngine()
        results = engine.compute_batch(df)

        # M2 has all anomalies, should be first
        self.assertEqual(results[0].meter_id, "M2")
        self.assertEqual(results[1].meter_id, "M1")


class TestConfidenceResult(unittest.TestCase):
    """Result dataclass and serialization."""

    def test_to_db_row(self) -> None:
        r = ConfidenceResult(
            meter_id="M1",
            dt_id="DT1",
            feeder_id="F1",
            date=date(2024, 1, 1),
            signals=LayerSignals(l1_is_anomaly=True),
            confidence=0.75,
            rank=1,
            l0_contrib=0.1,
            l1_contrib=0.6,
            l2_contrib=0.2,
            l3_contrib=0.1,
        )
        row = r.to_db_row()
        self.assertEqual(row["meter_id"], "M1")
        self.assertEqual(row["confidence"], 0.75)
        self.assertEqual(row["rank"], 1)
        self.assertEqual(row["l1_contrib"], 0.6)


if __name__ == "__main__":
    unittest.main()

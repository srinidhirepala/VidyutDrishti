"""Prototype-grade tests for Feature 21 - Evaluation Harness.

Run with:
    python C:\Hackathon\VidyutDrishti\logs\21-evaluation-harness\tests\test_harness.py -v
"""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

from app.evaluation.harness import (
    EvaluationHarness,
    GroundTruthLabel,
    DetectionPrediction,
    EvaluationMetrics,
    EvaluationResult,
)


class TestGroundTruthLabel(unittest.TestCase):
    """Ground truth dataclass."""

    def test_to_dict(self) -> None:
        l = GroundTruthLabel(
            meter_id="M1",
            date=date(2024, 1, 15),
            is_anomaly=True,
            anomaly_type="theft",
            notes="Confirmed bypass",
        )
        d = l.to_dict()
        self.assertEqual(d["meter_id"], "M1")
        self.assertEqual(d["is_anomaly"], True)
        self.assertEqual(d["anomaly_type"], "theft")


class TestDetectionPrediction(unittest.TestCase):
    """Prediction dataclass."""

    def test_to_dict(self) -> None:
        p = DetectionPrediction(
            meter_id="M1",
            date=date(2024, 1, 15),
            confidence=0.85,
            is_anomaly=True,
            anomaly_type="sudden_drop",
        )
        d = p.to_dict()
        self.assertEqual(d["confidence"], 0.85)
        self.assertEqual(d["is_anomaly"], True)


class TestEvaluationMetrics(unittest.TestCase):
    """Metrics calculations."""

    def test_perfect_detection(self) -> None:
        """All predictions correct."""
        m = EvaluationMetrics(
            total_samples=10,
            true_positives=5,
            false_positives=0,
            false_negatives=0,
            true_negatives=5,
        )
        self.assertEqual(m.accuracy, 1.0)
        self.assertEqual(m.precision, 1.0)
        self.assertEqual(m.recall, 1.0)
        self.assertEqual(m.f1_score, 1.0)
        self.assertEqual(m.specificity, 1.0)

    def test_all_false_positives(self) -> None:
        """Predicted anomalies but all were normal."""
        m = EvaluationMetrics(
            total_samples=10,
            true_positives=0,
            false_positives=5,
            false_negatives=0,
            true_negatives=5,
        )
        self.assertEqual(m.accuracy, 0.5)
        self.assertEqual(m.precision, 0.0)  # No true positives
        self.assertEqual(m.recall, 0.0)  # No true positives
        self.assertEqual(m.specificity, 0.5)

    def test_all_false_negatives(self) -> None:
        """Missed all anomalies."""
        m = EvaluationMetrics(
            total_samples=10,
            true_positives=0,
            false_positives=0,
            false_negatives=5,
            true_negatives=5,
        )
        self.assertEqual(m.accuracy, 0.5)
        self.assertEqual(m.precision, 0.0)  # No positive predictions
        self.assertEqual(m.recall, 0.0)  # No true positives found
        self.assertEqual(m.specificity, 1.0)  # All normal correctly identified

    def test_balanced_performance(self) -> None:
        """Mixed performance."""
        m = EvaluationMetrics(
            total_samples=100,
            true_positives=40,
            false_positives=10,
            false_negatives=10,
            true_negatives=40,
        )
        # Accuracy = (40 + 40) / 100 = 0.8
        self.assertEqual(m.accuracy, 0.8)
        # Precision = 40 / (40 + 10) = 0.8
        self.assertEqual(m.precision, 0.8)
        # Recall = 40 / (40 + 10) = 0.8
        self.assertEqual(m.recall, 0.8)
        # Specificity = 40 / (40 + 10) = 0.8
        self.assertEqual(m.specificity, 0.8)


class TestEvaluationHarness(unittest.TestCase):
    """Evaluation framework."""

    def setUp(self) -> None:
        self.harness = EvaluationHarness(confidence_threshold=0.5)

    def test_perfect_predictions(self) -> None:
        """When predictions match ground truth exactly."""
        ground_truth = [
            GroundTruthLabel("M1", date(2024, 1, 15), True, "theft"),
            GroundTruthLabel("M2", date(2024, 1, 15), False, "normal"),
        ]
        predictions = [
            DetectionPrediction("M1", date(2024, 1, 15), 0.8, True),
            DetectionPrediction("M2", date(2024, 1, 15), 0.2, False),
        ]

        result = self.harness.evaluate(ground_truth, predictions)

        self.assertEqual(result.metrics.accuracy, 1.0)
        self.assertEqual(result.metrics.true_positives, 1)
        self.assertEqual(result.metrics.true_negatives, 1)

    def test_false_positive(self) -> None:
        """Predicted anomaly but was normal."""
        ground_truth = [
            GroundTruthLabel("M1", date(2024, 1, 15), False, "normal"),
        ]
        predictions = [
            DetectionPrediction("M1", date(2024, 1, 15), 0.8, True),  # FP
        ]

        result = self.harness.evaluate(ground_truth, predictions)

        self.assertEqual(result.metrics.false_positives, 1)
        self.assertEqual(result.metrics.precision, 0.0)

    def test_false_negative(self) -> None:
        """Missed actual anomaly."""
        ground_truth = [
            GroundTruthLabel("M1", date(2024, 1, 15), True, "theft"),
        ]
        predictions = [
            DetectionPrediction("M1", date(2024, 1, 15), 0.3, False),  # FN
        ]

        result = self.harness.evaluate(ground_truth, predictions)

        self.assertEqual(result.metrics.false_negatives, 1)
        self.assertEqual(result.metrics.recall, 0.0)

    def test_missing_prediction(self) -> None:
        """No prediction for a meter (counts as negative prediction)."""
        ground_truth = [
            GroundTruthLabel("M1", date(2024, 1, 15), True, "theft"),
        ]
        predictions = []  # No predictions

        result = self.harness.evaluate(ground_truth, predictions)

        self.assertEqual(result.metrics.false_negatives, 1)

    def test_missing_ground_truth(self) -> None:
        """Prediction but no ground truth (not counted in evaluation)."""
        ground_truth = []
        predictions = [
            DetectionPrediction("M1", date(2024, 1, 15), 0.8, True),
        ]

        result = self.harness.evaluate(ground_truth, predictions)

        # Still counted as a sample with no actual truth
        self.assertEqual(result.metrics.total_samples, 1)

    def test_threshold_sweep(self) -> None:
        """Test multiple thresholds."""
        ground_truth = [
            GroundTruthLabel("M1", date(2024, 1, 15), True, "theft"),
            GroundTruthLabel("M2", date(2024, 1, 15), False, "normal"),
        ]
        predictions = [
            DetectionPrediction("M1", date(2024, 1, 15), 0.3, True),  # Low confidence
            DetectionPrediction("M2", date(2024, 1, 15), 0.7, True),  # High confidence
        ]

        results = self.harness.threshold_sweep(
            ground_truth, predictions, thresholds=[0.2, 0.5, 0.8]
        )

        self.assertEqual(len(results), 3)
        # At threshold 0.2: both predicted as anomaly
        self.assertEqual(results[0]["threshold"], 0.2)
        # At threshold 0.8: only M2 predicted
        self.assertEqual(results[2]["threshold"], 0.8)

    def test_load_from_dataframe(self) -> None:
        """Load ground truth from pandas DataFrame."""
        import pandas as pd

        df = pd.DataFrame({
            "meter_id": ["M1", "M2"],
            "date": [date(2024, 1, 15), date(2024, 1, 15)],
            "is_anomaly": [True, False],
            "anomaly_type": ["theft", "normal"],
        })

        labels = self.harness.load_ground_truth(df)

        self.assertEqual(len(labels), 2)
        self.assertTrue(labels[0].is_anomaly)
        self.assertFalse(labels[1].is_anomaly)


if __name__ == "__main__":
    unittest.main()

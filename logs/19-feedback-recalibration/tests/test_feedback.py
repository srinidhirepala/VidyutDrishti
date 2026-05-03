"""Prototype-grade tests for Feature 19 - Feedback Loop & Recalibration.

Run with:
    python C:\Hackathon\VidyutDrishti\logs\19-feedback-recalibration\tests\test_feedback.py -v
"""

from __future__ import annotations

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

from app.feedback.processor import (
    FeedbackProcessor,
    FeedbackRecord,
    AccuracyMetrics,
)


class TestFeedbackRecord(unittest.TestCase):
    """Feedback record dataclass."""

    def test_to_db_row(self) -> None:
        r = FeedbackRecord(
            meter_id="M1",
            inspection_date=date(2024, 1, 15),
            was_anomaly=True,
            detection_confidence=0.85,
            actual_kwh_observed=150.0,
            notes="Theft confirmed",
            inspector_id="INS001",
        )
        row = r.to_db_row()
        self.assertEqual(row["meter_id"], "M1")
        self.assertEqual(row["was_anomaly"], True)
        self.assertEqual(row["detection_confidence"], 0.85)


class TestAccuracyMetrics(unittest.TestCase):
    """Accuracy metric calculations."""

    def test_perfect_precision(self) -> None:
        """All predicted anomalies were true anomalies."""
        m = AccuracyMetrics(
            total_inspected=10,
            true_positives=8,
            false_positives=0,
            false_negatives=2,
        )
        self.assertEqual(m.precision, 1.0)
        self.assertAlmostEqual(m.recall, 0.8, places=2)

    def test_perfect_recall(self) -> None:
        """All true anomalies were detected."""
        m = AccuracyMetrics(
            total_inspected=10,
            true_positives=8,
            false_positives=2,
            false_negatives=0,
        )
        self.assertEqual(m.recall, 1.0)
        self.assertAlmostEqual(m.precision, 0.8, places=2)

    def test_f1_score(self) -> None:
        """F1 is harmonic mean of precision and recall."""
        m = AccuracyMetrics(
            total_inspected=10,
            true_positives=6,
            false_positives=2,
            false_negatives=2,
        )
        # Precision = 6/8 = 0.75, Recall = 6/8 = 0.75, F1 = 0.75
        self.assertAlmostEqual(m.precision, 0.75, places=2)
        self.assertAlmostEqual(m.recall, 0.75, places=2)
        self.assertAlmostEqual(m.f1_score, 0.75, places=2)

    def test_zero_division_handling(self) -> None:
        """Graceful handling when no predictions."""
        m = AccuracyMetrics(
            total_inspected=0,
            true_positives=0,
            false_positives=0,
            false_negatives=0,
        )
        self.assertEqual(m.precision, 0.0)
        self.assertEqual(m.recall, 0.0)
        self.assertEqual(m.f1_score, 0.0)


class TestFeedbackProcessor(unittest.TestCase):
    """Feedback processing and recalibration."""

    def setUp(self) -> None:
        self.processor = FeedbackProcessor(
            target_precision=0.8,
            target_recall=0.7,
        )

    def test_submit_feedback(self) -> None:
        """Feedback records are stored."""
        record = FeedbackRecord(
            meter_id="M1",
            inspection_date=date(2024, 1, 15),
            was_anomaly=True,
            detection_confidence=0.85,
        )
        self.processor.submit_feedback(record)
        self.assertEqual(len(self.processor.feedback_history), 1)

    def test_compute_metrics_basic(self) -> None:
        """Metrics computed from feedback history."""
        # TP: high confidence + was anomaly
        self.processor.submit_feedback(FeedbackRecord(
            "M1", date(2024, 1, 15), True, 0.85
        ))
        # FP: high confidence + was normal
        self.processor.submit_feedback(FeedbackRecord(
            "M2", date(2024, 1, 15), False, 0.75
        ))
        # FN: low confidence + was anomaly
        self.processor.submit_feedback(FeedbackRecord(
            "M3", date(2024, 1, 15), True, 0.3
        ))

        metrics = self.processor.compute_metrics()

        self.assertEqual(metrics.total_inspected, 3)
        self.assertEqual(metrics.true_positives, 1)
        self.assertEqual(metrics.false_positives, 1)
        self.assertEqual(metrics.false_negatives, 1)

    def test_suggest_threshold_raise_when_precision_low(self) -> None:
        """Suggest raising threshold when precision below target."""
        # Add many FPs (low precision scenario)
        for i in range(5):
            self.processor.submit_feedback(FeedbackRecord(
                f"M{i}", date(2024, 1, 15), False, 0.8  # Predicted anomaly, was normal
            ))
        # Add one TP
        self.processor.submit_feedback(FeedbackRecord(
            "M99", date(2024, 1, 15), True, 0.8
        ))

        suggestion = self.processor.suggest_threshold_adjustment(current_threshold=0.5)

        self.assertGreater(suggestion["suggested_threshold"], 0.5)
        self.assertIn("Precision", suggestion["reason"])

    def test_suggest_threshold_lower_when_recall_low(self) -> None:
        """Suggest lowering threshold when recall below target."""
        # Add many FNs (low recall scenario) - missed anomalies
        for i in range(5):
            self.processor.submit_feedback(FeedbackRecord(
                f"M{i}", date(2024, 1, 15), True, 0.3  # Low confidence, but was anomaly
            ))
        # Add one TP
        self.processor.submit_feedback(FeedbackRecord(
            "M99", date(2024, 1, 15), True, 0.8
        ))

        suggestion = self.processor.suggest_threshold_adjustment(current_threshold=0.5)

        self.assertLess(suggestion["suggested_threshold"], 0.5)
        self.assertIn("Recall", suggestion["reason"])

    def test_suggest_no_change_when_targets_met(self) -> None:
        """No adjustment when precision and recall on target."""
        # Good performance
        for i in range(8):
            self.processor.submit_feedback(FeedbackRecord(
                f"M{i}", date(2024, 1, 15), True, 0.8  # TP
            ))
        for i in range(2):
            self.processor.submit_feedback(FeedbackRecord(
                f"M{i+10}", date(2024, 1, 15), False, 0.8  # FP
            ))

        suggestion = self.processor.suggest_threshold_adjustment(current_threshold=0.5)

        self.assertEqual(suggestion["suggested_threshold"], 0.5)
        self.assertIn("No adjustment", suggestion["reason"])

    def test_get_feedback_summary(self) -> None:
        """Summary for reporting."""
        self.processor.submit_feedback(FeedbackRecord(
            "M1", date(2024, 1, 15), True, 0.85
        ))
        self.processor.submit_feedback(FeedbackRecord(
            "M2", date(2024, 1, 15), False, 0.75
        ))

        summary = self.processor.get_feedback_summary()

        self.assertEqual(summary["total_feedback"], 2)
        self.assertEqual(summary["confirmed_anomalies"], 1)
        self.assertEqual(summary["dismissed_false_positives"], 1)
        self.assertEqual(summary["confirmation_rate"], 0.5)

    def test_filter_by_meter(self) -> None:
        """Get summary filtered to specific meter."""
        self.processor.submit_feedback(FeedbackRecord(
            "M1", date(2024, 1, 15), True, 0.85
        ))
        self.processor.submit_feedback(FeedbackRecord(
            "M2", date(2024, 1, 16), False, 0.75
        ))

        summary = self.processor.get_feedback_summary(meter_id="M1")

        self.assertEqual(summary["total_feedback"], 1)

    def test_compute_metrics_since_date(self) -> None:
        """Filter metrics by date."""
        old_date = date(2024, 1, 1)
        new_date = date(2024, 1, 15)

        self.processor.submit_feedback(FeedbackRecord(
            "M1", old_date, True, 0.85
        ))
        self.processor.submit_feedback(FeedbackRecord(
            "M2", new_date, True, 0.85
        ))

        metrics = self.processor.compute_metrics(since=date(2024, 1, 10))

        self.assertEqual(metrics.total_inspected, 1)  # Only new_date


if __name__ == "__main__":
    unittest.main()

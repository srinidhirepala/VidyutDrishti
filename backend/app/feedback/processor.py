"""Feedback processing and model recalibration.

Processes inspection feedback to:
1. Track detection accuracy (true positives, false positives)
2. Calculate precision/recall metrics
3. Suggest threshold adjustments
4. Maintain feedback history for model improvement
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class FeedbackRecord:
    """Single inspection feedback record."""

    meter_id: str
    inspection_date: date
    was_anomaly: bool  # True if theft/meter fault confirmed
    detection_confidence: float  # Confidence score at time of detection
    actual_kwh_observed: float | None = None
    notes: str | None = None
    inspector_id: str | None = None

    # Metadata
    submitted_at: datetime = field(default_factory=datetime.utcnow)

    def to_db_row(self) -> dict[str, Any]:
        """Serialize for feedback table."""
        return {
            "meter_id": self.meter_id,
            "inspection_date": self.inspection_date,
            "was_anomaly": self.was_anomaly,
            "detection_confidence": self.detection_confidence,
            "actual_kwh_observed": self.actual_kwh_observed,
            "notes": self.notes,
            "inspector_id": self.inspector_id,
            "submitted_at": self.submitted_at,
        }


@dataclass
class AccuracyMetrics:
    """Detection accuracy metrics."""

    total_inspected: int
    true_positives: int  # Predicted anomaly, was anomaly
    false_positives: int  # Predicted anomaly, was normal
    false_negatives: int  # Predicted normal, was anomaly (missed)

    @property
    def precision(self) -> float:
        """Precision = TP / (TP + FP)"""
        if self.true_positives + self.false_positives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_positives)

    @property
    def recall(self) -> float:
        """Recall = TP / (TP + FN)"""
        if self.true_positives + self.false_negatives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_negatives)

    @property
    def f1_score(self) -> float:
        """F1 = 2 * (precision * recall) / (precision + recall)"""
        if self.precision + self.recall == 0:
            return 0.0
        return 2 * (self.precision * self.recall) / (self.precision + self.recall)


class FeedbackProcessor:
    """Process inspection feedback and compute accuracy metrics.

    Tracks detection performance and suggests threshold adjustments
    to optimize precision/recall trade-off.
    """

    def __init__(
        self,
        target_precision: float = 0.8,
        target_recall: float = 0.7,
    ) -> None:
        self.target_precision = target_precision
        self.target_recall = target_recall
        self.feedback_history: list[FeedbackRecord] = []

    def submit_feedback(self, record: FeedbackRecord) -> None:
        """Submit a new feedback record."""
        self.feedback_history.append(record)

    def compute_metrics(
        self,
        since: date | None = None,
        min_confidence: float = 0.0,
    ) -> AccuracyMetrics:
        """Compute accuracy metrics from feedback history.

        Args:
            since: Only consider feedback since this date
            min_confidence: Only consider detections above this confidence

        Returns:
            AccuracyMetrics with precision, recall, F1
        """
        feedback = self.feedback_history

        if since:
            feedback = [f for f in feedback if f.inspection_date >= since]

        if min_confidence > 0:
            feedback = [f for f in feedback if f.detection_confidence >= min_confidence]

        total = len(feedback)
        tp = sum(1 for f in feedback if f.detection_confidence >= 0.5 and f.was_anomaly)
        fp = sum(1 for f in feedback if f.detection_confidence >= 0.5 and not f.was_anomaly)
        fn = sum(1 for f in feedback if f.detection_confidence < 0.5 and f.was_anomaly)

        return AccuracyMetrics(
            total_inspected=total,
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
        )

    def suggest_threshold_adjustment(
        self,
        current_threshold: float = 0.5,
    ) -> dict[str, Any]:
        """Suggest threshold adjustment based on metrics.

        Analyzes current precision/recall against targets and
        recommends threshold changes.

        Returns:
            Dict with suggested_threshold, reason, expected_impact
        """
        metrics = self.compute_metrics()

        suggestion = {
            "current_threshold": current_threshold,
            "current_precision": metrics.precision,
            "current_recall": metrics.recall,
            "target_precision": self.target_precision,
            "target_recall": self.target_recall,
            "suggested_threshold": current_threshold,
            "reason": "No adjustment needed",
            "expected_impact": "Maintain current performance",
        }

        # If precision too low, raise threshold
        if metrics.precision < self.target_precision:
            suggestion["suggested_threshold"] = min(0.9, current_threshold + 0.1)
            suggestion["reason"] = f"Precision {metrics.precision:.2f} below target {self.target_precision}"
            suggestion["expected_impact"] = "Increase precision, may decrease recall"

        # If recall too low, lower threshold
        elif metrics.recall < self.target_recall:
            suggestion["suggested_threshold"] = max(0.3, current_threshold - 0.1)
            suggestion["reason"] = f"Recall {metrics.recall:.2f} below target {self.target_recall}"
            suggestion["expected_impact"] = "Increase recall, may decrease precision"

        return suggestion

    def get_feedback_summary(
        self,
        meter_id: str | None = None,
    ) -> dict[str, Any]:
        """Get summary of feedback for reporting.

        Args:
            meter_id: Optional meter to filter by

        Returns:
            Summary dict with counts and recent activity
        """
        feedback = self.feedback_history
        if meter_id:
            feedback = [f for f in feedback if f.meter_id == meter_id]

        total = len(feedback)
        confirmed_anomalies = sum(1 for f in feedback if f.was_anomaly)
        dismissed = total - confirmed_anomalies

        # Group by date
        by_date: dict[date, int] = {}
        for f in feedback:
            by_date[f.inspection_date] = by_date.get(f.inspection_date, 0) + 1

        return {
            "total_feedback": total,
            "confirmed_anomalies": confirmed_anomalies,
            "dismissed_false_positives": dismissed,
            "confirmation_rate": confirmed_anomalies / total if total > 0 else 0,
            "feedback_by_date": by_date,
            "recent_submissions": [f.to_db_row() for f in feedback[-5:]],
        }

    def export_feedback_csv(self, output_path: Path) -> int:
        """Export all feedback to CSV for analysis.

        Returns count of records exported.
        """
        if not self.feedback_history:
            return 0

        rows = [f.to_db_row() for f in self.feedback_history]
        df = pd.DataFrame(rows)
        df.to_csv(output_path, index=False)
        return len(rows)


def batch_process_feedback(
    feedback_csv: Path,
    output_report: Path,
) -> dict[str, Any]:
    """CLI helper: Process feedback from CSV and generate report.

    Returns accuracy metrics and threshold suggestions.
    """
    df = pd.read_csv(feedback_csv, parse_dates=["inspection_date"])

    processor = FeedbackProcessor()

    for _, row in df.iterrows():
        record = FeedbackRecord(
            meter_id=str(row["meter_id"]),
            inspection_date=row["inspection_date"].date(),
            was_anomaly=bool(row["was_anomaly"]),
            detection_confidence=float(row.get("detection_confidence", 0.5)),
            actual_kwh_observed=row.get("actual_kwh_observed"),
            notes=row.get("notes"),
            inspector_id=row.get("inspector_id"),
        )
        processor.submit_feedback(record)

    metrics = processor.compute_metrics()
    suggestion = processor.suggest_threshold_adjustment()

    report = {
        "accuracy_metrics": {
            "total_inspected": metrics.total_inspected,
            "true_positives": metrics.true_positives,
            "false_positives": metrics.false_positives,
            "false_negatives": metrics.false_negatives,
            "precision": round(metrics.precision, 3),
            "recall": round(metrics.recall, 3),
            "f1_score": round(metrics.f1_score, 3),
        },
        "threshold_suggestion": suggestion,
    }

    # Write report
    import json
    with open(output_report, "w") as f:
        json.dump(report, f, indent=2, default=str)

    return report

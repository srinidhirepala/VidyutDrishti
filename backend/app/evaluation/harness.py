"""Evaluation Harness: Benchmark detection system against labeled ground truth.

Provides end-to-end evaluation pipeline for measuring detection performance
using labeled test datasets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class GroundTruthLabel:
    """Labeled ground truth for a meter on a specific date."""

    meter_id: str
    date: date
    is_anomaly: bool  # True if actual theft/meter fault
    anomaly_type: str | None = None  # "theft", "meter_fault", "normal"
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "meter_id": self.meter_id,
            "date": self.date,
            "is_anomaly": self.is_anomaly,
            "anomaly_type": self.anomaly_type,
            "notes": self.notes,
        }


@dataclass
class DetectionPrediction:
    """Detection result for a meter on a specific date."""

    meter_id: str
    date: date
    confidence: float
    is_anomaly: bool  # True if system flagged
    anomaly_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "meter_id": self.meter_id,
            "date": self.date,
            "confidence": self.confidence,
            "is_anomaly": self.is_anomaly,
            "anomaly_type": self.anomaly_type,
        }


@dataclass
class EvaluationMetrics:
    """Performance metrics from evaluation."""

    total_samples: int
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int

    @property
    def accuracy(self) -> float:
        """Overall accuracy."""
        if self.total_samples == 0:
            return 0.0
        correct = self.true_positives + self.true_negatives
        return correct / self.total_samples

    @property
    def precision(self) -> float:
        """Precision = TP / (TP + FP)"""
        denom = self.true_positives + self.false_positives
        if denom == 0:
            return 0.0
        return self.true_positives / denom

    @property
    def recall(self) -> float:
        """Recall = TP / (TP + FN)"""
        denom = self.true_positives + self.false_negatives
        if denom == 0:
            return 0.0
        return self.true_positives / denom

    @property
    def f1_score(self) -> float:
        """F1 score."""
        if self.precision + self.recall == 0:
            return 0.0
        return 2 * (self.precision * self.recall) / (self.precision + self.recall)

    @property
    def specificity(self) -> float:
        """Specificity = TN / (TN + FP)"""
        denom = self.true_negatives + self.false_positives
        if denom == 0:
            return 0.0
        return self.true_negatives / denom

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_samples": self.total_samples,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "true_negatives": self.true_negatives,
            "accuracy": round(self.accuracy, 4),
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
            "specificity": round(self.specificity, 4),
        }


@dataclass
class EvaluationResult:
    """Complete evaluation result."""

    name: str
    metrics: EvaluationMetrics
    threshold_used: float
    confusion_matrix: dict[str, list]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_report(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "timestamp": self.timestamp.isoformat(),
            "threshold_used": self.threshold_used,
            "metrics": self.metrics.to_dict(),
            "confusion_matrix": self.confusion_matrix,
        }


class EvaluationHarness:
    """End-to-end evaluation framework for detection system.

    Compares detection predictions against ground truth labels
    to compute comprehensive performance metrics.
    """

    def __init__(self, confidence_threshold: float = 0.5) -> None:
        self.confidence_threshold = confidence_threshold

    def load_ground_truth(self, labels_df: pd.DataFrame) -> list[GroundTruthLabel]:
        """Load ground truth labels from DataFrame."""
        labels = []
        for _, row in labels_df.iterrows():
            label = GroundTruthLabel(
                meter_id=str(row["meter_id"]),
                date=row["date"] if isinstance(row["date"], date) else pd.to_datetime(row["date"]).date(),
                is_anomaly=bool(row["is_anomaly"]),
                anomaly_type=row.get("anomaly_type"),
                notes=row.get("notes"),
            )
            labels.append(label)
        return labels

    def load_predictions(self, predictions_df: pd.DataFrame) -> list[DetectionPrediction]:
        """Load detection predictions from DataFrame."""
        predictions = []
        for _, row in predictions_df.iterrows():
            pred = DetectionPrediction(
                meter_id=str(row["meter_id"]),
                date=row["date"] if isinstance(row["date"], date) else pd.to_datetime(row["date"]).date(),
                confidence=float(row.get("confidence", 0)),
                is_anomaly=float(row.get("confidence", 0)) >= self.confidence_threshold,
                anomaly_type=row.get("anomaly_type"),
            )
            predictions.append(pred)
        return predictions

    def evaluate(
        self,
        ground_truth: list[GroundTruthLabel],
        predictions: list[DetectionPrediction],
        name: str = "evaluation",
    ) -> EvaluationResult:
        """Run evaluation comparing predictions to ground truth.

        Args:
            ground_truth: List of labeled ground truth
            predictions: List of detection predictions
            name: Evaluation run name

        Returns:
            EvaluationResult with comprehensive metrics
        """
        # Create lookup by (meter_id, date)
        truth_lookup = {(l.meter_id, l.date): l for l in ground_truth}
        pred_lookup = {(p.meter_id, p.date): p for p in predictions}

        # Find all unique (meter, date) pairs
        all_keys = set(truth_lookup.keys()) | set(pred_lookup.keys())

        # Count outcomes
        tp = fp = fn = tn = 0
        cm_data = {"actual": [], "predicted": []}

        for key in all_keys:
            truth = truth_lookup.get(key)
            pred = pred_lookup.get(key)

            actual = truth.is_anomaly if truth else False
            predicted = pred.is_anomaly if pred else False

            cm_data["actual"].append("anomaly" if actual else "normal")
            cm_data["predicted"].append("anomaly" if predicted else "normal")

            if actual and predicted:
                tp += 1
            elif not actual and predicted:
                fp += 1
            elif actual and not predicted:
                fn += 1
            else:
                tn += 1

        metrics = EvaluationMetrics(
            total_samples=len(all_keys),
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            true_negatives=tn,
        )

        return EvaluationResult(
            name=name,
            metrics=metrics,
            threshold_used=self.confidence_threshold,
            confusion_matrix=cm_data,
        )

    def evaluate_from_csv(
        self,
        ground_truth_csv: Path,
        predictions_csv: Path,
        name: str = "evaluation",
    ) -> EvaluationResult:
        """Run evaluation from CSV files.

        Args:
            ground_truth_csv: Path to ground truth CSV
            predictions_csv: Path to predictions CSV
            name: Evaluation run name

        Returns:
            EvaluationResult
        """
        gt_df = pd.read_csv(ground_truth_csv, parse_dates=["date"])
        pred_df = pd.read_csv(predictions_csv, parse_dates=["date"])

        ground_truth = self.load_ground_truth(gt_df)
        predictions = self.load_predictions(pred_df)

        return self.evaluate(ground_truth, predictions, name)

    def threshold_sweep(
        self,
        ground_truth: list[GroundTruthLabel],
        predictions: list[DetectionPrediction],
        thresholds: list[float] | None = None,
    ) -> list[dict[str, Any]]:
        """Evaluate across multiple confidence thresholds.

        Args:
            ground_truth: Ground truth labels
            predictions: Predictions (with confidence scores)
            thresholds: List of thresholds to test (default: 0.1 to 0.9)

        Returns:
            List of metrics dicts for each threshold
        """
        if thresholds is None:
            thresholds = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

        results = []
        original_threshold = self.confidence_threshold

        for thresh in thresholds:
            self.confidence_threshold = thresh
            # Reload predictions with new threshold
            pred_lookup = {}
            for p in predictions:
                new_pred = DetectionPrediction(
                    meter_id=p.meter_id,
                    date=p.date,
                    confidence=p.confidence,
                    is_anomaly=p.confidence >= thresh,
                    anomaly_type=p.anomaly_type,
                )
                pred_lookup[(p.meter_id, p.date)] = new_pred
            new_predictions = list(pred_lookup.values())

            result = self.evaluate(ground_truth, new_predictions, f"threshold_{thresh}")
            results.append({
                "threshold": thresh,
                **result.metrics.to_dict(),
            })

        self.confidence_threshold = original_threshold
        return results


def run_evaluation_cli(
    ground_truth_csv: Path,
    predictions_csv: Path,
    output_json: Path,
    threshold: float = 0.5,
) -> dict[str, Any]:
    """CLI entry point for evaluation.

    Returns evaluation report as dict and writes to JSON.
    """
    harness = EvaluationHarness(confidence_threshold=threshold)
    result = harness.evaluate_from_csv(ground_truth_csv, predictions_csv)
    report = result.to_report()

    import json
    with open(output_json, "w") as f:
        json.dump(report, f, indent=2, default=str)

    return report

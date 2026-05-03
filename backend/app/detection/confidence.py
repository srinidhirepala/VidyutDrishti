"""Confidence Engine: Aggregates 4-layer signals into unified confidence score.

Combines Layer 0 (DT balance), Layer 1 (z-score), Layer 2 (peer comparison),
and Layer 3 (Isolation Forest) outputs into a single confidence score (0-1)
for ranking inspection priorities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class LayerSignals:
    """Signals from all 4 detection layers for a single meter."""

    # Layer 0: DT Balance (aggregate - applies to all meters under DT)
    l0_dt_imbalance_pct: float | None = None
    l0_is_anomaly: bool = False

    # Layer 1: Z-Score
    l1_z_score: float | None = None
    l1_is_anomaly: bool = False

    # Layer 2: Peer Comparison
    l2_deviation_pct: float | None = None
    l2_is_anomaly: bool = False

    # Layer 3: Isolation Forest
    l3_anomaly_score: float | None = None
    l3_is_anomaly: bool = False


@dataclass
class ConfidenceResult:
    """Unified confidence result for a single meter."""

    meter_id: str
    dt_id: str
    feeder_id: str
    date: date

    # Layer signals
    signals: LayerSignals

    # Aggregated score
    confidence: float  # 0.0 - 1.0
    rank: int  # 1 = highest priority

    # Layer contributions (for explainability)
    l0_contrib: float
    l1_contrib: float
    l2_contrib: float
    l3_contrib: float

    # Metadata
    computed_at: datetime = field(default_factory=datetime.utcnow)

    def to_db_row(self) -> dict[str, Any]:
        """Serialize to dict for detection_results table."""
        return {
            "meter_id": self.meter_id,
            "dt_id": self.dt_id,
            "feeder_id": self.feeder_id,
            "date": self.date,
            "confidence": self.confidence,
            "rank": self.rank,
            "l0_contrib": self.l0_contrib,
            "l1_contrib": self.l1_contrib,
            "l2_contrib": self.l2_contrib,
            "l3_contrib": self.l3_contrib,
            "l0_anomaly": self.signals.l0_is_anomaly,
            "l1_anomaly": self.signals.l1_is_anomaly,
            "l2_anomaly": self.signals.l2_is_anomaly,
            "l3_anomaly": self.signals.l3_is_anomaly,
            "computed_at": self.computed_at,
        }


class ConfidenceEngine:
    """Aggregate 4-layer detection signals into unified confidence score.

    Weights:
    - Layer 0: 10% (aggregate signal, less specific to individual meter)
    - Layer 1: 30% (individual historical baseline)
    - Layer 2: 30% (peer-relative comparison)
    - Layer 3: 30% (multivariate pattern detection)
    """

    WEIGHTS = {
        "l0": 0.10,
        "l1": 0.30,
        "l2": 0.30,
        "l3": 0.30,
    }

    def __init__(self) -> None:
        pass

    def _compute_layer_score(
        self,
        is_anomaly: bool,
        magnitude: float | None,
        threshold: float,
    ) -> float:
        """Compute normalized 0-1 score for a layer.

        Returns higher score for more extreme anomalies.
        """
        if not is_anomaly:
            return 0.0
        if magnitude is None:
            return 0.5  # Anomaly but no magnitude info

        # Normalize by threshold
        ratio = abs(magnitude) / threshold
        # Cap at 1.0 for extremes
        return min(1.0, ratio / 3.0)  # ratio=3 gives score=1.0

    def compute(
        self,
        meter_id: str,
        dt_id: str,
        feeder_id: str,
        target_date: date,
        signals: LayerSignals,
    ) -> ConfidenceResult:
        """Compute confidence score from layer signals.

        Args:
            meter_id: Meter identifier
            dt_id: Distribution transformer ID
            feeder_id: Feeder/substation ID
            target_date: Date of analysis
            signals: LayerSignals with all 4 layer outputs

        Returns:
            ConfidenceResult with aggregated score
        """
        # Compute individual layer scores
        l0_score = self._compute_layer_score(
            signals.l0_is_anomaly,
            signals.l0_dt_imbalance_pct,
            3.0,  # Layer 0 threshold
        )
        l1_score = self._compute_layer_score(
            signals.l1_is_anomaly,
            signals.l1_z_score,
            3.0,  # Layer 1 threshold
        )
        l2_score = self._compute_layer_score(
            signals.l2_is_anomaly,
            signals.l2_deviation_pct,
            10.0,  # Layer 2 threshold in percent
        )
        l3_score = self._compute_layer_score(
            signals.l3_is_anomaly,
            signals.l3_anomaly_score,
            0.5,  # Layer 3 threshold (anomaly score)
        )

        # Weighted aggregation
        confidence = (
            self.WEIGHTS["l0"] * l0_score +
            self.WEIGHTS["l1"] * l1_score +
            self.WEIGHTS["l2"] * l2_score +
            self.WEIGHTS["l3"] * l3_score
        )

        # Ensure 0-1 range
        confidence = max(0.0, min(1.0, confidence))

        # Compute contributions (percentage of total)
        total = l0_score + l1_score + l2_score + l3_score
        if total > 0:
            l0_contrib = l0_score / total
            l1_contrib = l1_score / total
            l2_contrib = l2_score / total
            l3_contrib = l3_score / total
        else:
            l0_contrib = l1_contrib = l2_contrib = l3_contrib = 0.25

        return ConfidenceResult(
            meter_id=meter_id,
            dt_id=dt_id,
            feeder_id=feeder_id,
            date=target_date,
            signals=signals,
            confidence=confidence,
            rank=0,  # Will be assigned by batch processor
            l0_contrib=l0_contrib,
            l1_contrib=l1_contrib,
            l2_contrib=l2_contrib,
            l3_contrib=l3_contrib,
        )

    def compute_batch(
        self,
        signals_df: pd.DataFrame,  # Columns for all layer signals
    ) -> list[ConfidenceResult]:
        """Compute confidence for all meters in batch and assign ranks.

        Args:
            signals_df: DataFrame with layer signal columns

        Returns:
            List of ConfidenceResult sorted by confidence descending
        """
        results: list[ConfidenceResult] = []

        for _, row in signals_df.iterrows():
            signals = LayerSignals(
                l0_dt_imbalance_pct=row.get("l0_dt_imbalance_pct"),
                l0_is_anomaly=bool(row.get("l0_is_anomaly", False)),
                l1_z_score=row.get("l1_z_score"),
                l1_is_anomaly=bool(row.get("l1_is_anomaly", False)),
                l2_deviation_pct=row.get("l2_deviation_pct"),
                l2_is_anomaly=bool(row.get("l2_is_anomaly", False)),
                l3_anomaly_score=row.get("l3_anomaly_score"),
                l3_is_anomaly=bool(row.get("l3_is_anomaly", False)),
            )

            result = self.compute(
                meter_id=str(row["meter_id"]),
                dt_id=str(row.get("dt_id", "")),
                feeder_id=str(row.get("feeder_id", "")),
                target_date=row.get("date", date.today()),
                signals=signals,
            )
            results.append(result)

        # Sort by confidence descending and assign ranks
        results.sort(key=lambda r: r.confidence, reverse=True)
        for i, result in enumerate(results, 1):
            result.rank = i

        return results


def compute_confidence_csv(
    signals_csv: Path,
    output_csv: Path,
) -> int:
    """CLI helper: compute confidence from CSV and write output.

    Returns count of meters processed.
    """
    signals_df = pd.read_csv(signals_csv, parse_dates=["date"])

    engine = ConfidenceEngine()
    results = engine.compute_batch(signals_df)

    if results:
        rows = [r.to_db_row() for r in results]
        df = pd.DataFrame(rows)
        df.to_csv(output_csv, index=False)

    return len(results)

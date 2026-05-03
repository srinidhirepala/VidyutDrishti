"""Leakage Quantification: Estimate revenue loss from detected anomalies.

Translates meter-level anomalies into financial impact (kWh lost, INR lost)
using tariff rates and anomaly magnitude.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class LeakageEstimate:
    """Financial impact estimate for a single meter anomaly."""

    meter_id: str
    dt_id: str
    feeder_id: str
    date: date

    # Detection context
    anomaly_type: str
    confidence: float

    # Quantification
    estimated_kwh_lost: float | None  # kWh unaccounted for
    tariff_rate_per_kwh: Decimal | None  # INR per kWh
    estimated_inr_lost: Decimal | None  # Financial impact

    # Methodology
    basis: str  # How estimate was derived (e.g., "peer_deviation", "z_score_extrapolation")

    # Metadata
    computed_at: datetime = field(default_factory=datetime.utcnow)

    def to_db_row(self) -> dict[str, Any]:
        """Serialize to dict for leakage_estimates table."""
        return {
            "meter_id": self.meter_id,
            "dt_id": self.dt_id,
            "feeder_id": self.feeder_id,
            "date": self.date,
            "anomaly_type": self.anomaly_type,
            "confidence": self.confidence,
            "estimated_kwh_lost": self.estimated_kwh_lost,
            "tariff_rate_per_kwh": float(self.tariff_rate_per_kwh) if self.tariff_rate_per_kwh else None,
            "estimated_inr_lost": float(self.estimated_inr_lost) if self.estimated_inr_lost else None,
            "basis": self.basis,
            "computed_at": self.computed_at,
        }


class LeakageQuantifier:
    """Quantify financial impact of detected anomalies.

    Uses detection results and tariff rates to estimate revenue leakage.
    """

    def __init__(
        self,
        default_tariff_per_kwh: Decimal = Decimal("7.50"),  # Typical domestic rate
    ) -> None:
        self.default_tariff = default_tariff_per_kwh

    def _estimate_from_peer_deviation(
        self,
        actual_kwh: float,
        peer_mean: float,
    ) -> tuple[float | None, str]:
        """Estimate loss from peer deviation.

        Returns: (kwh_lost, basis)
        """
        if peer_mean <= 0:
            return None, "insufficient_peer_data"

        # Loss = difference from expected (peer mean)
        loss = peer_mean - actual_kwh
        if loss <= 0:
            return 0.0, "no_loss_actual_exceeds_expected"

        return loss, "peer_deviation"

    def _estimate_from_z_score(
        self,
        actual_kwh: float,
        historical_mean: float,
        historical_std: float,
    ) -> tuple[float | None, str]:
        """Estimate loss from z-score deviation.

        Returns: (kwh_lost, basis)
        """
        if historical_mean <= 0 or historical_std <= 0:
            return None, "insufficient_history"

        # Expected consumption based on historical mean
        loss = historical_mean - actual_kwh
        if loss <= 0:
            return 0.0, "no_loss_actual_exceeds_expected"

        # Cap at 3 std devs (beyond that is likely meter fault, not theft)
        max_reasonable_loss = 3 * historical_std
        capped_loss = min(loss, max_reasonable_loss)

        return capped_loss, "z_score_extrapolation"

    def quantify(
        self,
        meter_id: str,
        dt_id: str,
        feeder_id: str,
        target_date: date,
        anomaly_type: str,
        confidence: float,
        actual_kwh: float,
        peer_mean: float | None = None,
        historical_mean: float | None = None,
        historical_std: float | None = None,
        tariff_per_kwh: Decimal | None = None,
    ) -> LeakageEstimate:
        """Quantify leakage for a single meter.

        Args:
            meter_id: Meter identifier
            dt_id: Distribution transformer ID
            feeder_id: Feeder/substation ID
            target_date: Date of anomaly
            anomaly_type: Type of anomaly (from classifier)
            confidence: Detection confidence
            actual_kwh: Actual consumption
            peer_mean: Peer group mean (if available)
            historical_mean: Historical mean (if available)
            historical_std: Historical std dev (if available)
            tariff_per_kwh: Tariff rate (uses default if None)

        Returns:
            LeakageEstimate with financial impact
        """
        tariff = tariff_per_kwh or self.default_tariff

        # Try peer deviation first (most reliable for theft)
        kwh_lost = None
        basis = "insufficient_data"

        if peer_mean is not None:
            kwh_lost, basis = self._estimate_from_peer_deviation(actual_kwh, peer_mean)

        # Fall back to z-score method
        if kwh_lost is None and historical_mean is not None and historical_std is not None:
            kwh_lost, basis = self._estimate_from_z_score(
                actual_kwh, historical_mean, historical_std
            )

        # Calculate INR
        inr_lost = None
        if kwh_lost is not None:
            inr_lost = Decimal(str(kwh_lost)) * tariff

        return LeakageEstimate(
            meter_id=meter_id,
            dt_id=dt_id,
            feeder_id=feeder_id,
            date=target_date,
            anomaly_type=anomaly_type,
            confidence=confidence,
            estimated_kwh_lost=kwh_lost,
            tariff_rate_per_kwh=tariff,
            estimated_inr_lost=inr_lost,
            basis=basis,
        )

    def quantify_batch(
        self,
        detections_df: pd.DataFrame,  # Detection results with metrics
        topology_df: pd.DataFrame,  # meter_id, dt_id, feeder_id
        target_date: date,
    ) -> list[LeakageEstimate]:
        """Quantify leakage for all detections in batch.

        Args:
            detections_df: DataFrame with detection results
            topology_df: DataFrame with meter topology
            target_date: Date to process

        Returns:
            List of LeakageEstimate
        """
        results: list[LeakageEstimate] = []

        if detections_df.empty:
            return results

        # Merge with topology
        merged = detections_df.merge(topology_df, on="meter_id", how="left")

        for _, row in merged.iterrows():
            dt_id = str(row.get("dt_id", ""))
            feeder_id = str(row.get("feeder_id", ""))

            estimate = self.quantify(
                meter_id=str(row["meter_id"]),
                dt_id=dt_id,
                feeder_id=feeder_id,
                target_date=target_date,
                anomaly_type=str(row.get("anomaly_type", "unknown")),
                confidence=float(row.get("confidence", 0.5)),
                actual_kwh=float(row.get("actual_kwh", 0)),
                peer_mean=row.get("peer_mean"),
                historical_mean=row.get("historical_mean"),
                historical_std=row.get("historical_std"),
            )
            results.append(estimate)

        return results


def quantify_leakage_csv(
    detections_csv: Path,
    topology_csv: Path,
    target_date: date,
    output_csv: Path,
) -> int:
    """CLI helper: quantify from CSV files and write output.

    Returns count of estimates generated.
    """
    detections_df = pd.read_csv(detections_csv)
    topology_df = pd.read_csv(topology_csv)

    quantifier = LeakageQuantifier()
    results = quantifier.quantify_batch(detections_df, topology_df, target_date)

    if results:
        rows = [r.to_db_row() for r in results]
        df = pd.DataFrame(rows)
        df.to_csv(output_csv, index=False)

    return len(results)

"""Zone risk classification logic.

Compares forecasted peak demand against feeder capacity to produce
HIGH/MEDIUM/LOW risk levels.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from .models import RiskLevel, ZoneRiskResult


# Default headroom thresholds (percent) for risk classification
# Configurable at runtime via ZoneRiskClassifier constructor
DEFAULT_HIGH_THRESHOLD = 10.0    # < 10% headroom = HIGH risk
DEFAULT_MEDIUM_THRESHOLD = 25.0  # < 25% headroom = MEDIUM risk
# >= 25% headroom = LOW risk


@dataclass
class FeederCapacity:
    """Static capacity data for a feeder."""

    feeder_id: str
    capacity_kva: float | None
    historical_peak_kw: float | None


class ZoneRiskClassifier:
    """Classify feeder zones by risk based on forecasted load vs capacity."""

    def __init__(
        self,
        high_threshold: float = DEFAULT_HIGH_THRESHOLD,
        medium_threshold: float = DEFAULT_MEDIUM_THRESHOLD,
        pf_assumption: float = 0.9,  # Assumed power factor to convert kVA->kW
    ) -> None:
        if not (0 < high_threshold < medium_threshold < 100):
            raise ValueError("Thresholds must satisfy 0 < high < medium < 100")
        self.high_threshold = high_threshold
        self.medium_threshold = medium_threshold
        self.pf_assumption = pf_assumption

    # -----------------------------------------------------------------------
    # Classification logic
    # -----------------------------------------------------------------------

    def _capacity_kw(self, cap: FeederCapacity) -> float | None:
        """Convert capacity to kW using assumed PF, or use historical peak as fallback."""
        if cap.capacity_kva is not None:
            return cap.capacity_kva * self.pf_assumption
        if cap.historical_peak_kw is not None:
            return cap.historical_peak_kw * 1.2  # 20% margin over historical
        return None

    def _headroom_percent(self, predicted_kw: float, capacity_kw: float) -> float:
        """Calculate headroom percentage. Negative means overload."""
        if capacity_kw <= 0:
            return -100.0
        return (capacity_kw - predicted_kw) / capacity_kw * 100.0

    def _classify(self, headroom: float) -> RiskLevel:
        if headroom < self.high_threshold:
            return RiskLevel.HIGH
        if headroom < self.medium_threshold:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def classify(
        self,
        feeder_id: str,
        forecast_date: date,
        predicted_peak_kw: float,
        capacity: FeederCapacity,
    ) -> ZoneRiskResult:
        """Produce a ZoneRiskResult for a single feeder/date."""
        capacity_kw = self._capacity_kw(capacity)
        if capacity_kw is None:
            # No capacity data - assume worst case (HIGH) to force attention
            headroom = -50.0
        else:
            headroom = self._headroom_percent(predicted_peak_kw, capacity_kw)

        return ZoneRiskResult(
            feeder_id=feeder_id,
            forecast_date=forecast_date,
            level=self._classify(headroom),
            predicted_peak_kw=predicted_peak_kw,
            capacity_kva=capacity.capacity_kva,
            headroom_percent=headroom,
            computed_at=datetime.utcnow(),
        )

    # -----------------------------------------------------------------------
    # Batch operations
    # -----------------------------------------------------------------------

    def classify_forecast_df(
        self,
        forecast_df: pd.DataFrame,
        capacities: dict[str, FeederCapacity],
    ) -> list[ZoneRiskResult]:
        """Classify all rows in a forecast DataFrame.

        Args:
            forecast_df: DataFrame with columns [feeder_id, ds (datetime), yhat]
            capacities: Dict mapping feeder_id to FeederCapacity

        Returns:
            List of ZoneRiskResult for each forecast row.
        """
        results: list[ZoneRiskResult] = []
        for _, row in forecast_df.iterrows():
            feeder_id = str(row["feeder_id"])
            forecast_date = row["ds"].date() if isinstance(row["ds"], datetime) else row["ds"]
            predicted = float(row["yhat"])
            cap = capacities.get(feeder_id, FeederCapacity(feeder_id, None, None))
            results.append(self.classify(feeder_id, forecast_date, predicted, cap))
        return results


def classify_zones(
    forecast_csv: Path,
    capacity_csv: Path,
    output_csv: Path,
    high_threshold: float = DEFAULT_HIGH_THRESHOLD,
    medium_threshold: float = DEFAULT_MEDIUM_THRESHOLD,
) -> None:
    """CLI helper: classify from CSV files and write results."""
    forecasts = pd.read_csv(forecast_csv, parse_dates=["ds"])
    caps_df = pd.read_csv(capacity_csv)

    capacities: dict[str, FeederCapacity] = {}
    for _, row in caps_df.iterrows():
        fid = str(row["feeder_id"])
        capacities[fid] = FeederCapacity(
            feeder_id=fid,
            capacity_kva=float(row["capacity_kva"]) if pd.notna(row.get("capacity_kva")) else None,
            historical_peak_kw=float(row["historical_peak_kw"])
                         if pd.notna(row.get("historical_peak_kw")) else None,
        )

    classifier = ZoneRiskClassifier(high_threshold, medium_threshold)
    results = classifier.classify_forecast_df(forecasts, capacities)

    rows = [r.to_db_row() for r in results]
    df = pd.DataFrame(rows)
    df.to_csv(output_csv, index=False)

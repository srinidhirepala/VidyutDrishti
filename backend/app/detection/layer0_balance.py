"""Layer 0: DT Energy Balance Analysis.

Compares DT incoming energy (kwh_in) against sum of downstream meter consumption
plus expected technical losses. Flags imbalance beyond ±8% threshold.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class BalanceResult:
    """Result of DT energy balance analysis for a single DT on a single day."""

    dt_id: str
    feeder_id: str
    date: date

    # Energy quantities (kWh)
    dt_in_kwh: float
    meters_sum_kwh: float
    technical_loss_pct: float  # Expected technical loss % (typically 5-8%)
    expected_consumption: float  # dt_in * (1 - technical_loss_pct)

    # Balance metrics
    imbalance_kwh: float  # meters_sum - expected_consumption
    imbalance_pct: float  # imbalance / dt_in * 100 (can be negative = under-reporting)

    # Thresholding
    threshold_pct: float  # Typically 3%
    is_anomaly: bool  # True if abs(imbalance_pct) > threshold_pct

    # Context for downstream layers
    n_meters: int  # Number of downstream meters aggregated
    n_meters_missing: int  # Count of meters with no data for this day

    # Metadata
    computed_at: datetime

    def to_db_row(self) -> dict[str, Any]:
        """Serialize to dict for layer0_balance table."""
        return {
            "dt_id": self.dt_id,
            "feeder_id": self.feeder_id,
            "date": self.date,
            "dt_in_kwh": self.dt_in_kwh,
            "meters_sum_kwh": self.meters_sum_kwh,
            "technical_loss_pct": self.technical_loss_pct,
            "imbalance_kwh": self.imbalance_kwh,
            "imbalance_pct": self.imbalance_pct,
            "threshold_pct": self.threshold_pct,
            "is_anomaly": self.is_anomaly,
            "n_meters": self.n_meters,
            "n_meters_missing": self.n_meters_missing,
            "computed_at": self.computed_at,
        }


class BalanceAnalyzer:
    """Analyze DT-level energy balance for Layer 0 anomaly detection.

    Layer 0 detects aggregate theft scenarios (bypass at DT meter, unrecorded
    hook connections, meter tampering affecting many downstream consumers).
    """

    def __init__(
        self,
        threshold_pct: float = 8.0,
        default_technical_loss: float = 6.0,  # 6% typical for LT distribution
    ) -> None:
        self.threshold_pct = threshold_pct
        self.default_technical_loss = default_technical_loss

    def analyze(
        self,
        dt_id: str,
        feeder_id: str,
        target_date: date,
        dt_reading: dict[str, Any] | None,  # Should have kwh_in, kwh_out, losses
        meter_readings: list[dict[str, Any]],  # List of {meter_id, kwh, ...}
    ) -> BalanceResult | None:
        """Analyze energy balance for a single DT on a single day.

        Args:
            dt_id: Distribution transformer identifier
            feeder_id: Feeder/substation identifier
            target_date: Date to analyze
            dt_reading: DT reading dict with 'kwh_in' (and optionally 'losses')
            meter_readings: List of meter reading dicts with 'kwh' and 'meter_id'

        Returns:
            BalanceResult or None if insufficient data
        """
        if dt_reading is None:
            return None

        dt_in = float(dt_reading.get("kwh_in", 0.0))
        if dt_in <= 0:
            return None  # Invalid or missing DT input

        # Technical losses from DT reading or default
        raw_losses = dt_reading.get("losses")
        if raw_losses is not None:
            tech_loss_pct = float(raw_losses)
        else:
            tech_loss_pct = 0.0
        if tech_loss_pct <= 0:
            tech_loss_pct = self.default_technical_loss

        # Expected consumption after technical losses
        expected_consumption = dt_in * (1.0 - tech_loss_pct / 100.0)

        # Sum downstream meter consumption
        meters_sum = sum(float(m.get("kwh", 0.0)) for m in meter_readings)
        n_meters = len(meter_readings)
        n_missing = 0  # Could be computed if we know expected meter count

        # Imbalance calculation
        imbalance_kwh = meters_sum - expected_consumption
        imbalance_pct = (imbalance_kwh / dt_in) * 100.0 if dt_in > 0 else 0.0

        # Anomaly detection
        is_anomaly = abs(imbalance_pct) > self.threshold_pct

        return BalanceResult(
            dt_id=dt_id,
            feeder_id=feeder_id,
            date=target_date,
            dt_in_kwh=dt_in,
            meters_sum_kwh=meters_sum,
            technical_loss_pct=tech_loss_pct,
            expected_consumption=expected_consumption,
            imbalance_kwh=imbalance_kwh,
            imbalance_pct=imbalance_pct,
            threshold_pct=self.threshold_pct,
            is_anomaly=is_anomaly,
            n_meters=n_meters,
            n_meters_missing=n_missing,
            computed_at=datetime.utcnow(),
        )

    def analyze_batch(
        self,
        dt_daily: pd.DataFrame,
        meter_daily: pd.DataFrame,
        topology: pd.DataFrame,  # meter_id -> dt_id mapping
        target_date: date,
    ) -> list[BalanceResult]:
        """Analyze energy balance for all DTs in batch.

        Args:
            dt_daily: DataFrame with dt_id, date, kwh_in, losses columns
            meter_daily: DataFrame with meter_id, date, kwh columns
            topology: DataFrame with meter_id, dt_id, feeder_id columns
            target_date: Date to analyze

        Returns:
            List of BalanceResult for each DT with data
        """
        results: list[BalanceResult] = []

        # Handle empty DataFrames
        if dt_daily.empty or "date" not in dt_daily.columns:
            return results
        if meter_daily.empty or "date" not in meter_daily.columns:
            meter_daily = pd.DataFrame(columns=["meter_id", "date", "kwh"])

        # Ensure date columns are datetime.date for comparison
        def normalize_date(col):
            if pd.api.types.is_datetime64_any_dtype(col):
                return col.dt.date
            return col

        # Filter to target date
        dt_day = dt_daily[normalize_date(dt_daily["date"]) == target_date]
        meter_day = meter_daily[normalize_date(meter_daily["date"]) == target_date]

        # Get unique DTs for this date
        if dt_day.empty:
            return results

        for _, dt_row in dt_day.iterrows():
            dt_id = str(dt_row["dt_id"])
            feeder_id = str(dt_row.get("feeder_id", ""))

            # Get meters under this DT
            dt_meters = topology[topology["dt_id"] == dt_id]
            meter_ids = set(dt_meters["meter_id"].tolist())

            # Get meter readings for these meters
            meter_rows = meter_day[meter_day["meter_id"].isin(meter_ids)]
            meter_readings = meter_rows.to_dict("records")

            result = self.analyze(
                dt_id=dt_id,
                feeder_id=feeder_id,
                target_date=target_date,
                dt_reading=dt_row.to_dict(),
                meter_readings=meter_readings,
            )
            if result is not None:
                results.append(result)

        return results


def analyze_balance_csv(
    dt_csv: Path,
    meters_csv: Path,
    topology_csv: Path,
    target_date: date,
    output_csv: Path,
    threshold_pct: float = 3.0,
) -> int:
    """CLI helper: analyze from CSV files and write output.

    Returns count of DTs analyzed.
    """
    dt_daily = pd.read_csv(dt_csv, parse_dates=["date"])
    meter_daily = pd.read_csv(meters_csv, parse_dates=["date"])
    topology = pd.read_csv(topology_csv)

    analyzer = BalanceAnalyzer(threshold_pct=threshold_pct)
    results = analyzer.analyze_batch(dt_daily, meter_daily, topology, target_date)

    if results:
        rows = [r.to_db_row() for r in results]
        df = pd.DataFrame(rows)
        df.to_csv(output_csv, index=False)

    return len(results)

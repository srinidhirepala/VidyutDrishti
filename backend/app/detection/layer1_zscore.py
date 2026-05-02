"""Layer 1: Z-Score Baseline Anomaly Detection.

Computes per-meter z-scores based on historical consumption patterns.
Flags individual meters with consumption significantly different from
their own historical mean (typically |z| > 3).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class ZScoreResult:
    """Result of z-score analysis for a single meter on a single day."""

    meter_id: str
    dt_id: str
    feeder_id: str
    date: date

    # Consumption
    actual_kwh: float
    historical_mean: float | None
    historical_std: float | None

    # Z-score
    z_score: float | None  # (actual - mean) / std
    abs_z_score: float | None  # Absolute value for thresholding

    # Thresholding
    threshold: float  # Typically 3.0
    is_anomaly: bool  # True if abs_z_score > threshold

    # Context
    n_historical_days: int  # Days used for mean/std calculation

    # Metadata
    computed_at: datetime

    def to_db_row(self) -> dict[str, Any]:
        """Serialize to dict for layer1_zscore table."""
        return {
            "meter_id": self.meter_id,
            "dt_id": self.dt_id,
            "feeder_id": self.feeder_id,
            "date": self.date,
            "actual_kwh": self.actual_kwh,
            "historical_mean": self.historical_mean,
            "historical_std": self.historical_std,
            "z_score": self.z_score,
            "abs_z_score": self.abs_z_score,
            "threshold": self.threshold,
            "is_anomaly": self.is_anomaly,
            "n_historical_days": self.n_historical_days,
            "computed_at": self.computed_at,
        }


def _compute_stats(series: pd.Series) -> tuple[float | None, float | None]:
    """Compute mean and std, returning None if insufficient data."""
    clean = series.dropna()
    if len(clean) < 7:  # Need at least 7 days for meaningful stats
        return None, None
    mean = float(clean.mean())
    std = float(clean.std())
    if std == 0:  # No variation - can't compute z-score
        return mean, None
    return mean, std


class ZScoreAnalyzer:
    """Z-score anomaly detection for individual meters (Layer 1).

    Flags meters with consumption significantly different from their
    historical baseline. This catches individual theft or meter faults.
    """

    def __init__(
        self,
        threshold: float = 3.0,
        min_history_days: int = 7,
        lookback_days: int = 90,  # Use last 90 days for stats
    ) -> None:
        self.threshold = threshold
        self.min_history_days = min_history_days
        self.lookback_days = lookback_days

    def analyze(
        self,
        meter_id: str,
        dt_id: str,
        feeder_id: str,
        target_date: date,
        daily_kwh: pd.Series,  # Index = date, values = kwh
    ) -> ZScoreResult | None:
        """Analyze z-score for a single meter on a single day.

        Args:
            meter_id: Meter identifier
            dt_id: Distribution transformer ID
            feeder_id: Feeder/substation ID
            target_date: Date to analyze
            daily_kwh: Series with daily kwh consumption, indexed by date

        Returns:
            ZScoreResult or None if insufficient history
        """
        if target_date not in daily_kwh.index:
            return None

        actual = float(daily_kwh[target_date])

        # Historical data: prior to target date, within lookback window
        prior = daily_kwh[daily_kwh.index < target_date]
        if len(prior) == 0:
            return None

        # Limit to lookback window
        cutoff = target_date - pd.Timedelta(days=self.lookback_days)
        prior = prior[prior.index >= cutoff]

        mean, std = _compute_stats(prior)
        if mean is None:
            return None

        # Compute z-score
        if std is None or std == 0:
            z_score = 0.0 if actual == mean else float("inf")
        else:
            z_score = (actual - mean) / std

        abs_z = abs(z_score) if z_score != float("inf") else float("inf")
        is_anomaly = abs_z > self.threshold if abs_z != float("inf") else True

        return ZScoreResult(
            meter_id=meter_id,
            dt_id=dt_id,
            feeder_id=feeder_id,
            date=target_date,
            actual_kwh=actual,
            historical_mean=mean,
            historical_std=std,
            z_score=z_score,
            abs_z_score=abs_z,
            threshold=self.threshold,
            is_anomaly=is_anomaly,
            n_historical_days=len(prior),
            computed_at=datetime.utcnow(),
        )

    def analyze_batch(
        self,
        meter_daily: pd.DataFrame,  # meter_id, date, kwh
        topology: pd.DataFrame,  # meter_id, dt_id, feeder_id
        target_date: date,
    ) -> list[ZScoreResult]:
        """Analyze z-scores for all meters in batch.

        Args:
            meter_daily: DataFrame with daily meter readings
            topology: DataFrame with meter-to-DT mapping
            target_date: Date to analyze

        Returns:
            List of ZScoreResult for each meter with sufficient history
        """
        results: list[ZScoreResult] = []

        if meter_daily.empty or "date" not in meter_daily.columns:
            return results

        # Ensure date column is date type
        if pd.api.types.is_datetime64_any_dtype(meter_daily["date"]):
            dates = meter_daily["date"].dt.date
        else:
            dates = meter_daily["date"]

        # Get unique meters
        meter_ids = meter_daily["meter_id"].unique()

        for mid in meter_ids:
            # Get topology for this meter
            topo = topology[topology["meter_id"] == mid]
            if topo.empty:
                continue
            dt_id = str(topo.iloc[0].get("dt_id", ""))
            feeder_id = str(topo.iloc[0].get("feeder_id", ""))

            # Get time series for this meter
            mask = meter_daily["meter_id"] == mid
            meter_data = meter_daily[mask]

            # Create daily series
            daily = pd.Series(
                meter_data["kwh"].values,
                index=pd.to_datetime(meter_data["date"]).dt.date
                if pd.api.types.is_datetime64_any_dtype(meter_data["date"])
                else meter_data["date"].values
            )

            result = self.analyze(
                meter_id=str(mid),
                dt_id=dt_id,
                feeder_id=feeder_id,
                target_date=target_date,
                daily_kwh=daily,
            )
            if result is not None:
                results.append(result)

        return results


def analyze_zscore_csv(
    meter_daily_csv: Path,
    topology_csv: Path,
    target_date: date,
    output_csv: Path,
    threshold: float = 3.0,
) -> int:
    """CLI helper: analyze from CSV files and write output.

    Returns count of meters analyzed.
    """
    meter_daily = pd.read_csv(meter_daily_csv, parse_dates=["date"])
    topology = pd.read_csv(topology_csv)

    analyzer = ZScoreAnalyzer(threshold=threshold)
    results = analyzer.analyze_batch(meter_daily, topology, target_date)

    if results:
        rows = [r.to_db_row() for r in results]
        df = pd.DataFrame(rows)
        df.to_csv(output_csv, index=False)

    return len(results)

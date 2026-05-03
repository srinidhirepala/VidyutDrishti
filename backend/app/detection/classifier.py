"""Behavioural classifier: Categorizes anomalies by consumption pattern.

Classifies detected anomalies into actionable categories:
- sudden_drop: Sharp decrease in consumption (theft indicator)
- spike: Unusual increase (meter fault or generation)
- flatline: Near-zero consumption for extended period (bypass/disconnect)
- erratic: High volatility (meter malfunction)
- normal_pattern: No clear anomaly pattern
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd


class AnomalyType(str, Enum):
    """Behavioural anomaly categories."""
    SUDDEN_DROP = "sudden_drop"
    SPIKE = "spike"
    FLATLINE = "flatline"
    ERRATIC = "erratic"
    NORMAL_PATTERN = "normal_pattern"


@dataclass
class ClassificationResult:
    """Classification result for a single meter."""

    meter_id: str
    dt_id: str
    feeder_id: str
    date: date

    # Classification
    anomaly_type: AnomalyType
    confidence: float  # 0-1 confidence in classification

    # Pattern metrics
    daily_change_pct: float | None  # Day-over-day change
    rolling_mean_ratio: float | None  # Today vs 7-day mean
    zero_slots_ratio: float | None  # % of slots with near-zero consumption
    cv_daily: float | None  # Coefficient of variation (volatility)

    # Context for investigators
    description: str

    # Metadata
    computed_at: datetime = field(default_factory=datetime.utcnow)

    def to_db_row(self) -> dict[str, Any]:
        """Serialize to dict for anomaly_labels table."""
        return {
            "meter_id": self.meter_id,
            "dt_id": self.dt_id,
            "feeder_id": self.feeder_id,
            "date": self.date,
            "anomaly_type": self.anomaly_type.value,
            "confidence": self.confidence,
            "daily_change_pct": self.daily_change_pct,
            "rolling_mean_ratio": self.rolling_mean_ratio,
            "zero_slots_ratio": self.zero_slots_ratio,
            "cv_daily": self.cv_daily,
            "description": self.description,
            "computed_at": self.computed_at,
        }


class BehaviouralClassifier:
    """Classify consumption patterns into behavioural anomaly types.

    Uses heuristics based on daily features to categorize anomalies
    for actionable investigation guidance.
    """

    # Classification thresholds
    DROP_THRESHOLD = -30.0  # 30% drop = suspicious
    SPIKE_THRESHOLD = 50.0  # 50% increase = unusual
    FLATLINE_THRESHOLD = 0.9  # 90% zero slots = flatline
    ERRATIC_CV = 0.5  # CV > 50% = high volatility

    def __init__(self) -> None:
        pass

    def _compute_metrics(self, df_day: pd.DataFrame, df_prior: pd.DataFrame) -> dict[str, float | None]:
        """Compute classification metrics from daily and prior data."""
        if df_day.empty or "kwh" not in df_day.columns:
            return {
                "daily_kwh": None,
                "prior_day_kwh": None,
                "rolling_7d_mean": None,
                "zero_slots_ratio": None,
                "cv_daily": None,
            }

        daily_kwh = float(df_day["kwh"].sum())

        # Prior day (if available)
        prior_day_kwh = None
        if not df_prior.empty and "kwh" in df_prior.columns:
            # Get the most recent prior day
            last_prior = df_prior.groupby(df_prior.index)["kwh"].sum().iloc[-1:]
            if not last_prior.empty:
                prior_day_kwh = float(last_prior.iloc[0])

        # 7-day rolling mean (if available)
        rolling_7d_mean = None
        if not df_prior.empty and len(df_prior) >= 1:
            # Use prior days for rolling mean
            prior_daily = df_prior.groupby(df_prior.index)["kwh"].sum()
            if len(prior_daily) >= 6:  # Need 6 prior days for 7-day total
                rolling_7d_mean = float(prior_daily.tail(6).mean())
            else:
                rolling_7d_mean = float(prior_daily.mean()) if len(prior_daily) > 0 else None

        # Zero slots ratio
        zero_slots = (df_day["kwh"] < 0.01).sum()
        zero_slots_ratio = zero_slots / len(df_day)

        # Coefficient of variation (volatility)
        daily_std = float(df_day["kwh"].std()) if len(df_day) > 1 else 0
        daily_mean = float(df_day["kwh"].mean()) if len(df_day) > 0 else 1
        cv_daily = daily_std / daily_mean if daily_mean > 0 else 0

        return {
            "daily_kwh": daily_kwh,
            "prior_day_kwh": prior_day_kwh,
            "rolling_7d_mean": rolling_7d_mean,
            "zero_slots_ratio": zero_slots_ratio,
            "cv_daily": cv_daily,
        }

    def classify(
        self,
        meter_id: str,
        dt_id: str,
        feeder_id: str,
        target_date: date,
        df_day: pd.DataFrame,
        df_prior: pd.DataFrame,
    ) -> ClassificationResult:
        """Classify consumption pattern for a single meter.

        Args:
            meter_id: Meter identifier
            dt_id: Distribution transformer ID
            feeder_id: Feeder/substation ID
            target_date: Date of classification
            df_day: DataFrame with 15-min readings for target date
            df_prior: DataFrame with prior readings for context

        Returns:
            ClassificationResult with anomaly type and metrics
        """
        metrics = self._compute_metrics(df_day, df_prior)

        daily_kwh = metrics["daily_kwh"]
        prior_day_kwh = metrics["prior_day_kwh"]
        rolling_7d_mean = metrics["rolling_7d_mean"]
        zero_slots_ratio = metrics["zero_slots_ratio"] or 0
        cv_daily = metrics["cv_daily"] or 0

        # Compute ratios
        daily_change_pct = None
        if prior_day_kwh and prior_day_kwh > 0 and daily_kwh is not None:
            daily_change_pct = ((daily_kwh - prior_day_kwh) / prior_day_kwh) * 100

        rolling_mean_ratio = None
        if rolling_7d_mean and rolling_7d_mean > 0 and daily_kwh is not None:
            rolling_mean_ratio = daily_kwh / rolling_7d_mean

        # Classification logic
        anomaly_type = AnomalyType.NORMAL_PATTERN
        confidence = 0.5
        description = "Normal consumption pattern"

        # Check for flatline (most distinctive)
        if zero_slots_ratio > self.FLATLINE_THRESHOLD:
            anomaly_type = AnomalyType.FLATLINE
            confidence = min(1.0, zero_slots_ratio)
            description = f"Flatline: {zero_slots_ratio*100:.0f}% of slots near zero (possible bypass/disconnect)"

        # Check for sudden drop
        elif daily_change_pct is not None and daily_change_pct < self.DROP_THRESHOLD:
            anomaly_type = AnomalyType.SUDDEN_DROP
            confidence = min(1.0, abs(daily_change_pct) / 100)
            description = f"Sudden drop: {abs(daily_change_pct):.0f}% decrease from prior day (theft indicator)"

        # Check for spike
        elif daily_change_pct is not None and daily_change_pct > self.SPIKE_THRESHOLD:
            anomaly_type = AnomalyType.SPIKE
            confidence = min(1.0, daily_change_pct / 100)
            description = f"Spike: {daily_change_pct:.0f}% increase from prior day (meter fault/generation)"

        # Check for erratic/volatile
        elif cv_daily > self.ERRATIC_CV:
            anomaly_type = AnomalyType.ERRATIC
            confidence = min(1.0, cv_daily)
            description = f"Erratic: {cv_daily*100:.0f}% volatility (meter malfunction)"

        return ClassificationResult(
            meter_id=meter_id,
            dt_id=dt_id,
            feeder_id=feeder_id,
            date=target_date,
            anomaly_type=anomaly_type,
            confidence=confidence,
            daily_change_pct=daily_change_pct,
            rolling_mean_ratio=rolling_mean_ratio,
            zero_slots_ratio=zero_slots_ratio,
            cv_daily=cv_daily,
            description=description,
        )

    def classify_batch(
        self,
        readings_df: pd.DataFrame,  # meter_id, ts, kwh columns
        topology_df: pd.DataFrame,  # meter_id, dt_id, feeder_id
        target_date: date,
    ) -> list[ClassificationResult]:
        """Classify all meters in batch.

        Args:
            readings_df: DataFrame with 15-min readings
            topology_df: DataFrame with meter-to-DT mapping
            target_date: Date to classify

        Returns:
            List of ClassificationResult for each meter
        """
        results: list[ClassificationResult] = []

        if readings_df.empty:
            return results

        # Ensure timestamp column
        if "ts" not in readings_df.columns:
            return results

        # Convert timestamps
        readings_df = readings_df.copy()
        readings_df["ts"] = pd.to_datetime(readings_df["ts"])
        readings_df["date"] = readings_df["ts"].dt.date

        # Filter to target date and prior 7 days
        cutoff = target_date - pd.Timedelta(days=7)
        relevant = readings_df[readings_df["date"] >= pd.Timestamp(cutoff).date()]

        # Get unique meters
        meter_ids = relevant["meter_id"].unique()

        for mid in meter_ids:
            meter_data = relevant[relevant["meter_id"] == mid]

            # Split into target day and prior
            df_day = meter_data[meter_data["date"] == target_date]
            df_prior = meter_data[meter_data["date"] < target_date]

            if df_day.empty:
                continue

            # Get topology
            topo = topology_df[topology_df["meter_id"] == mid]
            dt_id = str(topo.iloc[0]["dt_id"]) if not topo.empty else ""
            feeder_id = str(topo.iloc[0]["feeder_id"]) if not topo.empty else ""

            result = self.classify(
                meter_id=str(mid),
                dt_id=dt_id,
                feeder_id=feeder_id,
                target_date=target_date,
                df_day=df_day,
                df_prior=df_prior,
            )
            results.append(result)

        return results


def classify_anomalies_csv(
    readings_csv: Path,
    topology_csv: Path,
    target_date: date,
    output_csv: Path,
) -> int:
    """CLI helper: classify from CSV files and write output.

    Returns count of meters classified.
    """
    readings_df = pd.read_csv(readings_csv, parse_dates=["ts"])
    topology_df = pd.read_csv(topology_csv)

    classifier = BehaviouralClassifier()
    results = classifier.classify_batch(readings_df, topology_df, target_date)

    if results:
        rows = [r.to_db_row() for r in results]
        df = pd.DataFrame(rows)
        df.to_csv(output_csv, index=False)

    return len(results)

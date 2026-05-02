"""Feature engineering engine for meter-level anomaly detection.

Transforms raw 15-min meter readings into daily feature vectors
for Layer 1 (z-score), Layer 2 (peer comparison), and Layer 3 (Isolation Forest).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .models import MeterFeatures


def _compute_rolling_mean(series: pd.Series, window: int) -> float | None:
    """Compute rolling mean, returning None if insufficient data."""
    if len(series) < window:
        return None
    return float(series.iloc[-window:].mean())


def _compute_diurnal_features(df_day: pd.DataFrame) -> tuple[float | None, float | None, float | None]:
    """Compute peak, trough, and mean from 15-min slots.

    Returns (peak, trough, mean) or (None, None, None) if no data.
    """
    if df_day.empty or "kwh" not in df_day.columns:
        return None, None, None
    kwh = df_day["kwh"].dropna()
    if kwh.empty:
        return None, None, None
    return float(kwh.max()), float(kwh.min()), float(kwh.mean())


def _compute_voltage_variability(df_day: pd.DataFrame) -> float | None:
    """Compute voltage standard deviation for the day."""
    if df_day.empty or "voltage" not in df_day.columns:
        return None
    voltages = df_day["voltage"].dropna()
    if len(voltages) < 2:
        return None
    return float(voltages.std())


def _compute_pf_mean(df_day: pd.DataFrame) -> float | None:
    """Compute mean power factor for the day."""
    if df_day.empty or "pf" not in df_day.columns:
        return None
    pfs = df_day["pf"].dropna()
    if pfs.empty:
        return None
    return float(pfs.mean())


def _health_score(df_day: pd.DataFrame, expected_slots: int = 96) -> float:
    """Compute synthetic health score 0-1 based on data quality.

    Factors: missingness (60%), voltage range sanity (20%), pf sanity (20%).
    """
    if df_day.empty:
        return 0.0

    # Completeness score (60% weight)
    actual_slots = len(df_day)
    completeness_ratio = min(1.0, actual_slots / expected_slots)
    completeness_score = completeness_ratio * 0.6

    # Voltage sanity score (20% weight) - expect 200-260V
    voltage_score = 0.2  # Default perfect if no data
    if "voltage" in df_day.columns:
        voltages = df_day["voltage"].dropna()
        if not voltages.empty:
            out_of_range = ((voltages < 200) | (voltages > 260)).sum()
            voltage_ratio = 1 - (out_of_range / len(voltages))
            voltage_score = voltage_ratio * 0.2

    # PF sanity score (20% weight) - expect 0.7-1.0
    pf_score = 0.2  # Default perfect if no data
    if "pf" in df_day.columns:
        pfs = df_day["pf"].dropna()
        if not pfs.empty:
            out_of_range = ((pfs < 0.7) | (pfs > 1.0)).sum()
            pf_ratio = 1 - (out_of_range / len(pfs))
            pf_score = pf_ratio * 0.2

    score = completeness_score + voltage_score + pf_score
    return round(max(0.0, min(1.0, score)), 3)


class FeatureEngineer:
    """Engineer daily feature vectors from meter readings."""

    def __init__(
        self,
        slot_minutes: int = 15,
        expected_slots_per_day: int = 96,  # 24h * 4 slots/hour
        holidays: set[date] | None = None,
        inspections: dict[str, date] | None = None,
    ) -> None:
        self.slot_minutes = slot_minutes
        self.expected_slots = expected_slots_per_day
        self.holidays = holidays or set()
        self.inspections = inspections or {}  # meter_id -> last inspection date

    # -----------------------------------------------------------------------
    # Core methods
    # -----------------------------------------------------------------------

    def engineer_day(
        self,
        meter_id: str,
        dt_id: str,
        feeder_id: str,
        target_date: date,
        df_history: pd.DataFrame,  # Meter readings with ts, kwh, voltage, pf columns
    ) -> MeterFeatures | None:
        """Build feature vector for a single meter on a single day.

        Args:
            meter_id: Meter identifier
            dt_id: Distribution transformer ID
            feeder_id: Feeder/substation ID
            target_date: Date to engineer features for
            df_history: DataFrame with all available history for this meter

        Returns:
            MeterFeatures dataclass or None if insufficient data
        """
        if df_history.empty:
            return None

        # Ensure datetime index
        if "ts" in df_history.columns:
            df_history = df_history.copy()
            df_history["ts"] = pd.to_datetime(df_history["ts"])
        else:
            return None

        # Filter to target date and prior 30 days
        target_ts = pd.Timestamp(target_date)
        target_end = target_ts + pd.Timedelta(days=1)  # Include full target day
        df_history = df_history[df_history["ts"] < target_end]

        df_day = df_history[df_history["ts"].dt.date == target_date]
        df_prior = df_history[df_history["ts"].dt.date < target_date]

        if df_day.empty:
            return None  # No data for target date

        # Core consumption features
        total_kwh = float(df_day["kwh"].sum()) if "kwh" in df_day.columns else 0.0

        # Rolling 7-day mean
        rolling7 = None
        if not df_prior.empty and "kwh" in df_prior.columns:
            # Aggregate prior days to daily totals
            prior_daily = (
                df_prior.groupby(df_prior["ts"].dt.date)["kwh"].sum()
                if "kwh" in df_prior.columns else pd.Series(dtype=float)
            )
            rolling7 = _compute_rolling_mean(prior_daily, window=7)

        # Rolling 30-day for temp ratio
        rolling30 = None
        if not df_prior.empty and "kwh" in df_prior.columns:
            prior_daily = (
                df_prior.groupby(df_prior["ts"].dt.date)["kwh"].sum()
                if "kwh" in df_prior.columns else pd.Series(dtype=float)
            )
            rolling30 = _compute_rolling_mean(prior_daily, window=30)

        # Diurnal features
        peak, trough, diurnal_mean = _compute_diurnal_features(df_day)

        # Temporal features
        weekday = target_date.weekday()  # 0=Monday
        weekday_isin = 1 if weekday < 5 else 0
        is_holiday = 1 if target_date in self.holidays else 0

        # Domain features
        temp_ratio = None
        if rolling30 is not None and rolling30 > 0:
            temp_ratio = total_kwh / rolling30

        health = _health_score(df_day, self.expected_slots)
        voltage_var = _compute_voltage_variability(df_day)
        pf_mean = _compute_pf_mean(df_day)

        # Inspection context
        last_inspect = self.inspections.get(meter_id)
        if last_inspect:
            last_inspection_days = (target_date - last_inspect).days
        else:
            last_inspection_days = None

        # Missing slot count
        actual_slots = len(df_day)
        slots_missing = max(0, self.expected_slots - actual_slots)

        return MeterFeatures(
            meter_id=meter_id,
            dt_id=dt_id,
            feeder_id=feeder_id,
            date=target_date,
            total_kwh=total_kwh,
            rolling7_kwh=rolling7,
            peak_hour_kwh=peak,
            trough_hour_kwh=trough,
            diurnal_mean=diurnal_mean,
            weekday_isin=weekday_isin,
            is_holiday=is_holiday,
            day_of_week=weekday,
            temp_ratio=temp_ratio,
            meter_health_score=health,
            voltage_variability=voltage_var,
            pf_mean=pf_mean,
            last_inspection_days=last_inspection_days,
            computed_at=datetime.utcnow(),
            slots_missing=slots_missing,
            slots_total=self.expected_slots,
        )

    def engineer_batch(
        self,
        meters_df: pd.DataFrame,
        readings_df: pd.DataFrame,
        target_date: date,
    ) -> list[MeterFeatures]:
        """Engineer features for all meters in batch.

        Args:
            meters_df: DataFrame with meter_id, dt_id, feeder_id columns
            readings_df: DataFrame with meter_id, ts, kwh, voltage, pf columns
            target_date: Date to engineer features for

        Returns:
            List of MeterFeatures (may be fewer than input if data missing)
        """
        results: list[MeterFeatures] = []

        for _, meter_row in meters_df.iterrows():
            meter_id = str(meter_row["meter_id"])
            dt_id = str(meter_row.get("dt_id", ""))
            feeder_id = str(meter_row.get("feeder_id", ""))

            # Filter readings for this meter
            meter_readings = readings_df[readings_df["meter_id"] == meter_id]

            features = self.engineer_day(
                meter_id=meter_id,
                dt_id=dt_id,
                feeder_id=feeder_id,
                target_date=target_date,
                df_history=meter_readings,
            )
            if features is not None:
                results.append(features)

        return results


def build_features(
    readings_csv: Path,
    meters_csv: Path,
    target_date: date,
    output_csv: Path,
    holidays: set[date] | None = None,
) -> int:
    """CLI helper: build features from CSV files and write output.

    Returns count of meters processed.
    """
    readings = pd.read_csv(readings_csv, parse_dates=["ts"])
    meters = pd.read_csv(meters_csv)

    engineer = FeatureEngineer(holidays=holidays)
    features = engineer.engineer_batch(meters, readings, target_date)

    if features:
        rows = [f.to_db_row() for f in features]
        df = pd.DataFrame(rows)
        df.to_csv(output_csv, index=False)

    return len(features)

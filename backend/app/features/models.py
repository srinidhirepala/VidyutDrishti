"""Data models for engineered features."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass
class MeterFeatures:
    """Engineered features for a single meter on a single day.

    These features feed into Layer 1 (z-score), Layer 2 (peer comparison),
    and Layer 3 (Isolation Forest) anomaly detection.
    """

    meter_id: str
    dt_id: str
    feeder_id: str
    date: date

    # Core consumption features
    total_kwh: float
    rolling7_kwh: float | None  # 7-day rolling mean (missing if <7 days history)

    # Diurnal profile features
    peak_hour_kwh: float | None  # Highest 15-min slot consumption
    trough_hour_kwh: float | None  # Lowest 15-min slot consumption
    diurnal_mean: float | None  # Mean of 15-min slots for the day

    # Temporal features
    weekday_isin: int  # 0 = weekend, 1 = weekday
    is_holiday: int  # 0 = no, 1 = yes
    day_of_week: int  # 0 = Monday, 6 = Sunday

    # Domain-specific features
    temp_ratio: float | None  # day kWh / rolling30_kWh (if available)
    meter_health_score: float | None  # synthetic 0-1 score based on missingness/quality
    voltage_variability: float | None  # std dev of voltage readings
    pf_mean: float | None  # mean power factor

    # Inspection context
    last_inspection_days: int | None  # days since last inspection (None if never)

    # Computed metadata
    computed_at: datetime
    slots_missing: int  # count of missing 15-min slots in the day
    slots_total: int  # expected 96 slots for 15-min granularity

    def to_db_row(self) -> dict[str, Any]:
        """Serialize to dict for meter_daily_features table."""
        return {
            "meter_id": self.meter_id,
            "dt_id": self.dt_id,
            "feeder_id": self.feeder_id,
            "date": self.date,
            "total_kwh": self.total_kwh,
            "rolling7_kwh": self.rolling7_kwh,
            "peak_hour_kwh": self.peak_hour_kwh,
            "trough_hour_kwh": self.trough_hour_kwh,
            "diurnal_mean": self.diurnal_mean,
            "weekday_isin": self.weekday_isin,
            "is_holiday": self.is_holiday,
            "day_of_week": self.day_of_week,
            "temp_ratio": self.temp_ratio,
            "meter_health_score": self.meter_health_score,
            "voltage_variability": self.voltage_variability,
            "pf_mean": self.pf_mean,
            "last_inspection_days": self.last_inspection_days,
            "computed_at": self.computed_at,
            "slots_missing": self.slots_missing,
            "slots_total": self.slots_total,
        }

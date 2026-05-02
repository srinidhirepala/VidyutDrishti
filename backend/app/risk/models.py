"""Data models for zone risk classification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any


class RiskLevel(str, Enum):
    """Zone risk levels ordered from most to least severe."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

    def __lt__(self, other: "RiskLevel") -> bool:
        """Allow comparison: HIGH < MEDIUM < LOW is False; severity order."""
        order = {RiskLevel.HIGH: 0, RiskLevel.MEDIUM: 1, RiskLevel.LOW: 2}
        return order[self] < order[other]

    def __gt__(self, other: "RiskLevel") -> bool:
        order = {RiskLevel.HIGH: 0, RiskLevel.MEDIUM: 1, RiskLevel.LOW: 2}
        return order[self] > order[other]


@dataclass
class ZoneRiskResult:
    """Output of zone risk classification for a feeder on a specific date."""

    feeder_id: str
    forecast_date: date
    level: RiskLevel
    predicted_peak_kw: float
    capacity_kva: float | None
    headroom_percent: float  # (capacity - peak) / capacity * 100, negative if overloaded
    computed_at: datetime

    def to_db_row(self) -> dict[str, Any]:
        return {
            "feeder_id": self.feeder_id,
            "ts": datetime.combine(self.forecast_date, datetime.min.time()),
            "level": self.level.value,
            "predicted_peak_kw": self.predicted_peak_kw,
            "computed_at": self.computed_at,
        }

"""Feeder-level demand forecasting with seasonal baseline + confidence bands.

Prototype-grade: Uses rolling seasonal averages with trend to produce
Prophet-compatible output structure (forecast, lower, upper) without
the heavy cmdstan dependency. Suitable for hackathon demonstration.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class ForecastResult:
    """Single time-step forecast output (Prophet-compatible structure)."""

    ds: datetime
    yhat: float
    yhat_lower: float
    yhat_upper: float
    trend: float
    weekly: float
    yearly: float


@dataclass
class FeederForecast:
    """Complete 24-hour forecast for a feeder."""

    feeder_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    horizon_hours: int = 24
    resolution_minutes: int = 15
    points: list[ForecastResult] = field(default_factory=list)
    zone_risk: str = "LOW"  # LOW / MEDIUM / HIGH
    risk_score: float = 0.0  # 0-1 scale

    def to_dict(self) -> dict[str, Any]:
        max_cap = self._max_capacity()
        peak = max((p.yhat for p in self.points), default=0.0)
        return {
            "feeder_id": self.feeder_id,
            "created_at": self.created_at.isoformat(),
            "zone_risk": self.zone_risk,
            "risk_score": round(self.risk_score, 3),
            "peak_forecast_kw": round(peak, 1),
            "max_capacity_kw": round(max_cap, 1),
            "utilization_pct": round(peak / max_cap * 100, 1) if max_cap else 0.0,
            "points": [
                {
                    "timestamp": p.ds.isoformat(),
                    "forecast_kw": round(p.yhat, 2),
                    "lower_kw": round(p.yhat_lower, 2),
                    "upper_kw": round(p.yhat_upper, 2),
                    "components": {
                        "trend": round(p.trend, 2),
                        "weekly": round(p.weekly, 2),
                        "yearly": round(p.yearly, 2),
                    },
                }
                for p in self.points
            ],
        }

    def _max_capacity(self) -> float:
        # Mock capacity — in production this comes from asset registry
        return 5000.0


class FeederForecaster:
    """Prototype forecaster using seasonal rolling baseline.

    Fits on last 90 days of 15-minute feeder-aggregate readings and
    projects forward 24 hours with naive seasonal extrapolation +
    linear trend + calibrated Gaussian confidence bands.
    """

    def __init__(self, history_days: int = 90):
        self.history_days = history_days
        self._history: pd.DataFrame | None = None

    def fit(self, df: pd.DataFrame) -> "FeederForecaster":
        """Accepts DataFrame with columns: [timestamp, feeder_id, kw]."""
        df = df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)
        self._history = df
        return self

    def predict(
        self,
        feeder_id: str,
        horizon_hours: int = 24,
        resolution_minutes: int = 15,
    ) -> FeederForecast:
        if self._history is None:
            raise RuntimeError("Forecaster not fitted.")

        hist = self._history[self._history["feeder_id"] == feeder_id]
        if hist.empty:
            raise ValueError(f"No history for feeder {feeder_id}")

        # Create future timestamps
        now = hist.index.max().replace(minute=0, second=0, microsecond=0)
        steps = int(horizon_hours * 60 / resolution_minutes)
        future_times = [now + timedelta(minutes=i * resolution_minutes) for i in range(1, steps + 1)]

        points: list[ForecastResult] = []
        for ts in future_times:
            yhat, lower, upper, trend, weekly, yearly = self._predict_one(hist, ts)
            points.append(
                ForecastResult(
                    ds=ts,
                    yhat=yhat,
                    yhat_lower=lower,
                    yhat_upper=upper,
                    trend=trend,
                    weekly=weekly,
                    yearly=yearly,
                )
            )

        # Zone risk classification
        peak = max(p.yhat for p in points)
        max_cap = 5000.0
        util = peak / max_cap
        if util >= 0.88:
            zone_risk = "HIGH"
            risk_score = min(1.0, util)
        elif util >= 0.75:
            zone_risk = "MEDIUM"
            risk_score = util
        else:
            zone_risk = "LOW"
            risk_score = util * 0.5

        return FeederForecast(
            feeder_id=feeder_id,
            horizon_hours=horizon_hours,
            resolution_minutes=resolution_minutes,
            points=points,
            zone_risk=zone_risk,
            risk_score=risk_score,
        )

    def _predict_one(
        self, hist: pd.DataFrame, ts: datetime
    ) -> tuple[float, float, float, float, float, float]:
        """Predict a single timestep using seasonal components."""
        # Weekly seasonality: same hour+minute, same day-of-week, average over last 4 weeks
        dow = ts.weekday()
        minute = ts.hour * 60 + ts.minute
        mask = (hist.index.weekday == dow) & (hist.index.hour * 60 + hist.index.minute == minute)
        weekly_vals = hist.loc[mask, "kw"].tail(4)
        weekly = float(weekly_vals.mean()) if len(weekly_vals) > 0 else float(hist["kw"].mean())

        # Yearly seasonality: month effect (simplified)
        month = ts.month
        month_mask = hist.index.month == month
        yearly = float(hist.loc[month_mask, "kw"].mean()) if month_mask.any() else float(hist["kw"].mean())

        # Trend: linear regression on last 30 days
        recent = hist.tail(30 * 96)  # 30 days * 96 slots/day
        if len(recent) > 10:
            x = np.arange(len(recent))
            y = recent["kw"].values
            slope, intercept = np.polyfit(x, y, 1)
            trend = intercept + slope * (len(hist) + (ts - hist.index[-1]).total_seconds() / 900)
        else:
            trend = float(hist["kw"].mean())

        # Combine components (simplified additive model)
        yhat = 0.5 * trend + 0.3 * weekly + 0.2 * yearly

        # Confidence bands: ±1.5σ of recent residuals
        residuals = (hist["kw"] - hist["kw"].rolling(96, min_periods=1).mean()).dropna()
        sigma = float(residuals.std()) if len(residuals) > 0 else yhat * 0.05
        lower = yhat - 1.5 * sigma
        upper = yhat + 1.5 * sigma

        return yhat, lower, upper, trend, weekly, yearly

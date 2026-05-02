"""Forecast data models and persistence helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

# Try to import Prophet - may not be available in all environments
try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    Prophet = Any  # type: ignore


@dataclass
class ForecastResult:
    """Output of a single forecast run."""

    feeder_id: str
    forecast_date: date
    yhat: float
    yhat_lower: float
    yhat_upper: float
    model_version: str
    generated_at: datetime

    def to_db_row(self) -> dict[str, Any]:
        return {
            "feeder_id": self.feeder_id,
            "ts": datetime.combine(self.forecast_date, datetime.min.time()),
            "yhat": self.yhat,
            "yhat_lower": self.yhat_lower,
            "yhat_upper": self.yhat_upper,
            "model_version": self.model_version,
            "generated_at": self.generated_at,
        }


@dataclass
class ForecastModel:
    """Wrapper around a trained Prophet model with metadata."""

    feeder_id: str
    model: Prophet | None
    trained_at: datetime
    training_rows: int
    model_version: str
    mape: float | None = None  # Mean Absolute Percentage Error from validation

    def save(self, directory: Path) -> Path:
        """Serialize to disk via joblib."""
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.feeder_id}_{self.model_version}.joblib"
        joblib.dump(
            {
                "feeder_id": self.feeder_id,
                "model": self.model,
                "trained_at": self.trained_at,
                "training_rows": self.training_rows,
                "model_version": self.model_version,
                "mape": self.mape,
            },
            path,
        )
        return path

    @classmethod
    def load(cls, path: Path) -> "ForecastModel":
        """Deserialize from disk."""
        data = joblib.load(path)
        return cls(
            feeder_id=data["feeder_id"],
            model=data["model"],
            trained_at=data["trained_at"],
            training_rows=data["training_rows"],
            model_version=data["model_version"],
            mape=data.get("mape"),
        )

    def predict(self, future_df: pd.DataFrame) -> pd.DataFrame | None:
        """Generate predictions for future dates."""
        if self.model is None or not PROPHET_AVAILABLE:
            return None
        return self.model.predict(future_df)

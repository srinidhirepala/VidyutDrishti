"""Forecasting service: training, prediction, backtesting."""

from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from .models import PROPHET_AVAILABLE, ForecastModel, ForecastResult

if PROPHET_AVAILABLE:
    from prophet import Prophet
    from prophet.diagnostics import cross_validation, performance_metrics
else:
    Prophet = Any  # type: ignore

log = logging.getLogger("forecasting")


class ForecastService:
    """Train and manage Prophet models per feeder."""

    def __init__(self, model_dir: Path, horizon_days: int = 7) -> None:
        self.model_dir = Path(model_dir)
        self.horizon_days = horizon_days

    # -----------------------------------------------------------------------
    # Training
    # -----------------------------------------------------------------------

    def train(
        self,
        feeder_id: str,
        df: pd.DataFrame,
        *,
        changepoint_prior_scale: float = 0.05,
        seasonality_prior_scale: float = 10.0,
    ) -> ForecastModel | None:
        """Train a Prophet model on daily aggregate data.

        Args:
            feeder_id: Identifier for the feeder/substation.
            df: DataFrame with columns 'ds' (datetime) and 'y' (daily kWh).
            changepoint_prior_scale: Flexibility of trend changes.
            seasonality_prior_scale: Flexibility of seasonality components.

        Returns:
            Trained ForecastModel or None if Prophet unavailable.
        """
        if not PROPHET_AVAILABLE:
            log.warning("Prophet not available; skipping training")
            return None

        if df.empty or len(df) < 30:
            log.warning("Insufficient data for %s: %d rows", feeder_id, len(df))
            return None

        model = Prophet(
            daily_seasonality=False,  # We have daily granularity, not sub-daily
            weekly_seasonality=True,
            yearly_seasonality=True,
            changepoint_prior_scale=changepoint_prior_scale,
            seasonality_prior_scale=seasonality_prior_scale,
        )

        # Add holidays if available in the dataframe
        if "holiday" in df.columns:
            model.add_country_holidays(country_name="IN")

        model.fit(df[["ds", "y"]])

        # Generate model version from training data hash
        version = self._make_version(df)

        return ForecastModel(
            feeder_id=feeder_id,
            model=model,
            trained_at=datetime.utcnow(),
            training_rows=len(df),
            model_version=version,
            mape=None,  # Will be populated by backtest
        )

    def _make_version(self, df: pd.DataFrame) -> str:
        """Create deterministic version string from training data."""
        hash_input = f"{df['ds'].min()}|{df['ds'].max()}|{len(df)}|{df['y'].sum():.4f}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    # -----------------------------------------------------------------------
    # Prediction
    # -----------------------------------------------------------------------

    def forecast(
        self,
        model: ForecastModel,
        future_dates: list[date],
    ) -> list[ForecastResult]:
        """Generate forecasts for specific dates."""
        if model.model is None or not PROPHET_AVAILABLE:
            return []

        future_df = pd.DataFrame({"ds": [datetime.combine(d, datetime.min.time()) for d in future_dates]})
        preds = model.predict(future_df)
        if preds is None:
            return []

        generated_at = datetime.utcnow()
        results: list[ForecastResult] = []
        for _, row in preds.iterrows():
            results.append(
                ForecastResult(
                    feeder_id=model.feeder_id,
                    forecast_date=row["ds"].date(),
                    yhat=float(row["yhat"]),
                    yhat_lower=float(row["yhat_lower"]),
                    yhat_upper=float(row["yhat_upper"]),
                    model_version=model.model_version,
                    generated_at=generated_at,
                )
            )
        return results

    # -----------------------------------------------------------------------
    # Backtesting
    # -----------------------------------------------------------------------

    def backtest(
        self,
        df: pd.DataFrame,
        *,
        initial: str = "90 days",
        period: str = "30 days",
        horizon: str = "7 days",
    ) -> pd.DataFrame | None:
        """Run cross-validation and return performance metrics.

        Returns DataFrame with columns including 'mape', 'rmse', etc.
        """
        if not PROPHET_AVAILABLE:
            log.warning("Prophet not available; skipping backtest")
            return None

        if len(df) < 60:
            log.warning("Insufficient data for backtest: %d rows", len(df))
            return None

        model = Prophet(
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=True,
        )

        try:
            df_cv = cross_validation(
                model, initial=initial, period=period, horizon=horizon, parallel="processes"
            )
            df_p = performance_metrics(df_cv)
            return df_p
        except Exception as e:
            log.error("Backtest failed: %s", e)
            return None

    def mape(self, df_metrics: pd.DataFrame | None) -> float | None:
        """Extract mean MAPE from backtest metrics."""
        if df_metrics is None or df_metrics.empty or "mape" not in df_metrics.columns:
            return None
        return float(df_metrics["mape"].mean())

    # -----------------------------------------------------------------------
    # Persistence
    # -----------------------------------------------------------------------

    def save(self, model: ForecastModel) -> Path:
        return model.save(self.model_dir)

    def load(self, feeder_id: str, version: str) -> ForecastModel | None:
        path = self.model_dir / f"{feeder_id}_{version}.joblib"
        if not path.exists():
            return None
        return ForecastModel.load(path)

    def list_models(self, feeder_id: str) -> list[Path]:
        """List all saved models for a feeder."""
        pattern = f"{feeder_id}_*.joblib"
        return sorted(self.model_dir.glob(pattern))

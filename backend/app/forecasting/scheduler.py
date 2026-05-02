"""APScheduler integration for daily forecast generation.

This module is designed to be import-safe even when APScheduler is not
installed (tests). The actual scheduling only happens when
`start_scheduler()` is called with a live `BackgroundScheduler`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from app.db.session import SessionLocal
from app.db.models import Forecast as ForecastRow

from .models import PROPHET_AVAILABLE
from .service import ForecastService

if TYPE_CHECKING:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger("forecasting.scheduler")


def _daily_feeder_load(session: Any, feeder_id: str, lookback_days: int = 180) -> pd.DataFrame:
    """Aggregate meter_reading to daily feeder-level totals.

    In production this would query the meter_daily continuous aggregate;
    for the prototype we simulate with a simple query structure.
    """
    from sqlalchemy import text

    # Query using the continuous aggregate if available, else fall back to raw
    sql = text(
        """
        SELECT
            DATE(ts) as ds,
            SUM(kwh) as y
        FROM meter_reading mr
        JOIN consumer c ON c.meter_id = mr.meter_id
        WHERE c.feeder_id = :feeder_id
          AND ts >= :since
        GROUP BY DATE(ts)
        ORDER BY ds
        """
    )
    since = datetime.utcnow() - timedelta(days=lookback_days)
    result = session.execute(sql, {"feeder_id": feeder_id, "since": since})
    rows = result.fetchall()
    return pd.DataFrame(rows, columns=["ds", "y"])


def _run_forecast_job(feeder_id: str, model_dir: Path, horizon_days: int = 7) -> None:
    """Scheduled job: train model, generate forecast, persist to DB."""
    log.info("Starting forecast job for %s", feeder_id)
    session = SessionLocal()
    try:
        service = ForecastService(model_dir, horizon_days=horizon_days)

        # Load training data
        df = _daily_feeder_load(session, feeder_id)
        if df.empty or len(df) < 30:
            log.warning("Insufficient data for %s, skipping", feeder_id)
            return

        # Train model
        model = service.train(feeder_id, df)
        if model is None:
            log.error("Training failed for %s", feeder_id)
            return

        # Backtest for MAPE
        metrics = service.backtest(df)
        model.mape = service.mape(metrics)

        # Save model
        service.save(model)

        # Generate forecast for next N days
        future_dates = [datetime.utcnow().date() + timedelta(days=i) for i in range(1, horizon_days + 1)]
        forecasts = service.forecast(model, future_dates)

        # Persist to DB
        for fc in forecasts:
            row = ForecastRow(**fc.to_db_row())
            session.add(row)
        session.commit()

        log.info(
            "Forecast complete for %s: %d days, MAPE=%s",
            feeder_id, len(forecasts), model.mape,
        )
    except Exception as e:
        log.exception("Forecast job failed for %s: %s", feeder_id, e)
        session.rollback()
    finally:
        session.close()


def start_scheduler(
    scheduler: "BackgroundScheduler",
    model_dir: Path,
    feeder_ids: list[str],
    hour: int = 2,
    minute: int = 0,
) -> None:
    """Register daily forecast jobs for all feeders.

    Args:
        scheduler: APScheduler BackgroundScheduler instance.
        model_dir: Directory to save trained models.
        feeder_ids: List of feeder IDs to forecast.
        hour: UTC hour to run (default 2 AM).
        minute: UTC minute to run.
    """
    if not PROPHET_AVAILABLE:
        log.warning("Prophet not available; scheduler will not register forecast jobs")
        return

    for fid in feeder_ids:
        job_id = f"forecast_{fid}"
        scheduler.add_job(
            _run_forecast_job,
            "cron",
            hour=hour,
            minute=minute,
            id=job_id,
            replace_existing=True,
            args=[fid, model_dir],
            kwargs={"horizon_days": 7},
        )
        log.info("Registered forecast job %s at %02d:%02d UTC", job_id, hour, minute)

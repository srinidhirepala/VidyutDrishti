# Feature 05 - Prophet Forecasting

## Changes Log

### Implemented as specified in `features.md` section 05
- **Data models** (`forecasting/models.py`): `ForecastResult` dataclass for output; `ForecastModel` dataclass wrapping Prophet with metadata (feeder_id, trained_at, training_rows, model_version, mape). Persistence via `joblib`.
- **Service layer** (`forecasting/service.py`): `ForecastService` with methods for:
  - `train`: Fit Prophet on daily feeder aggregates with configurable changepoint/seasonality priors.
  - `forecast`: Generate predictions for future dates with confidence intervals.
  - `backtest`: Cross-validation using Prophet's diagnostics (initial/period/horizon).
  - `mape`: Extract mean absolute percentage error from backtest metrics.
  - `save/load/list_models`: Model persistence to `models/` directory.
- **Scheduler** (`forecasting/scheduler.py`): APScheduler integration with `_run_forecast_job` that loads training data, trains, backtests, saves, generates forecasts, and writes to DB. `start_scheduler` registers daily cron jobs per feeder.
- **Module init** (`forecasting/__init__.py`): Exports public API.

### Deviations from plan
- **Prophet made optional.** `features.md` listed Prophet as a core dependency. The implementation wraps all Prophet imports in `try/except` with `PROPHET_AVAILABLE` flag. Tests skip Prophet-dependent cases when unavailable. This allows the repo to be tested and linted on hosts without the heavy Prophet wheels (which require C++ build tools on Windows).
- **Daily aggregation from meter_reading.** The plan mentioned "daily aggregate from meter_daily continuous aggregate". The scheduler queries `meter_reading` directly with `DATE(ts)` aggregation for simplicity; production would use the `meter_daily` continuous aggregate for performance.
- **Horizon fixed at 7 days.** The plan mentioned "predicted kWh for each of the next 7 days". The implementation hardcodes 7 days; making it configurable is deferred to Feature 21 evaluation harness.

### New additions not explicitly in the plan
- `PROPHET_AVAILABLE` flag for import-safe gating.
- `ForecastModel.save/load` use `joblib` for serialization (supports Prophet's internal Stan model state).
- Deterministic model versioning via SHA256 hash of data bounds.
- `_daily_feeder_load` helper in scheduler queries across the meter_reading→consumer join for feeder-level aggregates.


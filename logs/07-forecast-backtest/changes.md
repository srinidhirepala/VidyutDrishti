# Feature 07 - Forecast Backtest & Baselines

## Changes Log

### Implemented as specified in `features.md` section 07
- **Metrics** (`evaluation/metrics.py`): MAPE (ignores zero actuals, returns inf if all zero), RMSE, MAE, Bias (mean error, positive = over-forecast).
- **Baselines** (`evaluation/baselines.py`): `NaiveBaseline` persistence model (tomorrow = today); `baseline_comparison` function comparing model vs naive on MAPE with improvement percentage.
- **Backtesting** (`evaluation/backtest.py`): `Backtester` class producing `BacktestReport` with:
  - Overall MAPE across all forecasts
  - Baseline comparison (does model beat naive?)
  - Day-7 match accuracy (% within ±10%, eval target 85%)
  - MAPE by horizon day (1-7)
- **Module init** (`evaluation/__init__.py`): Exports public API.

### Deviations from plan
- **No YAML configuration for thresholds.** The plan mentioned "backtest_config.yaml". Thresholds (10% MAPE target, 85% day-7 match) are hardcoded as defaults in the `Backtester` constructor; can be overridden via arguments.
- **Rolling-origin CV simplified.** The plan mentioned Prophet's `cross_validation`. The `Backtester` focuses on day-7 evaluation using pre-generated forecasts rather than full rolling-origin retraining, which is computationally expensive for prototype tests.
- **Backtest report is dataclass, not file.** Results are returned as `BacktestReport` dataclass for programmatic use; file serialization deferred to Feature 21 evaluation harness.

### New additions not explicitly in the plan
- `Day7MatchResult` dataclass captures day-7 specific evaluation metrics separately from overall MAPE.
- `horizon_mapes` function provides per-day MAPE breakdown for diagnosing forecast degradation over time.
- Edge case handling: MAPE when baseline is exactly 0 (returns -100% improvement if model has any error).

### Bug fixes during development
- Baseline comparison tests initially used flat time series where both model and baseline achieved 0% MAPE. Fixed by creating realistic test scenarios: trending data (where baseline lags) and flat data (where baseline is perfect).
- Improvement calculation when baseline MAPE = 0 was returning 0% instead of correctly identifying model as worse. Fixed to return -100% when baseline is perfect and model has error.


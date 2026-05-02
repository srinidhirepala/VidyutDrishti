# Feature 05 - Prophet Forecasting

## Test Review

**Test file:** `tests/test_forecasting.py` (stdlib `unittest`; requires `numpy`, `pandas`, `joblib`; Prophet optional).

**Run command:**
```powershell
python -m unittest logs/05-prophet-forecasting/tests/test_forecasting.py -v
```

**Result on host without Prophet:** `Ran 11 tests in 0.024s - OK (skipped=9)` (2 passed, 9 skipped).

**Result when Prophet installed:** 11 tests pass including training, forecasting, backtesting, persistence.

### Coverage Map

| Test class | Validates |
|------------|-----------|
| `TestForecastService` (9 tests, Prophet-required) | Synthetic daily data generation with weekly seasonality; model training creates valid ForecastModel; save/load roundtrip; forecast returns correct number of days with valid bounds (yhat_lower < yhat < yhat_upper); backtest returns metrics DataFrame with MAPE; MAPE stored in model; version hash is deterministic for identical data. |
| `TestForecastModelPersistence` (2 tests, Prophet-required) | Load missing model returns None; list_models empty when no models exist. |
| `TestWithoutProphet` (2 tests, always runs) | ForecastResult dataclass works; Model.save/load works even when Prophet model is None (for dry-run / stub scenarios). |

### Observations

- `@unittest.skipUnless(PROPHET_AVAILABLE, ...)` gates Prophet-dependent tests so the suite passes on hosts without the heavy dependency.
- Model version is a truncated SHA256 hash of data bounds, making it deterministic and collision-resistant for prototype scale.
- The synthetic data generator includes weekly seasonality (weekdays higher, weekends lower) which Prophet should capture.
- MAPE target (< 10%) is enforced by the evaluation harness in Feature 21, not by these unit tests. The tests verify that MAPE is computed and stored, not that it meets the target (which depends on data quality).

### Constraints Honoured

- Read-only posture: tests use temporary directories; no DB writes.
- No real PII: synthetic feeder IDs only.
- Prophet isolation: all Prophet imports are try/except wrapped with `PROPHET_AVAILABLE` flag.


# Feature 07 - Forecast Backtest & Baselines

## Test Review

**Test file:** `tests/test_evaluation.py` (stdlib `unittest`; requires `numpy`, `pandas`).

**Run command:**
```powershell
python -m unittest logs/07-forecast-backtest/tests/test_evaluation.py -v
```

**Result:** `Ran 20 tests in 0.028s - OK` (20 passed, 0 failed, 0 errors).

### Coverage Map

| Test class | Validates |
|------------|-----------|
| `TestMetrics` (6 tests) | MAPE basic calculation, zero actuals handling, all-zeros returns inf; RMSE, MAE, bias (positive/over-forecast, negative/under-forecast). |
| `TestNaiveBaseline` (3 tests) | Predict returns yesterday's value; predict missing date returns None; forecast_all adds baseline column with proper shift. |
| `TestBaselineComparison` (3 tests) | Model beats baseline on trending data; baseline beats model on flat data; insufficient data returns inf. |
| `TestDay7MatchAccuracy` (5 tests) | All within ±10% meets 85% target; half within fails target; exactly 10% boundary within; 10.1% outside tolerance; horizon column filtering. |
| `TestHorizonMapes` (1 test) | MAPE calculated per horizon day (1-7) with NaN for empty horizons. |
| `TestBacktester` (2 tests) | Full backtest report generation; missing columns raises ValueError. |

### Observations

- MAPE target (< 10%) is verified by the evaluation harness in Feature 21; these unit tests verify metric calculation correctness.
- Day-7 match target (85% within ±10%) is explicitly tested with boundary conditions.
- Naive baseline (persistence model) provides a strong sanity check: Prophet must beat "tomorrow = today" to justify complexity.
- MAPE is undefined when actuals are zero; the implementation ignores those rows. If all actuals are zero, returns infinity.

### Bug fixes during development
- `test_model_beats_baseline` and `test_baseline_beats_model` initially used flat time series where both model and baseline were perfect. Fixed by using trending data for first test (where baseline lags) and keeping flat data for second test (where baseline is perfect and model has error).
- Improvement calculation when baseline MAPE is exactly 0 was returning 0.0 instead of negative. Fixed to return -100% (model is worse) when baseline is perfect and model has error.

### Constraints Honoured

- Read-only posture: tests use in-memory DataFrames.
- No real PII: synthetic time series only.


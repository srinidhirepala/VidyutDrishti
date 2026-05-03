# Feature 14 - Behavioural Classifier

## Errors Log

### E14-001 - AttributeError on cutoff.date()
- **When:** Running batch classification tests.
- **Symptom:** `AttributeError: 'datetime.date' object has no attribute 'date'`
- **Root cause:** `cutoff` was already a date object from `target_date - pd.Timedelta`, not a Timestamp.
- **Resolution:** Changed `cutoff.date()` to `pd.Timestamp(cutoff).date()` to ensure consistent conversion.
- **Status:** Fixed; test passes.

### E14-002 - Test data date indexing
- **When:** Running individual classification tests.
- **Symptom:** `prior_day_kwh` was None or incorrect because df_prior wasn't properly indexed by date.
- **Root cause:** Test helper created DataFrames without date index for grouping.
- **Resolution:** Modified `_make_day_data` and `_make_prior_data` to set explicit date index.
- **Status:** Fixed; tests pass.

### E14-003 - Erratic test triggered spike instead
- **When:** Running `test_erratic`.
- **Symptom:** Expected `AnomalyType.ERRATIC` but got `AnomalyType.SPIKE`.
- **Root cause:** Test data `[10.0, 0.1] * 48` had high total causing large daily increase vs prior.
- **Resolution:** Changed test data to `[2.0, 0.5] * 48` (stable total ~120) and prior to match.
- **Status:** Fixed; test passes.

All 10 tests passed after fixes.


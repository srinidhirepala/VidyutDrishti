# Feature 07 - Forecast Backtest & Baselines

## Errors Log

### E07-001 - Baseline comparison tests with flat data had identical performance
- **When:** Running `TestBaselineComparison` tests.
- **Symptom:** `test_model_beats_baseline` failed: `beats_baseline` was False when expecting True; `test_baseline_beats_model` had improvement = 0.0 instead of negative.
- **Root cause:** Used flat time series `[100.0] * 10` where naive baseline (yesterday's value) also equals 100.0, giving both model and baseline 0% MAPE. No differentiation between model performance.
- **Resolution:** 
  - For `test_model_beats_baseline`: Changed to trending data `[100, 110, 120, ...]` where perfect model follows trend exactly but baseline (yesterday's value) lags behind, creating ~5-10% error.
  - For `test_baseline_beats_model`: Kept flat data but made model predict 110.0 (10% error) while baseline stays perfect at 100.0.
- **Status:** Fixed; tests pass.

### E07-002 - Improvement calculation with zero baseline MAPE
- **When:** Debugging `test_baseline_beats_model` after E07-001 fix.
- **Symptom:** `improvement_percent` was 0.0 instead of negative when baseline MAPE was 0.0.
- **Root cause:** Code had `if baseline_m == 0 or baseline_m == float("inf"): improvement = 0.0` which didn't distinguish between perfect baseline (0%) and invalid baseline (inf).
- **Resolution:** Changed logic to:
  - If baseline is inf: improvement = 0.0 (indeterminate)
  - If baseline is 0 and model > 0: improvement = -100.0 (model is worse)
  - If baseline is 0 and model is 0: improvement = 0.0 (tied)
  - Otherwise: normal percentage improvement calculation
- **Status:** Fixed; tests pass.

All 20 tests passed after fixes.


# Feature 10 - Layer 1 Z-Score Baseline

## Errors Log

### E10-001 - Zero std in test data caused inf z-score
- **When:** Running `test_low_consumption_creates_anomaly`.
- **Symptom:** Expected negative z-score but got `inf` because historical std was 0.
- **Root cause:** Test used `[100.0] * 14` for history (all identical values), resulting in std=0.
- **Resolution:** Changed test to use varied historical data `[70, 130, 100, 90, 110, 80, 120] * 2` to ensure non-zero std.
- **Status:** Fixed; test passes.

No other errors encountered during Feature 10 development. All 14 tests passed after fix.

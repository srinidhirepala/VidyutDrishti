# Feature 10 - Layer 1 Z-Score Baseline

## Test Review

**Test file:** `tests/test_layer1.py` (stdlib `unittest`; requires `numpy`, `pandas`).

**Run command:**
```powershell
python -m unittest logs/10-layer1-zscore/tests/test_layer1.py -v
```

**Result:** `Ran 14 tests in 0.016s - OK` (14 passed, 0 failed, 0 errors).

### Coverage Map

| Test class | Validates |
|------------|-----------|
| `TestComputeStats` (3 tests) | Mean/std computation with sufficient data; insufficient data returns None; zero std returns mean with None std |
| `TestZScoreAnalyzer` (8 tests) | Normal consumption z ~ 0 no anomaly; spike creates anomaly; low consumption creates anomaly; insufficient history returns None; target not in series returns None; z-score calculation with zero std; boundary at threshold; lookback window limits history to 90 days |
| `TestZScoreResult` (1 test) | Dataclass construction, to_db_row serialization |
| `TestBatchAnalysis` (2 tests) | Batch multiple meters; empty data returns empty list |

### Observations

- Layer 1 detects individual meter anomalies based on deviation from historical mean.
- Threshold is typically |z| > 3.0 (configurable, default 3.0).
- Requires minimum 7 days of history for meaningful statistics.
- Uses 90-day lookback window to adapt to seasonal changes.
- Zero std (no variation in history) results in infinite z-score for any deviation.
- Negative z = under-consumption (possible theft or meter fault); positive z = over-consumption (possible data error or generation).

### Bug fixes during development
- `test_low_consumption_creates_anomaly` initially used flat historical data (all 100s) which resulted in std=0 and z=inf. Fixed by creating varied historical data so std is non-zero.

### Constraints Honoured

- Read-only posture: tests use in-memory Series/DataFrames.
- No real PII: synthetic meter IDs only.

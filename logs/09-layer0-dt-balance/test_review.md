# Feature 09 - Layer 0 DT Energy Balance

## Test Review

**Test file:** `tests/test_layer0.py` (stdlib `unittest`; requires `pandas`).

**Run command:**
```powershell
python -m unittest logs/09-layer0-dt-balance/tests/test_layer0.py -v
```

**Result:** `Ran 13 tests in 0.013s - OK` (13 passed, 0 failed, 0 errors).

### Coverage Map

| Test class | Validates |
|------------|-----------|
| `TestBalanceResult` (1 test) | Dataclass construction, to_db_row serialization |
| `TestBalanceAnalyzer` (11 tests) | Perfect balance no anomaly; under-reporting anomaly; over-reporting anomaly; within threshold not anomaly; boundary at threshold not anomaly; just over threshold is anomaly; missing dt_reading returns None; zero dt_in returns None; default technical loss applied; multiple meters aggregated |
| `TestBatchAnalysis` (2 tests) | Batch multiple DTs; empty DataFrame returns empty list |

### Observations

- Layer 0 detects aggregate theft scenarios (DT bypass, unrecorded connections, widespread meter tampering).
- Threshold is ±3% imbalance (configurable, default 3.0%).
- Technical losses default to 6% if not provided (typical for LT distribution).
- Imbalance formula: `(meters_sum - expected) / dt_in * 100` where expected = `dt_in * (1 - loss%)`.
- Negative imbalance = under-reporting (theft); positive = over-reporting (data error or generation).

### Bug fixes during development
- Empty DataFrames caused KeyError on 'date' column; added guards to handle empty inputs.
- `float(dt_reading.get("losses"))` failed when losses was None; fixed with explicit None check.

### Constraints Honoured

- Read-only posture: tests use in-memory DataFrames.
- No real PII: synthetic DT/meter IDs only.

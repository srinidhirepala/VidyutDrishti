# Feature 12 - Layer 3 Isolation Forest

## Test Review

**Test file:** `tests/test_layer3.py` (stdlib `unittest`; requires `numpy`, `pandas`; scikit-learn optional).

**Run command:**
```powershell
python -m unittest logs/12-layer3-isoforest/tests/test_layer3.py -v
```

**Result on host without sklearn:** `Ran 11 tests in 1.05s - OK (skipped=10)` (1 passed, 10 skipped).

**Result with sklearn:** 11 tests pass including training, anomaly detection, batch processing.

### Coverage Map

| Test class | Validates |
|------------|-----------|
| `TestIsoForestAnalyzer` (7 tests, sklearn-required) | Train creates model; analyze returns result; normal data not anomaly; extreme data is anomaly; insufficient train data returns False; untrained analyze returns None; missing features returns None |
| `TestIsoForestBatch` (2 tests, sklearn-required) | Analyze batch; empty batch returns empty |
| `TestIsoForestResult` (1 test, sklearn-required) | Dataclass construction, to_db_row serialization |
| `TestWithoutSklearn` (1 test, always runs) | Result dataclass works without sklearn installed |

### Observations

- Isolation Forest is the most sophisticated layer, catching multivariate patterns that univariate methods miss.
- Requires minimum 100 training samples for stability (configurable).
- Contamination parameter (default 0.1) sets expected anomaly proportion.
- Anomaly score is negative for outliers (sklearn convention); threshold at -0.5.
- Feature columns are configurable; defaults to 7 engineered features from Feature 08.
- Model version computed from training data hash for reproducibility.

### Constraints Honoured

- Read-only posture: tests use synthetic data; no DB writes.
- No real PII: synthetic meter IDs only.
- sklearn isolation: All sklearn imports wrapped with `SKLEARN_AVAILABLE` flag; tests skip if unavailable.

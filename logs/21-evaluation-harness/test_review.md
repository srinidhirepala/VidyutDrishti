# Feature 21 - Evaluation Harness

## Test Review

**Test file:** `tests/test_harness.py` (stdlib `unittest`; requires `pandas`).

**Run command:**
```powershell
python C:\Hackathon\VidyutDrishti\logs\21-evaluation-harness\tests\test_harness.py
```

**Result:** `Ran 13 tests in 0.003s - OK` (13 passed, 0 failed, 0 errors).

### Coverage Map

| Test class | Validates |
|------------|-----------|
| `TestGroundTruthLabel` (1 test) | Dataclass construction, to_dict |
| `TestDetectionPrediction` (1 test) | Dataclass construction, to_dict |
| `TestEvaluationMetrics` (4 tests) | Perfect detection, all false positives, all false negatives, balanced performance |
| `TestEvaluationHarness` (7 tests) | Perfect predictions, false positive, false negative, missing prediction, missing ground truth, threshold sweep, load from DataFrame |

### Observations

- EvaluationHarness compares detection predictions against ground truth labels.
- Supports threshold sweeps to find optimal operating point.
- Metrics: accuracy, precision, recall, F1, specificity.
- Confusion matrix tracking for detailed analysis.
- Loads data from pandas DataFrames for flexibility.
- CLI entry point for CSV-based evaluation.

### Constraints Honoured

- Read-only posture: tests use synthetic data.
- No real PII: synthetic meter IDs only.


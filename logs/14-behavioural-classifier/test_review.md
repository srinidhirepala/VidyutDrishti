# Feature 14 - Behavioural Classifier

## Test Review

**Test file:** `tests/test_classifier.py` (stdlib `unittest`; requires `pandas`).

**Run command:**
```powershell
python C:\Hackathon\VidyutDrishti\logs\14-behavioural-classifier\tests\test_classifier.py
```

**Result:** `Ran 10 tests in 0.080s - OK` (10 passed, 0 failed, 0 errors).

### Coverage Map

| Test class | Validates |
|------------|-----------|
| `TestAnomalyType` (1 test) | Enum values for all anomaly types |
| `TestBehaviouralClassifier` (6 tests) | Normal pattern; sudden drop (40% decrease); flatline (95% zeros); spike (60% increase); erratic (high CV); flatline precedence over drop |
| `TestClassificationResult` (1 test) | Dataclass construction, to_db_row serialization |
| `TestBatchClassification` (2 tests) | Batch multiple meters; empty data returns empty |

### Observations

- Behavioural classifier categorizes anomalies into actionable types for investigators.
- Classification priority: flatline > sudden_drop > spike > erratic > normal.
- Thresholds: flatline (90% zeros), sudden drop (30% decrease), spike (50% increase), erratic (CV > 50%).
- Flatline is highest priority because it indicates clear tampering (bypass/disconnect).
- Provides human-readable descriptions for each classification.
- CV (coefficient of variation) captures intra-day volatility.

### Bug fixes during development

- **E14-001:** `cutoff.date()` failed because `cutoff` was already a date object; fixed with `pd.Timestamp(cutoff).date()`.
- **E14-002:** Test data had incorrect date indexing; fixed by adding explicit date columns and setting index.
- **E14-003:** Erratic test triggered spike instead; fixed by adjusting test data to have stable total while maintaining high volatility.

### Constraints Honoured

- Read-only posture: tests use synthetic data.
- No real PII: synthetic meter IDs only.


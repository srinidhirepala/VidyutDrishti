# Feature 06 - Zone Risk Classification

## Test Review

**Test file:** `tests/test_risk.py` (stdlib `unittest`; requires `pandas`).

**Run command:**
```powershell
python -m unittest logs/06-zone-risk-classification/tests/test_risk.py -v
```

**Result:** `Ran 14 tests in 0.059s - OK` (14 passed, 0 failed, 0 errors).

### Coverage Map

| Test class | Validates |
|------------|-----------|
| `TestRiskLevelEnum` (3 tests) | RiskLevel ordering (HIGH < MEDIUM < LOW), comparison operators, string values. |
| `TestZoneRiskResult` (1 test) | Dataclass construction, `to_db_row()` serialization for DB insertion. |
| `TestZoneRiskClassifier` (9 tests) | HIGH risk when headroom < 10%; MEDIUM risk when 10-25%; LOW risk when > 25%; HIGH when overloaded (negative headroom); fallback to historical peak when capacity_kva missing; assumes HIGH when no capacity data; custom threshold configuration; invalid threshold rejection; batch classification via DataFrame. |
| `TestClassifyZonesCSV` (1 test) | End-to-end CSV roundtrip: forecast + capacity input, risk CSV output. |

### Observations

- Default thresholds (HIGH < 10%, MEDIUM < 25%, LOW >= 25%) align with typical utility operational margins.
- Power factor assumption of 0.9 is conservative for Karnataka LT networks; configurable via constructor.
- When both capacity_kva and historical_peak_kw are missing, the classifier assumes -50% headroom (HIGH risk) to force attention rather than silently defaulting to LOW.
- RiskLevel implements comparison operators so `max(risk_levels)` returns the most severe risk in a set.

### Constraints Honoured

- Read-only posture: tests use temporary directories and in-memory DataFrames.
- No real PII: synthetic feeder IDs only.
- Headroom calculation: `(capacity - predicted) / capacity * 100`, negative when overloaded.


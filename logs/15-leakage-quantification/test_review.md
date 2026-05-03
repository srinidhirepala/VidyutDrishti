# Feature 15 - Leakage Quantification

## Test Review

**Test file:** `tests/test_leakage.py` (stdlib `unittest`; requires `pandas`).

**Run command:**
```powershell
python C:\Hackathon\VidyutDrishti\logs\15-leakage-quantification\tests\test_leakage.py
```

**Result:** `Ran 10 tests in 0.016s - OK` (10 passed, 0 failed, 0 errors).

### Coverage Map

| Test class | Validates |
|------------|-----------|
| `TestLeakageEstimate` (1 test) | Dataclass construction, to_db_row serialization |
| `TestLeakageQuantifier` (7 tests) | Peer deviation calculation; no loss when actual exceeds expected; z-score fallback; z-score caps at 3 std; insufficient data returns None; custom tariff; peer method preferred over z-score |
| `TestLeakageBatch` (2 tests) | Quantify batch; empty data returns empty |

### Observations

- Leakage quantification translates anomalies into financial impact for prioritization.
- Two estimation methods: peer deviation (most reliable for theft) and z-score extrapolation (fallback).
- Peer method: loss = peer_mean - actual (simple difference).
- Z-score method: capped at 3 std devs to avoid extreme outliers (likely meter fault, not theft).
- Default tariff: 7.50 INR/kWh (typical domestic rate); customizable per meter.
- INR calculation uses Decimal for financial precision.

### Bug fixes during development

- Test expected uncapped value but z-score method correctly caps at 3 std; adjusted test values to stay within cap.

### Constraints Honoured

- Read-only posture: tests use synthetic data.
- No real PII: synthetic meter IDs only.
- Financial precision: uses Decimal for currency calculations.


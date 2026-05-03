# Feature 16 - Inspection Queue

## Test Review

**Test file:** `tests/test_queue.py` (stdlib `unittest`; requires `pandas`).

**Run command:**
```powershell
python C:\Hackathon\VidyutDrishti\logs\16-inspection-queue\tests\test_queue.py
```

**Result:** `Ran 11 tests in 0.065s - OK` (11 passed, 0 failed, 0 errors).

### Coverage Map

| Test class | Validates |
|------------|-----------|
| `TestInspectionItem` (2 tests) | Default status pending; to_db_row serialization |
| `TestInspectionQueue` (9 tests) | Generate creates ranked items; respects max size; filters by min confidence; assign updates status; complete updates status; dismiss updates status; filter by zone; filter by feeder; get pending |

### Observations

- Inspection queue converts detection results into prioritized work orders for field teams.
- Ranking: confidence (primary), then financial impact (secondary).
- Configurable max queue size (default 100) and min confidence threshold (default 0.5).
- Lifecycle: pending → assigned → completed/dismissed.
- Assignment includes inspector ID and scheduled date.
- Filtering by zone/feeder enables territory-based dispatch.

### Constraints Honoured

- Read-only posture: tests use synthetic data.
- No real PII: synthetic meter IDs only.


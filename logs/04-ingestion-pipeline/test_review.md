# Feature 04 - Ingestion Pipeline & Data Quality

## Test Review

**Test file:** `tests/test_ingestion.py` (stdlib `unittest`; requires `numpy`, `pandas`).

**Run command:**
```powershell
python -m unittest logs/04-ingestion-pipeline/tests/test_ingestion.py -v
```

**Result:** `Ran 18 tests in 0.176s - OK` (18 passed, 0 failed, 0 errors).

### Coverage Map

| Test class | Validates |
|------------|-----------|
| `TestQualityGate` | All-clean pass; missing-required-column rejection; negative kWh rejection; voltage above max rejection; null meter_id rejection; null kWh allowed (allow_null); duplicate PK detection. |
| `TestImputer` | Gap classification buckets (short <=1h, medium 1-6h, long >6h); linear interpolation for short gaps; diurnal mean fill for medium gaps; long gaps left as NaN; imputation across multiple meters. |
| `TestLoader` | Meter row preparation without DB session; empty row no-op; reject recording with reason; consumer feeder derivation from dt_id. |
| `TestPipelineEndToEnd` | CSV round-trip with dry-run (session=None); CSV reader chunk streaming. |

### Observations

- Pipeline runs entirely without a live DB when `session=None`, making the test suite hermetic and fast (<200ms for 18 tests).
- The imputer's diurnal mean fill uses the actual per-slot-of-day mean from the series being imputed, not a global lookup. This is correct for prototype scale; production might use a precomputed seasonal profile.
- Idempotency is guaranteed by `ON CONFLICT (pk...) DO NOTHING` SQL in the loader, not by pre-filtering in Python. This keeps the loader simple and race-safe.
- Quality gate rejects are written to `ingest_errors` with full payload JSON for forensics; this table is intentionally not hypertabled (low volume, audit purpose).

### Constraints Honoured

- Read-only posture: test suite never writes to a real DB.
- No real PII: tests use synthetic meter IDs from the simulator.
- Ground-truth isolation: `injected_events` is loaded by the pipeline but never read by detection logic in later features.


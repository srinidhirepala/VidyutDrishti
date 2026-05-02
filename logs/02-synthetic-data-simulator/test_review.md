# Feature 02 - Synthetic Data Simulator

## Test Review

**Test file:** `tests/test_simulator.py` (stdlib `unittest`; requires `numpy`, `pandas`).

**Run command:**
```powershell
python -m unittest logs/02-synthetic-data-simulator/tests/test_simulator.py -v
```

**Result:** `Ran 16 tests in 1.083s - OK` (16 passed, 0 failed, 0 errors).

Additional smoke test on the production YAML:
```
python -c "from simulator.models import SimConfig; import yaml; ..."
-> OK: 2 DTs x 30 meters x 180 days; theft: 3 decoys: 2
```

### Coverage Map

| Test class | Validates |
|------------|-----------|
| `TestShapeAndTopology` | Consumer count, DT count, meter-reading row count (meters x days x 96), DT-reading row count (DTs x days x 96), per-meter strictly-increasing timestamps, and required column sets on both output frames. |
| `TestValueRanges` | kWh non-negative (or NaN when missing), voltage within `[voltage_min, voltage_max]`, PF in `[0,1]`, and that missing flags coincide with NaN in kwh/voltage. |
| `TestDeterminism` | Same seed yields byte-identical hashes of the meter-reading frame; different seeds yield different kWh vectors. |
| `TestInjectedScenarios` | `injected_events` captures 3 theft + 1 decoy; hook-bypass meter's post-event mean is <1/3 of pre-event mean; meter-stop meter is exactly 0.0 post-event. |
| `TestDTEnergyBalance` | For every (dt, ts), `kwh_in >= sum(meter kwh)` - technical loss is non-negative. |

### Observations

- Sub-2-second runtime on the small test config (2 DTs x 4 meters x 7 days = 5,376 rows), keeping the feedback loop tight.
- Determinism is deliberately hash-based (via `pd.util.hash_pandas_object`) rather than frame-equality; catches any accidental mutation of a global RNG.
- Gradual tampering is not a dedicated behavioural test case because its ramp is subtle at 7 days of data. It is exercised by the hook-bypass and meter-stop tests plus the `injected_events` recording check; the evaluation harness in Feature 21 will test gradual tampering at full 180-day scale.
- Missing-reading probabilities are set to zero for medium/long gaps in the small config; Feature 04 (ingestion + data quality) is where those are exercised end-to-end.

### Constraints Honoured

- Read-only posture: tests operate entirely on in-memory DataFrames, no DB, no network.
- No real PII: all identifiers are synthetic (`DT1-M02`, etc.).
- Ground-truth isolation: `injected_events` is returned as a separate DataFrame; detection code paths never see it.
- Prototype discipline: avoids property-based or fuzz testing; relies on a fixed seed and targeted assertions.


# Feature 08 - Daily Feature Engineering

## Test Review

**Test file:** `tests/test_features.py` (stdlib `unittest`; requires `numpy`, `pandas`).

**Run command:**
```powershell
python -m unittest logs/08-feature-engineering/tests/test_features.py -v
```

**Result:** `Ran 18 tests in 0.139s - OK` (18 passed, 0 failed, 0 errors).

### Coverage Map

| Test class | Validates |
|------------|-----------|
| `TestDiurnalFeatures` (3 tests) | Peak/trough/mean computation from 15-min slots; empty data handling; all-NaN handling. |
| `TestHealthScore` (4 tests) | Perfect data scores >= 0.8; missing slots reduces score; out-of-range voltage reduces score; empty data returns 0. |
| `TestFeatureEngineer` (11 tests) | engineer_day returns features; total_kwh sum correct; rolling7 computed with 9+ days history; rolling7 None with <7 days; temp_ratio computed with 30+ days; weekday_isin correct for weekday/weekend; holiday detection; inspection days computed; no inspection returns None; empty history returns None. |
| `TestMeterFeaturesDataclass` (1 test) | to_db_row serialization includes all fields. |

### Observations

- Feature vector includes 17 fields covering consumption (total_kwh, rolling7, diurnal stats), temporal (weekday/holiday/day_of_week), domain-specific (temp_ratio, health, voltage_var, pf_mean), and operational context (last_inspection_days).
- Health score uses weighted composition: completeness (60%), voltage sanity (20%), PF sanity (20%).
- Rolling features require minimum history: 7 days for rolling7, 30 days for temp_ratio.
- Holiday set passed to FeatureEngineer constructor enables domain-aware features.

### Bug fixes during development

- **E08-001:** `test_temp_ratio_computed` used invalid date `date(2024, 1, 35)` (January has 31 days). Fixed to `date(2024, 2, 4)` (day 35 from Jan 1).
- **E08-002:** Date filtering `df_history[df_history["ts"] <= target_ts]` only kept timestamps up to midnight, missing all daytime slots. Fixed to use `target_end = target_ts + 1 day` and filter `< target_end`.
- **E08-003:** Health score formula multiplied completeness by (voltage+pf) instead of adding weighted components. Fixed to additive: `completeness_score + voltage_score + pf_score`.

### Constraints Honoured

- Read-only posture: tests use in-memory DataFrames.
- No real PII: synthetic meter IDs only.

# Feature 09 - Layer 0 DT Energy Balance

## Changes Log

### Implemented as specified in `features.md` section 09
- **Data model** (`detection/layer0_balance.py`): `BalanceResult` dataclass with fields for DT energy balance analysis; `to_db_row()` for DB serialization.
- **Analyzer** (`detection/layer0_balance.py`): `BalanceAnalyzer` class with:
  - `analyze`: Single DT/day analysis comparing kwh_in vs meters_sum with technical loss adjustment
  - `analyze_batch`: Batch processing for multiple DTs from DataFrames
  - Imbalance calculation with configurable ±3% threshold
  - Anomaly flag when |imbalance| > threshold
- **CLI helper** (`analyze_balance_csv`): CSV-to-CSV batch processing.
- **Module init** (`detection/__init__.py`): Exports public API.

### Deviations from plan
- **No continuous aggregate integration in code.** The plan mentioned "query dt_daily continuous aggregate". The implementation accepts DataFrames (which could come from any source including the continuous aggregate) for testability.
- **No topology CSV reader in production code.** The batch method accepts topology as a DataFrame; CSV reading is in the CLI helper for testing.

### New additions not explicitly in the plan
- `expected_consumption` field calculated as `dt_in * (1 - loss%)` for transparency.
- `n_meters_missing` field for tracking data completeness (currently 0, reserved for future).
- Empty DataFrame guards to prevent runtime errors in batch processing.

### Bug fixes during development
- Empty DataFrames caused KeyError; added guards for empty inputs and missing columns.
- None losses caused TypeError in float(); added explicit None check with fallback to default.

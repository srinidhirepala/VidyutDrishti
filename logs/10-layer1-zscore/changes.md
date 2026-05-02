# Feature 10 - Layer 1 Z-Score Baseline

## Changes Log

### Implemented as specified in `features.md` section 10
- **Data model** (`detection/layer1_zscore.py`): `ZScoreResult` dataclass with z-score, mean, std, and anomaly flag; `to_db_row()` for DB serialization.
- **Analyzer** (`detection/layer1_zscore.py`): `ZScoreAnalyzer` class with:
  - `analyze`: Single meter/day z-score calculation using historical mean/std
  - `analyze_batch`: Batch processing for multiple meters from DataFrames
  - Configurable threshold (default |z| > 3.0)
  - 90-day lookback window for statistics
  - Minimum 7 days history requirement
- **Helper** (`_compute_stats`): Returns (mean, std) with guards for insufficient data and zero std.
- **CLI helper** (`analyze_zscore_csv`): CSV-to-CSV batch processing.
- **Module init** (`detection/__init__.py`): Updated exports.

### Deviations from plan
- **No direct SQL for statistics.** The plan mentioned "rolling mean/std via SQL window functions". Implementation uses pandas Series operations for testability and flexibility; SQL window functions can be added in production for performance.
- **Simplified batch interface.** Accepts DataFrames rather than SQL query results for hermetic testing.

### New additions not explicitly in the plan
- `abs_z_score` field for easier thresholding and sorting.
- `n_historical_days` field to track how much history was used.
- Zero std handling: returns z_score = inf when no historical variation.
- Lookback window (90 days) to prevent statistics from becoming stale.

### Bug fixes during development
- `test_low_consumption_creates_anomaly` used flat history causing std=0; fixed by adding variation to historical data.

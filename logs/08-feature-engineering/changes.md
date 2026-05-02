# Feature 08 - Daily Feature Engineering

## Changes Log

### Implemented as specified in `features.md` section 08
- **Data models** (`features/models.py`): `MeterFeatures` dataclass with 17 fields covering consumption, temporal, domain-specific, and operational features; `to_db_row()` serialization.
- **Engine** (`features/engineer.py`): `FeatureEngineer` class with:
  - `engineer_day`: Build feature vector for single meter/date
  - `engineer_batch`: Batch processing for all meters
  - Rolling aggregations: 7-day mean, 30-day mean for temp_ratio
  - Diurnal features: peak, trough, mean from 15-min slots
  - Health score: weighted composition of completeness (60%), voltage sanity (20%), PF sanity (20%)
  - Temporal features: weekday_isin, is_holiday, day_of_week
  - Inspection context: days since last inspection
- **CLI helper** (`build_features`): CSV-to-CSV batch processing.
- **Module init** (`features/__init__.py`): Exports public API.

### Deviations from plan
- **No materialized view in code.** The plan mentioned "Materialized view: meter_daily_features hypertable". The implementation produces feature dataclasses that callers persist to DB; the SQL schema already defines the table structure in Feature 03.
- **No billing_slab_id in features.** The plan listed this as a feature field. Omitted because tariff slab mapping requires business rules not defined in the prototype; can be added as a lookup layer.
- **No direct DB integration in engineer.** The engineer accepts DataFrames and returns dataclasses; persistence handled by caller (scheduler or API layer).

### New additions not explicitly in the plan
- `temp_ratio`: Day consumption / 30-day rolling mean as a temporal anomaly indicator.
- `voltage_variability` and `pf_mean`: Power quality features for technical loss identification.
- `meter_health_score`: Synthetic 0-1 score for dashboard visualization.
- `slots_missing` and `slots_total`: Data quality tracking for downstream imputation awareness.

### Bug fixes during development
- Invalid date `date(2024, 1, 35)` in test - changed to valid date.
- Date filtering `<= target_ts` only kept midnight rows - fixed to `< target_end` (next day).
- Health score formula was multiplicative instead of additive - fixed weighted sum.

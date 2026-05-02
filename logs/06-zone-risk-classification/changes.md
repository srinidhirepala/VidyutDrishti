# Feature 06 - Zone Risk Classification

## Changes Log

### Implemented as specified in `features.md` section 06
- **Data models** (`risk/models.py`): `RiskLevel` Enum (HIGH/MEDIUM/LOW) with comparison operators; `ZoneRiskResult` dataclass with `to_db_row()` serialization; headroom percentage included.
- **Classifier** (`risk/classifier.py`): `ZoneRiskClassifier` with:
  - `classify`: Single feeder/date classification based on forecasted peak vs capacity.
  - `classify_forecast_df`: Batch classification from forecast DataFrame.
  - Headroom thresholds: HIGH < 10%, MEDIUM < 25%, LOW >= 25% (configurable).
  - Capacity fallback: uses `capacity_kva * pf` if available, else `historical_peak_kw * 1.2`.
  - Worst-case assumption: HIGH risk (-50% headroom) when no capacity data exists.
- **CLI helper** (`classify_zones` function): CSV-to-CSV interface for batch processing.
- **Module init** (`risk/__init__.py`): Exports public API.

### Deviations from plan
- **Thresholds explicit rather than configured via YAML.** The plan mentioned "configurable headroom thresholds". Implemented as constructor arguments with defaults (10%/25%) rather than external YAML file to keep the prototype self-contained.
- **Power factor assumption 0.9.** Not explicitly stated in plan; chosen as conservative default for Karnataka LT distribution.
- **No direct DB integration in classifier.** The classifier accepts DataFrames and returns dataclasses; DB writes are handled by the caller (scheduler or API layer). This matches the plan's "write to zone_risk table" but keeps the classifier pure.

### New additions not explicitly in the plan
- `RiskLevel` implements `__lt__` and `__gt__` for severity comparison, enabling `max()` over a set of risks to find the worst.
- `FeederCapacity` dataclass to encapsulate capacity data with optional fields.
- Headroom percentage stored in result for transparency in dashboards.


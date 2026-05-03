# Feature 14 - Behavioural Classifier

## Changes Log

### Implemented as specified in `features.md` section 14
- **Data models** (`detection/classifier.py`): `AnomalyType` enum (sudden_drop, spike, flatline, erratic, normal_pattern); `ClassificationResult` dataclass with type, confidence, metrics, and description.
- **Classifier** (`detection/classifier.py`): `BehaviouralClassifier` class with:
  - `classify`: Categorizes single meter into anomaly type
  - `classify_batch`: Batch processing for all meters
  - Priority: flatline > sudden_drop > spike > erratic > normal
  - Metrics: daily_change_pct, zero_slots_ratio, cv_daily, rolling_mean_ratio
  - Human-readable descriptions for investigators
- **Thresholds**: flatline (90% zeros), drop (30% decrease), spike (50% increase), erratic (CV > 50%).
- **CLI helper** (`classify_anomalies_csv`): CSV-to-CSV batch processing.
- **Module init** (`detection/__init__.py`): Updated exports.

### Deviations from plan
- **No rule-based fuzzy logic with complex predicates.** Implementation uses simple sequential threshold checks which is more maintainable and performant.
- **No direct SQL integration.** Classifier accepts DataFrames for testability.

### New additions not explicitly in the plan
- `rolling_mean_ratio` metric for context.
- `description` field with human-readable explanation.
- CV (coefficient of variation) for volatility detection.
- Priority ordering ensures flatline (clearest tampering indicator) is detected first.

### Bug fixes during development
- **E14-001:** `cutoff.date()` AttributeError fixed with `pd.Timestamp(cutoff).date()`.
- **E14-002:** Test data date indexing fixed.
- **E14-003:** Erratic test data adjusted to avoid triggering spike.


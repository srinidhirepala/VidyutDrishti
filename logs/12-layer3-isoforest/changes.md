# Feature 12 - Layer 3 Isolation Forest

## Changes Log

### Implemented as specified in `features.md` section 12
- **Data model** (`detection/layer3_isoforest.py`): `IsoForestResult` dataclass with anomaly score, feature names/values, and model version; `to_db_row()` for DB serialization.
- **Analyzer** (`detection/layer3_isoforest.py`): `IsoForestAnalyzer` class with:
  - `train`: Fits Isolation Forest on historical normal data
  - `analyze`: Scores single meter against trained model
  - `analyze_batch`: Batch scoring for efficiency
  - Configurable feature columns (defaults to 7 engineered features)
  - Contamination parameter for expected anomaly proportion
  - Model versioning via training data hash
- **CLI helper** (`train_and_analyze_csv`): CSV-to-CSV workflow.
- **Module init** (`detection/__init__.py`): Updated exports.

### Deviations from plan
- **sklearn made optional.** `features.md` listed scikit-learn as a core dependency. The implementation wraps imports with `SKLEARN_AVAILABLE` flag for host testing, similar to Prophet in Feature 05.
- **No feature importance extraction.** The plan mentioned "top 2 driving features". Implementation includes feature names and values but doesn't compute SHAP or permutation importance; can be added in production.

### New additions not explicitly in the plan
- `SKLEARN_AVAILABLE` flag for import-safe gating.
- `_compute_version` for deterministic model versioning.
- Batch scoring method for production efficiency.
- NaN handling via median imputation in feature preparation.

### Bug fixes during development
- None required for this feature.

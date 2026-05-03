# Feature 13 - Confidence Engine

## Changes Log

### Implemented as specified in `features.md` section 13
- **Data models** (`detection/confidence.py`): `LayerSignals` dataclass for 4-layer inputs; `ConfidenceResult` dataclass with aggregated score, rank, and layer contributions.
- **Engine** (`detection/confidence.py`): `ConfidenceEngine` class with:
  - `compute`: Aggregates 4-layer signals into 0-1 confidence score
  - `compute_batch`: Batch processing with ranking
  - Layer weights: L0 (10%), L1 (30%), L2 (30%), L3 (30%)
  - Threshold-based normalization per layer
  - Contribution percentages for explainability
- **CLI helper** (`compute_confidence_csv`): CSV-to-CSV batch processing.
- **Module init** (`detection/__init__.py`): Updated exports.

### Deviations from plan
- **Simplified layer score calculation.** The plan mentioned "weighted ensemble of layer scores". Implementation uses threshold-normalized scores (anomaly magnitude / threshold) capped at 1.0.
- **No SQL materialized view integration.** Engine accepts DataFrames for testability; SQL integration in production pipeline.

### New additions not explicitly in the plan
- `LayerSignals` dataclass for clean 4-layer input packaging.
- Layer contribution percentages (`l0_contrib`, etc.) for explainability.
- Rank assignment in batch mode (1 = highest priority).
- Anomaly without magnitude defaults to score 0.5.

### Bug fixes during development
- None required for this feature.


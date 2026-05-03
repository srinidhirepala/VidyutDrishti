# Feature 15 - Leakage Quantification

## Changes Log

### Implemented as specified in `features.md` section 15
- **Data model** (`evaluation/leakage.py`): `LeakageEstimate` dataclass with kWh lost, tariff rate, INR lost, and methodology; `to_db_row()` for DB serialization.
- **Quantifier** (`evaluation/leakage.py`): `LeakageQuantifier` class with:
  - `quantify`: Estimates leakage for single meter using peer deviation or z-score fallback
  - `quantify_batch`: Batch processing for all detections
  - Peer method: loss = peer_mean - actual (most reliable for theft)
  - Z-score method: capped at 3 std devs (avoids extreme outliers)
  - Default tariff: 7.50 INR/kWh; customizable per meter
  - Decimal for financial precision
- **CLI helper** (`quantify_leakage_csv`): CSV-to-CSV batch processing.
- **Module init** (`evaluation/__init__.py`): Updated exports.

### Deviations from plan
- **Simplified estimation methods.** Plan mentioned "peer deviation OR historical delta". Implementation adds z-score capping for robustness.
- **No consumer category tariffs.** All meters use same default rate; category-specific rates can be added via lookup layer.

### New additions not explicitly in the plan
- `basis` field documenting methodology (peer_deviation, z_score_extrapolation, etc.).
- 3 std cap on z-score method to avoid extreme estimates.
- Decimal for INR calculations (financial precision).

### Bug fixes during development
- Test expected uncapped z-score value; adjusted to use values within 3 std cap.


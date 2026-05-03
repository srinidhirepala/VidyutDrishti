# Feature 13 - Confidence Engine

## Test Review

**Test file:** `tests/test_confidence.py` (stdlib `unittest`; requires `pandas`).

**Run command:**
```powershell
python C:\Hackathon\VidyutDrishti\logs\13-confidence-engine\tests\test_confidence.py
```

**Result:** `Ran 13 tests in 0.011s - OK` (13 passed, 0 failed, 0 errors).

### Coverage Map

| Test class | Validates |
|------------|-----------|
| `TestLayerSignals` (2 tests) | Default signals construction; custom signals with values |
| `TestConfidenceEngine` (9 tests) | No anomalies zero confidence; single layer anomaly; all layers max confidence; weights sum to one; confidence range 0-1; anomaly without magnitude; contributions sum to one; no signals equal contributions |
| `TestConfidenceBatch` (2 tests) | Batch assigns ranks; results sorted by confidence descending |
| `TestConfidenceResult` (1 test) | Dataclass construction, to_db_row serialization |

### Observations

- Confidence engine aggregates 4-layer signals into unified 0-1 score for ranking.
- Weights: Layer 0 (10%), Layer 1 (30%), Layer 2 (30%), Layer 3 (30%).
- Layer 0 has lower weight because it's an aggregate signal (applies to all meters under DT).
- Individual layer scores normalized by their thresholds (L0: 3%, L1: 3 sigma, L2: 10%, L3: -0.5 score).
- Contributions show which layers drove the confidence (for explainability).
- Rank 1 = highest priority (highest confidence).

### Constraints Honoured

- Read-only posture: tests use synthetic data.
- No real PII: synthetic meter IDs only.


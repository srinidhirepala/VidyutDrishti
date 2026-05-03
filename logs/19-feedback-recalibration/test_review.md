# Feature 19 - Feedback Loop & Recalibration

## Test Review

**Test file:** `tests/test_feedback.py` (stdlib `unittest`).

**Run command:**
```powershell
python C:\Hackathon\VidyutDrishti\logs\19-feedback-recalibration\tests\test_feedback.py
```

**Result:** `Ran 13 tests in 0.001s - OK` (13 passed, 0 failed, 0 errors).

### Coverage Map

| Test class | Validates |
|------------|-----------|
| `TestFeedbackRecord` (1 test) | Dataclass construction, to_db_row serialization |
| `TestAccuracyMetrics` (4 tests) | Perfect precision, perfect recall, F1 score, zero division handling |
| `TestFeedbackProcessor` (8 tests) | Submit feedback, compute metrics, suggest threshold raise (low precision), suggest threshold lower (low recall), no change when targets met, feedback summary, filter by meter, metrics since date |

### Observations

- FeedbackProcessor tracks inspection outcomes to measure detection accuracy.
- Metrics: Precision (TP / (TP + FP)), Recall (TP / (TP + FN)), F1 (harmonic mean).
- Threshold adjustment logic:
  - If precision < target: raise threshold (fewer predictions, more precise)
  - If recall < target: lower threshold (more predictions, fewer missed)
- Target defaults: precision 0.8, recall 0.7 (configurable).
- Date filtering for time-bounded analysis.
- Meter-specific feedback tracking for per-meter history.

### Constraints Honoured

- Read-only posture: tests use synthetic feedback data.
- No real PII: synthetic meter IDs only.

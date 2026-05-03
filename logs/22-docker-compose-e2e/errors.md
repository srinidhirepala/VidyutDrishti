# Feature 22 - Docker Compose + E2E Test

## Errors Log

### E22-001 - Import path mismatch
- **When:** Running initial E2E tests.
- **Symptom:** `ModuleNotFoundError: No module named 'simulator.generator'`
- **Root cause:** Simulator uses different module structure than assumed.
- **Resolution:** Updated imports to use `models` and `generate` modules.
- **Status:** Fixed.

### E22-002 - ZScoreAnalyzer signature mismatch
- **When:** Running test_detection_pipeline.
- **Symptom:** `TypeError: ZScoreAnalyzer.analyze_batch() missing 1 required positional argument: 'target_date'` and later `'topology'`.
- **Root cause:** Test used wrong parameter order.
- **Resolution:** Fixed call to use correct signature with topology DataFrame.
- **Status:** Fixed.

All 8 E2E tests passed after fixes.


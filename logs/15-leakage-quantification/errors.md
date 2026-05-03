# Feature 15 - Leakage Quantification

## Errors Log

### E15-001 - Z-score cap caused test failure
- **When:** Running `test_z_score_fallback_when_no_peers`.
- **Symptom:** Expected 50.0 kWh loss but got 30.0 (capped at 3 std).
- **Root cause:** Test used values where loss (50) exceeded 3 std (30), triggering the safety cap.
- **Resolution:** Adjusted test values (actual=70, mean=100, std=15) so loss (30) equals exactly 3 std.
- **Status:** Fixed; test passes.

No other errors encountered during Feature 15 development. All 10 tests passed after fix.


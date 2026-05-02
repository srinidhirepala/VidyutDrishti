# Feature 08 - Daily Feature Engineering

## Errors Log

### E08-001 - Invalid date in test (day 35 of January)
- **When:** Running `test_temp_ratio_computed`.
- **Symptom:** `ValueError: day is out of range for month` for `date(2024, 1, 35)`.
- **Root cause:** January has 31 days; day 35 is invalid.
- **Resolution:** Changed target date to `date(2024, 2, 4)` which is day 35 counting from Jan 1.
- **Status:** Fixed; test passes.

### E08-002 - Date filtering excluded all but midnight rows
- **When:** Running `test_total_kwh_sum_correct`.
- **Symptom:** Expected 96.0 kWh (96 slots × 1.0 kWh) but got 1.0 (only one row matched).
- **Root cause:** Filter `df_history[df_history["ts"] <= target_ts]` with `target_ts = pd.Timestamp(date(2024, 1, 1))` only keeps timestamps <= 2024-01-01 00:00:00, excluding all daytime slots.
- **Resolution:** Changed filter to `df_history["ts"] < target_end` where `target_end = target_ts + pd.Timedelta(days=1)` to include the full target day.
- **Status:** Fixed; test passes.

### E08-003 - Health score formula was multiplicative
- **When:** Running `test_perfect_data_high_score`.
- **Symptom:** Expected health score >= 0.8 for perfect data but got 0.4.
- **Root cause:** Formula was `max(0, 1 - missing_penalty) * (voltage_ok + pf_ok)` which with perfect data gives `1 * (0.2 + 0.2) = 0.4`.
- **Resolution:** Changed to additive weighted sum: `completeness_score + voltage_score + pf_score` where each component is already weighted (0.6, 0.2, 0.2), giving 1.0 for perfect data.
- **Status:** Fixed; all tests pass.

All 18 tests passed after fixes.

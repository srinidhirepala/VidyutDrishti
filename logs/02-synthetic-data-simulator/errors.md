# Feature 02 - Synthetic Data Simulator

## Errors Log

### E02-001 - `holidays` package not installed on host
- **When:** Designing `resolve_holidays()` and the prototype test harness.
- **Symptom:** `ModuleNotFoundError: No module named 'holidays'` on the host Python 3.10 environment.
- **Root cause:** The package is listed in `backend/pyproject.toml` (and will be present in the Docker image) but is not installed on the developer machine used for running tests today.
- **Resolution:** Made holiday resolution optional at runtime:
  1. If the config provides an explicit `holiday_dates: [...]` list, use that verbatim (this is how the prototype test supplies holidays).
  2. Otherwise try `import holidays` and query `country_holidays("IN", subdiv="KA", years=...)`.
  3. If the import fails, return an empty set so the generator still runs (holiday dips become no-ops).
- **Status:** Resolved. Tests pass an explicit list and do not depend on the package; production runs inside the Docker image where the package is present.

### E02-002 - Diurnal normalisation drifted daily totals
- **When:** Initial load-model design (before the first test run).
- **Symptom:** Per-day kWh totals after multiplying the diurnal profile did not equal the sampled daily total; they were off by the ratio of `hourly_mean` to `slot_mean`.
- **Root cause:** The diurnal profile was normalised to average 1.0 at hourly resolution but then repeated across `slots_per_hour` slots, so the slot-level mean drifted above 1.0 and inflated the total.
- **Resolution:** Added a second normalisation step after `np.repeat` so the final slot profile averages exactly 1.0, and computed per-slot energy via `(daily_total / slots) * profile`, which preserves the daily total by construction. The `TestShapeAndTopology` / `TestValueRanges` suites implicitly validate this because `TestDTEnergyBalance` would otherwise fail.
- **Status:** Resolved before any test-run evidence was captured (caught during code review before first execution).

### E02-003 - PowerShell mangled the inline `python -c` smoke test
- **When:** Validating the production YAML loads via a one-liner.
- **Symptom:** PowerShell reformatted / wrapped the long `-c` argument across multiple lines and still executed it, but the console transcript showed confusing line wrapping. Exit code and final output were correct (`OK: 2 DTs x 30 meters x 180 days; theft: 3 decoys: 2`).
- **Root cause:** PowerShell line-wrapping of long single-line commands; cosmetic only.
- **Resolution:** Kept the command; documented the cosmetic effect so it is not misread as an error.
- **Status:** Resolved / documented.

No functional bugs surfaced during the test run; all 16 cases passed on the first execution.

### E02-004 - Kluster review flagged 3 MEDIUM (P4) items on first pass
- **When:** Automated kluster review immediately after the first green test run.
- **Symptom:** Three MEDIUM severity findings:
  1. `_inject_missing` uses per-meter Python loops over Poisson samples (O(M*N) overhead).
  2. DT `kwh_in` computation performs a full merge + group-by across the long meter-reading frame.
  3. `build_dataset` had grown into a 95-line orchestrator mixing concerns.
- **Root cause:** Initial implementation prioritised readability over performance; items 2 and 3 were structurally entangled.
- **Resolution:**
  1. Kept as-is (see `changes.md` - Refactor after kluster review). Acceptable at prototype scale.
  2. Replaced with per-DT running-sum accumulation inside `_build_meter_readings`; `_build_dt_readings` now operates on NumPy arrays directly. No long-frame merge required.
  3. Extracted `_build_meter_readings` and `_build_dt_readings` helpers; `build_dataset` is now ~15 lines of pure orchestration.
- **Validation:** All 16 tests re-ran after the refactor and passed. Runtime decreased from 1.08s to 0.50s.
- **Status:** Resolved (items 2 and 3) / accepted (item 1, documented).

### E02-005 - Kluster flagged HIGH: hardcoded default DB credentials
- **When:** Second kluster review pass after the performance refactor.
- **Symptom:** `backend/app/config.py` and `docker-compose.yml` both carried a default value for `DB_PASSWORD` (`"vidyutdrishti"`), even though they were overridable via environment. Marked HIGH severity because "insecure defaults frequently leak into production via accidental promotion".
- **Root cause:** Original scaffolding prioritised a zero-friction first boot over secret hygiene.
- **Resolution:**
  - `backend/app/config.py`: `db_name`, `db_user`, `db_password` now use `Field(...)` with no default; the settings object refuses to instantiate unless the values come from the environment (via `infra/.env`).
  - `docker-compose.yml`: switched to `${VAR:?message}` syntax so `docker compose up` fails loudly if any of `DB_NAME` / `DB_USER` / `DB_PASSWORD` is unset; also switched the `env_file` reference from `.env.sample` to `.env` so the sample is strictly a template.
  - `infra/.env.sample`: replaced the placeholder `vidyutdrishti` password with `change-me-before-first-use` and added an explicit warning comment directing the user to rotate it.
- **Validation:** Feature 01 scaffolding tests and Feature 02 simulator tests both re-ran clean after the change (structure and behaviour unaffected).
- **Status:** Resolved.


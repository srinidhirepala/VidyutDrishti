# Feature 02 - Synthetic Data Simulator

## Changes Log

### Implemented as specified in `features.md` section 02
- CLI entrypoint `python -m simulator.generate --config ... --out ...` in `simulator/generate.py`.
- 2 DTs, 60 meters, 180 days at 15-minute cadence configured in `simulator/config.yaml` (production default).
- Consumer mix 70% domestic / 25% commercial / 5% industrial via `category_mix`.
- Load model composed of: base daily total (Gaussian), diurnal profile (24-hour weights normalised to mean 1.0), seasonal multipliers (summer Mar-Jun, monsoon Jun-Sep), weekend and holiday multipliers, multiplicative Gaussian noise.
- Voltage sampled from `N(230, 5)` clipped to `[210, 250]`.
- PF drawn uniformly per category (domestic 0.90-0.98, commercial 0.85-0.95, industrial 0.80-0.92).
- DT-level `kwh_in` = sum of meter kWh × `(1 + technical_loss)` with technical loss drawn in `[2%, 6%]` per DT and jittered per slot.
- Missing-reading injector with three gap regimes (short, medium, long).
- Three theft scenarios (hook bypass on DT1-M12, gradual tampering on DT2-M07, meter stop on DT1-M23) + two decoys (vacancy on DT2-M15, equipment fault on DT1-M01).
- Ground-truth table `injected_events.csv` written alongside the reading tables, kept separate from any detection code path.

### Deviations from plan
- **`holidays` package made optional.** The plan said "Python 3.11, NumPy, Pandas, PyYAML, holidays" as the stack. The host used for testing does not have the `holidays` package, so `resolve_holidays()` falls back to an explicit `holiday_dates` list from the config if the package is absent. Production config (`simulator/config.yaml`) sets `holiday_dates: null`, which causes the runtime Docker image (where `holidays` is installed) to query the IN/KA subdivision as originally planned.
- **Validation kept hand-rolled.** The plan mentioned "property-based sanity checks (row counts, value ranges, monotonic timestamps)". Rather than pulling in `hypothesis`, the prototype validates the same invariants via targeted `unittest` cases in `logs/02-.../tests/test_simulator.py` on a small 2x4x7 dataset. This keeps the dependency surface minimal.
- **No separate `reports/` artefact.** The plan did not require one for this feature but mentions the idea elsewhere; omitted here.
- **Module split.** Rather than a single `simulator.generate` module the code is split into `models.py` (`SimConfig`, `TheftScenario`, `Decoy`), `load_model.py` (diurnal / seasonal helpers), `scenarios.py` (theft + decoy injection), `dataset.py` (orchestrator), and `generate.py` (CLI). Improves testability; imports from tests use `dataset.build_dataset` directly.

### New additions not explicitly in the plan
- `SimConfig.from_dict` + `validate()` method - lets the test suite build configs programmatically without a YAML file.
- `noise_std_fraction` as an explicit config knob (the plan specified "Gaussian noise" but left the magnitude implicit).
- `SimConfig.slots_per_day` convenience property to avoid scattering `(24*60)//slot_minutes` across the codebase.

### Refactor after kluster review
Kluster flagged three MEDIUM (P4) items on the first pass (see `errors.md` E02-004). Two of them were addressed immediately; one was explicitly accepted at prototype scale.

- **Addressed: `build_dataset` was a semi-god function (lines mixing topology, simulation, and DT aggregation).** Split into three helpers: `_build_topology`, `_build_meter_readings`, `_build_dt_readings`. The public `build_dataset` is now a thin orchestrator.
- **Addressed: redundant merge+groupby to compute DT `kwh_in`.** Running per-DT sums are now accumulated inside `_build_meter_readings` as a `dict[str, np.ndarray]`, and `_build_dt_readings` consumes that directly. No long-frame merge is required. Side-effect: test suite runtime fell from 1.08s to 0.50s on the same config.
- **Accepted as-is: `_inject_missing` Poisson loop.** At the prototype scale (60 meters x 17,280 slots), the gap injection runs in microseconds per meter. Vectorising across meters would complicate the random-state discipline (each meter must produce a reproducible mask under the same seed). Revisit only if the simulator is ever scaled to thousands of meters.


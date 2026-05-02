"""Scenario injection: theft and legitimate decoys.

Each function takes a per-meter 1-D kWh array indexed by slot and
returns a modified copy. The simulator records the applied event in
``injected_events`` which later serves as ground truth.
"""

from __future__ import annotations

import numpy as np

from .models import Decoy, SimConfig, TheftScenario


def _slot_bounds(cfg: SimConfig, start_day: int, end_day: int) -> tuple[int, int]:
    slots = cfg.slots_per_day
    return start_day * slots, min(end_day, cfg.days) * slots


def apply_hook_bypass(series: np.ndarray, cfg: SimConfig, s: TheftScenario) -> np.ndarray:
    """Sudden drop to near-zero kWh."""
    out = series.copy()
    lo, hi = _slot_bounds(cfg, s.start_day, s.end_day)
    out[lo:hi] *= (1.0 - s.severity)
    return out


def apply_gradual_tampering(series: np.ndarray, cfg: SimConfig, s: TheftScenario) -> np.ndarray:
    """Linear ramp from 0 to severity over the window."""
    out = series.copy()
    lo, hi = _slot_bounds(cfg, s.start_day, s.end_day)
    n = hi - lo
    if n <= 0:
        return out
    ramp = np.linspace(0.0, s.severity, n)
    out[lo:hi] *= (1.0 - ramp)
    return out


def apply_meter_stop(series: np.ndarray, cfg: SimConfig, s: TheftScenario) -> np.ndarray:
    """Flat-zero readings across the window."""
    out = series.copy()
    lo, hi = _slot_bounds(cfg, s.start_day, s.end_day)
    out[lo:hi] = 0.0
    return out


def apply_theft(series: np.ndarray, cfg: SimConfig, s: TheftScenario) -> np.ndarray:
    kind_map = {
        "hook_bypass": apply_hook_bypass,
        "gradual_tampering": apply_gradual_tampering,
        "meter_stop": apply_meter_stop,
    }
    if s.kind not in kind_map:
        raise ValueError(f"Unknown theft kind: {s.kind}")
    return kind_map[s.kind](series, cfg, s)


def apply_decoy(series: np.ndarray, cfg: SimConfig, d: Decoy) -> np.ndarray:
    """Legitimate-but-suspicious patterns used to test specificity."""
    out = series.copy()
    lo, hi = _slot_bounds(cfg, d.start_day, d.end_day)
    if d.kind == "vacancy":
        out[lo:hi] *= (1.0 - d.severity)
    elif d.kind == "equipment_fault":
        out[lo:hi] = 0.0
    else:
        raise ValueError(f"Unknown decoy kind: {d.kind}")
    return out

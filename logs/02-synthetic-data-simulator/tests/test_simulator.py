"""Prototype-grade tests for Feature 02 - Synthetic Data Simulator.

Run with:
    python -m unittest logs/02-synthetic-data-simulator/tests/test_simulator.py -v

Uses a small 2-DT x 4-meter x 7-day config so the whole suite finishes
in a couple of seconds even on a modest laptop. The production config
lives at simulator/config.yaml.
"""

from __future__ import annotations

import hashlib
import sys
import unittest
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from simulator.dataset import build_dataset  # noqa: E402
from simulator.models import SimConfig  # noqa: E402


def _small_config() -> SimConfig:
    """Compact config that still exercises every code path."""
    raw = {
        "seed": 123,
        "dt_count": 2,
        "meters_per_dt": 4,
        "category_mix": {"domestic": 0.5, "commercial": 0.25, "industrial": 0.25},
        "start_date": "2024-01-01",
        "days": 7,
        "slot_minutes": 15,
        "daily_kwh_mean": {"domestic": 12.0, "commercial": 60.0, "industrial": 200.0},
        "daily_kwh_std": {"domestic": 2.0, "commercial": 10.0, "industrial": 30.0},
        "diurnal_weights": {
            "domestic":   [0.4]*6 + [1.0]*12 + [1.5]*6,
            "commercial": [0.3]*6 + [1.5]*12 + [0.6]*6,
            "industrial": [0.9]*24,
        },
        "summer_months": [3, 4, 5, 6],
        "summer_multiplier": 1.25,
        "monsoon_months": [6, 7, 8, 9],
        "monsoon_multiplier": 0.92,
        "weekend_multiplier": {"domestic": 1.10, "commercial": 0.70, "industrial": 0.95},
        "holiday_multiplier": 0.75,
        "holiday_dates": ["2024-01-01"],   # explicit so no dep on `holidays` pkg
        "voltage_mean": 230.0,
        "voltage_std": 5.0,
        "voltage_min": 210.0,
        "voltage_max": 250.0,
        "pf_range": {
            "domestic": [0.90, 0.98],
            "commercial": [0.85, 0.95],
            "industrial": [0.80, 0.92],
        },
        "dt_technical_loss_min": 0.02,
        "dt_technical_loss_max": 0.06,
        "noise_std_fraction": 0.05,
        "missing_short_prob": 0.005,
        "missing_medium_prob": 0.0,    # suppress stochastic gap tests at this scale
        "missing_long_prob": 0.0,
        "theft_scenarios": [
            {"meter_id": "DT1-M02", "kind": "hook_bypass",
             "start_day": 3, "end_day": 7, "severity": 0.95},
            {"meter_id": "DT2-M03", "kind": "gradual_tampering",
             "start_day": 2, "end_day": 6, "severity": 0.6},
            {"meter_id": "DT1-M04", "kind": "meter_stop",
             "start_day": 4, "end_day": 7, "severity": 1.0},
        ],
        "decoys": [
            {"meter_id": "DT2-M01", "kind": "vacancy",
             "start_day": 2, "end_day": 7, "severity": 0.9},
        ],
    }
    return SimConfig.from_dict(raw)


class TestShapeAndTopology(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.cfg = _small_config()
        cls.out = build_dataset(cls.cfg)

    def test_consumer_row_count(self) -> None:
        self.assertEqual(len(self.out["consumers"]),
                         self.cfg.dt_count * self.cfg.meters_per_dt)

    def test_dt_row_count(self) -> None:
        self.assertEqual(len(self.out["dts"]), self.cfg.dt_count)

    def test_meter_reading_row_count(self) -> None:
        expected = self.cfg.dt_count * self.cfg.meters_per_dt \
                   * self.cfg.days * self.cfg.slots_per_day
        self.assertEqual(len(self.out["meter_readings"]), expected)

    def test_dt_reading_row_count(self) -> None:
        expected = self.cfg.dt_count * self.cfg.days * self.cfg.slots_per_day
        self.assertEqual(len(self.out["dt_readings"]), expected)

    def test_timestamps_monotonic_per_meter(self) -> None:
        mr = self.out["meter_readings"]
        for mid, grp in mr.groupby("meter_id"):
            ts = pd.Series(grp["ts"].tolist())
            self.assertTrue((ts.iloc[1:].values > ts.iloc[:-1].values).all(),
                            f"timestamps not strictly increasing for {mid}")

    def test_required_columns_present(self) -> None:
        self.assertEqual(
            set(self.out["meter_readings"].columns),
            {"meter_id", "ts", "kwh", "voltage", "power_factor", "missing"},
        )
        self.assertEqual(set(self.out["dt_readings"].columns), {"dt_id", "ts", "kwh_in"})


class TestValueRanges(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.cfg = _small_config()
        cls.mr = build_dataset(cls.cfg)["meter_readings"]

    def test_kwh_non_negative_or_missing(self) -> None:
        non_missing = self.mr[~self.mr["missing"]]
        self.assertTrue((non_missing["kwh"] >= 0.0).all())

    def test_voltage_in_bounds(self) -> None:
        non_missing = self.mr[~self.mr["missing"]]
        self.assertTrue(non_missing["voltage"].between(
            self.cfg.voltage_min, self.cfg.voltage_max).all())

    def test_power_factor_in_bounds(self) -> None:
        non_missing = self.mr[~self.mr["missing"]]
        self.assertTrue(non_missing["power_factor"].between(0.0, 1.0).all())

    def test_missing_readings_are_nan(self) -> None:
        missing = self.mr[self.mr["missing"]]
        if len(missing):
            self.assertTrue(missing["kwh"].isna().all())
            self.assertTrue(missing["voltage"].isna().all())


class TestDeterminism(unittest.TestCase):

    def test_same_seed_same_output(self) -> None:
        cfg = _small_config()
        a = build_dataset(cfg)["meter_readings"]
        b = build_dataset(cfg)["meter_readings"]
        ah = hashlib.sha256(pd.util.hash_pandas_object(a, index=True).values.tobytes()).hexdigest()
        bh = hashlib.sha256(pd.util.hash_pandas_object(b, index=True).values.tobytes()).hexdigest()
        self.assertEqual(ah, bh)

    def test_different_seed_different_output(self) -> None:
        cfg_a = _small_config()
        cfg_b = _small_config()
        cfg_b.seed = 999
        a = build_dataset(cfg_a)["meter_readings"]["kwh"].to_numpy()
        b = build_dataset(cfg_b)["meter_readings"]["kwh"].to_numpy()
        # Not element-equal; use rough inequality.
        self.assertFalse(np.array_equal(np.nan_to_num(a), np.nan_to_num(b)))


class TestInjectedScenarios(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.cfg = _small_config()
        cls.out = build_dataset(cls.cfg)

    def test_injected_events_recorded(self) -> None:
        ev = self.out["injected_events"]
        # 3 theft + 1 decoy
        self.assertEqual(len(ev), 4)
        self.assertEqual(set(ev["event_type"]),
                         {"theft", "decoy"})

    def test_hook_bypass_drops_load(self) -> None:
        mr = self.out["meter_readings"]
        series = mr[mr["meter_id"] == "DT1-M02"].set_index("ts")["kwh"]
        before = series.iloc[: 3 * self.cfg.slots_per_day].dropna().mean()
        after = series.iloc[3 * self.cfg.slots_per_day :].dropna().mean()
        self.assertGreater(before, after * 3,
                           "Hook bypass should leave post-event mean well below pre-event mean")

    def test_meter_stop_is_zero(self) -> None:
        mr = self.out["meter_readings"]
        series = mr[mr["meter_id"] == "DT1-M04"].set_index("ts")["kwh"]
        post = series.iloc[4 * self.cfg.slots_per_day :].dropna()
        self.assertTrue((post == 0.0).all(), "meter_stop should emit zero kWh post-event")


class TestDTEnergyBalance(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.cfg = _small_config()
        cls.out = build_dataset(cls.cfg)

    def test_dt_kwh_in_at_or_above_meter_sum(self) -> None:
        mr = self.out["meter_readings"].merge(
            self.out["consumers"][["meter_id", "dt_id"]], on="meter_id", how="left"
        )
        mr["kwh_filled"] = mr["kwh"].fillna(0.0)
        meter_sum = mr.groupby(["dt_id", "ts"])["kwh_filled"].sum().reset_index()
        merged = meter_sum.merge(self.out["dt_readings"], on=["dt_id", "ts"], how="inner")
        # kwh_in should never be less than meter sum (technical loss is non-negative)
        self.assertTrue((merged["kwh_in"] >= merged["kwh_filled"] - 1e-9).all())


if __name__ == "__main__":
    unittest.main()

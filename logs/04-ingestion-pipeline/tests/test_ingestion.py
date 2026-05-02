"""Prototype-grade tests for Feature 04 - Ingestion Pipeline & Data Quality.

Run with:
    python -m unittest logs/04-ingestion-pipeline/tests/test_ingestion.py -v

Uses the Feature 02 simulator to produce a tiny in-memory dataset, then
exercises the quality gate, imputer, and loader (with session=None so
no live DB is required).
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

from app.ingestion.imputer import (  # noqa: E402
    SHORT_GAP_MAX_MINUTES,
    _classify_gaps,
    impute_meter_readings,
    impute_meter_series,
)
from app.ingestion.loader import (  # noqa: E402
    insert_rows,
    load_consumers,
    load_dt_readings,
    load_meter_readings,
    record_rejects,
)
from app.ingestion.pipeline import run_csv_ingest  # noqa: E402
from app.ingestion.quality import apply_quality_gate, duplicate_report  # noqa: E402
from app.ingestion.readers import CSVReader  # noqa: E402
from app.ingestion.schema import (  # noqa: E402
    CONSUMER_SCHEMA,
    DT_READING_SCHEMA,
    METER_READING_SCHEMA,
)


# ---------------------------------------------------------------------------
# Quality gate
# ---------------------------------------------------------------------------

class TestQualityGate(unittest.TestCase):

    def _valid_meter_frame(self, n: int = 10) -> pd.DataFrame:
        ts = pd.date_range("2024-01-01", periods=n, freq="15min")
        return pd.DataFrame({
            "meter_id": ["DT1-M01"] * n,
            "ts": ts,
            "kwh": np.full(n, 0.5),
            "voltage": np.full(n, 230.0),
            "power_factor": np.full(n, 0.9),
        })

    def test_all_clean_passes(self) -> None:
        df = self._valid_meter_frame()
        res = apply_quality_gate(df, METER_READING_SCHEMA)
        self.assertEqual(len(res.clean), len(df))
        self.assertEqual(len(res.rejected), 0)
        self.assertEqual(res.reject_rate, 0.0)

    def test_missing_required_column_rejects_whole_batch(self) -> None:
        df = self._valid_meter_frame().drop(columns=["voltage"])
        res = apply_quality_gate(df, METER_READING_SCHEMA)
        self.assertEqual(len(res.clean), 0)
        self.assertEqual(len(res.rejected), len(df))
        self.assertTrue((res.rejected["reason"]
                         .str.startswith("missing_columns")).all())

    def test_negative_kwh_rejected(self) -> None:
        df = self._valid_meter_frame()
        df.loc[0, "kwh"] = -1.0
        res = apply_quality_gate(df, METER_READING_SCHEMA)
        self.assertEqual(len(res.rejected), 1)
        self.assertEqual(res.rejected["reason"].iloc[0], "below_min_kwh")

    def test_voltage_above_max_rejected(self) -> None:
        df = self._valid_meter_frame()
        df.loc[0, "voltage"] = 999.0
        res = apply_quality_gate(df, METER_READING_SCHEMA)
        self.assertEqual(len(res.rejected), 1)
        self.assertEqual(res.rejected["reason"].iloc[0], "above_max_voltage")

    def test_null_meter_id_rejected(self) -> None:
        df = self._valid_meter_frame()
        df.loc[0, "meter_id"] = None
        res = apply_quality_gate(df, METER_READING_SCHEMA)
        self.assertEqual(len(res.rejected), 1)
        self.assertEqual(res.rejected["reason"].iloc[0], "null_meter_id")

    def test_null_kwh_allowed_because_allow_null(self) -> None:
        df = self._valid_meter_frame()
        df.loc[0, "kwh"] = np.nan
        res = apply_quality_gate(df, METER_READING_SCHEMA)
        self.assertEqual(len(res.rejected), 0)

    def test_duplicate_report(self) -> None:
        df = self._valid_meter_frame(4)
        dup = df.iloc[[0]].copy()
        combined = pd.concat([df, dup], ignore_index=True)
        dups = duplicate_report(combined, pk=["meter_id", "ts"])
        self.assertEqual(len(dups), 2)


# ---------------------------------------------------------------------------
# Imputer
# ---------------------------------------------------------------------------

class TestImputer(unittest.TestCase):

    def _series(self, vals: list[float | None]) -> pd.DataFrame:
        n = len(vals)
        ts = pd.date_range("2024-01-01", periods=n, freq="15min")
        return pd.DataFrame({
            "meter_id": ["M1"] * n,
            "ts": ts,
            "kwh": [np.nan if v is None else float(v) for v in vals],
        })

    def test_classify_gaps_buckets_correctly(self) -> None:
        mask = np.array([
            False, True, False,          # 1-slot short gap (15 min)
            True, True, True,            # 3-slot short gap (45 min)
            False,
            *([True] * 8),               # 8 slots = 120 min -> medium (2h)
            False,
            *([True] * 20),             # 20 slots = 300 min -> medium (5h)
            False,
            *([True] * 24),             # 24 slots = 360 min -> medium (equals 6h)
            False,
            *([True] * 30),             # 30 slots = 450 min -> long (>6h)
        ], dtype=bool)
        s, m, long_ = _classify_gaps(mask, slot_minutes=15)
        self.assertEqual(s.sum(), 4)         # 1 + 3
        self.assertEqual(m.sum(), 8 + 20 + 24)  # 52 slots, all <= 6h
        self.assertEqual(long_.sum(), 30)      # > 6h
        # Every gap slot assigned to exactly one bucket
        self.assertTrue(np.array_equal(mask, s | m | long_))
        self.assertEqual((s & m).sum(), 0)
        self.assertEqual((m & long_).sum(), 0)

    def test_short_gap_linear_interpolation(self) -> None:
        df = self._series([1.0, None, 3.0])    # middle slot missing (15 min)
        res = impute_meter_series(df)
        self.assertAlmostEqual(res.frame["kwh"].iloc[1], 2.0)
        self.assertTrue(bool(res.frame["imputed"].iloc[1]))
        self.assertEqual(res.n_short_imputed, 1)

    def test_medium_gap_filled_with_diurnal_mean(self) -> None:
        # 96 slots of 1 kWh (so diurnal mean is 1.0 everywhere) + 8 NaNs = 2h gap
        base = [1.0] * 96
        gap = [None] * 8
        tail = [1.0] * 96
        df = self._series(base + gap + tail)
        res = impute_meter_series(df)
        filled = res.frame["kwh"].iloc[96:104].to_numpy()
        self.assertTrue(np.allclose(filled, 1.0))
        self.assertEqual(res.n_medium_imputed, 8)

    def test_long_gap_left_nan(self) -> None:
        base = [1.0] * 96
        gap = [None] * 50     # 12.5 h > 6h
        df = self._series(base + gap)
        res = impute_meter_series(df)
        tail = res.frame["kwh"].iloc[-50:]
        self.assertTrue(tail.isna().all())
        self.assertEqual(res.n_long_left_nan, 50)
        self.assertEqual(res.n_medium_imputed, 0)
        self.assertEqual(res.n_short_imputed, 0)

    def test_impute_meter_readings_across_multiple_meters(self) -> None:
        n = 20
        ts = pd.date_range("2024-01-01", periods=n, freq="15min")
        frames: list[pd.DataFrame] = []
        for mid in ["A", "B"]:
            vals = [1.0] * n
            vals[5] = None
            frames.append(pd.DataFrame({"meter_id": mid, "ts": ts, "kwh": vals}))
        df = pd.concat(frames, ignore_index=True)
        res = impute_meter_readings(df)
        self.assertEqual(res.n_short_imputed, 2)
        self.assertTrue(res.frame["kwh"].notna().all())


# ---------------------------------------------------------------------------
# Loader (session=None)
# ---------------------------------------------------------------------------

class TestLoader(unittest.TestCase):

    def test_insert_meter_rows_without_db(self) -> None:
        ts = pd.Timestamp("2024-01-01 00:00:00")
        df = pd.DataFrame([
            {"meter_id": "M1", "ts": ts, "kwh": 0.5, "voltage": 230.0,
             "power_factor": 0.92, "source": "ami", "imputed": False},
            {"meter_id": "M1", "ts": ts + timedelta(minutes=15), "kwh": 0.7,
             "voltage": 231.0, "power_factor": 0.93, "source": "ami", "imputed": True},
        ])
        stats = load_meter_readings(None, df)
        self.assertEqual(stats.attempted, 2)
        self.assertEqual(stats.written, 2)
        self.assertEqual(stats.table, "meter_reading")

    def test_insert_rows_noop_when_empty(self) -> None:
        self.assertEqual(insert_rows(None, "meter_reading", []), 0)

    def test_record_rejects_emits_reason(self) -> None:
        df = pd.DataFrame([{"meter_id": "X", "ts": pd.Timestamp("2024-01-01"),
                            "kwh": -1.0, "voltage": 230, "power_factor": 0.9,
                            "reason": "below_min_kwh"}])
        n = record_rejects(None, df, source="test")
        self.assertEqual(n, 1)

    def test_consumer_loader_derives_feeder_if_missing(self) -> None:
        df = pd.DataFrame([
            {"meter_id": "DT1-M01", "dt_id": "DT1", "tariff_category": "domestic"},
        ])
        stats = load_consumers(None, df)
        self.assertEqual(stats.written, 1)


# ---------------------------------------------------------------------------
# End-to-end pipeline over real simulator output (CSV round trip)
# ---------------------------------------------------------------------------

class TestPipelineEndToEnd(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        from simulator.dataset import build_dataset
        from simulator.models import SimConfig

        raw = {
            "seed": 7, "dt_count": 1, "meters_per_dt": 2,
            "category_mix": {"domestic": 1.0},
            "start_date": "2024-01-01", "days": 3, "slot_minutes": 15,
            "daily_kwh_mean": {"domestic": 12.0},
            "daily_kwh_std": {"domestic": 2.0},
            "diurnal_weights": {"domestic": [1.0] * 24},
            "summer_months": [], "summer_multiplier": 1.0,
            "monsoon_months": [], "monsoon_multiplier": 1.0,
            "weekend_multiplier": {"domestic": 1.0},
            "holiday_multiplier": 1.0, "holiday_dates": [],
            "voltage_mean": 230.0, "voltage_std": 5.0,
            "voltage_min": 210.0, "voltage_max": 250.0,
            "pf_range": {"domestic": [0.9, 0.98]},
            "dt_technical_loss_min": 0.02, "dt_technical_loss_max": 0.04,
            "noise_std_fraction": 0.05,
            "missing_short_prob": 0.0,
            "missing_medium_prob": 0.0,
            "missing_long_prob": 0.0,
            "theft_scenarios": [],
            "decoys": [],
        }
        cls.cfg = SimConfig.from_dict(raw)
        cls.data = build_dataset(cls.cfg)

    def test_pipeline_roundtrip_with_dry_run(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, df in self.data.items():
                df.to_csv(root / f"{name}.csv", index=False)

            report = run_csv_ingest(root, session=None)

            # All meter chunks should have loaded (dry run counts are truthful)
            total_loaded = sum(s.written for s in report.meter)
            expected = self.cfg.dt_count * self.cfg.meters_per_dt \
                       * self.cfg.days * self.cfg.slots_per_day
            self.assertEqual(total_loaded, expected)
            self.assertGreater(len(report.dt), 0)
            self.assertEqual(report.rejected_rows, 0)

    def test_csv_reader_streams_in_chunks(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.data["meter_readings"].to_csv(root / "meter_readings.csv", index=False)
            reader = CSVReader(root, batch_rows=500)
            chunks = list(reader.read_meter_readings())
            self.assertGreater(len(chunks), 1)
            self.assertEqual(sum(len(c) for c in chunks), len(self.data["meter_readings"]))


if __name__ == "__main__":
    unittest.main()

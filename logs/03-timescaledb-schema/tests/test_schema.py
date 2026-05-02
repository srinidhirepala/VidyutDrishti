"""Prototype-grade tests for Feature 03 - TimescaleDB schema & migrations.

Strategy: no live Postgres is available on the test host, so this suite
verifies (a) the SQLAlchemy metadata is self-consistent, (b) the
migration script declares every ORM table plus the required TimescaleDB
calls, and (c) the seed YAMLs parse and cover the expected shapes.

Run with:
    python -m unittest logs/03-timescaledb-schema/tests/test_schema.py -v
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "backend"))

from app.db.base import Base  # noqa: E402
from app.db import models  # noqa: F401, E402 - register tables on metadata


EXPECTED_TABLES = {
    # Dimensions
    "feeder", "dt", "consumer", "tariff_slab", "holiday",
    # Hypertables
    "meter_reading", "dt_reading",
    # Analytics
    "forecast", "zone_risk", "feature_daily", "flag", "confidence",
    "inspection", "audit_log", "ingest_errors", "injected_events", "job_run",
}


class TestORMMetadata(unittest.TestCase):

    def test_all_expected_tables_registered(self) -> None:
        registered = set(Base.metadata.tables.keys())
        missing = EXPECTED_TABLES - registered
        self.assertEqual(missing, set(), f"ORM is missing tables: {missing}")

    def test_meter_reading_has_composite_pk(self) -> None:
        t = Base.metadata.tables["meter_reading"]
        pk_cols = {c.name for c in t.primary_key.columns}
        self.assertEqual(pk_cols, {"meter_id", "ts"})

    def test_dt_reading_has_composite_pk(self) -> None:
        t = Base.metadata.tables["dt_reading"]
        pk_cols = {c.name for c in t.primary_key.columns}
        self.assertEqual(pk_cols, {"dt_id", "ts"})

    def test_feature_daily_has_composite_pk(self) -> None:
        t = Base.metadata.tables["feature_daily"]
        pk_cols = {c.name for c in t.primary_key.columns}
        self.assertEqual(pk_cols, {"meter_id", "date"})

    def test_foreign_keys_declared(self) -> None:
        consumer = Base.metadata.tables["consumer"]
        fks = {fk.target_fullname for fk in consumer.foreign_keys}
        self.assertIn("dt.dt_id", fks)
        self.assertIn("feeder.feeder_id", fks)


class TestInitialMigration(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        path = REPO / "db" / "migrations" / "versions" / "0001_initial.py"
        cls.src = path.read_text(encoding="utf-8")

    def test_revision_identifiers(self) -> None:
        self.assertRegex(self.src, r'revision\s*=\s*"0001_initial"')
        self.assertRegex(self.src, r'down_revision\s*=\s*None')

    def test_every_orm_table_created(self) -> None:
        missing = [t for t in EXPECTED_TABLES if f'create_table(\n        "{t}"' not in self.src]
        self.assertEqual(missing, [], f"Migration does not create tables: {missing}")

    def test_hypertables_declared(self) -> None:
        self.assertIn("create_hypertable('meter_reading', 'ts'", self.src)
        self.assertIn("create_hypertable('dt_reading', 'ts'", self.src)

    def test_continuous_aggregates_declared(self) -> None:
        for mv in ("meter_hourly", "meter_daily", "dt_hourly"):
            self.assertIn(mv, self.src, f"Continuous aggregate {mv!r} missing")
        self.assertIn("timescaledb.continuous", self.src)

    def test_retention_and_compression_policies(self) -> None:
        self.assertIn("add_compression_policy", self.src)
        self.assertIn("add_retention_policy", self.src)

    def test_downgrade_defined(self) -> None:
        self.assertIn("def downgrade", self.src)
        self.assertIn("DROP TABLE IF EXISTS", self.src)


class TestSeedData(unittest.TestCase):

    def test_holidays_yaml_valid(self) -> None:
        raw = yaml.safe_load((REPO / "db" / "seed" / "holidays.yaml").read_text(encoding="utf-8"))
        self.assertIn("holidays", raw)
        self.assertEqual(raw["region"], "KA")
        for entry in raw["holidays"]:
            self.assertRegex(str(entry["date"]), r"^\d{4}-\d{2}-\d{2}$")
            self.assertTrue(entry["name"])
        # Must cover at least the national mandatory holidays.
        names = " ".join(e["name"] for e in raw["holidays"])
        for must in ("Republic Day", "Independence Day", "Gandhi Jayanti"):
            self.assertIn(must, names)

    def test_tariff_slab_yaml_valid(self) -> None:
        raw = yaml.safe_load((REPO / "db" / "seed" / "tariff_slab.yaml").read_text(encoding="utf-8"))
        self.assertIn("slabs", raw)
        for cat in ("domestic", "commercial", "industrial"):
            self.assertIn(cat, raw["slabs"])
            slabs = raw["slabs"][cat]
            self.assertGreater(len(slabs), 0)
            # Must end in an open upper bound.
            self.assertIsNone(slabs[-1]["slab_to"])
            # Slabs must be contiguous and ascending.
            prev_to = 0.0
            for s in slabs:
                self.assertEqual(s["slab_from"], prev_to,
                                 f"non-contiguous slab in {cat}: {s}")
                self.assertGreater(s["rate_inr"], 0)
                prev_to = s["slab_to"] if s["slab_to"] is not None else float("inf")


class TestAlembicConfig(unittest.TestCase):

    def test_alembic_ini_present(self) -> None:
        ini = REPO / "db" / "migrations" / "alembic.ini"
        self.assertTrue(ini.exists())
        src = ini.read_text(encoding="utf-8")
        self.assertIn("[alembic]", src)
        self.assertIn("script_location", src)

    def test_env_py_imports_base(self) -> None:
        env = (REPO / "db" / "migrations" / "env.py").read_text(encoding="utf-8")
        self.assertIn("from app.db.base import Base", env)
        self.assertIn("target_metadata = Base.metadata", env)


if __name__ == "__main__":
    unittest.main()

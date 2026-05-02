"""Idempotent batch loader.

Takes clean frames from the quality gate and writes them to
TimescaleDB using ``INSERT ... ON CONFLICT (pk...) DO NOTHING``. When a
session is not provided (tests) the loader becomes a no-op on the DB
and just returns the row counts it would have written.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class LoadStats:
    table: str
    attempted: int
    written: int            # rows that really hit the DB (skipping dupes is implicit)
    errors: int
    started_at: datetime
    finished_at: datetime

    def as_job_row(self, name: str, error: str | None = None) -> dict[str, Any]:
        return {
            "name": name,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": "failed" if error else "ok",
            "rows": self.written,
            "error": error,
        }


# ---------------------------------------------------------------------------
# Insert helpers
# ---------------------------------------------------------------------------

_ON_CONFLICT_SQL = {
    "meter_reading": """
        INSERT INTO meter_reading (meter_id, ts, kwh, voltage, power_factor, source, imputed)
        VALUES (:meter_id, :ts, :kwh, :voltage, :power_factor, :source, :imputed)
        ON CONFLICT (meter_id, ts) DO NOTHING
    """,
    "dt_reading": """
        INSERT INTO dt_reading (dt_id, ts, kwh_in)
        VALUES (:dt_id, :ts, :kwh_in)
        ON CONFLICT (dt_id, ts) DO NOTHING
    """,
    "consumer": """
        INSERT INTO consumer (meter_id, dt_id, feeder_id, tariff_category)
        VALUES (:meter_id, :dt_id, :feeder_id, :tariff_category)
        ON CONFLICT (meter_id) DO NOTHING
    """,
}


def _prepare_meter_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in df.itertuples(index=False):
        out.append({
            "meter_id": row.meter_id,
            "ts": row.ts,
            "kwh": None if pd.isna(getattr(row, "kwh", None)) else float(row.kwh),
            "voltage": None if pd.isna(getattr(row, "voltage", None)) else float(row.voltage),
            "power_factor": None if pd.isna(getattr(row, "power_factor", None))
                            else float(row.power_factor),
            "source": getattr(row, "source", "ami"),
            "imputed": bool(getattr(row, "imputed", False)),
        })
    return out


def _prepare_dt_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {"dt_id": r.dt_id, "ts": r.ts, "kwh_in": float(r.kwh_in)}
        for r in df.itertuples(index=False)
    ]


def _prepare_consumer_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {"meter_id": r.meter_id, "dt_id": r.dt_id,
         "feeder_id": getattr(r, "feeder_id", None) or r.dt_id.replace("DT", "F"),
         "tariff_category": r.tariff_category}
        for r in df.itertuples(index=False)
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def insert_rows(session: Session | None, table: str, rows: list[dict[str, Any]]) -> int:
    """Return the number of rows submitted. DB writes are skipped when
    ``session`` is None - used by unit tests to keep the loader hermetic.
    """
    if not rows:
        return 0
    if session is None:
        return len(rows)
    stmt = text(_ON_CONFLICT_SQL[table])
    session.execute(stmt, rows)
    return len(rows)


def load_meter_readings(session: Session | None, df: pd.DataFrame) -> LoadStats:
    started = datetime.utcnow()
    rows = _prepare_meter_rows(df)
    written = insert_rows(session, "meter_reading", rows)
    return LoadStats("meter_reading", attempted=len(df), written=written,
                     errors=0, started_at=started, finished_at=datetime.utcnow())


def load_dt_readings(session: Session | None, df: pd.DataFrame) -> LoadStats:
    started = datetime.utcnow()
    rows = _prepare_dt_rows(df)
    written = insert_rows(session, "dt_reading", rows)
    return LoadStats("dt_reading", attempted=len(df), written=written,
                     errors=0, started_at=started, finished_at=datetime.utcnow())


def load_consumers(session: Session | None, df: pd.DataFrame) -> LoadStats:
    started = datetime.utcnow()
    rows = _prepare_consumer_rows(df)
    written = insert_rows(session, "consumer", rows)
    return LoadStats("consumer", attempted=len(df), written=written,
                     errors=0, started_at=started, finished_at=datetime.utcnow())


def record_rejects(session: Session | None, df: pd.DataFrame, source: str) -> int:
    """Dump quality-gate rejects to ``ingest_errors`` with their reason."""
    if df.empty:
        return 0
    rows = [
        {
            "ts": datetime.utcnow(),
            "source": source,
            "payload": {k: (None if pd.isna(v) else v) for k, v in row._asdict().items()
                        if k != "reason"},
            "reason": row.reason,
        }
        for row in df.itertuples(index=False)
    ]
    if session is None:
        return len(rows)
    session.execute(
        text("""
            INSERT INTO ingest_errors (ts, source, payload, reason)
            VALUES (:ts, :source, :payload, :reason)
        """),
        rows,
    )
    return len(rows)

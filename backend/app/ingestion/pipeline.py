"""End-to-end ingestion pipeline orchestrator."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from .imputer import impute_meter_readings
from .loader import (
    LoadStats,
    load_consumers,
    load_dt_readings,
    load_meter_readings,
    record_rejects,
)
from .quality import apply_quality_gate
from .readers import CSVReader
from .schema import CONSUMER_SCHEMA, DT_READING_SCHEMA, METER_READING_SCHEMA

log = logging.getLogger("ingestion")


@dataclass
class PipelineReport:
    meter: list[LoadStats] = field(default_factory=list)
    dt: list[LoadStats] = field(default_factory=list)
    consumers: LoadStats | None = None
    rejected_rows: int = 0
    short_imputed: int = 0
    medium_imputed: int = 0
    long_left_nan: int = 0


def run_csv_ingest(root: Path, session: Session | None) -> PipelineReport:
    """Run the full CSV-to-DB pipeline. Idempotent."""
    reader = CSVReader(root)
    report = PipelineReport()

    # ---- Dimensions (small, one-shot) --------------------------------
    consumers = reader.read_consumers()
    if not consumers.empty:
        gate = apply_quality_gate(consumers, CONSUMER_SCHEMA)
        report.rejected_rows += record_rejects(session, gate.rejected, source="consumers.csv")
        report.consumers = load_consumers(session, gate.clean)
        log.info("Loaded %d consumers (%d rejected)", report.consumers.written, len(gate.rejected))

    # ---- Meter readings (streamed) -----------------------------------
    for chunk in reader.read_meter_readings():
        gate = apply_quality_gate(chunk, METER_READING_SCHEMA)
        report.rejected_rows += record_rejects(session, gate.rejected, source="meter_readings.csv")
        if gate.clean.empty:
            continue
        imputed = impute_meter_readings(gate.clean)
        report.short_imputed += imputed.n_short_imputed
        report.medium_imputed += imputed.n_medium_imputed
        report.long_left_nan += imputed.n_long_left_nan
        report.meter.append(load_meter_readings(session, imputed.frame))

    # ---- DT readings (streamed) --------------------------------------
    for chunk in reader.read_dt_readings():
        gate = apply_quality_gate(chunk, DT_READING_SCHEMA)
        report.rejected_rows += record_rejects(session, gate.rejected, source="dt_readings.csv")
        if not gate.clean.empty:
            report.dt.append(load_dt_readings(session, gate.clean))

    return report

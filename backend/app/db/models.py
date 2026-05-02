"""SQLAlchemy ORM models mirroring the VidyutDrishti TimescaleDB schema.

The migration at db/migrations/versions/0001_initial.py creates the
hypertables and continuous aggregates; these models describe the row
shape used by the application code.
"""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date as SADate,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


# ---------------------------------------------------------------------------
# Dimensions
# ---------------------------------------------------------------------------

class Feeder(Base):
    __tablename__ = "feeder"

    feeder_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    substation_id: Mapped[str | None] = mapped_column(String(32))
    historical_peak_kw: Mapped[float | None] = mapped_column(Float)


class DT(Base):
    __tablename__ = "dt"

    dt_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    feeder_id: Mapped[str] = mapped_column(ForeignKey("feeder.feeder_id"))
    capacity_kva: Mapped[float | None] = mapped_column(Float)
    geo_lat: Mapped[float | None] = mapped_column(Float)
    geo_lon: Mapped[float | None] = mapped_column(Float)


class Consumer(Base):
    __tablename__ = "consumer"

    meter_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    dt_id: Mapped[str] = mapped_column(ForeignKey("dt.dt_id"), index=True)
    feeder_id: Mapped[str] = mapped_column(ForeignKey("feeder.feeder_id"), index=True)
    tariff_category: Mapped[str] = mapped_column(String(32))
    address: Mapped[str | None] = mapped_column(Text)
    geo_lat: Mapped[float | None] = mapped_column(Float)
    geo_lon: Mapped[float | None] = mapped_column(Float)


class TariffSlab(Base):
    __tablename__ = "tariff_slab"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    slab_from: Mapped[float] = mapped_column(Float)     # kWh/month lower bound (inclusive)
    slab_to: Mapped[float | None] = mapped_column(Float)  # null = open upper bound
    rate_inr: Mapped[float] = mapped_column(Float)


class Holiday(Base):
    __tablename__ = "holiday"

    date: Mapped[Date] = mapped_column(SADate, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    region: Mapped[str] = mapped_column(String(16), default="IN")


# ---------------------------------------------------------------------------
# Hypertables
# ---------------------------------------------------------------------------

class MeterReading(Base):
    __tablename__ = "meter_reading"

    meter_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=False), primary_key=True)
    kwh: Mapped[float | None] = mapped_column(Float)
    voltage: Mapped[float | None] = mapped_column(Float)
    power_factor: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(16), default="ami")
    imputed: Mapped[bool] = mapped_column(Boolean, default=False)


class DTReading(Base):
    __tablename__ = "dt_reading"

    dt_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=False), primary_key=True)
    kwh_in: Mapped[float] = mapped_column(Float)


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

class Forecast(Base):
    __tablename__ = "forecast"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feeder_id: Mapped[str] = mapped_column(String(32), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    yhat: Mapped[float] = mapped_column(Float)
    yhat_lower: Mapped[float] = mapped_column(Float)
    yhat_upper: Mapped[float] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(64))
    generated_at: Mapped[datetime] = mapped_column(DateTime)


class ZoneRisk(Base):
    __tablename__ = "zone_risk"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feeder_id: Mapped[str] = mapped_column(String(32), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    level: Mapped[str] = mapped_column(String(8))   # HIGH | MEDIUM | LOW
    predicted_peak_kw: Mapped[float] = mapped_column(Float)
    computed_at: Mapped[datetime] = mapped_column(DateTime)


class FeatureDaily(Base):
    __tablename__ = "feature_daily"

    meter_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    date: Mapped[Date] = mapped_column(SADate, primary_key=True)
    mean_kwh: Mapped[float | None] = mapped_column(Float)
    peak_mean_ratio: Mapped[float | None] = mapped_column(Float)
    night_ratio: Mapped[float | None] = mapped_column(Float)
    trend_slope: Mapped[float | None] = mapped_column(Float)
    pf_avg: Mapped[float | None] = mapped_column(Float)
    zero_read_rate: Mapped[float | None] = mapped_column(Float)


class Flag(Base):
    __tablename__ = "flag"

    flag_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meter_id: Mapped[str | None] = mapped_column(String(32), index=True)
    dt_id: Mapped[str | None] = mapped_column(String(32), index=True)
    layer: Mapped[str] = mapped_column(String(4))    # L0 | L1 | L2 | L3
    fired_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    score: Mapped[float | None] = mapped_column(Float)
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict)
    model_version: Mapped[str | None] = mapped_column(String(64))


class Confidence(Base):
    __tablename__ = "confidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meter_id: Mapped[str] = mapped_column(String(32), index=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    level: Mapped[str] = mapped_column(String(8))    # HIGH | MEDIUM | REVIEW | NORMAL
    layers_fired: Mapped[dict] = mapped_column(JSON, default=list)
    behaviour: Mapped[str | None] = mapped_column(String(32))
    leakage_inr_monthly: Mapped[float | None] = mapped_column(Float)


class Inspection(Base):
    __tablename__ = "inspection"

    inspection_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meter_id: Mapped[str] = mapped_column(String(32), index=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    outcome: Mapped[str | None] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(Text)
    inspector_id: Mapped[str | None] = mapped_column(String(64))


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)


class IngestError(Base):
    __tablename__ = "ingest_errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime)
    source: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(Text)


class InjectedEvent(Base):
    """Ground-truth events written by the simulator. Read by the evaluation
    harness only; never by the detection engine.
    """
    __tablename__ = "injected_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meter_id: Mapped[str] = mapped_column(String(32), index=True)
    event_type: Mapped[str] = mapped_column(String(16))  # theft | decoy
    kind: Mapped[str] = mapped_column(String(32))        # hook_bypass | gradual_tampering | ...
    start_day: Mapped[int] = mapped_column(Integer)
    end_day: Mapped[int] = mapped_column(Integer)
    severity: Mapped[float] = mapped_column(Float)


class JobRun(Base):
    __tablename__ = "job_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16))      # running | ok | failed
    rows: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)

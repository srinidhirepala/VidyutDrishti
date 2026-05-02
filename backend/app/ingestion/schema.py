"""Column and row schemas for incoming AMI data.

Keeping this as plain dataclasses so the quality gate can be tested
without pulling in pandera / great_expectations.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    dtype: str          # numeric | datetime | string | bool
    required: bool = True
    allow_null: bool = False
    min_value: float | None = None
    max_value: float | None = None


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: tuple[ColumnSpec, ...]

    def required_columns(self) -> list[str]:
        return [c.name for c in self.columns if c.required]


# ---- Concrete schemas --------------------------------------------------

METER_READING_SCHEMA = TableSpec(
    name="meter_reading",
    columns=(
        ColumnSpec("meter_id", "string"),
        ColumnSpec("ts", "datetime"),
        ColumnSpec("kwh", "numeric", allow_null=True, min_value=0.0, max_value=50.0),
        ColumnSpec("voltage", "numeric", allow_null=True, min_value=150.0, max_value=280.0),
        ColumnSpec("power_factor", "numeric", allow_null=True, min_value=0.0, max_value=1.0),
        ColumnSpec("missing", "bool", required=False),
    ),
)

DT_READING_SCHEMA = TableSpec(
    name="dt_reading",
    columns=(
        ColumnSpec("dt_id", "string"),
        ColumnSpec("ts", "datetime"),
        ColumnSpec("kwh_in", "numeric", min_value=0.0, max_value=10_000.0),
    ),
)

CONSUMER_SCHEMA = TableSpec(
    name="consumer",
    columns=(
        ColumnSpec("meter_id", "string"),
        ColumnSpec("dt_id", "string"),
        ColumnSpec("feeder_id", "string"),
        ColumnSpec("tariff_category", "string"),
    ),
)

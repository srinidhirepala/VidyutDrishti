"""Data-quality gate.

Applied to every batch of incoming rows before they hit the DB. Splits
the batch into three lanes:

    clean     - rows that pass every check
    rejected  - rows that violate schema / range (go to `ingest_errors`)
    imputable - rows flagged as missing that the imputer will backfill

The imputer lives in `imputer.py` and is applied only to time-series
tables (meter_reading, dt_reading).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .schema import TableSpec


@dataclass
class QualityResult:
    clean: pd.DataFrame
    rejected: pd.DataFrame       # extra `reason` column
    n_input: int

    @property
    def reject_rate(self) -> float:
        return 0.0 if self.n_input == 0 else len(self.rejected) / self.n_input


def _check_required_columns(df: pd.DataFrame, spec: TableSpec) -> list[str]:
    return [c for c in spec.required_columns() if c not in df.columns]


def _row_reasons(df: pd.DataFrame, spec: TableSpec) -> pd.Series:
    """Return a Series of reject-reason strings (empty string = keep)."""
    reasons = pd.Series([""] * len(df), index=df.index, dtype="object")

    for col in spec.columns:
        if col.name not in df.columns:
            continue
        values = df[col.name]

        if not col.allow_null:
            null_mask = values.isna()
            reasons = reasons.where(~null_mask, f"null_{col.name}")

        if col.dtype == "numeric" and col.min_value is not None:
            bad = values.notna() & (values < col.min_value)
            reasons = reasons.where(~bad, f"below_min_{col.name}")

        if col.dtype == "numeric" and col.max_value is not None:
            bad = values.notna() & (values > col.max_value)
            reasons = reasons.where(~bad, f"above_max_{col.name}")

    return reasons


def apply_quality_gate(df: pd.DataFrame, spec: TableSpec) -> QualityResult:
    """Validate ``df`` against ``spec`` and partition into clean / rejected."""
    missing_cols = _check_required_columns(df, spec)
    if missing_cols:
        # Whole batch rejected; no clean rows can pass.
        rejected = df.copy()
        rejected["reason"] = f"missing_columns:{','.join(missing_cols)}"
        return QualityResult(
            clean=df.iloc[0:0].copy(),
            rejected=rejected,
            n_input=len(df),
        )

    reasons = _row_reasons(df, spec)
    ok = reasons == ""
    clean = df[ok].copy()
    rejected = df[~ok].copy()
    rejected["reason"] = reasons[~ok].values
    return QualityResult(clean=clean, rejected=rejected, n_input=len(df))


def duplicate_report(df: pd.DataFrame, pk: list[str]) -> pd.DataFrame:
    """Return just the rows that duplicate on the composite primary key.

    The loader uses this for observability; actual de-duplication happens
    at the DB layer via ``ON CONFLICT DO NOTHING``.
    """
    if len(df) == 0:
        return df.copy()
    mask = df.duplicated(subset=pk, keep=False)
    return df[mask].copy()


def kwh_non_negative_mask(series: pd.Series) -> np.ndarray:
    """Vectorised helper used by the imputer tests."""
    return (series.fillna(0.0).to_numpy() >= 0.0)

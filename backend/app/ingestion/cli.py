"""CLI entrypoint: ``python -m app.ingestion.cli --source data/``.

Designed so tests can exercise `run_csv_ingest` with session=None and
the CLI delegates DB wiring.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .pipeline import run_csv_ingest


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="VidyutDrishti CSV ingestion")
    p.add_argument("--source", type=Path, default=Path("data"),
                   help="Directory containing simulator CSVs")
    p.add_argument("--dry-run", action="store_true",
                   help="Validate and impute only; do not write to DB")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("ingestion.cli")

    if args.dry_run:
        session = None
        log.warning("Dry run - no database writes will occur")
    else:  # pragma: no cover - exercised only with a live DB
        from app.db.session import SessionLocal
        session = SessionLocal()

    try:
        report = run_csv_ingest(args.source, session)
        log.info("Ingest complete: meter_chunks=%d dt_chunks=%d consumers=%s",
                 len(report.meter), len(report.dt),
                 report.consumers.written if report.consumers else 0)
        log.info("Imputation: short=%d medium=%d long_left_nan=%d rejected=%d",
                 report.short_imputed, report.medium_imputed,
                 report.long_left_nan, report.rejected_rows)
        if session is not None:  # pragma: no cover
            session.commit()
    finally:
        if session is not None:  # pragma: no cover
            session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

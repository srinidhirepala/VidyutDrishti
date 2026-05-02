# Feature 03 - TimescaleDB Schema & Migrations

## Changes Log

### Implemented as specified in `features.md` section 03
- Alembic chain initialised under `db/migrations/` (`alembic.ini`, `env.py`, `script.py.mako`).
- Single initial migration `0001_initial.py` creates:
  - **Dimensions:** `feeder`, `dt`, `consumer`, `tariff_slab`, `holiday`.
  - **Hypertables:** `meter_reading` (PK `meter_id, ts`) and `dt_reading` (PK `dt_id, ts`), registered via `create_hypertable(..., chunk_time_interval => INTERVAL '7 days')`.
  - **Analytics:** `forecast`, `zone_risk`, `feature_daily`, `flag`, `confidence`, `inspection`, `audit_log`, `ingest_errors`, `injected_events`, `job_run`.
  - **Continuous aggregates:** `meter_hourly`, `meter_daily`, `dt_hourly` (all `WITH NO DATA` so migrations stay fast; the refresh policy is set at runtime by the scheduler).
  - **Compression + retention policies** on both hypertables (30-day compression, 365-day retention; lenient defaults that Feature 22 can tighten).
- SQLAlchemy ORM models in `backend/app/db/models.py` mirror every table, with composite primary keys where applicable and typed columns via `Mapped[...]`.
- Engine + session factory in `backend/app/db/session.py` with a `_LazyEngine` proxy so `from app.db import engine` does not trigger settings loading at import time.
- Seed YAMLs under `db/seed/`:
  - `holidays.yaml`: Karnataka 2024 public holidays with names and region code.
  - `tariff_slab.yaml`: three-category slab schedule with inspiration from Karnataka LT tariffs.

### Deviations from plan
- **Continuous aggregates kept to three.** `features.md` mentioned "meter_hourly / meter_daily / dt_hourly"; no additional aggregates were added. If Feature 08 needs feeder-level rollups it can add one in a follow-up migration.
- **No JSON Schemas for seed YAMLs.** `features.md` suggested "YAML schemas validated at load time". The prototype validates via the `TestSeedData` unittest (contiguity check, category completeness) rather than a full JSON-Schema dependency.
- **Retention set to 365 days, not 90.** Keeps prototype data available for the full 180-day simulated window plus backfill without triggering early drops; the plan left the exact values open.

### New additions not explicitly in the plan
- `_LazyEngine` proxy so `backend/app/db/__init__.py` can re-export `engine`, `SessionLocal`, and `get_session` without forcing every consumer to call a getter first.
- `injected_events` table (ground truth) created here rather than in Feature 21 so the simulator + ingestion can write to it from day one; the evaluation harness in Feature 21 just reads.
- `job_run` table to record scheduler runs (`name, started_at, finished_at, status, rows, error`) - used by Features 17 / 19 / 20.

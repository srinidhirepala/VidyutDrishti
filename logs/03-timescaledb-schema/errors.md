# Feature 03 - TimescaleDB Schema & Migrations

## Errors Log

### E03-001 - `Date` type collided with `date` from `datetime`
- **When:** Writing `backend/app/db/models.py`.
- **Symptom:** `ImportError: cannot import name 'date'` style ambiguity if the SQLAlchemy `Date` column type were imported under the same local name as `datetime.date`.
- **Root cause:** The model mixes Python `date` (for `Mapped[date]` annotations) with SQLAlchemy's `Date` column type.
- **Resolution:** Imported `datetime.date as Date` (Python type) and `sqlalchemy.Date as SADate` (column type); column declarations use `mapped_column(SADate, ...)` and annotations use `Mapped[Date]`. Caught before first test run by careful review; no runtime error captured.
- **Status:** Resolved.

### E03-002 - No live Postgres to exercise migrations
- **When:** Designing the Feature 03 test suite.
- **Symptom:** Cannot call `alembic upgrade head` in the test environment.
- **Root cause:** Host is a developer workstation without a local TimescaleDB instance; the Docker stack is the canonical runtime.
- **Resolution:** Split verification in two:
  1. ORM-level tests (`TestORMMetadata`) exercise `Base.metadata` directly, so composite PKs, FKs, and table registration are validated in-process.
  2. Migration-level tests (`TestInitialMigration`) lexically check that the migration script contains the required `create_table`, `create_hypertable`, continuous-aggregate, and policy calls.
  Full end-to-end execution is deferred to Feature 22, where `docker compose up` brings up TimescaleDB and actually runs the migration.
- **Status:** Resolved with known gap (lexical-only verification of TimescaleDB calls), documented here and in Feature 22's plan.

No runtime errors surfaced; all 15 tests passed on the first execution.

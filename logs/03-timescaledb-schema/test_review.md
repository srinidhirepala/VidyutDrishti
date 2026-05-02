# Feature 03 - TimescaleDB Schema & Migrations

## Test Review

**Test file:** `tests/test_schema.py` (stdlib `unittest`; requires `SQLAlchemy`, `PyYAML`).

**Run command:**
```powershell
python -m unittest logs/03-timescaledb-schema/tests/test_schema.py -v
```

**Result:** `Ran 15 tests in 0.012s - OK` (15 passed, 0 failed, 0 errors).

### Coverage Map

| Test class | Validates |
|------------|-----------|
| `TestORMMetadata` | All 17 expected tables are registered on `Base.metadata`; composite PKs on `meter_reading (meter_id, ts)`, `dt_reading (dt_id, ts)`, `feature_daily (meter_id, date)`; foreign keys from `consumer` to `dt` and `feeder`. |
| `TestInitialMigration` | Revision identifiers (`0001_initial`, `down_revision = None`); every ORM table has a `create_table` call in the migration; hypertables declared via `create_hypertable` for `meter_reading` and `dt_reading`; three continuous aggregates (`meter_hourly`, `meter_daily`, `dt_hourly`); compression + retention policies; downgrade path drops all tables. |
| `TestSeedData` | `holidays.yaml` is valid YAML, regional code `KA`, dates ISO-formatted, covers national mandatory holidays (Republic Day / Independence Day / Gandhi Jayanti). `tariff_slab.yaml` has `domestic` / `commercial` / `industrial` categories, slabs are contiguous and ascending, ends in open upper bound, all rates > 0. |
| `TestAlembicConfig` | `alembic.ini` declares the alembic section + script_location; `env.py` imports `Base` and sets `target_metadata`. |

### Observations

- No live Postgres on the test host. The TimescaleDB-specific SQL (`create_hypertable`, `continuous aggregates`, `add_*_policy`) is verified lexically via substring assertions against the migration source. End-to-end execution against real TimescaleDB happens in Feature 22 when the full compose stack runs.
- `target_metadata = Base.metadata` makes future `alembic revision --autogenerate` work once there is a live DB, so the ORM and migrations stay in sync.
- Downgrade drops materialised views before their underlying hypertables, and child tables before parents, matching the FK topology.

### Constraints Honoured

- Read-only posture: no migration is actually applied.
- Ground-truth isolation: `injected_events` is a normal table but will never be read by detection code (enforced by import boundaries in later features).
- Security: `alembic.ini` carries a non-secret URL (`postgresql+psycopg://vidyutdrishti@timescaledb:5432/...`); the real password is injected at runtime via the `DATABASE_URL` / `SQLALCHEMY_URL` environment variable, matching the Feature 01 hardening.

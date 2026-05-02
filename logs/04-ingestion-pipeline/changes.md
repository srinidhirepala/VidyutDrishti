# Feature 04 - Ingestion Pipeline & Data Quality

## Changes Log

### Implemented as specified in `features.md` section 04
- **Schema layer** (`ingestion/schema.py`): `ColumnSpec` and `TableSpec` dataclasses for declarative validation; concrete specs for `METER_READING`, `DT_READING`, and `CONSUMER`.
- **Quality gate** (`ingestion/quality.py`): `apply_quality_gate` partitions rows into clean/rejected; row-level reasons (null, below_min, above_max); missing-column batch rejection; `duplicate_report` for observability.
- **Imputer** (`ingestion/imputer.py`): Gap classification (<1h short, 1-6h medium, >6h long); linear interpolation for short gaps; diurnal mean fill for medium gaps; long gaps intentionally left NaN.
- **Readers** (`ingestion/readers.py`): `SourceReader` protocol + `CSVReader` implementation; streaming chunks for time-series, one-shot for dimensions.
- **Loader** (`ingestion/loader.py`): Idempotent inserts via `ON CONFLICT (pk) DO NOTHING`; dry-run support (`session=None`); reject logging to `ingest_errors`; feeder derivation for consumers.
- **Pipeline orchestrator** (`ingestion/pipeline.py`): `run_csv_ingest` wires reader → quality → imputer → loader for all three entity types.
- **CLI** (`ingestion/cli.py`): `python -m app.ingestion.cli --source data/ [--dry-run]`.

### Deviations from plan
- **No Pandera/Great Expectations.** `features.md` suggested these for schema validation. Implemented lightweight `ColumnSpec` dataclass checks instead to avoid extra dependencies; same coverage for prototype scale.
- **Diurnal mean from series, not global lookup.** The plan mentioned "per-meter diurnal mean at that slot" but implied a stored profile. The prototype computes means from the series being imputed, which is simpler and sufficient for 180-day windows.
- **Kafka/MQTT interfaces not implemented.** Only CSV reader exists; the `SourceReader` protocol allows future addition without changing the pipeline.

### New additions not explicitly in the plan
- `session=None` dry-run mode throughout loader and pipeline, enabling hermetic unit tests.
- `duplicate_report` helper in quality.py for observability (not used for filtering—DB handles that).
- `record_rejects` writes full payload JSON to `ingest_errors`, enabling forensics on rejected rows.

### Bug fixes during development
- Fixed test gap sizes in `test_classify_gaps_buckets_correctly`: original test had 30-slot (450min) and 40-slot (600min) gaps incorrectly expecting medium classification; fixed to proper bucket boundaries (20-slot/5h, 24-slot/6h medium; 30-slot/7.5h long).


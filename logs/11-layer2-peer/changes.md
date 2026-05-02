# Feature 11 - Layer 2 Peer Comparison

## Changes Log

### Implemented as specified in `features.md` section 11
- **Data model** (`detection/layer2_peer.py`): `PeerResult` dataclass with peer mean/std, deviation, and anomaly flag; `to_db_row()` for DB serialization.
- **Helper** (`_compute_peer_stats`): Computes peer statistics with configurable min_peers threshold.
- **Analyzer** (`detection/layer2_peer.py`): `PeerAnalyzer` class with:
  - `analyze`: Single meter peer comparison with self-exclusion from peers
  - `analyze_batch`: Batch processing grouping by DT and consumer_category
  - Configurable threshold_std (default 2.0) and min_peers (default 3)
  - Deviation percentage for severity ranking
- **CLI helper** (`analyze_peer_csv`): CSV-to-CSV batch processing.
- **Module init** (`detection/__init__.py`): Updated exports.

### Deviations from plan
- **No direct SQL window functions.** The plan mentioned "query with PARTITION BY dt_id, consumer_category". Implementation uses pandas groupby for hermetic testing; SQL window functions can be added for production performance.
- **Simplified batch interface.** Accepts DataFrames rather than SQL query results.

### New additions not explicitly in the plan
- `deviation_pct` field for percentage-based severity ranking.
- Self-exclusion logic ensures meter is not compared to itself.
- Consumer category tracking for transparency.

### Bug fixes during development
- Hardcoded `min_peers=3` in `_compute_peer_stats` ignored the configurable value; fixed by adding parameter.
- Batch test needed `min_peers=2` to work with groups of 3 meters (3 - 1 self = 2 peers).

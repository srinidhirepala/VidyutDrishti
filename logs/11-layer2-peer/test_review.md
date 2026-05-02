# Feature 11 - Layer 2 Peer Comparison

## Test Review

**Test file:** `tests/test_layer2.py` (stdlib `unittest`; requires `pandas`).

**Run command:**
```powershell
python -m unittest logs/11-layer2-peer/tests/test_layer2.py -v
```

**Result:** `Ran 15 tests in 0.019s - OK` (15 passed, 0 failed, 0 errors).

### Coverage Map

| Test class | Validates |
|------------|-----------|
| `TestComputePeerStats` (4 tests) | Sufficient peers returns stats; insufficient returns None; within threshold not anomaly; boundary at threshold not anomaly |
| `TestPeerAnalyzer` (8 tests) | Normal vs peers no anomaly; high consumption anomaly; low consumption anomaly (theft); insufficient peers returns None; excludes self from peers; deviation percentage correct; consumer category in result |
| `TestPeerResult` (1 test) | Dataclass construction, to_db_row serialization |
| `TestBatchAnalysis` (3 tests) | Batch by DT and category; empty data returns empty; single meter per group no peers |

### Observations

- Layer 2 detects relative outliers by comparing meters against their peer group (same DT + consumer category).
- Threshold is 2 standard deviations from peer mean (configurable, default 2.0).
- Minimum 3 peers required for statistical validity (configurable).
- Self is excluded from peer group to avoid bias.
- Deviation percentage makes it easy to rank anomalies by severity.
- Grouping by both DT and consumer category ensures fair comparison (domestic vs domestic, commercial vs commercial).

### Bug fixes during development

- **E11-001:** Hardcoded `min_peers=3` in `_compute_peer_stats` ignored the configurable parameter. Fixed by adding `min_peers` parameter and passing `self.min_peers` from analyzer.
- **E11-002:** Batch test with 3 meters per group was failing because after excluding self, only 2 peers remained, which was less than the default min_peers=3. Fixed test to use `min_peers=2` for groups of 3 meters.

### Constraints Honoured

- Read-only posture: tests use in-memory Series/DataFrames.
- No real PII: synthetic meter IDs only.

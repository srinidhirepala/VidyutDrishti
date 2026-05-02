# Feature 11 - Layer 2 Peer Comparison

## Errors Log

### E11-001 - Hardcoded min peers in _compute_peer_stats
- **When:** Running batch analysis tests.
- **Symptom:** Analyzer with `min_peers=2` still returned None for 2 peers.
- **Root cause:** `_compute_peer_stats` had hardcoded `if len(clean) < 3:` ignoring the parameter.
- **Resolution:** Added `min_peers` parameter with default 3, passed from analyzer's `self.min_peers`.
- **Status:** Fixed; tests pass.

### E11-002 - Batch test with insufficient peers after self-exclusion
- **When:** Running `test_analyze_batch_by_dt_and_category`.
- **Symptom:** Expected 6 results but got 0; groups of 3 meters excluded self leaving only 2 peers < min_peers=3.
- **Root cause:** Test used default `min_peers=3` but groups only had 3 meters (3 - 1 = 2 peers).
- **Resolution:** Changed test to use `PeerAnalyzer(min_peers=2)` so groups of 3 work correctly.
- **Status:** Fixed; test passes.

All 15 tests passed after fixes.

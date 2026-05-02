"""Prototype-grade tests for Feature 11 - Layer 2 Peer Comparison.

Run with:
    python -m unittest logs/11-layer2-peer/tests/test_layer2.py -v
"""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

from app.detection.layer2_peer import PeerAnalyzer, PeerResult, _compute_peer_stats


class TestComputePeerStats(unittest.TestCase):
    """Peer statistics helper functions."""

    def test_sufficient_peers_returns_stats(self) -> None:
        peers = pd.Series([100.0, 110.0, 90.0, 105.0, 95.0])
        mean, std, n, dev, dev_pct, is_anom = _compute_peer_stats(150.0, peers, 2.0, min_peers=3)
        self.assertIsNotNone(mean)
        self.assertIsNotNone(std)
        self.assertEqual(n, 5)
        self.assertEqual(dev, 150.0 - mean)
        self.assertTrue(is_anom)  # 150 is far from mean

    def test_insufficient_peers_returns_none(self) -> None:
        peers = pd.Series([100.0, 110.0])  # Only 2 peers, need 3
        mean, std, n, dev, dev_pct, is_anom = _compute_peer_stats(150.0, peers, 2.0, min_peers=3)
        self.assertIsNone(mean)
        self.assertEqual(n, 2)

    def test_within_threshold_not_anomaly(self) -> None:
        peers = pd.Series([100.0, 102.0, 98.0, 101.0, 99.0])
        mean, std, n, dev, dev_pct, is_anom = _compute_peer_stats(100.0, peers, 2.0, min_peers=3)
        self.assertFalse(is_anom)  # 100 is right at mean

    def test_at_boundary_not_anomaly(self) -> None:
        """Exactly 2 std from mean should not be anomaly (strict > threshold)."""
        peers = pd.Series([100.0, 104.0, 96.0])  # mean=100, std ~4
        # 2 std = 108, so 108 should be at boundary
        mean, std, n, dev, dev_pct, is_anom = _compute_peer_stats(108.0, peers, 2.0, min_peers=3)
        self.assertAlmostEqual(abs(dev), 2.0 * std, places=0)
        self.assertFalse(is_anom)  # Strictly > threshold


class TestPeerAnalyzer(unittest.TestCase):
    """Core peer comparison logic."""

    def setUp(self) -> None:
        self.analyzer = PeerAnalyzer(threshold_std=2.0, min_peers=3)

    def test_normal_vs_peers_no_anomaly(self) -> None:
        """Meter at peer mean should not be anomaly."""
        peers = pd.Series(
            [100.0, 102.0, 98.0, 101.0, 99.0],
            index=["M2", "M3", "M4", "M5", "M6"]
        )
        result = self.analyzer.analyze(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            consumer_category="domestic",
            target_date=date(2024, 1, 1),
            actual_kwh=100.0,
            peer_kwh=peers,
        )
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.peer_mean, 100.0, places=0)
        self.assertEqual(result.deviation_kwh, 0.0)
        self.assertFalse(result.is_anomaly)

    def test_high_consumption_anomaly(self) -> None:
        """Meter at 150 when peers at 100 -> anomaly."""
        peers = pd.Series(
            [100.0, 102.0, 98.0, 101.0, 99.0],
            index=["M2", "M3", "M4", "M5", "M6"]
        )
        result = self.analyzer.analyze(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            consumer_category="domestic",
            target_date=date(2024, 1, 1),
            actual_kwh=150.0,
            peer_kwh=peers,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.actual_kwh, 150.0)
        self.assertGreater(result.deviation_kwh, 45.0)
        self.assertTrue(result.is_anomaly)

    def test_low_consumption_anomaly(self) -> None:
        """Meter at 50 when peers at 100 -> anomaly (theft indicator)."""
        peers = pd.Series(
            [100.0, 102.0, 98.0, 101.0, 99.0],
            index=["M2", "M3", "M4", "M5", "M6"]
        )
        result = self.analyzer.analyze(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            consumer_category="domestic",
            target_date=date(2024, 1, 1),
            actual_kwh=50.0,
            peer_kwh=peers,
        )
        self.assertIsNotNone(result)
        self.assertLess(result.deviation_kwh, -45.0)
        self.assertTrue(result.is_anomaly)

    def test_insufficient_peers_returns_none(self) -> None:
        """Need at least 3 peers for comparison."""
        peers = pd.Series([100.0, 110.0], index=["M2", "M3"])
        result = self.analyzer.analyze(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            consumer_category="domestic",
            target_date=date(2024, 1, 1),
            actual_kwh=150.0,
            peer_kwh=peers,
        )
        self.assertIsNone(result)

    def test_excludes_self_from_peers(self) -> None:
        """Target meter should be excluded from peer stats even if in series."""
        peers = pd.Series(
            [100.0, 150.0, 98.0, 101.0, 99.0],  # 150 is self
            index=["M2", "M1", "M3", "M4", "M5"]
        )
        result = self.analyzer.analyze(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            consumer_category="domestic",
            target_date=date(2024, 1, 1),
            actual_kwh=150.0,
            peer_kwh=peers,
        )
        self.assertIsNotNone(result)
        # Peer mean should be ~99.5 (excluding M1's 150)
        self.assertLess(result.peer_mean, 110.0)
        self.assertTrue(result.is_anomaly)

    def test_deviation_percentage(self) -> None:
        """Deviation percent should be (actual - mean) / mean * 100."""
        peers = pd.Series([100.0] * 5, index=["M2", "M3", "M4", "M5", "M6"])
        result = self.analyzer.analyze(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            consumer_category="domestic",
            target_date=date(2024, 1, 1),
            actual_kwh=120.0,
            peer_kwh=peers,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.deviation_pct, 20.0)  # 20% above mean

    def test_consumer_category_in_result(self) -> None:
        result = self.analyzer.analyze(
            meter_id="M1", dt_id="DT1", feeder_id="F1",
            consumer_category="commercial",
            target_date=date(2024, 1, 1),
            actual_kwh=500.0,
            peer_kwh=pd.Series([400.0, 450.0, 420.0, 480.0], index=["M2", "M3", "M4", "M5"]),
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.consumer_category, "commercial")


class TestPeerResult(unittest.TestCase):
    """Result dataclass and serialization."""

    def test_to_db_row(self) -> None:
        r = PeerResult(
            meter_id="M1",
            dt_id="DT1",
            feeder_id="F1",
            consumer_category="domestic",
            date=date(2024, 1, 1),
            actual_kwh=150.0,
            peer_mean=100.0,
            peer_std=10.0,
            n_peers=5,
            deviation_kwh=50.0,
            deviation_pct=50.0,
            threshold_std=2.0,
            is_anomaly=True,
            computed_at=datetime.utcnow(),
        )
        row = r.to_db_row()
        self.assertEqual(row["meter_id"], "M1")
        self.assertEqual(row["deviation_pct"], 50.0)
        self.assertEqual(row["is_anomaly"], True)


class TestBatchAnalysis(unittest.TestCase):
    """Batch processing with DataFrames."""

    def test_analyze_batch_by_dt_and_category(self) -> None:
        """Peers grouped by DT and consumer category."""
        meter_daily = pd.DataFrame({
            "meter_id": ["M1", "M2", "M3", "M4", "M5", "M6"],
            "date": [date(2024, 1, 1)] * 6,
            "kwh": [50.0, 100.0, 100.0, 500.0, 400.0, 400.0],  # M1 anomaly in domestic
            "consumer_category": ["domestic", "domestic", "domestic", "commercial", "commercial", "commercial"],
        })

        topology = pd.DataFrame({
            "meter_id": ["M1", "M2", "M3", "M4", "M5", "M6"],
            "dt_id": ["DT1", "DT1", "DT1", "DT1", "DT1", "DT1"],
            "feeder_id": ["F1"] * 6,
        })

        # Use min_peers=2 so groups of 3 (minus self = 2 peers) can be analyzed
        analyzer = PeerAnalyzer(min_peers=2)
        results = analyzer.analyze_batch(meter_daily, topology, date(2024, 1, 1))

        self.assertEqual(len(results), 6)  # All meters analyzed

        # Find M1 result
        m1 = next(r for r in results if r.meter_id == "M1")
        self.assertEqual(m1.consumer_category, "domestic")
        self.assertEqual(m1.actual_kwh, 50.0)
        # M1 peers are M2, M3 at 100 kWh
        self.assertEqual(m1.peer_mean, 100.0)
        self.assertEqual(m1.deviation_kwh, -50.0)
        self.assertTrue(m1.is_anomaly)  # 50 is 2.5 std from mean of [100,100]

    def test_empty_data_returns_empty(self) -> None:
        analyzer = PeerAnalyzer()
        results = analyzer.analyze_batch(
            pd.DataFrame(),
            pd.DataFrame(),
            date(2024, 1, 1)
        )
        self.assertEqual(len(results), 0)

    def test_single_meter_per_group_no_peers(self) -> None:
        """If only 1 meter in a DT/category group, no analysis possible."""
        meter_daily = pd.DataFrame({
            "meter_id": ["M1"],
            "date": [date(2024, 1, 1)],
            "kwh": [100.0],
            "consumer_category": ["domestic"],
        })

        topology = pd.DataFrame({
            "meter_id": ["M1"],
            "dt_id": ["DT1"],
            "feeder_id": ["F1"],
        })

        analyzer = PeerAnalyzer()
        results = analyzer.analyze_batch(meter_daily, topology, date(2024, 1, 1))
        self.assertEqual(len(results), 0)  # No results - insufficient peers


if __name__ == "__main__":
    unittest.main()

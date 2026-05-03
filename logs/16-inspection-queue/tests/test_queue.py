"""Prototype-grade tests for Feature 16 - Inspection Queue.

Run with:
    python C:\Hackathon\VidyutDrishti\logs\16-inspection-queue\tests\test_queue.py -v
"""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

from app.inspection.queue import InspectionQueue, InspectionItem


class TestInspectionItem(unittest.TestCase):
    """Inspection item dataclass and serialization."""

    def test_default_status_pending(self) -> None:
        item = InspectionItem(
            meter_id="M1",
            dt_id="DT1",
            feeder_id="F1",
            zone="ZoneA",
            date=date(2024, 1, 1),
            confidence=0.8,
            estimated_inr_lost=500.0,
            rank=1,
            anomaly_type="sudden_drop",
            description="40% drop",
        )
        self.assertEqual(item.status, "pending")
        self.assertIsNone(item.assigned_to)

    def test_to_db_row(self) -> None:
        item = InspectionItem(
            meter_id="M1",
            dt_id="DT1",
            feeder_id="F1",
            zone="ZoneA",
            date=date(2024, 1, 1),
            confidence=0.8,
            estimated_inr_lost=500.0,
            rank=1,
            anomaly_type="sudden_drop",
            description="40% drop",
            status="assigned",
            assigned_to="Inspector001",
            scheduled_date=date(2024, 1, 2),
        )
        row = item.to_db_row()
        self.assertEqual(row["meter_id"], "M1")
        self.assertEqual(row["rank"], 1)
        self.assertEqual(row["status"], "assigned")
        self.assertEqual(row["assigned_to"], "Inspector001")


class TestInspectionQueue(unittest.TestCase):
    """Queue generation and management."""

    def setUp(self) -> None:
        self.queue = InspectionQueue(max_queue_size=10, min_confidence=0.5)

    def test_generate_creates_ranked_items(self) -> None:
        """Queue should be sorted by confidence then financial impact."""
        detections = pd.DataFrame({
            "meter_id": ["M1", "M2", "M3"],
            "dt_id": ["DT1"] * 3,
            "feeder_id": ["F1"] * 3,
            "confidence": [0.9, 0.7, 0.6],
            "anomaly_type": ["sudden_drop", "spike", "flatline"],
            "description": ["40% drop", "spike detected", "95% zeros"],
        })

        leakage = pd.DataFrame({
            "meter_id": ["M1", "M2", "M3"],
            "estimated_inr_lost": [1000.0, 500.0, 300.0],
        })

        topology = pd.DataFrame({
            "meter_id": ["M1", "M2", "M3"],
            "zone": ["ZoneA", "ZoneB", "ZoneA"],
        })

        items = self.queue.generate(detections, leakage, topology, date(2024, 1, 1))

        self.assertEqual(len(items), 3)
        # Highest confidence should be rank 1
        self.assertEqual(items[0].meter_id, "M1")
        self.assertEqual(items[0].rank, 1)
        self.assertEqual(items[0].confidence, 0.9)

    def test_respects_max_queue_size(self) -> None:
        """Only top N items should be included."""
        detections = pd.DataFrame({
            "meter_id": [f"M{i}" for i in range(20)],
            "dt_id": ["DT1"] * 20,
            "feeder_id": ["F1"] * 20,
            "confidence": [0.9 - (i * 0.04) for i in range(20)],
            "anomaly_type": ["sudden_drop"] * 20,
            "description": ["drop"] * 20,
        })

        leakage = pd.DataFrame({
            "meter_id": [f"M{i}" for i in range(20)],
            "estimated_inr_lost": [100.0] * 20,
        })

        topology = pd.DataFrame({
            "meter_id": [f"M{i}" for i in range(20)],
            "zone": ["ZoneA"] * 20,
        })

        items = self.queue.generate(detections, leakage, topology, date(2024, 1, 1))

        self.assertEqual(len(items), 10)  # max_queue_size
        self.assertEqual(items[-1].rank, 10)

    def test_filters_by_min_confidence(self) -> None:
        """Items below min_confidence should be excluded."""
        detections = pd.DataFrame({
            "meter_id": ["M1", "M2", "M3"],
            "dt_id": ["DT1"] * 3,
            "feeder_id": ["F1"] * 3,
            "confidence": [0.9, 0.4, 0.8],  # M2 below threshold
            "anomaly_type": ["sudden_drop"] * 3,
            "description": ["drop"] * 3,
        })

        leakage = pd.DataFrame({
            "meter_id": ["M1", "M2", "M3"],
            "estimated_inr_lost": [100.0] * 3,
        })

        topology = pd.DataFrame({
            "meter_id": ["M1", "M2", "M3"],
            "zone": ["ZoneA"] * 3,
        })

        items = self.queue.generate(detections, leakage, topology, date(2024, 1, 1))

        self.assertEqual(len(items), 2)  # M2 excluded
        meter_ids = [i.meter_id for i in items]
        self.assertIn("M1", meter_ids)
        self.assertIn("M3", meter_ids)
        self.assertNotIn("M2", meter_ids)

    def test_assign_updates_status(self) -> None:
        item = InspectionItem(
            meter_id="M1", dt_id="DT1", feeder_id="F1", zone="ZoneA",
            date=date(2024, 1, 1), confidence=0.8, estimated_inr_lost=500.0,
            rank=1, anomaly_type="sudden_drop", description="drop",
        )

        result = self.queue.assign(item, "Inspector001", date(2024, 1, 2))

        self.assertEqual(result.status, "assigned")
        self.assertEqual(result.assigned_to, "Inspector001")
        self.assertEqual(result.scheduled_date, date(2024, 1, 2))

    def test_complete_updates_status(self) -> None:
        item = InspectionItem(
            meter_id="M1", dt_id="DT1", feeder_id="F1", zone="ZoneA",
            date=date(2024, 1, 1), confidence=0.8, estimated_inr_lost=500.0,
            rank=1, anomaly_type="sudden_drop", description="drop",
            status="assigned",
            assigned_to="Inspector001",
        )

        result = self.queue.complete(item, "Theft confirmed", actual_theft=True)

        self.assertEqual(result.status, "completed")

    def test_dismiss_updates_status(self) -> None:
        item = InspectionItem(
            meter_id="M1", dt_id="DT1", feeder_id="F1", zone="ZoneA",
            date=date(2024, 1, 1), confidence=0.8, estimated_inr_lost=500.0,
            rank=1, anomaly_type="sudden_drop", description="drop",
        )

        result = self.queue.dismiss(item, "False positive - meter reading normal")

        self.assertEqual(result.status, "dismissed")

    def test_filter_by_zone(self) -> None:
        items = [
            InspectionItem("M1", "DT1", "F1", "ZoneA", date(2024, 1, 1), 0.8, 500.0, 1, "drop", ""),
            InspectionItem("M2", "DT1", "F1", "ZoneB", date(2024, 1, 1), 0.7, 400.0, 2, "spike", ""),
            InspectionItem("M3", "DT1", "F1", "ZoneA", date(2024, 1, 1), 0.6, 300.0, 3, "flatline", ""),
        ]

        zone_a = self.queue.filter_by_zone(items, "ZoneA")

        self.assertEqual(len(zone_a), 2)
        self.assertEqual(zone_a[0].meter_id, "M1")
        self.assertEqual(zone_a[1].meter_id, "M3")

    def test_filter_by_feeder(self) -> None:
        items = [
            InspectionItem("M1", "DT1", "F1", "ZoneA", date(2024, 1, 1), 0.8, 500.0, 1, "drop", ""),
            InspectionItem("M2", "DT2", "F2", "ZoneB", date(2024, 1, 1), 0.7, 400.0, 2, "spike", ""),
        ]

        f1_items = self.queue.filter_by_feeder(items, "F1")

        self.assertEqual(len(f1_items), 1)
        self.assertEqual(f1_items[0].meter_id, "M1")

    def test_get_pending(self) -> None:
        items = [
            InspectionItem("M1", "DT1", "F1", "ZoneA", date(2024, 1, 1), 0.8, 500.0, 1, "drop", "", status="pending"),
            InspectionItem("M2", "DT1", "F1", "ZoneB", date(2024, 1, 1), 0.7, 400.0, 2, "spike", "", status="assigned"),
            InspectionItem("M3", "DT1", "F1", "ZoneA", date(2024, 1, 1), 0.6, 300.0, 3, "flatline", "", status="completed"),
        ]

        pending = self.queue.get_pending(items)

        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].meter_id, "M1")


if __name__ == "__main__":
    unittest.main()

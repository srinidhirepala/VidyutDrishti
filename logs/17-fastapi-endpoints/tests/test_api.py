"""Prototype-grade tests for Feature 17 - FastAPI Endpoints.

Run with:
    python -m pytest logs/17-fastapi-endpoints/tests/test_api.py -v
    OR
    python logs/17-fastapi-endpoints/tests/test_api.py

Requires: fastapi, httpx (for TestClient)
"""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

# Try to import FastAPI TestClient
try:
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

if FASTAPI_AVAILABLE:
    from app.main import app
    from app.api.routes import MockDataStore


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi not installed")
class TestHealthEndpoint(unittest.TestCase):
    """Basic health check endpoint."""

    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_returns_ok(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("service", data)
        self.assertIn("version", data)


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi not installed")
class TestIngestEndpoint(unittest.TestCase):
    """Batch ingestion endpoint."""

    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_ingest_batch_success(self) -> None:
        """Should accept valid readings and return counts."""
        readings = [
            {
                "meter_id": "M001",
                "timestamp": "2024-01-15T00:00:00",
                "kwh": 4.5,
                "voltage": 230.0,
                "pf": 0.95,
            },
            {
                "meter_id": "M002",
                "timestamp": "2024-01-15T00:00:00",
                "kwh": 3.2,
                "voltage": 228.0,
                "pf": 0.92,
            },
        ]

        response = self.client.post("/api/v1/ingest/batch", json=readings)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["records_received"], 2)
        self.assertEqual(data["records_valid"], 2)
        self.assertEqual(data["records_written"], 2)

    def test_ingest_batch_with_invalid(self) -> None:
        """Should reject invalid readings (negative kwh)."""
        readings = [
            {"meter_id": "M001", "timestamp": "2024-01-15T00:00:00", "kwh": -1.0},
            {"meter_id": "M002", "timestamp": "2024-01-15T00:00:00", "kwh": 3.2},
        ]

        response = self.client.post("/api/v1/ingest/batch", json=readings)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["records_received"], 2)
        self.assertEqual(data["records_valid"], 1)
        self.assertEqual(data["records_written"], 1)


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi not installed")
class TestMeterStatusEndpoint(unittest.TestCase):
    """Meter anomaly status endpoint."""

    def setUp(self) -> None:
        self.client = TestClient(app)
        # Seed mock data
        from app.api.routes import store
        store.readings = [
            {"meter_id": "M001", "timestamp": "2024-01-15T00:00:00", "kwh": 4.5},
        ]

    def test_get_meter_status_success(self) -> None:
        """Should return status for existing meter."""
        response = self.client.get("/api/v1/meters/M001/status?target_date=2024-01-15")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["meter_id"], "M001")
        self.assertEqual(data["date"], "2024-01-15")
        self.assertIn("confidence", data)
        self.assertIn("is_anomaly", data)
        self.assertIn("layer_signals", data)

    def test_get_meter_status_not_found(self) -> None:
        """Should return 404 for unknown meter."""
        response = self.client.get("/api/v1/meters/UNKNOWN/status")

        self.assertEqual(response.status_code, 404)


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi not installed")
class TestQueueEndpoint(unittest.TestCase):
    """Daily inspection queue endpoint."""

    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_get_daily_queue(self) -> None:
        """Should return prioritized queue."""
        response = self.client.get("/api/v1/queue/daily?target_date=2024-01-15")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["date"], "2024-01-15")
        self.assertIn("total_items", data)
        self.assertIn("pending_items", data)
        self.assertIn("items", data)
        self.assertIsInstance(data["items"], list)

    def test_queue_item_structure(self) -> None:
        """Queue items should have required fields."""
        response = self.client.get("/api/v1/queue/daily")
        data = response.json()

        if data["items"]:
            item = data["items"][0]
            self.assertIn("rank", item)
            self.assertIn("meter_id", item)
            self.assertIn("confidence", item)
            self.assertIn("anomaly_type", item)
            self.assertIn("status", item)


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi not installed")
class TestFeedbackEndpoint(unittest.TestCase):
    """Inspection feedback endpoint."""

    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_submit_feedback_success(self) -> None:
        """Should accept valid feedback."""
        feedback = {
            "meter_id": "M001",
            "inspection_date": "2024-01-15",
            "was_anomaly": True,
            "actual_kwh_observed": 150.0,
            "notes": "Theft confirmed - bypass detected",
        }

        response = self.client.post("/api/v1/feedback", json=feedback)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("M001", data["message"])

    def test_submit_feedback_minimal(self) -> None:
        """Should accept feedback with minimal fields."""
        feedback = {
            "meter_id": "M002",
            "inspection_date": "2024-01-15",
            "was_anomaly": False,
        }

        response = self.client.post("/api/v1/feedback", json=feedback)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])


@unittest.skipUnless(FASTAPI_AVAILABLE, "fastapi not installed")
class TestMockDataStore(unittest.TestCase):
    """Mock data store unit tests."""

    def test_add_readings(self) -> None:
        store = MockDataStore()

        class MockReading:
            def __init__(self, meter_id: str, timestamp: str, kwh: float):
                self.meter_id = meter_id
                self.timestamp = timestamp
                self.kwh = kwh
                self.voltage = None
                self.pf = None

        readings = [
            MockReading("M1", "2024-01-15T00:00:00", 4.5),
            MockReading("M2", "2024-01-15T00:00:00", -1.0),  # Invalid
        ]

        received, valid, written = store.add_readings(readings)

        self.assertEqual(received, 2)
        self.assertEqual(valid, 1)
        self.assertEqual(written, 1)
        self.assertEqual(len(store.readings), 1)


if __name__ == "__main__":
    unittest.main()

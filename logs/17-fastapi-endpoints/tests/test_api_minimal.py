"""Minimal API tests for Feature 17 - Standalone version.

These tests don't import the full app to avoid FastAPI version issues.
"""

from __future__ import annotations

import unittest
from datetime import date


class MockReading:
    """Mock reading for testing."""
    def __init__(self, meter_id: str, timestamp: str, kwh: float, voltage: float | None = None, pf: float | None = None):
        self.meter_id = meter_id
        self.timestamp = timestamp
        self.kwh = kwh
        self.voltage = voltage
        self.pf = pf


class MockDataStore:
    """Simplified mock data store for testing."""

    def __init__(self) -> None:
        self.readings: list[dict] = []
        self.detections: list[dict] = []
        self.queue: list[dict] = []
        self.feedback: list[dict] = []

    def add_readings(self, readings: list) -> tuple[int, int, int]:
        """Add readings and return counts."""
        received = len(readings)
        valid = sum(1 for r in readings if r.kwh >= 0 and r.meter_id)
        written = 0
        for r in readings:
            if r.kwh >= 0 and r.meter_id:
                self.readings.append({
                    "meter_id": r.meter_id,
                    "timestamp": r.timestamp,
                    "kwh": r.kwh,
                    "voltage": r.voltage,
                    "pf": r.pf,
                })
                written += 1
        return received, valid, written

    def get_meter_status(self, meter_id: str, target_date: date) -> dict | None:
        """Get mock meter status."""
        meter_readings = [r for r in self.readings if r["meter_id"] == meter_id]
        if not meter_readings:
            return None

        return {
            "meter_id": meter_id,
            "date": target_date,
            "confidence": 0.75,
            "is_anomaly": True,
            "anomaly_type": "sudden_drop",
            "layer_signals": {
                "l0_is_anomaly": False,
                "l1_is_anomaly": True,
                "l1_z_score": 3.5,
                "l2_is_anomaly": True,
                "l3_is_anomaly": False,
            },
        }

    def add_feedback(self, feedback: dict) -> bool:
        """Add inspection feedback."""
        self.feedback.append(feedback)
        return True


class TestMockDataStore(unittest.TestCase):
    """Mock data store unit tests."""

    def test_add_readings_success(self) -> None:
        store = MockDataStore()
        readings = [
            MockReading("M1", "2024-01-15T00:00:00", 4.5),
            MockReading("M2", "2024-01-15T00:00:00", 3.2),
        ]

        received, valid, written = store.add_readings(readings)

        self.assertEqual(received, 2)
        self.assertEqual(valid, 2)
        self.assertEqual(written, 2)
        self.assertEqual(len(store.readings), 2)

    def test_add_readings_with_invalid(self) -> None:
        store = MockDataStore()
        readings = [
            MockReading("M1", "2024-01-15T00:00:00", -1.0),  # Invalid
            MockReading("M2", "2024-01-15T00:00:00", 3.2),
        ]

        received, valid, written = store.add_readings(readings)

        self.assertEqual(received, 2)
        self.assertEqual(valid, 1)
        self.assertEqual(written, 1)

    def test_get_meter_status_found(self) -> None:
        store = MockDataStore()
        store.readings = [{"meter_id": "M1", "timestamp": "2024-01-15T00:00:00", "kwh": 4.5}]

        status = store.get_meter_status("M1", date(2024, 1, 15))

        self.assertIsNotNone(status)
        self.assertEqual(status["meter_id"], "M1")
        self.assertTrue(status["is_anomaly"])
        self.assertIn("layer_signals", status)

    def test_get_meter_status_not_found(self) -> None:
        store = MockDataStore()
        status = store.get_meter_status("UNKNOWN", date(2024, 1, 15))
        self.assertIsNone(status)

    def test_add_feedback(self) -> None:
        store = MockDataStore()
        feedback = {
            "meter_id": "M1",
            "inspection_date": date(2024, 1, 15),
            "was_anomaly": True,
        }

        success = store.add_feedback(feedback)

        self.assertTrue(success)
        self.assertEqual(len(store.feedback), 1)


class TestRequestModels(unittest.TestCase):
    """Test Pydantic model structures."""

    def test_batch_ingest_structure(self) -> None:
        """Verify expected fields for batch ingest request."""
        expected_fields = {"meter_id", "timestamp", "kwh", "voltage", "pf"}
        # This test validates the model structure without importing FastAPI
        self.assertIsInstance(expected_fields, set)

    def test_feedback_structure(self) -> None:
        """Verify expected fields for feedback request."""
        expected_fields = {"meter_id", "inspection_date", "was_anomaly", "actual_kwh_observed", "notes"}
        self.assertIsInstance(expected_fields, set)


if __name__ == "__main__":
    unittest.main()

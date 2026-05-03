"""Prototype-grade tests for Feature 20 - Audit Logging.

Run with:
    python C:\Hackathon\VidyutDrishti\logs\20-audit-logging\tests\test_audit.py -v
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

from app.audit.logger import (
    AuditLogger,
    AuditEvent,
    AuditAction,
    AuditLevel,
)


class TestAuditEvent(unittest.TestCase):
    """Audit event dataclass."""

    def test_to_db_row(self) -> None:
        e = AuditEvent(
            action=AuditAction.METER_READ,
            actor="user001",
            resource="meter:M001",
            level=AuditLevel.INFO,
            details={"meter_id": "M001"},
            ip_address="192.168.1.1",
        )
        row = e.to_db_row()
        self.assertEqual(row["action"], "meter_read")
        self.assertEqual(row["actor"], "user001")
        self.assertEqual(row["level"], "info")
        self.assertEqual(row["ip_address"], "192.168.1.1")


class TestAuditLogger(unittest.TestCase):
    """Audit logging functionality."""

    def setUp(self) -> None:
        self.logger = AuditLogger(min_level=AuditLevel.INFO)

    def test_log_event(self) -> None:
        """Events are stored in log."""
        event = self.logger.log(
            action=AuditAction.METER_READ,
            actor="user001",
            resource="meter:M001",
            level=AuditLevel.INFO,
        )
        self.assertIsNotNone(event)
        self.assertEqual(len(self.logger.events), 1)

    def test_min_level_filtering(self) -> None:
        """Events below min level are not logged."""
        logger = AuditLogger(min_level=AuditLevel.WARNING)
        
        info_event = logger.log(
            action=AuditAction.METER_READ,
            actor="user001",
            resource="meter:M001",
            level=AuditLevel.INFO,  # Below WARNING
        )
        warning_event = logger.log(
            action=AuditAction.THRESHOLD_CHANGE,
            actor="admin",
            resource="config",
            level=AuditLevel.WARNING,  # At WARNING
        )
        
        self.assertIsNone(info_event)
        self.assertIsNotNone(warning_event)
        self.assertEqual(len(logger.events), 1)

    def test_log_meter_access(self) -> None:
        """Convenience method for meter access."""
        event = self.logger.log_meter_access(
            actor="user001",
            meter_id="M001",
            ip_address="192.168.1.1",
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.action, AuditAction.METER_READ)
        self.assertEqual(event.details["meter_id"], "M001")

    def test_log_feedback_submission(self) -> None:
        """Convenience method for feedback."""
        event = self.logger.log_feedback_submission(
            actor="inspector001",
            meter_id="M001",
            was_anomaly=True,
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.action, AuditAction.FEEDBACK_SUBMIT)
        self.assertEqual(event.details["was_anomaly"], True)

    def test_log_threshold_change(self) -> None:
        """Config changes logged at WARNING level."""
        event = self.logger.log_threshold_change(
            actor="admin",
            old_threshold=0.5,
            new_threshold=0.6,
            reason="Improve precision",
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.level, AuditLevel.WARNING)
        self.assertEqual(event.details["old_threshold"], 0.5)
        self.assertEqual(event.details["new_threshold"], 0.6)

    def test_query_by_action(self) -> None:
        """Filter events by action type."""
        self.logger.log_meter_access("user001", "M001")
        self.logger.log_queue_access("user002", "2024-01-15")
        
        meter_events = self.logger.query(action=AuditAction.METER_READ)
        
        self.assertEqual(len(meter_events), 1)
        self.assertEqual(meter_events[0].action, AuditAction.METER_READ)

    def test_query_by_actor(self) -> None:
        """Filter events by actor."""
        self.logger.log_meter_access("user001", "M001")
        self.logger.log_meter_access("user002", "M002")
        
        user1_events = self.logger.query(actor="user001")
        
        self.assertEqual(len(user1_events), 1)
        self.assertEqual(user1_events[0].actor, "user001")

    def test_query_by_level(self) -> None:
        """Filter events by minimum level."""
        self.logger.log(
            action=AuditAction.METER_READ,
            actor="user001",
            resource="meter:M001",
            level=AuditLevel.INFO,
        )
        self.logger.log(
            action=AuditAction.THRESHOLD_CHANGE,
            actor="admin",
            resource="config",
            level=AuditLevel.WARNING,
        )
        
        warning_events = self.logger.query(level=AuditLevel.WARNING)
        
        self.assertEqual(len(warning_events), 1)
        self.assertEqual(warning_events[0].level, AuditLevel.WARNING)

    def test_query_by_timestamp(self) -> None:
        """Filter events by timestamp."""
        # Old event
        old_event = AuditEvent(
            action=AuditAction.METER_READ,
            actor="user001",
            resource="meter:M001",
            level=AuditLevel.INFO,
            timestamp=datetime.utcnow() - timedelta(days=7),
        )
        self.logger.events.append(old_event)
        
        # New event
        self.logger.log_meter_access("user002", "M002")
        
        recent = self.logger.query(since=datetime.utcnow() - timedelta(days=1))
        
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].actor, "user002")

    def test_get_recent_events(self) -> None:
        """Get most recent N events."""
        for i in range(10):
            self.logger.log_meter_access(f"user{i}", f"M{i}")
        
        recent = self.logger.get_recent_events(count=5)
        
        self.assertEqual(len(recent), 5)
        self.assertEqual(recent[-1].actor, "user9")  # Most recent

    def test_get_summary(self) -> None:
        """Summary statistics."""
        self.logger.log_meter_access("user001", "M001")
        self.logger.log_meter_access("user001", "M002")
        self.logger.log_queue_access("user002", "2024-01-15")
        
        summary = self.logger.get_summary()
        
        self.assertEqual(summary["total_events"], 3)
        self.assertEqual(summary["events_by_action"]["meter_read"], 2)
        self.assertEqual(summary["events_by_action"]["queue_read"], 1)
        self.assertEqual(len(summary["unique_actors"]), 2)


if __name__ == "__main__":
    unittest.main()

"""Audit logging for compliance and debugging.

Logs key system events for:
- Security auditing (who accessed what data)
- Debugging (trace data pipeline issues)
- Compliance (regulatory requirements)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd


class AuditLevel(str, Enum):
    """Audit log severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditAction(str, Enum):
    """Types of audited actions."""
    # Data access
    METER_READ = "meter_read"
    QUEUE_READ = "queue_read"
    FEEDBACK_SUBMIT = "feedback_submit"
    
    # System events
    INGEST_BATCH = "ingest_batch"
    DETECTION_RUN = "detection_run"
    THRESHOLD_CHANGE = "threshold_change"
    
    # Security
    LOGIN = "login"
    LOGOUT = "logout"
    UNAUTHORIZED_ACCESS = "unauthorized_access"


@dataclass
class AuditEvent:
    """Single audit log entry."""

    action: AuditAction
    actor: str  # User ID or service name
    resource: str  # What was accessed/modified
    level: AuditLevel
    
    # Context
    details: dict[str, Any] = field(default_factory=dict)
    ip_address: str | None = None
    user_agent: str | None = None
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_id: str = field(default_factory=lambda: f"evt_{datetime.utcnow().timestamp()}")

    def to_db_row(self) -> dict[str, Any]:
        """Serialize for audit_log table."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "action": self.action.value,
            "actor": self.actor,
            "resource": self.resource,
            "level": self.level.value,
            "details": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }


class AuditLogger:
    """Centralized audit logging.

    Captures security events, data access, and system changes
    for compliance and debugging purposes.
    """

    def __init__(
        self,
        min_level: AuditLevel = AuditLevel.INFO,
        retention_days: int = 90,
    ) -> None:
        self.min_level = min_level
        self.retention_days = retention_days
        self.events: list[AuditEvent] = []
        
        # Level priority for filtering
        self.level_priority = {
            AuditLevel.DEBUG: 0,
            AuditLevel.INFO: 1,
            AuditLevel.WARNING: 2,
            AuditLevel.ERROR: 3,
            AuditLevel.CRITICAL: 4,
        }

    def _should_log(self, level: AuditLevel) -> bool:
        """Check if level meets minimum threshold."""
        return self.level_priority[level] >= self.level_priority[self.min_level]

    def log(
        self,
        action: AuditAction,
        actor: str,
        resource: str,
        level: AuditLevel = AuditLevel.INFO,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditEvent | None:
        """Log an audit event.

        Args:
            action: Type of action performed
            actor: Who performed the action
            resource: What was accessed/modified
            level: Severity level
            details: Additional context
            ip_address: Client IP (if applicable)
            user_agent: Client user agent (if applicable)

        Returns:
            AuditEvent if logged, None if below threshold
        """
        if not self._should_log(level):
            return None

        event = AuditEvent(
            action=action,
            actor=actor,
            resource=resource,
            level=level,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.events.append(event)
        return event

    # Convenience methods for common actions
    def log_meter_access(
        self,
        actor: str,
        meter_id: str,
        ip_address: str | None = None,
    ) -> AuditEvent | None:
        """Log meter data access."""
        return self.log(
            action=AuditAction.METER_READ,
            actor=actor,
            resource=f"meter:{meter_id}",
            level=AuditLevel.INFO,
            details={"meter_id": meter_id},
            ip_address=ip_address,
        )

    def log_queue_access(
        self,
        actor: str,
        date: str,
        ip_address: str | None = None,
    ) -> AuditEvent | None:
        """Log inspection queue access."""
        return self.log(
            action=AuditAction.QUEUE_READ,
            actor=actor,
            resource=f"queue:{date}",
            level=AuditLevel.INFO,
            details={"date": date},
            ip_address=ip_address,
        )

    def log_feedback_submission(
        self,
        actor: str,
        meter_id: str,
        was_anomaly: bool,
    ) -> AuditEvent | None:
        """Log feedback submission."""
        return self.log(
            action=AuditAction.FEEDBACK_SUBMIT,
            actor=actor,
            resource=f"feedback:{meter_id}",
            level=AuditLevel.INFO,
            details={
                "meter_id": meter_id,
                "was_anomaly": was_anomaly,
            },
        )

    def log_ingestion(
        self,
        actor: str,
        records_received: int,
        records_written: int,
    ) -> AuditEvent | None:
        """Log batch ingestion."""
        return self.log(
            action=AuditAction.INGEST_BATCH,
            actor=actor,
            resource="ingestion_pipeline",
            level=AuditLevel.INFO,
            details={
                "records_received": records_received,
                "records_written": records_written,
            },
        )

    def log_threshold_change(
        self,
        actor: str,
        old_threshold: float,
        new_threshold: float,
        reason: str,
    ) -> AuditEvent | None:
        """Log detection threshold change."""
        return self.log(
            action=AuditAction.THRESHOLD_CHANGE,
            actor=actor,
            resource="detection_config",
            level=AuditLevel.WARNING,  # Config changes are notable
            details={
                "old_threshold": old_threshold,
                "new_threshold": new_threshold,
                "reason": reason,
            },
        )

    def log_security_event(
        self,
        action: AuditAction,
        actor: str,
        resource: str,
        level: AuditLevel,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent | None:
        """Log security-related event."""
        return self.log(
            action=action,
            actor=actor,
            resource=resource,
            level=level,
            details=details,
        )

    def query(
        self,
        action: AuditAction | None = None,
        actor: str | None = None,
        level: AuditLevel | None = None,
        since: datetime | None = None,
    ) -> list[AuditEvent]:
        """Query audit log with filters.

        Args:
            action: Filter by action type
            actor: Filter by actor
            level: Filter by minimum level
            since: Filter by timestamp

        Returns:
            Matching audit events
        """
        results = self.events

        if action:
            results = [e for e in results if e.action == action]

        if actor:
            results = [e for e in results if e.actor == actor]

        if level:
            results = [e for e in results 
                      if self.level_priority[e.level] >= self.level_priority[level]]

        if since:
            results = [e for e in results if e.timestamp >= since]

        return results

    def get_recent_events(
        self,
        count: int = 100,
        level: AuditLevel | None = None,
    ) -> list[AuditEvent]:
        """Get most recent events."""
        events = self.events
        if level:
            events = [e for e in events 
                     if self.level_priority[e.level] >= self.level_priority[level]]
        return events[-count:]

    def export_to_csv(self, output_path: Path) -> int:
        """Export audit log to CSV.

        Returns count of events exported.
        """
        if not self.events:
            return 0

        rows = [e.to_db_row() for e in self.events]
        df = pd.DataFrame(rows)
        df.to_csv(output_path, index=False)
        return len(rows)

    def get_summary(self) -> dict[str, Any]:
        """Get audit log summary statistics."""
        if not self.events:
            return {
                "total_events": 0,
                "events_by_action": {},
                "events_by_level": {},
                "unique_actors": [],
            }

        by_action: dict[str, int] = {}
        by_level: dict[str, int] = {}
        actors: set[str] = set()

        for e in self.events:
            by_action[e.action.value] = by_action.get(e.action.value, 0) + 1
            by_level[e.level.value] = by_level.get(e.level.value, 0) + 1
            actors.add(e.actor)

        return {
            "total_events": len(self.events),
            "events_by_action": by_action,
            "events_by_level": by_level,
            "unique_actors": list(actors),
        }


def export_audit_csv(
    audit_csv: Path,
    output_report: Path,
) -> dict[str, Any]:
    """CLI helper: Export audit log summary from CSV.

    Returns summary statistics.
    """
    df = pd.read_csv(audit_csv, parse_dates=["timestamp"])
    
    summary = {
        "total_events": len(df),
        "events_by_action": df["action"].value_counts().to_dict(),
        "events_by_level": df["level"].value_counts().to_dict(),
        "unique_actors": df["actor"].unique().tolist(),
        "date_range": {
            "start": df["timestamp"].min().isoformat() if not df.empty else None,
            "end": df["timestamp"].max().isoformat() if not df.empty else None,
        },
    }

    import json
    with open(output_report, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    return summary

"""Inspection Queue: Manage prioritized list of meters for field inspection.

Generates daily inspection queues from detection results, ranked by
confidence score and financial impact. Supports filtering by zone,
feeder, and risk level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class InspectionItem:
    """Single item in the inspection queue."""

    meter_id: str
    dt_id: str
    feeder_id: str
    zone: str | None
    date: date

    # Ranking
    confidence: float  # 0-1 detection confidence
    estimated_inr_lost: float | None  # Financial impact
    rank: int  # Position in queue (1 = highest priority)

    # Detection context
    anomaly_type: str
    description: str

    # Assignment
    status: str = "pending"  # pending, assigned, completed, dismissed
    assigned_to: str | None = None
    scheduled_date: date | None = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_db_row(self) -> dict[str, Any]:
        """Serialize to dict for inspection_queue table."""
        return {
            "meter_id": self.meter_id,
            "dt_id": self.dt_id,
            "feeder_id": self.feeder_id,
            "zone": self.zone,
            "date": self.date,
            "confidence": self.confidence,
            "estimated_inr_lost": self.estimated_inr_lost,
            "rank": self.rank,
            "anomaly_type": self.anomaly_type,
            "description": self.description,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "scheduled_date": self.scheduled_date,
            "created_at": self.created_at,
        }


class InspectionQueue:
    """Generate and manage daily inspection queues.

    Converts detection results into prioritized work orders
    for field inspection teams.
    """

    def __init__(
        self,
        max_queue_size: int = 100,  # Top N meters per day
        min_confidence: float = 0.5,  # Only above this threshold
    ) -> None:
        self.max_queue_size = max_queue_size
        self.min_confidence = min_confidence

    def generate(
        self,
        detection_results: pd.DataFrame,  # From confidence engine
        leakage_estimates: pd.DataFrame,  # From leakage quantifier
        topology_df: pd.DataFrame,  # meter_id, zone, etc.
        target_date: date,
    ) -> list[InspectionItem]:
        """Generate inspection queue for a single day.

        Args:
            detection_results: DataFrame with confidence scores and anomaly types
            leakage_estimates: DataFrame with financial impact estimates
            topology_df: DataFrame with zone and location info
            target_date: Date for queue generation

        Returns:
            List of InspectionItem sorted by priority (rank 1 = highest)
        """
        # Merge detection results with leakage estimates
        merged = detection_results.merge(
            leakage_estimates[["meter_id", "estimated_inr_lost"]],
            on="meter_id",
            how="left"
        )

        # Merge with topology for zone info
        merged = merged.merge(topology_df, on="meter_id", how="left")

        # Filter by confidence threshold
        qualified = merged[merged["confidence"] >= self.min_confidence]

        # Sort by confidence descending, then by financial impact
        qualified = qualified.sort_values(
            by=["confidence", "estimated_inr_lost"],
            ascending=[False, False]
        )

        # Take top N
        top_n = qualified.head(self.max_queue_size)

        # Create inspection items
        items: list[InspectionItem] = []
        for rank, (_, row) in enumerate(top_n.iterrows(), 1):
            item = InspectionItem(
                meter_id=str(row["meter_id"]),
                dt_id=str(row.get("dt_id", "")),
                feeder_id=str(row.get("feeder_id", "")),
                zone=str(row.get("zone")) if pd.notna(row.get("zone")) else None,
                date=target_date,
                confidence=float(row["confidence"]),
                estimated_inr_lost=float(row["estimated_inr_lost"]) if pd.notna(row.get("estimated_inr_lost")) else None,
                rank=rank,
                anomaly_type=str(row.get("anomaly_type", "unknown")),
                description=str(row.get("description", "")),
                status="pending",
                assigned_to=None,
                scheduled_date=None,
            )
            items.append(item)

        return items

    def assign(
        self,
        item: InspectionItem,
        inspector_id: str,
        scheduled_date: date,
    ) -> InspectionItem:
        """Assign an inspection item to a field inspector.

        Args:
            item: Inspection item to assign
            inspector_id: ID of assigned inspector
            scheduled_date: Date of scheduled inspection

        Returns:
            Updated InspectionItem
        """
        item.assigned_to = inspector_id
        item.scheduled_date = scheduled_date
        item.status = "assigned"
        return item

    def complete(
        self,
        item: InspectionItem,
        findings: str,
        actual_theft: bool = False,
    ) -> InspectionItem:
        """Mark inspection as completed.

        Args:
            item: Inspection item to complete
            findings: Inspector's findings/description
            actual_theft: Whether theft was confirmed

        Returns:
            Updated InspectionItem
        """
        item.status = "completed"
        # Note: findings would be stored separately in a detailed report table
        return item

    def dismiss(
        self,
        item: InspectionItem,
        reason: str,
    ) -> InspectionItem:
        """Dismiss item from queue (false positive).

        Args:
            item: Inspection item to dismiss
            reason: Reason for dismissal

        Returns:
            Updated InspectionItem
        """
        item.status = "dismissed"
        # Note: reason would be stored separately for feedback
        return item

    def filter_by_zone(
        self,
        items: list[InspectionItem],
        zone: str,
    ) -> list[InspectionItem]:
        """Filter queue items by zone."""
        return [item for item in items if item.zone == zone]

    def filter_by_feeder(
        self,
        items: list[InspectionItem],
        feeder_id: str,
    ) -> list[InspectionItem]:
        """Filter queue items by feeder."""
        return [item for item in items if item.feeder_id == feeder_id]

    def get_pending(self, items: list[InspectionItem]) -> list[InspectionItem]:
        """Get only pending items."""
        return [item for item in items if item.status == "pending"]


def generate_queue_csv(
    detections_csv: Path,
    leakage_csv: Path,
    topology_csv: Path,
    target_date: date,
    output_csv: Path,
    max_size: int = 100,
) -> int:
    """CLI helper: generate queue from CSVs and write output.

    Returns count of items in queue.
    """
    detection_results = pd.read_csv(detections_csv, parse_dates=["date"])
    leakage_estimates = pd.read_csv(leakage_csv)
    topology_df = pd.read_csv(topology_csv)

    queue = InspectionQueue(max_queue_size=max_size)
    items = queue.generate(detection_results, leakage_estimates, topology_df, target_date)

    if items:
        rows = [item.to_db_row() for item in items]
        df = pd.DataFrame(rows)
        df.to_csv(output_csv, index=False)

    return len(items)

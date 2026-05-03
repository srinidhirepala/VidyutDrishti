"""FastAPI REST API routes for VidyutDrishti.

Endpoints:
- POST /api/v1/ingest/batch - Ingest meter readings
- GET /api/v1/meters/{meter_id}/status - Get meter anomaly status
- GET /api/v1/queue/daily - Get daily inspection queue
- POST /api/v1/feedback - Submit inspection feedback
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

# Try to import app modules - may not be available during testing
try:
    from app.ingestion.pipeline import IngestionPipeline
    from app.detection.confidence import ConfidenceEngine, LayerSignals
    from app.inspection.queue import InspectionQueue
    INGESTION_AVAILABLE = True
except ImportError:
    INGESTION_AVAILABLE = False

router = APIRouter()  # Prefix applied in main.py for compatibility


# ========== Request/Response Models ==========

class BatchIngestRequest(BaseModel):
    """Request model for batch meter reading ingestion."""
    meter_id: str
    timestamp: str
    kwh: float
    voltage: float | None = None
    pf: float | None = None


class BatchIngestResponse(BaseModel):
    """Response model for batch ingestion."""
    records_received: int
    records_valid: int
    records_written: int


class MeterStatusResponse(BaseModel):
    """Response model for meter status."""
    meter_id: str
    date: date
    confidence: float | None
    is_anomaly: bool
    anomaly_type: str | None
    layer_signals: dict[str, Any] | None


class QueueItem(BaseModel):
    """Inspection queue item."""
    rank: int
    meter_id: str
    dt_id: str
    feeder_id: str
    zone: str | None
    confidence: float
    estimated_inr_lost: float | None
    anomaly_type: str
    description: str
    status: str


class DailyQueueResponse(BaseModel):
    """Response model for daily inspection queue."""
    date: date
    total_items: int
    pending_items: int
    items: list[QueueItem]


class FeedbackRequest(BaseModel):
    """Request model for inspection feedback."""
    meter_id: str
    inspection_date: date
    was_anomaly: bool
    actual_kwh_observed: float | None = None
    notes: str | None = None


class FeedbackResponse(BaseModel):
    """Response model for feedback submission."""
    success: bool
    message: str


# ========== Mock Data Store (for prototype) ==========

class MockDataStore:
    """In-memory mock data store for prototype API."""

    def __init__(self) -> None:
        self.readings: list[dict] = []
        self.detections: list[dict] = []
        self.queue: list[dict] = []
        self.feedback: list[dict] = []

    def add_readings(self, readings: list[BatchIngestRequest]) -> tuple[int, int, int]:
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
        # Return mock data if meter exists in readings
        meter_readings = [r for r in self.readings if r["meter_id"] == meter_id]
        if not meter_readings:
            return None

        # Mock detection result
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

    def get_queue(self, target_date: date) -> list[dict]:
        """Get mock inspection queue."""
        if not self.queue:
            # Return default mock queue
            return [
                {
                    "rank": 1,
                    "meter_id": "M001",
                    "dt_id": "DT001",
                    "feeder_id": "F001",
                    "zone": "ZoneA",
                    "confidence": 0.85,
                    "estimated_inr_lost": 1250.0,
                    "anomaly_type": "sudden_drop",
                    "description": "40% consumption drop detected",
                    "status": "pending",
                },
                {
                    "rank": 2,
                    "meter_id": "M042",
                    "dt_id": "DT007",
                    "feeder_id": "F003",
                    "zone": "ZoneB",
                    "confidence": 0.72,
                    "estimated_inr_lost": 890.0,
                    "anomaly_type": "flatline",
                    "description": "95% zero readings",
                    "status": "pending",
                },
            ]
        return [q for q in self.queue if q.get("date") == target_date]

    def add_feedback(self, feedback: FeedbackRequest) -> bool:
        """Add inspection feedback."""
        self.feedback.append({
            "meter_id": feedback.meter_id,
            "inspection_date": feedback.inspection_date,
            "was_anomaly": feedback.was_anomaly,
            "actual_kwh_observed": feedback.actual_kwh_observed,
            "notes": feedback.notes,
        })
        return True


# Global mock store
store = MockDataStore()


# ========== API Routes ==========

@router.post("/ingest/batch", response_model=BatchIngestResponse)
async def ingest_batch(readings: list[BatchIngestRequest]) -> BatchIngestResponse:
    """Ingest batch of meter readings.

    Accepts a batch of 15-minute interval readings for processing.
    Returns counts of received, validated, and stored records.
    """
    received, valid, written = store.add_readings(readings)

    return BatchIngestResponse(
        records_received=received,
        records_valid=valid,
        records_written=written,
    )


@router.get("/meters/{meter_id}/status", response_model=MeterStatusResponse)
async def get_meter_status(
    meter_id: str,
    target_date: date = Query(default_factory=date.today),
) -> MeterStatusResponse:
    """Get anomaly detection status for a specific meter.

    Returns confidence score, anomaly flag, layer signals,
    and classification for the specified meter and date.
    """
    status = store.get_meter_status(meter_id, target_date)

    if status is None:
        raise HTTPException(status_code=404, detail=f"Meter {meter_id} not found")

    return MeterStatusResponse(
        meter_id=status["meter_id"],
        date=status["date"],
        confidence=status["confidence"],
        is_anomaly=status["is_anomaly"],
        anomaly_type=status["anomaly_type"],
        layer_signals=status["layer_signals"],
    )


@router.get("/queue/daily", response_model=DailyQueueResponse)
async def get_daily_queue(
    target_date: date = Query(default_factory=date.today),
) -> DailyQueueResponse:
    """Get prioritized inspection queue for a specific date.

    Returns ranked list of meters requiring inspection,
    including confidence scores and estimated financial impact.
    """
    queue_items = store.get_queue(target_date)

    items = [
        QueueItem(
            rank=item["rank"],
            meter_id=item["meter_id"],
            dt_id=item["dt_id"],
            feeder_id=item["feeder_id"],
            zone=item.get("zone"),
            confidence=item["confidence"],
            estimated_inr_lost=item.get("estimated_inr_lost"),
            anomaly_type=item["anomaly_type"],
            description=item["description"],
            status=item["status"],
        )
        for item in queue_items
    ]

    pending = [i for i in items if i.status == "pending"]

    return DailyQueueResponse(
        date=target_date,
        total_items=len(items),
        pending_items=len(pending),
        items=items,
    )


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(feedback: FeedbackRequest) -> FeedbackResponse:
    """Submit inspection feedback for recalibration.

    Records whether an anomaly was confirmed or dismissed,
    enabling model recalibration and accuracy tracking.
    """
    success = store.add_feedback(feedback)

    if success:
        return FeedbackResponse(
            success=True,
            message=f"Feedback recorded for meter {feedback.meter_id}",
        )
    else:
        raise HTTPException(status_code=500, detail="Failed to record feedback")

"""FastAPI entrypoint.

Feature 01 provides a stub with /health only. The full API surface
(forecast, zone-risk, inspection-queue, meter, audit, feedback) is
implemented in Feature 17.
"""

from __future__ import annotations

from fastapi import FastAPI

from app import __version__
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="AT&C Loss Recovery Intelligence System - prototype API.",
)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Liveness probe. Does not touch the database."""
    return {"status": "ok", "service": settings.app_name, "version": __version__}

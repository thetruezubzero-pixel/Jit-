"""Health check router."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/", summary="Health check")
async def health_check() -> dict:
    """Return API health status."""
    return {"status": "ok", "service": "Jit Accounting & Legal Analysis System", "version": "0.1.0"}

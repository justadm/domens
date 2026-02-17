from fastapi import APIRouter

from app.monitoring_runtime import monitoring_service

router = APIRouter(prefix="/v1/monitoring", tags=["monitoring"])


@router.post("/run-once")
async def run_monitor_once() -> dict:
    return await monitoring_service.run_once()

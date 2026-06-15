from fastapi import APIRouter, Request

from app.monitoring_runtime import monitoring_service
from app.routers.guards import require_admin_user

router = APIRouter(prefix="/v1/monitoring", tags=["monitoring"])


@router.post("/run-once")
async def run_monitor_once(request: Request) -> dict:
    require_admin_user(request)
    return await monitoring_service.run_once()

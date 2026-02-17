from fastapi import APIRouter, Query

from app.state import store

router = APIRouter(prefix="/v1/activity", tags=["activity"])


@router.get("/recent")
async def recent_activity(limit: int = Query(default=20, ge=1, le=100)) -> dict:
    return {"items": store.list_recent_activity(limit=limit)}

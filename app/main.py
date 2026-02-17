from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.monitoring_runtime import monitoring_service
from app.routers.activity import router as activity_router
from app.routers.alerts import router as alerts_router
from app.routers.auth import router as auth_router
from app.routers.domains import router as domains_router
from app.routers.max import router as max_router
from app.routers.monitoring import router as monitoring_router
from app.routers.registrations import router as registrations_router
from app.routers.telegram import router as telegram_router
from app.schemas import HealthResponse

app = FastAPI(title="Domens MVP", version="0.1.0")
web_dir = Path(__file__).resolve().parent.parent / "web"

app.include_router(domains_router)
app.include_router(alerts_router)
app.include_router(registrations_router)
app.include_router(telegram_router)
app.include_router(max_router)
app.include_router(monitoring_router)
app.include_router(activity_router)
app.include_router(auth_router)
app.mount("/web", StaticFiles(directory=web_dir), name="web")


@app.get("/", include_in_schema=False)
async def web_index() -> FileResponse:
    return FileResponse(web_dir / "index.html")


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@app.on_event("startup")
async def startup_monitor() -> None:
    await monitoring_service.start()


@app.on_event("shutdown")
async def shutdown_monitor() -> None:
    await monitoring_service.stop()

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.monitoring_runtime import monitoring_service
from app.routers.activity import router as activity_router
from app.routers.admin import router as admin_router
from app.routers.alerts import router as alerts_router
from app.routers.auth import router as auth_router
from app.routers.cabinet import router as cabinet_router
from app.routers.copilot import router as copilot_router
from app.routers.domains import router as domains_router
from app.routers.max import router as max_router
from app.routers.monitoring import router as monitoring_router
from app.routers.registrations import router as registrations_router
from app.routers.telegram import router as telegram_router
from app.schemas import HealthResponse
from app.state import store
from app.telegram_polling_runtime import telegram_polling_service

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
app.include_router(cabinet_router)
app.include_router(admin_router)
app.include_router(copilot_router)
app.mount("/web", StaticFiles(directory=web_dir), name="web")


@app.get("/", include_in_schema=False)
async def web_index() -> FileResponse:
    return FileResponse(web_dir / "index.html")


@app.get("/admin", include_in_schema=False)
@app.get("/admin/", include_in_schema=False)
async def web_admin_index() -> RedirectResponse:
    return RedirectResponse(url="/?mode=admin#cabinet-section", status_code=307)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@app.on_event("startup")
async def startup_monitor() -> None:
    store.ensure_base_roles()
    env_admin_ids = [item.strip() for item in str(settings.telegram_admin_user_ids or "").split(",") if item.strip()]
    if env_admin_ids:
        store.sync_admin_roles_from_env(env_admin_ids, granted_by="startup:env")
    await monitoring_service.start()
    await telegram_polling_service.start()


@app.on_event("shutdown")
async def shutdown_monitor() -> None:
    await monitoring_service.stop()
    await telegram_polling_service.stop()

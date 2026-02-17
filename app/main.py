from fastapi import FastAPI

from app.routers.alerts import router as alerts_router
from app.routers.domains import router as domains_router
from app.routers.registrations import router as registrations_router
from app.routers.telegram import router as telegram_router
from app.schemas import HealthResponse

app = FastAPI(title="Domens MVP", version="0.1.0")

app.include_router(domains_router)
app.include_router(alerts_router)
app.include_router(registrations_router)
app.include_router(telegram_router)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()

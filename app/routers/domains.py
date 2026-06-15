import asyncio

from fastapi import APIRouter, Request

from app.config import settings
from app.routers.guards import require_admin_user
from app.schemas import (
    CandidateIngestRequest,
    CandidateIngestResponse,
    DomainCheckRequest,
    DomainCheckResponse,
    DomainCheckResult,
)
from app.services.domain_checker import infer_status
from app.services.domain_scoring import score_domain
from app.services.timeweb_api import TimewebApiClient

router = APIRouter(prefix="/v1/domains", tags=["domains"])
timeweb_client = TimewebApiClient(
    base_url=settings.timeweb_api_base_url, api_token=settings.timeweb_api_token
)


@router.post("/check", response_model=DomainCheckResponse)
async def check_domains(payload: DomainCheckRequest, request: Request) -> DomainCheckResponse:
    require_admin_user(request)

    async def check_one(domain: str) -> DomainCheckResult:
        status, eta = await infer_status(domain, timeweb_client=timeweb_client)
        return DomainCheckResult(
            domain=domain,
            status=status,
            score=score_domain(domain),
            drop_time_estimated_at=eta,
        )

    results: list[DomainCheckResult] = []
    if payload.domains:
        results = await asyncio.gather(*(check_one(domain) for domain in payload.domains))

    return DomainCheckResponse(results=results)


@router.post("/candidates", response_model=CandidateIngestResponse, status_code=202)
async def add_candidates(payload: CandidateIngestRequest, request: Request) -> CandidateIngestResponse:
    require_admin_user(request)
    return CandidateIngestResponse(accepted=len(payload.candidates))

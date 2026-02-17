from fastapi import APIRouter

from app.schemas import (
    CandidateIngestRequest,
    CandidateIngestResponse,
    DomainCheckRequest,
    DomainCheckResponse,
    DomainCheckResult,
)
from app.services.domain_checker import infer_status
from app.services.domain_scoring import score_domain

router = APIRouter(prefix="/v1/domains", tags=["domains"])


@router.post("/check", response_model=DomainCheckResponse)
async def check_domains(payload: DomainCheckRequest) -> DomainCheckResponse:
    results: list[DomainCheckResult] = []
    for domain in payload.domains:
        status, eta = infer_status(domain)
        results.append(
            DomainCheckResult(
                domain=domain,
                status=status,
                score=score_domain(domain),
                drop_time_estimated_at=eta,
            )
        )

    return DomainCheckResponse(results=results)


@router.post("/candidates", response_model=CandidateIngestResponse, status_code=202)
async def add_candidates(payload: CandidateIngestRequest) -> CandidateIngestResponse:
    return CandidateIngestResponse(accepted=len(payload.candidates))

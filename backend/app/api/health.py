from __future__ import annotations

from fastapi import APIRouter

from ..llm import client
from ..schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(contract_version="1", llm_mode=client.mode)

from __future__ import annotations

from fastapi import APIRouter

from .. import db
from ..llm import client as llm_client
from ..schemas import ReportResponse
from ..services.report import build_markdown
from .deps import require_dataset

router = APIRouter(tags=["report"])


@router.post("/api/report/{dataset_id}", response_model=ReportResponse)
def report(dataset_id: str) -> ReportResponse:
    dataset = require_dataset(dataset_id)
    quality = db.loads(dataset.quality_json, None)
    result = build_markdown(
        dataset_id,
        db.fetch_finding_payloads(dataset_id),
        db.fetch_actions(dataset_id),
        db.fetch_tasks(dataset_id),
        quality,
        llm_client,
    )
    return ReportResponse.model_validate(result)

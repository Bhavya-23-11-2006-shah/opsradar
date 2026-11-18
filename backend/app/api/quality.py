from __future__ import annotations

from fastapi import APIRouter

from .. import db
from ..schemas import QualityResponse
from .deps import require_dataset

router = APIRouter(tags=["quality"])


@router.get("/api/quality/{dataset_id}", response_model=QualityResponse)
def quality(dataset_id: str) -> QualityResponse:
    dataset = require_dataset(dataset_id)
    stored = db.loads(dataset.quality_json, None)
    if not stored:
        return QualityResponse(
            missing=[],
            duplicates=[],
            inconsistent=[],
            health_score=0,
            summary="Analysis has not run yet, so no quality checks are available.",
        )
    return QualityResponse.model_validate(stored)

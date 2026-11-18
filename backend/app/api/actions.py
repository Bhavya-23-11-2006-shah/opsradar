from __future__ import annotations

from fastapi import APIRouter

from .. import db
from ..schemas import ActionsResponse
from .deps import require_dataset

router = APIRouter(tags=["actions"])


@router.get("/api/actions/{dataset_id}", response_model=ActionsResponse)
def actions(dataset_id: str) -> ActionsResponse:
    require_dataset(dataset_id)
    return ActionsResponse(
        log=db.fetch_actions(dataset_id),
        tasks=db.fetch_tasks(dataset_id),
    )

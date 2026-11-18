from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks

from .. import db
from ..schemas import AnalyzeResponse, ProgressResponse
from ..services.pipeline import run_pipeline
from .deps import require_dataset

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])


@router.post("/api/analyze/{dataset_id}", response_model=AnalyzeResponse)
def analyze(dataset_id: str, background_tasks: BackgroundTasks) -> AnalyzeResponse:
    dataset = require_dataset(dataset_id)
    if dataset.status == "running":
        return AnalyzeResponse()
    if not dataset.mapping_json:
        db.set_progress(
            dataset_id,
            status="error",
            step=None,
            percent=0,
            message="Confirm a schema mapping before running the analysis.",
        )
        return AnalyzeResponse()

    db.set_progress(dataset_id, status="running", step="Cleaning", percent=1, message="Starting analysis")
    background_tasks.add_task(run_pipeline, dataset_id)
    logger.info("analysis queued for %s", dataset_id)
    return AnalyzeResponse()


@router.get("/api/progress/{dataset_id}", response_model=ProgressResponse)
def progress(dataset_id: str) -> ProgressResponse:
    dataset = require_dataset(dataset_id)
    return ProgressResponse(
        status=dataset.status or "idle",
        step=dataset.step if dataset.step else None,
        percent=float(dataset.percent or 0.0),
        message=dataset.message,
    )

from __future__ import annotations

import logging

from fastapi import APIRouter

from ..schemas import DemoRequest, UploadResponse
from ..services import demo_data

logger = logging.getLogger(__name__)

router = APIRouter(tags=["demo"])


@router.post("/api/demo/generate", response_model=UploadResponse)
def generate_demo(payload: DemoRequest) -> UploadResponse:
    result = demo_data.generate_dataset(payload.industry)
    return UploadResponse.model_validate(result)

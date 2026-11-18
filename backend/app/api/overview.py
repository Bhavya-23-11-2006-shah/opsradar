from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .. import db
from ..schemas import OverviewResponse
from ..services.overview import build_overview
from .deps import require_dataset

router = APIRouter(tags=["overview"])


@router.get("/api/overview/{dataset_id}", response_model=OverviewResponse)
def overview(
    dataset_id: str,
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
    product: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    courier: Optional[str] = Query(None),
) -> OverviewResponse:
    dataset = require_dataset(dataset_id)
    snapshot = db.loads(dataset.snapshot_json, None)
    if not snapshot:
        raise HTTPException(status_code=409, detail="Analysis has not run for this dataset yet.")

    for label, value in (("from", from_), ("to", to)):
        if value:
            try:
                date.fromisoformat(value[:10])
            except ValueError as exc:
                raise HTTPException(
                    status_code=422, detail=f"'{label}' must be an ISO date (YYYY-MM-DD)."
                ) from exc

    result = build_overview(
        snapshot,
        from_date=from_,
        to_date=to,
        product=product,
        location=location,
        courier=courier,
    )
    return OverviewResponse.model_validate(result)

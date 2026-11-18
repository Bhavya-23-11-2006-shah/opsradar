from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from .. import db
from ..config import ACTOR
from ..schemas import (
    DECISION_STATUS,
    DecisionRequest,
    Finding,
    FindingType,
    InvestigationTask,
    Severity,
    Status,
    StatusRequest,
    TaskRequest,
)
from .deps import require_dataset, require_finding

router = APIRouter(tags=["findings"])

PREVIEW_EVIDENCE = 5


def _preview(payload: dict) -> dict:
    preview = dict(payload)
    preview["evidenceRows"] = list(payload.get("evidenceRows", []))[:PREVIEW_EVIDENCE]
    return preview


def _matches(
    payload: dict,
    finding_type: Optional[str],
    severity: Optional[str],
    status: Optional[str],
    search: Optional[str],
) -> bool:
    if finding_type and payload.get("type") != finding_type:
        return False
    if severity and payload.get("severity") != severity:
        return False
    if status and payload.get("status") != status:
        return False
    if search:
        needle = search.strip().lower()
        entities = payload.get("relatedEntities", {})
        haystack = " ".join(
            [
                payload.get("title", ""),
                payload.get("summary", ""),
                payload.get("businessImpact", ""),
                payload.get("recommendation", {}).get("action", ""),
                " ".join(entities.get("products", [])),
                " ".join(entities.get("locations", [])),
                " ".join(entities.get("couriers", [])),
                " ".join(entities.get("orders", [])),
            ]
        ).lower()
        if needle not in haystack:
            return False
    return True


@router.get("/api/findings/{dataset_id}", response_model=List[Finding])
def list_findings(
    dataset_id: str,
    finding_type: Optional[FindingType] = Query(None, alias="type"),
    severity: Optional[Severity] = Query(None),
    status: Optional[Status] = Query(None),
    search: Optional[str] = Query(None),
) -> List[Finding]:
    require_dataset(dataset_id)
    payloads = db.fetch_finding_payloads(dataset_id)
    filtered = [
        _preview(payload)
        for payload in payloads
        if _matches(payload, finding_type, severity, status, search)
    ]
    return [Finding.model_validate(payload) for payload in filtered]


@router.get("/api/findings/{dataset_id}/{finding_id}", response_model=Finding)
def get_finding(dataset_id: str, finding_id: str) -> Finding:
    require_dataset(dataset_id)
    payload = require_finding(dataset_id, finding_id)
    return Finding.model_validate(payload)


@router.post("/api/findings/{dataset_id}/{finding_id}/decision", response_model=Finding)
def decide(dataset_id: str, finding_id: str, body: DecisionRequest) -> Finding:
    require_dataset(dataset_id)
    payload = require_finding(dataset_id, finding_id)
    new_status = DECISION_STATUS[body.decision]
    payload["status"] = new_status
    db.update_finding_payload(dataset_id, payload)
    db.add_action(
        dataset_id,
        finding_id=finding_id,
        finding_title=payload.get("title", ""),
        decision=body.decision,
        note=body.note,
        actor=ACTOR,
    )
    return Finding.model_validate(payload)


@router.patch("/api/findings/{dataset_id}/{finding_id}/status", response_model=Finding)
def change_status(dataset_id: str, finding_id: str, body: StatusRequest) -> Finding:
    require_dataset(dataset_id)
    payload = require_finding(dataset_id, finding_id)
    payload["status"] = body.status
    db.update_finding_payload(dataset_id, payload)
    db.add_action(
        dataset_id,
        finding_id=finding_id,
        finding_title=payload.get("title", ""),
        decision="status_changed",
        note=f"Status changed to {body.status}.",
        actor=ACTOR,
    )
    return Finding.model_validate(payload)


@router.post("/api/findings/{dataset_id}/{finding_id}/task", response_model=InvestigationTask)
def create_task(dataset_id: str, finding_id: str, body: TaskRequest) -> InvestigationTask:
    require_dataset(dataset_id)
    payload = require_finding(dataset_id, finding_id)
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="A task title is required.")
    task = db.add_task(dataset_id, finding_id=finding_id, title=title)
    db.add_action(
        dataset_id,
        finding_id=finding_id,
        finding_title=payload.get("title", ""),
        decision="task_created",
        note=title,
        actor=ACTOR,
    )
    return InvestigationTask.model_validate(task)

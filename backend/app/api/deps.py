"""Shared API dependencies."""

from __future__ import annotations

from fastapi import HTTPException

from .. import db


def require_dataset(dataset_id: str):
    dataset = db.get_dataset(dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail=f"Unknown dataset '{dataset_id}'.")
    return dataset


def require_finding(dataset_id: str, finding_id: str) -> dict:
    payload = db.get_finding_payload(dataset_id, finding_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Unknown finding '{finding_id}'.")
    return payload

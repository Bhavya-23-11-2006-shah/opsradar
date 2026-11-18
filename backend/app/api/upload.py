from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile

from .. import db
from ..config import ALLOWED_EXTENSIONS, DATA_DIR, MAX_UPLOAD_BYTES
from ..schemas import (
    MapSchemaRequest,
    MapSchemaResponse,
    SchemaMapping,
    UploadedFile,
    UploadResponse,
)
from ..services import cleaning
from ..services.schema_mapper import suggest_mappings
from .deps import require_dataset

logger = logging.getLogger(__name__)

router = APIRouter(tags=["upload"])

CHUNK = 1024 * 1024


def _unique_name(name: str, used: set[str]) -> str:
    if name not in used:
        used.add(name)
        return name
    stem, suffix = Path(name).stem, Path(name).suffix
    counter = 2
    while f"{stem}_{counter}{suffix}" in used:
        counter += 1
    final = f"{stem}_{counter}{suffix}"
    used.add(final)
    return final


@router.post("/api/upload", response_model=UploadResponse)
async def upload_files(files: List[UploadFile] = File(..., description="CSV or Excel files")) -> UploadResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files were uploaded; the multipart field is 'files'.")

    dataset_id = f"ds-{uuid.uuid4().hex[:12]}"
    dataset_dir = DATA_DIR / "datasets" / dataset_id
    raw_dir = dataset_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    used_names: set[str] = set()
    frames = {}
    entries: list[dict] = []
    total_bytes = 0

    try:
        for index, upload in enumerate(files):
            safe_name = cleaning.sanitise_filename(upload.filename or f"upload_{index + 1}.csv")
            suffix = Path(safe_name).suffix.lower()
            if suffix not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=415,
                    detail=f"{safe_name}: only CSV, XLSX and XLS files are supported.",
                )
            safe_name = _unique_name(safe_name, used_names)
            target = raw_dir / safe_name

            written = 0
            with target.open("wb") as sink:
                while True:
                    chunk = await upload.read(CHUNK)
                    if not chunk:
                        break
                    written += len(chunk)
                    total_bytes += len(chunk)
                    if total_bytes > MAX_UPLOAD_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail=f"Upload exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
                        )
                    sink.write(chunk)
            await upload.close()

            if written == 0:
                raise HTTPException(status_code=422, detail=f"{safe_name} is empty.")

            try:
                frame = cleaning.read_table(target, safe_name)
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(
                    status_code=422,
                    detail=f"{safe_name} could not be parsed: {exc.__class__.__name__}.",
                ) from exc
            if len(frame.columns) == 0:
                raise HTTPException(status_code=422, detail=f"{safe_name} has no columns.")

            frames[safe_name] = frame
            entries.append(
                {
                    "_name": safe_name,
                    "_rows": int(len(frame)),
                    "_columns": [str(column) for column in frame.columns],
                }
            )

        mappings = suggest_mappings(frames)
        by_name = {mapping.file_name: mapping for mapping in mappings}
        upload_entries = []
        for entry in entries:
            mapping = by_name[entry["_name"]]
            upload_entries.append(
                UploadedFile(
                    name=entry["_name"],
                    detected_type=mapping.file_type,
                    rows=entry["_rows"],
                    columns=entry["_columns"],
                    suggested_mapping=mapping,
                )
            )

        db.create_dataset(
            dataset_id,
            industry=None,
            files=[entry.model_dump(by_alias=True) for entry in upload_entries],
        )
        db.update_dataset(
            dataset_id,
            mapping_json=SchemaMapping(files=mappings).model_dump_json(by_alias=True),
        )
        logger.info("upload stored dataset %s with %s files", dataset_id, len(upload_entries))
        return UploadResponse(dataset_id=dataset_id, files=upload_entries)
    except Exception:
        shutil.rmtree(dataset_dir, ignore_errors=True)
        raise


@router.post("/api/map-schema", response_model=MapSchemaResponse)
def map_schema(payload: MapSchemaRequest) -> MapSchemaResponse:
    require_dataset(payload.dataset_id)
    file_names = {mapping.file_name for mapping in payload.mapping.files}
    if not file_names:
        raise HTTPException(status_code=422, detail="The mapping must contain at least one file.")

    db.update_dataset(
        payload.dataset_id,
        mapping_json=payload.mapping.model_dump_json(by_alias=True),
    )
    logger.info("mapping confirmed for %s (%s files)", payload.dataset_id, len(payload.mapping.files))
    return MapSchemaResponse(dataset_id=payload.dataset_id, mapping=payload.mapping)

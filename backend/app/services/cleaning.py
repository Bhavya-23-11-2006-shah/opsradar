"""Loading, normalisation and the data-quality report."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

from ..schemas import FileMapping, QualityResponse, SchemaMapping

logger = logging.getLogger(__name__)

DATE_FIELDS = ["date", "promisedDate", "shippedDate", "deliveredDate"]
NUMERIC_FIELDS = ["stock", "dailySalesRate", "reorderLevel", "quantity", "amount", "rating"]
ROW_CAP = 50

STATUS_ALIASES = {
    "delivered": "delivered",
    "complete": "delivered",
    "completed": "delivered",
    "fulfilled": "delivered",
    "shipped": "shipped",
    "dispatched": "shipped",
    "in transit": "in_transit",
    "in_transit": "in_transit",
    "intransit": "in_transit",
    "pending": "pending",
    "processing": "pending",
    "open": "open",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "returned": "returned",
    "rto": "returned",
}


@dataclass
class CleaningResult:
    frames: dict[str, pd.DataFrame]
    quality: dict
    notes: list[str] = field(default_factory=list)
    row_counts: dict[str, int] = field(default_factory=dict)


def sanitise_filename(name: str) -> str:
    base = Path(str(name).replace("\\", "/")).name
    base = base.strip() or "upload.csv"
    cleaned = "".join(ch for ch in base if ch.isalnum() or ch in {".", "_", "-", " "}).strip()
    cleaned = cleaned.replace(" ", "_")
    if not cleaned or cleaned.startswith("."):
        cleaned = f"upload_{cleaned or 'file'}"
    return cleaned[:120]


def read_table(path: Path, file_name: str) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, sheet_name=0)
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return pd.read_csv(path, encoding=encoding, sep=None, engine="python")
        except UnicodeDecodeError:
            continue
        except Exception:
            break
    return pd.read_csv(path)


def _read_raw_frames(dataset_dir: Path, mapping: SchemaMapping) -> tuple[dict[str, pd.DataFrame], list[str]]:
    frames: dict[str, pd.DataFrame] = {}
    notes: list[str] = []
    raw_dir = dataset_dir / "raw"
    for file_mapping in mapping.files:
        path = raw_dir / file_mapping.file_name
        if not path.exists():
            notes.append(f"{file_mapping.file_name} is listed in the mapping but missing on disk; skipped.")
            continue
        try:
            frame = read_table(path, file_mapping.file_name)
        except Exception as exc:  # noqa: BLE001 - unreadable input must not kill the run
            notes.append(f"{file_mapping.file_name} could not be parsed ({exc.__class__.__name__}); skipped.")
            continue

        frame = frame.copy()
        frame["_row_id"] = [f"{file_mapping.file_name}:{position + 2}" for position in range(len(frame))]
        frame["_file"] = file_mapping.file_name

        rename: dict[str, str] = {}
        for canonical, column in (file_mapping.fields or {}).items():
            if column and column in frame.columns and canonical not in rename.values():
                rename[column] = canonical
        frame = frame.rename(columns=rename)
        frames[file_mapping.file_name] = frame
        notes.append(f"{file_mapping.file_name}: {len(frame)} rows, type {file_mapping.file_type}.")
    return frames, notes


def _to_iso(value) -> Optional[str]:
    if value is None or pd.isna(value):
        return None
    try:
        return pd.Timestamp(value).date().isoformat()
    except Exception:  # noqa: BLE001
        return None


def _normalise_frame(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()
    for column in df.columns:
        if df[column].dtype == object or str(df[column].dtype).startswith("string"):
            df[column] = df[column].map(
                lambda value: " ".join(str(value).split()).strip() if isinstance(value, str) else value
            )
            df[column] = df[column].replace({"": None, "nan": None, "NaN": None, "None": None, "null": None})

    for column in DATE_FIELDS:
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], errors="coerce", format="mixed")

    for column in NUMERIC_FIELDS:
        if column in df.columns:
            df[column] = pd.to_numeric(
                df[column].astype("string").str.replace(r"[£$€,\s]", "", regex=True),
                errors="coerce",
            )

    if "status" in df.columns:
        df["status"] = df["status"].map(
            lambda value: STATUS_ALIASES.get(str(value).strip().lower(), str(value).strip().lower())
            if value is not None and not pd.isna(value)
            else None
        )

    if "category" in df.columns:
        df["category"] = df["category"].map(
            lambda value: " ".join(str(value).split()).strip()
            if value is not None and not pd.isna(value)
            else None
        )

    for key in ("orderId", "productId", "customerId", "courier", "warehouse", "city"):
        if key in df.columns:
            df[key] = df[key].map(
                lambda value: str(value).strip() if value is not None and not pd.isna(value) else None
            )
    return df


def _issue_row_ids(df: pd.DataFrame, mask: pd.Series, cap: int = ROW_CAP) -> list[str]:
    if "_row_id" not in df.columns or mask is None:
        return []
    selected = df.loc[mask.fillna(False), "_row_id"].astype(str).tolist()
    return selected[:cap]


def _missing_issues(frames: dict[str, pd.DataFrame]) -> list[dict]:
    issues: list[dict] = []
    for file_name, df in frames.items():
        for column in df.columns:
            if str(column).startswith("_") or df[column].isna().sum() == 0:
                continue
            mask = df[column].isna()
            count = int(mask.sum())
            share = count / max(len(df), 1) * 100
            issues.append(
                {
                    "file": file_name,
                    "column": str(column),
                    "count": count,
                    "rowIds": _issue_row_ids(df, mask),
                    "note": f"{count} of {len(df)} values missing in {column} ({share:.1f}%).",
                }
            )
    issues.sort(key=lambda item: item["count"], reverse=True)
    return issues[:20]


def _duplicate_issues(frames: dict[str, pd.DataFrame]) -> list[dict]:
    issues: list[dict] = []
    for file_name, df in frames.items():
        data_columns = [column for column in df.columns if not str(column).startswith("_")]
        mask = df.duplicated(subset=data_columns, keep="first")
        if int(mask.sum()) > 0:
            count = int(mask.sum())
            issues.append(
                {
                    "file": file_name,
                    "column": None,
                    "count": count,
                    "rowIds": _issue_row_ids(df, mask),
                    "note": f"{count} exact duplicate rows found in {file_name} (first occurrence kept).",
                }
            )
        if "orderId" in df.columns and df["orderId"].notna().any():
            dup_mask = df["orderId"].duplicated(keep="first") & df["orderId"].notna()
            if int(dup_mask.sum()) > 0:
                issues.append(
                    {
                        "file": file_name,
                        "column": "orderId",
                        "count": int(dup_mask.sum()),
                        "rowIds": _issue_row_ids(df, dup_mask),
                        "note": f"{int(dup_mask.sum())} rows repeat an orderId already seen in {file_name}.",
                    }
                )
    return issues


def _inconsistent_issues(frames: dict[str, pd.DataFrame], dataset_dir: Path, mapping: SchemaMapping) -> list[dict]:
    issues: list[dict] = []
    today = pd.Timestamp(date.today())
    inventory_products: set[str] = set()
    for file_name, df in frames.items():
        kind = next((f.file_type for f in mapping.files if f.file_name == file_name), "unknown")
        if kind == "inventory" and "productId" in df.columns:
            inventory_products.update(df["productId"].dropna().astype(str))

    def add(file_name: str, column: Optional[str], mask: pd.Series, note: str) -> None:
        df = frames[file_name]
        count = int(mask.fillna(False).sum())
        if count == 0:
            return
        issues.append(
            {
                "file": file_name,
                "column": column,
                "count": count,
                "rowIds": _issue_row_ids(df, mask),
                "note": note.format(count=count),
            }
        )

    for file_name, df in frames.items():
        if {"deliveredDate", "shippedDate"} <= set(df.columns):
            mask = df["deliveredDate"].notna() & df["shippedDate"].notna() & (df["deliveredDate"] < df["shippedDate"])
            add(file_name, "deliveredDate", mask, "{count} rows delivered before they shipped.")
        if {"deliveredDate", "date"} <= set(df.columns):
            mask = df["deliveredDate"].notna() & df["date"].notna() & (df["deliveredDate"] < df["date"])
            add(file_name, "deliveredDate", mask, "{count} rows delivered before the order date.")
        if "stock" in df.columns:
            mask = df["stock"].notna() & (df["stock"] < 0)
            add(file_name, "stock", mask, "{count} rows carry negative stock.")
        if "quantity" in df.columns:
            mask = df["quantity"].notna() & (df["quantity"] < 0)
            add(file_name, "quantity", mask, "{count} rows carry negative quantity.")
        if "rating" in df.columns:
            mask = df["rating"].notna() & ((df["rating"] < 1) | (df["rating"] > 5))
            add(file_name, "rating", mask, "{count} rows have a rating outside 1-5.")
        if "deliveredDate" in df.columns:
            mask = df["deliveredDate"].notna() & (df["deliveredDate"] > today)
            add(file_name, "deliveredDate", mask, "{count} rows carry a delivery date in the future.")
        if "orderId" in df.columns and "productId" in df.columns and inventory_products:
            mask = (
                df["productId"].notna()
                & ~df["productId"].astype(str).isin(inventory_products)
                & ~df["productId"].astype(str).str.startswith("P-UNKNOWN")
            )
            # Only meaningful for order-like files.
            kind = next((f.file_type for f in mapping.files if f.file_name == file_name), "unknown")
            if kind in {"orders", "deliveries"}:
                unknown_mask = df["productId"].notna() & ~df["productId"].astype(str).isin(inventory_products)
                add(
                    file_name,
                    "productId",
                    unknown_mask,
                    "{count} rows reference a productId missing from the inventory file.",
                )

    return issues


def clean_dataset(dataset_dir: Path, mapping: SchemaMapping) -> CleaningResult:
    raw_frames, notes = _read_raw_frames(dataset_dir, mapping)
    cleaned_files: dict[str, pd.DataFrame] = {}
    row_counts: dict[str, int] = {}

    for file_name, raw in raw_frames.items():
        df = _normalise_frame(raw)
        row_counts[file_name] = len(df)
        cleaned_files[file_name] = df

    missing = _missing_issues(cleaned_files)
    duplicates = _duplicate_issues(cleaned_files)
    inconsistent = _inconsistent_issues(cleaned_files, dataset_dir, mapping)

    # Drop exact duplicate rows before analysis, keeping originals intact on disk.
    deduped: dict[str, pd.DataFrame] = {}
    for file_name, df in cleaned_files.items():
        data_columns = [column for column in df.columns if not str(column).startswith("_")]
        deduped[file_name] = df.drop_duplicates(subset=data_columns, keep="first").reset_index(drop=True)

    total_rows = sum(len(df) for df in cleaned_files.values()) or 1
    total_cells = sum(len(df) * max(len(df.columns) - 2, 1) for df in cleaned_files.values()) or 1
    missing_cells = sum(int(issue["count"]) for issue in missing)
    dup_rows = sum(int(issue["count"]) for issue in duplicates if issue["column"] is None)
    incons_rows = sum(int(issue["count"]) for issue in inconsistent)

    penalty = min(40.0, missing_cells / total_cells * 120)
    penalty += min(30.0, dup_rows / total_rows * 300)
    penalty += min(30.0, incons_rows / total_rows * 150)
    health_score = round(max(0.0, 100.0 - penalty), 1)

    type_frames: dict[str, pd.DataFrame] = {}
    for file_mapping in mapping.files:
        if file_mapping.file_name not in deduped:
            continue
        existing = type_frames.get(file_mapping.file_type)
        df = deduped[file_mapping.file_name]
        type_frames[file_mapping.file_type] = df if existing is None else pd.concat([existing, df], ignore_index=True)

    for required in ("orders", "complaints"):
        if required not in type_frames:
            notes.append(f"No {required} file detected; analyses that need it will be skipped.")

    summary = (
        f"Cleaned {total_rows} rows across {len(cleaned_files)} file(s). "
        f"{missing_cells} missing values, {dup_rows} duplicate rows, {incons_rows} inconsistent rows. "
        f"Health score {health_score}/100."
    )

    quality = QualityResponse(
        missing=[_to_issue(item) for item in missing],
        duplicates=[_to_issue(item) for item in duplicates],
        inconsistent=[_to_issue(item) for item in inconsistent],
        health_score=health_score,
        summary=summary,
    )
    logger.info("cleaning: %s", summary)
    return CleaningResult(frames=type_frames, quality=quality.model_dump(by_alias=True), notes=notes, row_counts=row_counts)


def _to_issue(item: dict) -> dict:
    return {
        "file": item["file"],
        "column": item.get("column"),
        "count": int(item["count"]),
        "rowIds": list(item.get("rowIds") or []),
        "note": item["note"],
    }

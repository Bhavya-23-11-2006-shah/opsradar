"""Shared detector plumbing: Candidate container, evidence and date helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Iterable, Optional

import numpy as np
import pandas as pd

EVIDENCE_COLUMNS = [
    "orderId",
    "productId",
    "productName",
    "date",
    "promisedDate",
    "shippedDate",
    "deliveredDate",
    "warehouse",
    "city",
    "courier",
    "status",
    "category",
    "complaintText",
    "stock",
    "dailySalesRate",
    "reorderLevel",
    "quantity",
    "amount",
    "rating",
]


@dataclass
class Candidate:
    type: str
    title: str
    summary: str
    stat_strength: float
    affected_count: int
    affected_value: float
    recency_days: float
    trend: float
    customers: int
    facts: list[dict] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    entities: dict[str, list[str]] = field(default_factory=dict)
    action_hint: str = ""
    preventive_hint: str = ""
    unit: str = "orders"
    affected: Optional[pd.DataFrame] = None
    group: dict[str, str] = field(default_factory=dict)


def serialise(value) -> str | int | float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (bool, np.bool_)):
        return 1 if value else 0
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return round(float(value), 2)
    if isinstance(value, (int, float)):
        return value
    text = str(value)
    return text if len(text) <= 500 else text[:497] + "..."


def fact(statement: str, metric: str, value) -> dict:
    if isinstance(value, (np.integer,)):
        value = int(value)
    elif isinstance(value, (np.floating,)):
        value = round(float(value), 2)
    elif isinstance(value, float):
        value = round(value, 2)
    return {"statement": statement, "metric": metric, "value": value}


def evidence_rows(
    frame: pd.DataFrame,
    *,
    limit: int = 12,
    columns: Optional[Iterable[str]] = None,
) -> list[dict]:
    if frame is None or frame.empty:
        return []
    selected = [column for column in (columns or EVIDENCE_COLUMNS) if column in frame.columns]
    rows: list[dict] = []
    for _, row in frame.head(limit).iterrows():
        fields = {column: serialise(row.get(column)) for column in selected}
        source = row.get("_file") if "_file" in frame.columns else None
        row_id = row.get("_row_id")
        row_id = serialise(row_id) or serialise(row.get("orderId")) or ""
        rows.append(
            {
                "source": str(source or "dataset"),
                "rowId": str(row_id),
                "fields": fields,
            }
        )
    return rows


def dataset_as_of(linked) -> pd.Timestamp:
    """Latest observed date. Promised dates are excluded: they point into the future."""
    stamps: list[pd.Timestamp] = []
    for frame in (linked.complaint_view, linked.order_view):
        for column in ("date", "deliveredDate"):
            if frame is not None and column in frame.columns and frame[column].notna().any():
                stamps.append(pd.Timestamp(frame[column].max()))
    if linked.sales is not None and "date" in linked.sales.columns and linked.sales["date"].notna().any():
        stamps.append(pd.Timestamp(linked.sales["date"].max()))
    if not stamps:
        return pd.Timestamp(date.today())
    return max(stamps).normalize()


def entity_lists(frame: pd.DataFrame, *, limit: int = 12) -> dict[str, list[str]]:
    def unique(column: str) -> list[str]:
        if column not in frame.columns:
            return []
        values = [str(value) for value in frame[column].dropna().unique() if str(value).strip()]
        return values[:limit]

    return {
        "products": unique("productId") or unique("productName"),
        "locations": list(dict.fromkeys(unique("warehouse") + unique("city")))[:limit],
        "couriers": unique("courier"),
        "orders": unique("orderId")[:20],
    }


def label(row_or_frame, dimension: str) -> str:
    return {
        "courier": "courier",
        "warehouse": "warehouse",
        "city": "city",
        "productId": "product",
        "productName": "product",
    }.get(dimension, dimension)


def display_product(frame: pd.DataFrame, product_id: str) -> str:
    if frame is not None and "productName" in frame.columns:
        names = frame.loc[frame.get("productId", pd.Series(dtype="object")) == product_id, "productName"].dropna()
        if not names.empty:
            return str(names.iloc[0])
    return str(product_id)

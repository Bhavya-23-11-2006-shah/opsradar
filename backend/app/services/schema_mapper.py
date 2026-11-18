"""Schema inference: detect the file type and map real columns to canonical fields.

Nothing here is tied to a specific demo dataset. Synonyms + rapidfuzz + dtype
checks produce per-field confidence, and the user's confirmed mapping is what
every later stage consumes.
"""

from __future__ import annotations

import re
from typing import Optional

import pandas as pd
from rapidfuzz import fuzz

from ..schemas import FileMapping

CANONICAL_FIELDS: list[str] = [
    "orderId",
    "customerId",
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
    "complaintText",
    "category",
    "stock",
    "dailySalesRate",
    "reorderLevel",
    "quantity",
    "amount",
    "rating",
]

SYNONYMS: dict[str, list[str]] = {
    "orderId": [
        "order id",
        "orderid",
        "order number",
        "order no",
        "order reference",
        "order code",
        "id",
    ],
    "customerId": ["customer id", "customerid", "customer", "client id", "buyer id", "user id", "account id"],
    "productId": ["product id", "productid", "sku", "sku id", "item id", "product code", "item code", "article id"],
    "productName": ["product name", "product", "item name", "item", "title", "product title", "sku name"],
    "date": [
        "date",
        "order date",
        "created at",
        "created date",
        "purchase date",
        "day",
        "timestamp",
        "transaction date",
        "invoice date",
    ],
    "promisedDate": [
        "promised date",
        "promised delivery",
        "promised",
        "expected delivery",
        "expected date",
        "due date",
        "delivery promise",
        "eta",
        "target date",
        "committed date",
    ],
    "deliveredDate": [
        "delivered date",
        "delivery date",
        "delivered on",
        "actual delivery",
        "date delivered",
        "received date",
        "delivered at",
    ],
    "shippedDate": ["shipped date", "ship date", "dispatch date", "shipped on", "date shipped", "shipped at"],
    "warehouse": [
        "warehouse",
        "warehouse id",
        "warehouse name",
        "fulfilment centre",
        "fulfillment center",
        "hub",
        "distribution center",
        "warehouse code",
    ],
    "city": ["city", "destination city", "delivery city", "customer city", "town", "ship to city", "region"],
    "courier": [
        "courier",
        "courier name",
        "carrier",
        "shipping partner",
        "logistics partner",
        "shipper",
        "courier id",
        "delivery partner",
    ],
    "status": ["status", "order status", "delivery status", "state", "shipment status", "fulfilment status"],
    "complaintText": [
        "complaint",
        "complaint text",
        "feedback",
        "review text",
        "comment",
        "description",
        "issue",
        "message",
        "customer complaint",
        "remarks",
        "notes",
    ],
    "category": [
        "category",
        "complaint category",
        "issue category",
        "product category",
        "reason",
        "issue type",
        "complaint type",
        "type",
    ],
    "stock": [
        "stock",
        "stock on hand",
        "inventory",
        "inventory level",
        "available stock",
        "qty on hand",
        "on hand",
        "stock level",
        "units available",
    ],
    "dailySalesRate": [
        "daily sales rate",
        "sales rate",
        "avg daily sales",
        "average daily sales",
        "daily velocity",
        "velocity",
        "daily demand",
        "sales per day",
    ],
    "reorderLevel": [
        "reorder level",
        "reorder point",
        "minimum stock",
        "min stock",
        "reorder threshold",
        "safety stock",
        "min level",
    ],
    "quantity": ["quantity", "qty", "units", "units sold", "quantity sold", "order qty", "pieces", "quantity ordered"],
    "amount": [
        "amount",
        "revenue",
        "sales amount",
        "total amount",
        "order value",
        "total",
        "value",
        "price",
        "gmv",
        "net sales",
    ],
    "rating": ["rating", "stars", "star rating", "review rating", "customer rating", "review score", "score"],
}

DATE_FIELDS = {"date", "promisedDate", "shippedDate", "deliveredDate"}
NUMERIC_FIELDS = {"stock", "dailySalesRate", "reorderLevel", "quantity", "amount", "rating"}
TEXT_FIELDS = {"complaintText", "productName", "category", "status", "city", "warehouse", "courier"}

GENERIC_SYNONYMS = {
    "id",
    "name",
    "title",
    "type",
    "date",
    "status",
    "value",
    "text",
    "item",
    "product",
    "total",
}

TYPE_BOOSTS: dict[str, dict[str, float]] = {
    "orders": {"orderId": 0.06, "promisedDate": 0.06, "quantity": 0.04, "amount": 0.04, "customerId": 0.03},
    "deliveries": {
        "deliveredDate": 0.07,
        "shippedDate": 0.07,
        "promisedDate": 0.05,
        "courier": 0.05,
        "status": 0.04,
    },
    "complaints": {"complaintText": 0.08, "category": 0.05, "orderId": 0.04, "date": 0.03},
    "reviews": {"rating": 0.08, "complaintText": 0.04, "productId": 0.03},
    "inventory": {"stock": 0.08, "reorderLevel": 0.06, "dailySalesRate": 0.06, "productId": 0.04},
    "sales": {"quantity": 0.05, "amount": 0.05, "date": 0.05, "productId": 0.05},
    "unknown": {},
}


def normalise_name(value: str) -> str:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(value))
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().lower()
    return re.sub(r"\s+", " ", text)


def _looks_numeric(series: pd.Series) -> bool:
    sample = series.dropna()
    if sample.empty:
        return False
    sample = sample.astype("string").str.replace(r"[£$€,\s]", "", regex=True).head(80)
    converted = pd.to_numeric(sample, errors="coerce")
    return float(converted.notna().mean()) >= 0.8


def _looks_date(series: pd.Series) -> bool:
    sample = series.dropna()
    if sample.empty:
        return False
    text = sample.astype("string").head(50)
    dateish = text.str.contains(r"\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}", regex=True)
    if float(dateish.fillna(False).mean()) < 0.6:
        return False
    parsed = pd.to_datetime(text, errors="coerce", format="mixed", dayfirst=False)
    return float(parsed.notna().mean()) >= 0.7


def _looks_long_text(series: pd.Series) -> bool:
    sample = series.dropna()
    if sample.empty:
        return False
    lengths = sample.astype("string").str.len()
    return float(lengths.mean()) >= 25


def _score(canonical: str, column: str, series: pd.Series) -> float:
    norm_col = normalise_name(column)
    if not norm_col:
        return 0.0

    best = 0.0
    for synonym in SYNONYMS[canonical]:
        norm_syn = normalise_name(synonym)
        if norm_col == norm_syn:
            # A bare "id"/"name" is plausible but weak evidence.
            score = 0.62 if norm_syn in GENERIC_SYNONYMS else 0.97
        elif norm_syn in GENERIC_SYNONYMS:
            # Generic words must match as whole words only (never "total" in "totally").
            score = 0.55 if re.search(rf"\b{re.escape(norm_syn)}\b", norm_col) else 0.0
        elif re.search(rf"\b{re.escape(norm_syn)}\b", norm_col) or re.search(
            rf"\b{re.escape(norm_col)}\b", norm_syn
        ):
            score = 0.9
        else:
            ratio = fuzz.ratio(norm_col, norm_syn)
            # Plain character similarity is noisy on unrelated text, so only
            # close spellings earn a score at all.
            if ratio >= 90:
                score = 0.75 + (ratio - 90) / 100.0 * 0.2
            elif ratio >= 82:
                score = 0.6
            else:
                score = 0.0
        best = max(best, score)

    if best < 0.5:
        return 0.0

    if canonical in DATE_FIELDS and _looks_date(series):
        best += 0.04
    if canonical in NUMERIC_FIELDS and _looks_numeric(series):
        best += 0.04
    if canonical == "complaintText" and _looks_long_text(series):
        best += 0.03
    if canonical in {"stock", "dailySalesRate", "reorderLevel", "quantity", "amount", "rating"} and _looks_date(series):
        best -= 0.15
    if canonical in DATE_FIELDS and _looks_numeric(series):
        best -= 0.1
    return max(0.0, min(best, 0.99))


def _assign(df: pd.DataFrame, boosts: dict[str, float]) -> tuple[dict, dict]:
    candidates: list[tuple[float, str, str]] = []
    for canonical in CANONICAL_FIELDS:
        for column in df.columns:
            score = _score(canonical, column, df[column]) + boosts.get(canonical, 0.0)
            if score >= 0.5:
                candidates.append((score, canonical, str(column)))
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))

    fields: dict[str, Optional[str]] = {}
    confidence: dict[str, float] = {}
    used: set[str] = set()
    for score, canonical, column in candidates:
        if canonical in fields or column in used or score < 0.55:
            continue
        fields[canonical] = column
        confidence[canonical] = round(min(score, 0.99), 2)
        used.add(column)
    return fields, confidence


def detect_file_type(df: pd.DataFrame, matched: set[str], file_name: str = "") -> str:
    name = normalise_name(file_name)
    scores = {
        "orders": 0.0,
        "deliveries": 0.0,
        "complaints": 0.0,
        "reviews": 0.0,
        "inventory": 0.0,
        "sales": 0.0,
    }
    if "complaintText" in matched:
        scores["complaints"] += 5
    if "rating" in matched:
        scores["reviews"] += 6
    if {"stock", "reorderLevel", "dailySalesRate"} & matched:
        scores["inventory"] += 5
    if "deliveredDate" in matched:
        scores["deliveries"] += 4
    if "shippedDate" in matched:
        scores["deliveries"] += 3
    if "promisedDate" in matched:
        scores["orders"] += 4
        scores["deliveries"] += 1
    if "courier" in matched:
        scores["deliveries"] += 2
        scores["orders"] += 1
    if "orderId" in matched:
        scores["orders"] += 2
        scores["deliveries"] += 1
    if {"quantity", "amount"} & matched:
        scores["orders"] += 2
    if "date" in matched and "productId" in matched and "orderId" not in matched:
        scores["sales"] += 4
    if "dailySalesRate" in matched:
        scores["sales"] += 2
    if "status" in matched:
        scores["orders"] += 1
        scores["deliveries"] += 1

    for kind in scores:
        if kind in name or kind.rstrip("s") in name:
            scores[kind] += 3

    best_kind = max(scores, key=lambda key: scores[key])
    if scores[best_kind] < 2:
        return "unknown"
    return best_kind


def infer_file_mapping(file_name: str, df: pd.DataFrame) -> FileMapping:
    preliminary_fields, _ = _assign(df, {})
    matched = set(preliminary_fields)
    file_type = detect_file_type(df, matched, file_name)
    fields, confidence = _assign(df, TYPE_BOOSTS.get(file_type, {}))

    # Keep only mappings that make sense for the detected type, but never lose a
    # field the user may still need: unsupported ids stay available.
    if file_type == "inventory":
        for drop in ("complaintText", "deliveredDate", "shippedDate"):
            fields.pop(drop, None)
            confidence.pop(drop, None)
    if file_type == "complaints":
        for drop in ("stock", "dailySalesRate", "reorderLevel", "rating"):
            fields.pop(drop, None)
            confidence.pop(drop, None)

    return FileMapping(
        file_name=file_name,
        file_type=file_type,  # type: ignore[arg-type]
        fields=fields,
        confidence=confidence,
    )


def suggest_mappings(frames: dict[str, pd.DataFrame]) -> list[FileMapping]:
    return [infer_file_mapping(name, df) for name, df in frames.items()]

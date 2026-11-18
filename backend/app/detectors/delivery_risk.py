"""Delivery risk: per-order miss probability from the historical delay distribution."""

from __future__ import annotations

import logging
from collections import Counter
from math import isnan
from typing import Optional

import pandas as pd

from .common import Candidate, dataset_as_of, evidence_rows, fact

logger = logging.getLogger(__name__)

RECENT_WINDOW_DAYS = 14
MIN_HISTORY = 20
MIN_GROUP_HISTORY = 10
RISK_THRESHOLD = 0.5
MIN_FLAGGED = 3


def _prepare(linked):
    frame = linked.order_view
    if frame is None or frame.empty or "promisedDate" not in frame.columns:
        return None
    frame = frame.copy()
    frame["promisedDate"] = pd.to_datetime(frame["promisedDate"], errors="coerce", format="mixed")
    if "deliveredDate" in frame.columns:
        frame["deliveredDate"] = pd.to_datetime(frame["deliveredDate"], errors="coerce", format="mixed")
    else:
        frame["deliveredDate"] = pd.NaT
    if "status" not in frame.columns:
        frame["status"] = None
    status = frame["status"].astype("string").str.lower()
    frame["_open"] = frame["deliveredDate"].isna() & ~status.isin(["cancelled", "canceled", "returned"])
    return frame


def _rates(history: pd.DataFrame, as_of: pd.Timestamp) -> tuple[float, float, float, int]:
    if history.empty:
        return 0.25, 0.25, 0.25, 0
    overall = float(history["late"].mean())
    recent = history[history["deliveredDate"] >= as_of - pd.Timedelta(days=RECENT_WINDOW_DAYS)]
    recent_rate = float(recent["late"].mean()) if len(recent) >= 5 else overall
    earlier = history[history["deliveredDate"] < as_of - pd.Timedelta(days=RECENT_WINDOW_DAYS)]
    base_rate = float(earlier["late"].mean()) if len(earlier) >= 5 else overall
    return overall, recent_rate, base_rate, len(history)


def _rate_tables(delivered: pd.DataFrame, as_of: pd.Timestamp) -> dict[str, dict[str, tuple[float, float, float, int]]]:
    tables: dict[str, dict[str, tuple[float, float, float, int]]] = {}
    for dimension in ("courier", "warehouse", "city"):
        if dimension not in delivered.columns:
            continue
        table: dict[str, tuple[float, float, float, int]] = {}
        for value, group in delivered.dropna(subset=[dimension]).groupby(dimension):
            if len(group) < MIN_GROUP_HISTORY:
                continue
            table[str(value)] = _rates(group, as_of)
        tables[dimension] = table
    return tables


def _order_probability(row, tables, global_rates, as_of: pd.Timestamp) -> float:
    warehouse_rate = tables.get("warehouse", {}).get(str(row.get("warehouse")), global_rates)[1]
    courier_rate = tables.get("courier", {}).get(str(row.get("courier")), global_rates)[1]
    base = max(warehouse_rate, courier_rate)

    promised = row.get("promisedDate")
    if promised is None or pd.isna(promised):
        return min(0.95, base)
    days_left = (promised - as_of).days
    if days_left < 0:
        probability = max(base, 0.8)
    elif days_left == 0:
        probability = base + 0.15
    elif days_left <= 2:
        probability = base + 0.08
    else:
        probability = base
    return min(0.95, max(0.0, probability))


def _amount(row) -> float:
    try:
        value = float(row.get("amount"))
        return 0.0 if isnan(value) else value
    except (TypeError, ValueError):
        return 0.0


def detect(linked, *, max_candidates: int = 4) -> tuple[list[Candidate], list[dict], list[str]]:
    frame = _prepare(linked)
    notes: list[str] = []
    if frame is None:
        logger.info("delivery_risk: no promised dates, skipped")
        return [], [], ["No promisedDate column: delivery risk skipped."]

    as_of = dataset_as_of(linked)
    delivered = frame[frame["deliveredDate"].notna() & frame["promisedDate"].notna()].copy()
    if len(delivered) < MIN_HISTORY:
        return [], [], ["Not enough delivered orders to estimate delay distributions; delivery risk skipped."]
    delivered["late"] = delivered["late"].fillna(False).astype(bool)

    open_orders = frame[frame["_open"] & frame["promisedDate"].notna()].copy()
    if open_orders.empty:
        return [], [], ["No open orders with a promised date: delivery risk skipped."]

    global_rates = _rates(delivered, as_of)
    tables = _rate_tables(delivered, as_of)

    flagged_rows: list[tuple[int, float]] = []
    at_risk_orders: list[dict] = []
    for index, row in open_orders.iterrows():
        probability = _order_probability(row, tables, global_rates, as_of)
        if probability < RISK_THRESHOLD:
            continue
        flagged_rows.append((index, probability))
        at_risk_orders.append(
            {
                "orderId": str(row.get("orderId")),
                "courier": None if pd.isna(row.get("courier")) else str(row.get("courier")),
                "warehouse": None if pd.isna(row.get("warehouse")) else str(row.get("warehouse")),
                "city": None if pd.isna(row.get("city")) else str(row.get("city")),
                "productId": None if pd.isna(row.get("productId")) else str(row.get("productId")),
                "amount": _amount(row),
                "date": row["date"].date().isoformat() if pd.notna(row.get("date")) else None,
                "promisedDate": row["promisedDate"].date().isoformat(),
                "probability": round(probability, 2),
            }
        )

    if not flagged_rows:
        return [], [], ["No open order crossed the miss-probability threshold."]

    flagged = open_orders.loc[[index for index, _ in flagged_rows]].copy()
    flagged["_probability"] = [probability for _, probability in flagged_rows]

    candidates: list[Candidate] = []
    for dimension, bucket in (("warehouse", "locations"), ("city", "locations"), ("courier", "couriers")):
        if dimension not in flagged.columns:
            continue
        counts = Counter(value for value in flagged[dimension].dropna().astype(str))
        for value, count in counts.most_common():
            if count < MIN_FLAGGED:
                continue
            group_flagged = flagged[flagged[dimension].astype(str) == str(value)]
            history = delivered[delivered[dimension].astype(str) == str(value)]
            overall_rate, recent_rate, base_rate, support = (
                _rates(history, as_of) if len(history) >= MIN_GROUP_HISTORY else global_rates
            )
            group_open_count = int(
                (open_orders[dimension].astype(str) == str(value)).sum()
            )
            average_probability = float(group_flagged["_probability"].mean())
            value_total = float(pd.to_numeric(group_flagged.get("amount", pd.Series(dtype="float")), errors="coerce").fillna(0).sum())
            customers = int(group_flagged["customerId"].dropna().nunique()) if "customerId" in group_flagged.columns else 0
            dimension_label = {"courier": "courier", "warehouse": "warehouse", "city": "city"}[dimension]

            entities = {
                "products": [str(item) for item in group_flagged["productId"].dropna().unique()[:12]]
                if "productId" in group_flagged.columns
                else [],
                "locations": [str(value)] if dimension in {"warehouse", "city"} else [
                    str(item) for item in group_flagged["city"].dropna().unique()[:5]
                ],
                "couriers": [str(value)] if dimension == "courier" else [
                    str(item) for item in group_flagged["courier"].dropna().unique()[:5]
                ],
                "orders": [str(item) for item in group_flagged["orderId"].dropna().head(20)],
            }

            candidates.append(
                Candidate(
                    type="delivery_risk",
                    title=f"{count} open orders at risk via {dimension_label} {value}",
                    summary=(
                        f"{count} of {group_open_count} open {dimension_label} {value} orders are likely to miss "
                        f"their promised date; the last {RECENT_WINDOW_DAYS} days show a "
                        f"{round(recent_rate * 100, 1)}% late share versus {round(base_rate * 100, 1)}% before."
                    ),
                    stat_strength=min(1.0, 0.5 * recent_rate + min(count / 15, 0.5)),
                    affected_count=count,
                    affected_value=value_total,
                    recency_days=0.0,
                    trend=min(1.0, max(0.0, recent_rate - base_rate) * 2),
                    customers=customers,
                    facts=[
                        fact(
                            f"{count} of {group_open_count} open {dimension_label} {value} orders are at risk of missing their promised date.",
                            "orders_at_risk",
                            int(count),
                        ),
                        fact(
                            f"Recent late-delivery share (last {RECENT_WINDOW_DAYS} days) is {round(recent_rate * 100, 1)}%.",
                            "recent_late_share",
                            round(recent_rate * 100, 1),
                        ),
                        fact(
                            f"Baseline late-delivery share is {round(base_rate * 100, 1)}%.",
                            "baseline_late_share",
                            round(base_rate * 100, 1),
                        ),
                        fact(
                            f"Average miss probability for the flagged orders is {round(average_probability * 100, 1)}%.",
                            "average_miss_probability",
                            round(average_probability * 100, 1),
                        ),
                        fact(
                            f"{round(count / max(group_open_count, 1) * 100, 1)}% of this group's open orders are flagged.",
                            "open_orders_at_risk_share",
                            round(count / max(group_open_count, 1) * 100, 1),
                        ),
                    ],
                    evidence=evidence_rows(group_flagged, limit=12),
                    entities=entities,
                    action_hint=(
                        f"Call the {dimension_label} {value} account today about the {count} flagged orders, "
                        "re-confirm promised dates with customers and pre-emptively upgrade the most valuable ones."
                    ),
                    preventive_hint=(
                        f"Set a daily promise-risk check for {dimension_label} {value} and route new orders to a "
                        "backup carrier while the late share stays above 30%."
                    ),
                    unit="orders",
                    affected=group_flagged,
                    group={dimension: str(value)},
                )
            )

    candidates.sort(key=lambda item: (item.affected_count, item.stat_strength), reverse=True)
    logger.info("delivery_risk: %s candidates, %s orders at risk", len(candidates), len(at_risk_orders))
    return candidates[:max_candidates], at_risk_orders, notes

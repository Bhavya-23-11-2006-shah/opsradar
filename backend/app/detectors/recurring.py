"""Recurring complaint concentration: category x (courier, warehouse, city, product)."""

from __future__ import annotations

import logging
from math import erfc, sqrt

import pandas as pd

from .common import Candidate, dataset_as_of, entity_lists, evidence_rows, fact

logger = logging.getLogger(__name__)

DIMENSIONS = [
    ("courier", "courier"),
    ("warehouse", "warehouse"),
    ("city", "city"),
    ("productId", "product"),
]

MIN_GROUP_COUNT = 5
MIN_LIFT = 1.6
MIN_Z = 2.33


def _p_value(z: float) -> float:
    """One-sided p-value for a two-proportion z-test (error function, no heavy import)."""
    return 0.5 * erfc(abs(z) / sqrt(2))


def detect(linked, *, max_candidates: int = 8) -> list[Candidate]:
    complaints = linked.complaint_view
    orders = linked.order_view
    if complaints is None or complaints.empty or "category" not in complaints.columns:
        logger.info("recurring: no categorised complaints, skipped")
        return []

    as_of = dataset_as_of(linked)
    total_orders = max(len(orders), 0)
    candidates: list[Candidate] = []
    best_by_key: dict[tuple[str, str, str], Candidate] = {}

    for dimension, _entity_bucket in DIMENSIONS:
        if dimension not in complaints.columns:
            continue
        for category, subset in complaints.dropna(subset=["category"]).groupby("category"):
            if category in {"Other", None} or len(subset) < 8:
                continue
            counts = subset.dropna(subset=[dimension])[dimension].astype(str).value_counts()
            for value, count in counts.items():
                if count < MIN_GROUP_COUNT:
                    continue
                share = count / len(subset)
                if total_orders and dimension in orders.columns:
                    base_count = int((orders[dimension].astype(str) == str(value)).sum())
                    base_share = max(base_count / total_orders, 0.01)
                else:
                    base_count = count
                    base_share = 1 / max(len(counts), 1)
                expected = len(subset) * base_share
                if expected <= 0:
                    continue
                lift = share / base_share
                z = (count - expected) / sqrt(expected * (1 - min(base_share, 0.99)))
                if z < MIN_Z or lift < MIN_LIFT:
                    continue

                affected = subset[subset[dimension].astype(str) == str(value)]
                affected_orders = pd.DataFrame()
                if total_orders and "orderId" in affected.columns and "orderId" in orders.columns:
                    affected_orders = orders[orders["orderId"].astype(str).isin(affected["orderId"].dropna().astype(str))]
                value_total = float(pd.to_numeric(affected_orders.get("amount", pd.Series(dtype="float")), errors="coerce").fillna(0).sum())
                customers = int(affected_orders["customerId"].dropna().nunique()) if "customerId" in affected_orders.columns and not affected_orders.empty else 0

                latest = affected["date"].max() if "date" in affected.columns else None
                recency = max(0.0, (as_of - pd.Timestamp(latest)).days) if latest is not None and pd.notna(latest) else 7.0

                if "date" in affected.columns and affected["date"].notna().any():
                    recent = affected[affected["date"] >= as_of - pd.Timedelta(days=13)]
                    earlier = affected[affected["date"] < as_of - pd.Timedelta(days=13)]
                    trend = 0.0
                    if len(earlier) >= 3:
                        trend = max(0.0, min(1.0, (recent.shape[0] / 14) / max(earlier.shape[0] / 45, 0.05) - 0.5))
                else:
                    trend = 0.0

                product_label = str(value)
                if dimension == "productId" and "productName" in affected.columns:
                    names = affected["productName"].dropna()
                    if not names.empty:
                        product_label = str(names.iloc[0])

                dimension_label = {"courier": "courier", "warehouse": "warehouse", "city": "city", "productId": "product"}[dimension]
                group_label = f"{dimension_label} {product_label}" if dimension != "productId" else f"product {product_label}"
                share_pct = round(share * 100, 1)
                base_pct = round(base_share * 100, 1)
                p_value = _p_value(z)

                facts = [
                    fact(
                        f"{count} of {len(subset)} {str(category).lower()} complaints ({share_pct}%) involve {group_label}.",
                        "complaint_share",
                        share_pct,
                    ),
                    fact(
                        f"{group_label} accounts for {base_pct}% of all orders.",
                        "order_share",
                        base_pct,
                    ),
                    fact(
                        f"Lift is {round(lift, 2)}x the order baseline (z={round(z, 2)}, p={round(p_value, 4)}).",
                        "lift",
                        round(lift, 2),
                    ),
                    fact(
                        f"Statistical test used {count} complaints against a baseline of {base_count} orders.",
                        "sample_size",
                        int(count),
                    ),
                ]

                entities = entity_lists(affected)
                if dimension == "productId":
                    entities["products"] = [str(value)]
                elif dimension == "courier":
                    entities["couriers"] = [str(value)]
                else:
                    entities["locations"] = [str(value)]

                key = (str(category), dimension, str(value))
                candidate = Candidate(
                    type="recurring_issue",
                    title=f"{category} complaints concentrate on {group_label}",
                    summary=(
                        f"{count} of {len(subset)} {str(category).lower()} complaints ({share_pct}%) come from "
                        f"{group_label}, which handles {base_pct}% of orders — a {round(lift, 2)}x lift."
                    ),
                    stat_strength=min(1.0, z / 6),
                    affected_count=int(count),
                    affected_value=value_total,
                    recency_days=recency,
                    trend=trend,
                    customers=customers,
                    facts=facts,
                    evidence=evidence_rows(affected, limit=12),
                    entities=entities,
                    action_hint=(
                        f"Audit {group_label} handling for {str(category).lower()} on the next dispatch cycle "
                        f"and review the {count} complaint orders with the {dimension_label} owner."
                    ),
                    preventive_hint=(
                        f"Add a {str(category).lower()} checkpoint to {group_label} and track its complaint share weekly."
                    ),
                    unit="complaints",
                    affected=affected,
                    group={dimension: str(value)},
                )
                previous = best_by_key.get(key)
                if previous is None or candidate.stat_strength > previous.stat_strength:
                    best_by_key[key] = candidate

    candidates = list(best_by_key.values())
    candidates.sort(key=lambda item: (item.stat_strength, item.affected_count), reverse=True)
    logger.info("recurring: %s candidates", len(candidates))
    return candidates[:max_candidates]

"""Emerging complaint spikes plus the daily anomaly flags used by the overview."""

from __future__ import annotations

import logging
from math import sqrt

import numpy as np
import pandas as pd

from .common import Candidate, dataset_as_of, entity_lists, evidence_rows, fact

logger = logging.getLogger(__name__)

RECENT_DAYS = 7
BASELINE_DAYS = 21


def daily_anomaly_dates(complaints: pd.DataFrame) -> set[str]:
    if complaints is None or complaints.empty or "date" not in complaints.columns:
        return set()
    series = complaints.dropna(subset=["date"]).groupby(complaints["date"].dt.date).size().sort_index()
    if len(series) < 7:
        return set()
    recent = series.tail(30)
    median = float(recent.median())
    mad = float((recent - median).abs().median())
    if mad == 0:
        std = float(recent.std(ddof=0)) or 1.0
        mad = std * 1.4826
    flagged: set[str] = set()
    for day, value in recent.items():
        z = 0.6745 * (float(value) - median) / mad
        if z >= 3.0 and float(value) >= max(3.0, median * 1.8):
            flagged.add(pd.Timestamp(day).date().isoformat())
    if not flagged and len(recent) > 0:
        threshold = median + 2.5 * mad
        for day, value in recent.items():
            if float(value) > threshold and value >= 3:
                flagged.add(pd.Timestamp(day).date().isoformat())
    return flagged


def detect(linked, *, max_candidates: int = 5) -> list[Candidate]:
    complaints = linked.complaint_view
    if complaints is None or complaints.empty or "date" not in complaints.columns:
        logger.info("spikes: no dated complaints, skipped")
        return []

    frame = complaints.dropna(subset=["date"]).copy()
    if frame.empty:
        return []

    as_of = dataset_as_of(linked)
    recent_start = as_of - pd.Timedelta(days=RECENT_DAYS - 1)
    baseline_start = recent_start - pd.Timedelta(days=BASELINE_DAYS)
    key = "productId" if "productId" in frame.columns and frame["productId"].notna().any() else "productName"

    candidates: list[Candidate] = []
    for product, subset in frame.groupby(key):
        if product is None or (isinstance(product, float) and pd.isna(product)):
            continue
        recent = subset[(subset["date"] >= recent_start) & (subset["date"] <= as_of)]
        baseline = subset[(subset["date"] >= baseline_start) & (subset["date"] < recent_start)]
        recent_total = int(len(recent))
        if recent_total < 5:
            continue
        expected = len(baseline) / BASELINE_DAYS * RECENT_DAYS
        if expected <= 0:
            expected = 0.3
        z = (recent_total - expected) / sqrt(max(expected, 1.0))
        ratio = recent_total / max(expected, 0.5)
        if z < 3 or ratio < 2:
            continue

        product_name = str(product)
        if "productName" in recent.columns:
            names = recent["productName"].dropna()
            if not names.empty:
                product_name = str(names.iloc[0])

        category_counts = recent["category"].value_counts() if "category" in recent.columns else pd.Series(dtype=int)
        top_category = str(category_counts.index[0]) if not category_counts.empty else "uncategorised"
        share = float(category_counts.iloc[0]) / recent_total if not category_counts.empty else 0.0
        value_total = float(pd.to_numeric(recent.get("amount", pd.Series(dtype="float")), errors="coerce").fillna(0).sum())
        entities = entity_lists(recent)
        if key == "productId":
            entities["products"] = [str(product)]

        summary = (
            f"{recent_total} complaints about {product_name} in the last {RECENT_DAYS} days versus "
            f"{round(expected, 1)} expected from the prior {BASELINE_DAYS}-day baseline ({round(ratio, 1)}x), "
            f"led by {top_category.lower()} ({round(share * 100, 1)}%)."
        )
        candidates.append(
            Candidate(
                type="complaint_spike",
                title=f"Complaint spike on {product_name} in the last {RECENT_DAYS} days",
                summary=summary,
                stat_strength=min(1.0, z / 7),
                affected_count=recent_total,
                affected_value=value_total,
                recency_days=0.0,
                trend=min(1.0, ratio / 5),
                customers=int(recent["customerId"].dropna().nunique()) if "customerId" in recent.columns else 0,
                facts=[
                    fact(
                        f"{recent_total} complaints about {product_name} were recorded in the last {RECENT_DAYS} days.",
                        "recent_complaints",
                        recent_total,
                    ),
                    fact(
                        f"The prior {BASELINE_DAYS}-day baseline implies {round(expected, 1)} complaints for a {RECENT_DAYS}-day window.",
                        "expected_complaints",
                        round(expected, 1),
                    ),
                    fact(
                        f"The spike is {round(ratio, 1)}x the baseline (z={round(z, 2)}).",
                        "spike_ratio",
                        round(ratio, 2),
                    ),
                    fact(
                        f"{round(share * 100, 1)}% of the recent complaints are {top_category.lower()}.",
                        "top_category_share",
                        round(share * 100, 1),
                    ),
                ],
                evidence=evidence_rows(recent, limit=12),
                entities=entities,
                action_hint=(
                    f"Pull the last {recent_total} {product_name} complaints into one review today, "
                    f"starting with {top_category.lower()}, and pause promotions until the cause is scoped."
                ),
                preventive_hint=(
                    f"Watch {product_name} complaint volume daily for two weeks and alert the product owner above "
                    f"{round(expected, 1)} complaints per week."
                ),
                unit="complaints",
                affected=recent,
                group={key: str(product)},
            )
        )

    candidates.sort(key=lambda item: item.stat_strength, reverse=True)
    logger.info("spikes: %s candidates", len(candidates))
    return candidates[:max_candidates]

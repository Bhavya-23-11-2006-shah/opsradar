"""Robust (median/MAD) anomaly detection on sales, revenue, returns and stock."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from .common import Candidate, dataset_as_of, evidence_rows, fact

logger = logging.getLogger(__name__)

MIN_POINTS = 14
Z_THRESHOLD = 3.5
RECENT_DAYS = 14


def _series_for(linked) -> tuple[pd.DataFrame, str, str]:
    """Choose the best available daily series: units, then revenue, then orders."""
    sales = linked.sales
    if sales is not None and not sales.empty and "date" in sales.columns:
        sales = sales.copy()
        sales["date"] = pd.to_datetime(sales["date"], errors="coerce", format="mixed")
        sales = sales.dropna(subset=["date"])
        if "quantity" in sales.columns and sales["quantity"].notna().any():
            return sales, "quantity", "units"
        if "amount" in sales.columns and sales["amount"].notna().any():
            return sales, "amount", "revenue"

    orders = linked.order_view
    if orders is not None and not orders.empty and "date" in orders.columns:
        orders = orders.copy()
        orders["date"] = pd.to_datetime(orders["date"], errors="coerce", format="mixed")
        orders = orders.dropna(subset=["date"])
        if "quantity" in orders.columns and orders["quantity"].notna().any():
            return orders, "quantity", "units"
    return pd.DataFrame(), "", ""


def detect(linked, *, max_candidates: int = 6) -> list[Candidate]:
    frame, metric_column, unit_label = _series_for(linked)
    if frame.empty or not metric_column:
        logger.info("anomalies: no usable daily series, skipped")
        return []

    frame = frame.dropna(subset=[metric_column])
    if frame.empty:
        return []

    key = "productId" if "productId" in frame.columns and frame["productId"].notna().any() else "productName"
    frame = frame.dropna(subset=[key]).copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce", format="mixed")
    frame = frame.dropna(subset=["date"])

    daily = frame.groupby([key, frame["date"].dt.normalize()])[metric_column].sum().reset_index()
    daily.columns = [key, "date", "value"]
    as_of = dataset_as_of(linked)

    candidates: list[Candidate] = []
    for product, subset in daily.groupby(key):
        series = subset.sort_values("date")
        if len(series) < MIN_POINTS:
            continue
        values = pd.to_numeric(series["value"], errors="coerce").dropna()
        if values.empty:
            continue
        median = float(values.median())
        mad = float((values - median).abs().median())
        if mad == 0:
            std = float(values.std(ddof=0))
            if std == 0:
                continue
            mad = std * 1.4826
        series = series.assign(robust_z=0.6745 * (pd.to_numeric(series["value"], errors="coerce") - median) / mad)
        series = series.dropna(subset=["robust_z"])
        extremes = series[series["robust_z"].abs() >= Z_THRESHOLD]
        if extremes.empty:
            continue

        extremes = extremes[extremes["date"] >= as_of - pd.Timedelta(days=RECENT_DAYS)]
        if extremes.empty:
            continue
        worst = extremes.loc[extremes["robust_z"].abs().idxmax()]
        observed = float(worst["value"])
        direction = "drop" if observed < median else "spike"
        product_name = str(product)
        if "productName" in frame.columns:
            names = frame.loc[frame[key] == product, "productName"].dropna()
            if not names.empty:
                product_name = str(names.iloc[0])

        rows = frame[(frame[key] == product) & (frame["date"].dt.normalize() == worst["date"])]
        value_total = float(pd.to_numeric(rows.get("amount", pd.Series(dtype="float")), errors="coerce").fillna(0).sum()) if "amount" in rows.columns else 0.0

        baseline_ratio = observed / median if median else 0.0
        candidates.append(
            Candidate(
                type="anomaly",
                title=f"Daily {unit_label} {direction} for {product_name} on {worst['date'].date().isoformat()}",
                summary=(
                    f"{unit_label.capitalize()} for {product_name} reached {round(observed, 1)} on "
                    f"{worst['date'].date().isoformat()} against a median of {round(median, 1)} "
                    f"(robust z={round(float(worst['robust_z']), 1)})."
                ),
                stat_strength=min(1.0, abs(float(worst["robust_z"])) / 8),
                affected_count=int(len(rows)),
                affected_value=value_total,
                recency_days=max(0.0, (as_of - pd.Timestamp(worst["date"])).days),
                trend=min(1.0, abs(baseline_ratio - 1)),
                customers=int(rows["customerId"].dropna().nunique()) if "customerId" in rows.columns else 0,
                facts=[
                    fact(
                        f"{unit_label.capitalize()} on {worst['date'].date().isoformat()} were {round(observed, 1)}.",
                        "observed_value",
                        round(observed, 1),
                    ),
                    fact(
                        f"The median for {product_name} across {len(series)} days is {round(median, 1)}.",
                        "median_value",
                        round(median, 1),
                    ),
                    fact(
                        f"Robust z-score (median/MAD) is {round(float(worst['robust_z']), 1)}.",
                        "robust_z",
                        round(float(worst["robust_z"]), 2),
                    ),
                    fact(
                        f"Observed volume is {round(baseline_ratio * 100, 1)}% of the median.",
                        "median_ratio",
                        round(baseline_ratio * 100, 1),
                    ),
                ],
                evidence=evidence_rows(rows, limit=10),
                entities={
                    "products": [str(product)],
                    "locations": [],
                    "couriers": [],
                    "orders": [str(value) for value in rows["orderId"].dropna().head(20)] if "orderId" in rows.columns else [],
                },
                action_hint=(
                    f"Check whether {product_name} had a stock-out, listing change or promotion break on "
                    f"{worst['date'].date().isoformat()}, and confirm the next {unit_label} plan with the category manager."
                ),
                preventive_hint=(
                    f"Add a daily {unit_label} alert for {product_name} at 50% deviation from its rolling median."
                ),
                unit=unit_label,
                affected=rows,
                group={key: str(product)},
            )
        )

    candidates.sort(key=lambda item: item.stat_strength, reverse=True)
    logger.info("anomalies: %s candidates", len(candidates))
    return candidates[:max_candidates]

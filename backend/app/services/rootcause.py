"""Root-cause factors computed from data, phrased strictly as correlations."""

from __future__ import annotations

import logging

import pandas as pd

from ..detectors.common import fact

logger = logging.getLogger(__name__)

DIMENSIONS = [
    ("courier", "courier"),
    ("warehouse", "warehouse"),
    ("city", "city"),
    ("productId", "product"),
]


def detect_factors(linked, affected: pd.DataFrame, *, limit: int = 3) -> list[dict]:
    """Compare each dimension inside the affected rows with the whole dataset."""
    if affected is None or affected.empty:
        return []
    baseline = linked.order_view if linked.order_view is not None and not linked.order_view.empty else linked.complaint_view
    if baseline is None or baseline.empty:
        return []

    facts: list[tuple[float, dict]] = []
    for dimension, dimension_label in DIMENSIONS:
        if dimension not in affected.columns or dimension not in baseline.columns:
            continue
        values = affected[dimension].dropna().astype(str)
        if values.empty:
            continue
        counts = values.value_counts()
        if counts.empty:
            continue
        top_value = str(counts.index[0])
        count = int(counts.iloc[0])
        if count < 3:
            continue
        share = count / len(values)
        base_count = int((baseline[dimension].astype(str) == top_value).sum())
        base_share = max(base_count / max(len(baseline), 1), 0.01)
        lift = share / base_share
        if share < 0.25 or lift < 1.3:
            continue

        name = top_value
        if dimension == "productId" and "productName" in affected.columns:
            names = affected.loc[affected["productId"].astype(str) == top_value, "productName"].dropna()
            if not names.empty:
                name = str(names.iloc[0])

        facts.append(
            (
                lift,
                fact(
                    f"{round(share * 100, 1)}% of the affected rows involve {dimension_label} {name} "
                    f"versus {round(base_share * 100, 1)}% of all orders ({round(lift, 1)}x lift).",
                    f"{dimension}_share",
                    round(share * 100, 1),
                ),
            )
        )

    if "date" in affected.columns:
        dates = pd.to_datetime(affected["date"], errors="coerce", format="mixed").dropna()
        base_dates = None
        for column in ("date", "promisedDate"):
            if column in baseline.columns:
                base_dates = pd.to_datetime(baseline[column], errors="coerce", format="mixed").dropna()
                break
        if not dates.empty and base_dates is not None and not base_dates.empty:
            months = dates.dt.strftime("%Y-%m")
            base_months = base_dates.dt.strftime("%Y-%m")
            top_month = str(months.value_counts().index[0])
            count = int((months == top_month).sum())
            share = count / len(months)
            base_share = max(float((base_months == top_month).mean()), 0.01)
            lift = share / base_share
            if share >= 0.4 and lift >= 1.3:
                facts.append(
                    (
                        lift,
                        fact(
                            f"{round(share * 100, 1)}% of the affected rows fall in {top_month} "
                            f"versus {round(base_share * 100, 1)}% of all orders ({round(lift, 1)}x lift).",
                            "month_share",
                            round(share * 100, 1),
                        ),
                    )
                )

    facts.sort(key=lambda item: item[0], reverse=True)
    logger.info("rootcause: %s factors", len(facts))
    return [item[1] for item in facts[:limit]]

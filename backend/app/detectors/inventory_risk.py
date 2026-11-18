"""Inventory risk: days of cover from recent sales velocity."""

from __future__ import annotations

import logging
from datetime import timedelta

import pandas as pd

from .common import Candidate, dataset_as_of, evidence_rows, fact

logger = logging.getLogger(__name__)

COVER_ALERT_DAYS = 7
COVER_CRITICAL_DAYS = 3
RECENT_SALES_DAYS = 14


def sales_rate_from_history(linked) -> dict[str, float]:
    sales = linked.sales
    if sales is None or sales.empty or "date" not in sales.columns or "quantity" not in sales.columns:
        return {}
    frame = sales.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce", format="mixed")
    frame = frame.dropna(subset=["date"])
    if frame.empty or "productId" not in frame.columns:
        return {}
    as_of = dataset_as_of(linked)
    recent = frame[frame["date"] >= as_of - pd.Timedelta(days=RECENT_SALES_DAYS)]
    if recent.empty:
        recent = frame
    totals = recent.groupby("productId")["quantity"].sum()
    days = max(RECENT_SALES_DAYS, 1)
    return {str(product): float(total) / days for product, total in totals.items()}


def unit_price(linked) -> dict[str, float]:
    sales = linked.sales
    if sales is None or sales.empty or "quantity" not in sales.columns or "amount" not in sales.columns:
        return {}
    frame = sales.dropna(subset=["quantity", "amount"])
    prices: dict[str, float] = {}
    for product, group in frame.groupby("productId"):
        quantity = pd.to_numeric(group["quantity"], errors="coerce").sum()
        amount = pd.to_numeric(group["amount"], errors="coerce").sum()
        if quantity and quantity > 0:
            prices[str(product)] = float(amount) / float(quantity)
    return prices


def detect(linked, *, max_candidates: int = 6) -> list[Candidate]:
    inventory = linked.inventory
    if inventory is None or inventory.empty or "stock" not in inventory.columns:
        logger.info("inventory_risk: no inventory stock column, skipped")
        return []

    frame = inventory.copy()
    frame["stock"] = pd.to_numeric(frame["stock"], errors="coerce")
    frame = frame.dropna(subset=["stock"])
    if frame.empty:
        return []

    history_rates = sales_rate_from_history(linked)
    prices = unit_price(linked)
    as_of = dataset_as_of(linked)
    candidates: list[Candidate] = []

    for _, row in frame.iterrows():
        product_id = str(row.get("productId")) if pd.notna(row.get("productId")) else None
        if not product_id:
            continue
        stock = float(row["stock"])
        rate = pd.to_numeric(pd.Series([row.get("dailySalesRate")]), errors="coerce").iloc[0]
        rate = float(rate) if pd.notna(rate) else history_rates.get(product_id)
        if not rate or rate <= 0:
            continue
        reorder = pd.to_numeric(pd.Series([row.get("reorderLevel")]), errors="coerce").iloc[0]
        reorder = float(reorder) if pd.notna(reorder) else None

        days_cover = stock / rate if rate > 0 else 0.0
        below_reorder = reorder is not None and stock <= reorder
        if stock > 0 and days_cover > COVER_ALERT_DAYS and not below_reorder:
            continue
        if stock <= 0:
            days_cover = 0.0

        price = prices.get(product_id, 0.0)
        target_stock = max(reorder or 0.0, rate * COVER_ALERT_DAYS)
        shortfall = max(target_stock - stock, 0.0)
        value_total = shortfall * price
        product_name = str(row.get("productName")) if pd.notna(row.get("productName")) else product_id
        stockout_date = (as_of + pd.Timedelta(days=max(0.0, days_cover))).date().isoformat()

        if stock <= 0:
            title = f"{product_name} is out of stock"
        elif days_cover < 1:
            title = f"{product_name} will stock out within a day"
        else:
            title = f"{product_name} will stock out in about {int(round(days_cover))} days"

        related_sales = pd.DataFrame()
        if linked.sales is not None and not linked.sales.empty and "productId" in linked.sales.columns:
            related_sales = linked.sales[linked.sales["productId"].astype(str) == product_id].head(5)

        facts = [
            fact(f"{product_name} has {int(stock)} units on hand.", "stock_on_hand", int(stock)),
            fact(
                f"Recent daily sales run at {round(rate, 2)} units per day.",
                "daily_sales_rate",
                round(rate, 2),
            ),
            fact(
                f"Days of cover is {round(days_cover, 1)} days.",
                "days_of_cover",
                round(days_cover, 1),
            ),
            fact(
                f"Projected stock-out date is {stockout_date}.",
                "projected_stockout",
                stockout_date,
            ),
        ]
        if reorder is not None:
            facts.append(
                fact(
                    f"The reorder level is {int(reorder)} units.",
                    "reorder_level",
                    int(reorder),
                )
            )

        unit_label = "products"
        candidates.append(
            Candidate(
                type="inventory_risk",
                title=title,
                summary=(
                    f"{product_name} holds {int(stock)} units against a {round(rate, 2)}/day sales rate, "
                    f"leaving {round(days_cover, 1)} days of cover"
                    + (f" and sitting below the {int(reorder)}-unit reorder level." if reorder is not None and below_reorder else ".")
                ),
                stat_strength=min(1.0, max(0.0, 1 - days_cover / 14) + (0.15 if below_reorder else 0)),
                affected_count=1,
                affected_value=value_total,
                recency_days=0.0,
                trend=0.5 if below_reorder else 0.3,
                customers=0,
                facts=facts,
                evidence=evidence_rows(frame[frame["productId"].astype(str) == product_id], limit=3)
                + evidence_rows(related_sales, limit=5),
                entities={"products": [product_id], "locations": [], "couriers": [], "orders": []},
                action_hint=(
                    f"Approve an emergency replenishment of {int(shortfall)} units for {product_name} today, "
                    f"or cap new orders to cover the {round(days_cover, 1)} days of stock on hand."
                ),
                preventive_hint=(
                    f"Raise the reorder level for {product_name} above {int(rate * 10)} units and review its "
                    f"velocity weekly."
                ),
                unit=unit_label,
                affected=frame[frame["productId"].astype(str) == product_id],
                group={"productId": product_id},
            )
        )

    candidates.sort(key=lambda item: item.stat_strength, reverse=True)
    logger.info("inventory_risk: %s candidates", len(candidates))
    return candidates[:max_candidates]

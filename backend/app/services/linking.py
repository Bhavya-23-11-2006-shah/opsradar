"""Link orders, deliveries, complaints, inventory and sales into one view."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class LinkedData:
    frames: dict[str, pd.DataFrame]
    orders: pd.DataFrame
    deliveries: pd.DataFrame
    complaints: pd.DataFrame
    inventory: pd.DataFrame
    sales: pd.DataFrame
    reviews: pd.DataFrame
    order_view: pd.DataFrame
    complaint_view: pd.DataFrame
    orphan_complaints: int = 0
    orphan_orders: int = 0
    notes: list[str] = field(default_factory=list)


def _empty(*columns: str) -> pd.DataFrame:
    return pd.DataFrame({column: pd.Series(dtype="object") for column in columns})


def _ensure_order_key(frame: pd.DataFrame) -> pd.DataFrame:
    if "orderId" in frame.columns:
        frame = frame.copy()
        frame["orderId"] = frame["orderId"].astype("string").str.strip()
    return frame


def _first_non_null(series_list: list[pd.Series]) -> pd.Series:
    result = series_list[0].copy()
    for series in series_list[1:]:
        result = result.where(result.notna(), series)
    return result


def link_datasets(frames: dict[str, pd.DataFrame]) -> LinkedData:
    orders = _ensure_order_key(frames.get("orders", _empty("orderId")))
    deliveries = _ensure_order_key(frames.get("deliveries", _empty("orderId")))
    complaints = _ensure_order_key(frames.get("complaints", _empty("orderId")))
    inventory = frames.get("inventory", _empty("productId")).copy()
    sales = _ensure_order_key(frames.get("sales", _empty("productId")))
    reviews = frames.get("reviews", _empty("productId")).copy()
    notes: list[str] = []

    if "productId" in inventory.columns:
        inventory["productId"] = inventory["productId"].astype("string").str.strip()
        inventory = inventory.drop_duplicates(subset=["productId"], keep="last")

    product_names: dict[str, str] = {}
    if {"productId", "productName"} <= set(inventory.columns):
        for product_id, product_name in zip(inventory["productId"], inventory["productName"]):
            if pd.notna(product_id) and pd.notna(product_name):
                product_names[str(product_id)] = str(product_name)

    order_view = orders.copy()
    if not deliveries.empty:
        delivery_cols = [
            column
            for column in ("orderId", "shippedDate", "deliveredDate", "promisedDate", "courier", "warehouse", "city", "status", "_row_id")
            if column in deliveries.columns
        ]
        delivery_subset = deliveries[delivery_cols].drop_duplicates(subset=["orderId"], keep="last")
        merged = order_view.merge(delivery_subset, on="orderId", how="left", suffixes=("", "_delivery"))
        for column in ("shippedDate", "deliveredDate", "promisedDate", "courier", "warehouse", "city", "status"):
            delivery_column = f"{column}_delivery"
            if delivery_column in merged.columns and column in merged.columns:
                merged[column] = _first_non_null([merged[column], merged[delivery_column]])
                merged = merged.drop(columns=[delivery_column])
        order_view = merged

    if "productName" not in order_view.columns:
        order_view["productName"] = None
    order_view["productName"] = order_view.apply(
        lambda row: row.get("productName")
        if pd.notna(row.get("productName"))
        else product_names.get(str(row.get("productId"))),
        axis=1,
    )

    if "promisedDate" in order_view.columns:
        order_view["promisedDate"] = pd.to_datetime(order_view["promisedDate"], errors="coerce", format="mixed")
    if "deliveredDate" in order_view.columns:
        order_view["deliveredDate"] = pd.to_datetime(order_view["deliveredDate"], errors="coerce", format="mixed")
    if "shippedDate" in order_view.columns:
        order_view["shippedDate"] = pd.to_datetime(order_view["shippedDate"], errors="coerce", format="mixed")

    if {"deliveredDate", "promisedDate"} <= set(order_view.columns):
        order_view["delayDays"] = (
            (order_view["deliveredDate"] - order_view["promisedDate"]).dt.days
        )
        order_view["late"] = (order_view["delayDays"] > 0).fillna(False)
    else:
        order_view["delayDays"] = pd.NA
        order_view["late"] = False

    status_series = order_view["status"].astype("string").str.lower() if "status" in order_view.columns else None
    cancelled = status_series.isin(["cancelled", "canceled", "returned"]) if status_series is not None else False
    delivered = order_view["deliveredDate"].notna() if "deliveredDate" in order_view.columns else False
    order_view["open"] = (~delivered) & (~cancelled)

    complaint_view = complaints.copy()
    complaint_view["category"] = None
    if not complaint_view.empty:
        order_cols = [
            column
            for column in ("orderId", "productId", "productName", "warehouse", "city", "courier", "customerId", "date")
            if column in order_view.columns
        ]
        order_subset = order_view[order_cols].drop_duplicates(subset=["orderId"], keep="first")
        complaint_view = complaint_view.merge(order_subset, on="orderId", how="left", suffixes=("", "_order"))
        for column in ("productId", "productName", "warehouse", "city", "courier", "customerId"):
            order_column = f"{column}_order"
            if order_column in complaint_view.columns:
                if column in complaint_view.columns:
                    complaint_view[column] = _first_non_null([complaint_view[column], complaint_view[order_column]])
                    complaint_view = complaint_view.drop(columns=[order_column])
                else:
                    complaint_view = complaint_view.rename(columns={order_column: column})
        if "date_order" in complaint_view.columns:
            if "date" in complaint_view.columns:
                complaint_view["date"] = _first_non_null([complaint_view["date"], complaint_view["date_order"]])
                complaint_view = complaint_view.drop(columns=["date_order"])
            else:
                complaint_view = complaint_view.rename(columns={"date_order": "date"})

    if "date" in complaint_view.columns:
        complaint_view["date"] = pd.to_datetime(complaint_view["date"], errors="coerce", format="mixed")

    if not sales.empty and "productName" not in sales.columns:
        sales = sales.copy()
        sales["productName"] = sales["productId"].map(lambda value: product_names.get(str(value)))

    orphan_complaints = 0
    if not complaint_view.empty and "orderId" in order_view.columns:
        known_orders = set(order_view["orderId"].dropna().astype(str))
        orphan_complaints = int(
            complaint_view["orderId"].notna().sum()
            - complaint_view["orderId"].dropna().astype(str).isin(known_orders).sum()
        )
    orphan_orders = 0
    if not orders.empty and "productId" in orders.columns and product_names:
        orphan_orders = int((~orders["productId"].astype(str).isin(product_names)).sum())

    if not orders.empty:
        notes.append(f"Linked {len(orders)} orders with {len(deliveries)} delivery rows.")
    else:
        notes.append("Orders file missing: order-level analyses skipped.")
    if orphan_complaints:
        notes.append(f"{orphan_complaints} complaints could not be linked to an order.")
    if orphan_orders:
        notes.append(f"{orphan_orders} orders reference products missing from inventory.")

    logger.info("linking: %s orders, %s complaints, %s orphans", len(orders), len(complaint_view), orphan_complaints + orphan_orders)

    return LinkedData(
        frames=frames,
        orders=orders,
        deliveries=deliveries,
        complaints=complaints,
        inventory=inventory,
        sales=sales,
        reviews=reviews,
        order_view=order_view,
        complaint_view=complaint_view,
        orphan_complaints=orphan_complaints,
        orphan_orders=orphan_orders,
        notes=notes,
    )

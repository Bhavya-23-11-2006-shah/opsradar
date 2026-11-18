"""Overview aggregation from the stored analytics snapshot."""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {"open", "investigating", "escalated"}
MAX_TREND_DAYS = 120


def _serialise(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def build_snapshot(linked, findings: list[dict], at_risk_orders: list[dict]) -> dict:
    complaints = linked.complaint_view
    rows: list[dict] = []
    if complaints is not None and not complaints.empty:
        for _, row in complaints.iterrows():
            complaint_date = row.get("date")
            rows.append(
                {
                    "date": complaint_date.date().isoformat() if pd.notna(complaint_date) else None,
                    "category": _serialise(row.get("category")) or "Other",
                    "productId": _serialise(row.get("productId")),
                    "productName": _serialise(row.get("productName")),
                    "courier": _serialise(row.get("courier")),
                    "warehouse": _serialise(row.get("warehouse")),
                    "city": _serialise(row.get("city")),
                }
            )

    inventory_rows: list[dict] = []
    inventory = linked.inventory
    if inventory is not None and not inventory.empty and "stock" in inventory.columns:
        from ..detectors.inventory_risk import sales_rate_from_history

        rates = sales_rate_from_history(linked)
        for _, row in inventory.iterrows():
            stock = pd.to_numeric(pd.Series([row.get("stock")]), errors="coerce").iloc[0]
            rate = pd.to_numeric(pd.Series([row.get("dailySalesRate")]), errors="coerce").iloc[0]
            product_id = _serialise(row.get("productId"))
            if pd.isna(rate) or not rate:
                rate = rates.get(str(product_id), 0.0)
            rate = float(rate) if rate and not pd.isna(rate) else 0.0
            stock_value = float(stock) if pd.notna(stock) else 0.0
            days_cover = round(stock_value / rate, 1) if rate > 0 else None
            inventory_rows.append(
                {
                    "productId": product_id,
                    "productName": _serialise(row.get("productName")),
                    "daysCover": days_cover,
                }
            )

    product_ids: set[str] = set()
    locations: set[str] = set()
    couriers: set[str] = set()
    for frame in (linked.order_view, complaints, linked.inventory, linked.sales):
        if frame is None or frame.empty:
            continue
        for column, bucket in (
            ("productId", product_ids),
            ("warehouse", locations),
            ("city", locations),
            ("courier", couriers),
        ):
            if column in frame.columns:
                bucket.update(str(value) for value in frame[column].dropna().unique() if str(value).strip())

    date_min = None
    date_max = None
    if rows:
        dates = [row["date"] for row in rows if row["date"]]
        if dates:
            date_min, date_max = min(dates), max(dates)

    findings_summary = [
        {
            "id": finding["id"],
            "status": finding["status"],
            "severity": finding["severity"],
            "riskScore": finding["riskScore"],
            "type": finding["type"],
            "createdAt": finding["createdAt"],
            "products": finding.get("relatedEntities", {}).get("products", []),
            "locations": finding.get("relatedEntities", {}).get("locations", []),
            "couriers": finding.get("relatedEntities", {}).get("couriers", []),
        }
        for finding in findings
    ]

    snapshot = {
        "complaints": rows,
        "atRiskOrders": at_risk_orders,
        "inventory": inventory_rows,
        "findings": findings_summary,
        "filters": {
            "products": sorted(product_ids),
            "locations": sorted(locations),
            "couriers": sorted(couriers),
            "dateMin": date_min,
            "dateMax": date_max,
        },
    }
    logger.info(
        "snapshot: %s complaint rows, %s at-risk orders, %s inventory rows",
        len(rows),
        len(at_risk_orders),
        len(inventory_rows),
    )
    return snapshot


def _anomaly_flags(counts: list[int]) -> list[bool]:
    """Flag days whose trailing 7-day complaint total is abnormally high."""
    window = 7
    if len(counts) < window + 3:
        return [False] * len(counts)
    series = pd.Series(counts, dtype="float64")
    rolling = series.rolling(window, min_periods=window).sum()
    median = float(rolling.median())
    mad = float((rolling - median).abs().median())
    if mad == 0:
        std = float(rolling.std(ddof=0))
        mad = std * 1.4826 if std else 1.0
    flags = []
    for value in rolling:
        if pd.isna(value):
            flags.append(False)
            continue
        z = 0.6745 * (float(value) - median) / mad
        flags.append(bool(z >= 1.8 and float(value) >= max(6.0, median * 1.25)))
    return flags


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def build_overview(
    snapshot: dict,
    *,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    product: Optional[str] = None,
    location: Optional[str] = None,
    courier: Optional[str] = None,
) -> dict:
    start = _parse_date(from_date)
    end = _parse_date(to_date)
    filters = snapshot.get("filters", {})
    all_products = filters.get("products", [])

    def complaint_matches(row: dict) -> bool:
        row_date = _parse_date(row.get("date"))
        if start and row_date and row_date < start:
            return False
        if end and row_date and row_date > end:
            return False
        if product and row.get("productId") != product:
            return False
        if courier and row.get("courier") != courier:
            return False
        if location and location not in {row.get("warehouse"), row.get("city")}:
            return False
        return True

    complaints = [row for row in snapshot.get("complaints", []) if complaint_matches(row)]

    def finding_matches(finding: dict) -> bool:
        if product and product not in finding.get("products", []):
            return False
        if location and location not in finding.get("locations", []) and location not in finding.get("couriers", []):
            return False
        if courier and courier not in finding.get("couriers", []):
            return False
        return True

    findings = [finding for finding in snapshot.get("findings", []) if finding_matches(finding)]

    def order_matches(order: dict) -> bool:
        if product and order.get("productId") != product:
            return False
        if courier and order.get("courier") != courier:
            return False
        if location and location not in {order.get("warehouse"), order.get("city")}:
            return False
        order_date = _parse_date(order.get("promisedDate")) or _parse_date(order.get("date"))
        if start and order_date and order_date < start:
            return False
        if end and order_date and order_date > end:
            return False
        return True

    at_risk_orders = [order for order in snapshot.get("atRiskOrders", []) if order_matches(order)]

    inventory = snapshot.get("inventory", [])
    if product:
        inventory = [row for row in inventory if row.get("productId") == product]
    near_stockout = [
        row
        for row in inventory
        if row.get("daysCover") is not None and float(row["daysCover"]) <= 7
    ]

    trends: list[dict] = []
    if complaints:
        dates = sorted({row["date"] for row in complaints if row.get("date")})
        if dates:
            first = start or _parse_date(dates[0])
            last = end or _parse_date(dates[-1])
            if first and last and first <= last:
                span = min((last - first).days + 1, MAX_TREND_DAYS)
                first = last - timedelta(days=span - 1)
                counts_by_date = Counter(row["date"] for row in complaints if row.get("date"))
                series_dates = [first + timedelta(days=offset) for offset in range(span)]
                counts = [int(counts_by_date.get(day.isoformat(), 0)) for day in series_dates]
                flags = _anomaly_flags(counts)
                trends = [
                    {"date": day.isoformat(), "complaints": value, "anomaly": flag}
                    for day, value, flag in zip(series_dates, counts, flags)
                ]

    category_counts = Counter(row.get("category") or "Other" for row in complaints)
    category_breakdown = [
        {"category": category, "count": int(count)}
        for category, count in category_counts.most_common()
    ]

    risk_distribution: list[dict] = []
    for group in ("courier", "warehouse", "city"):
        counts = Counter(row.get(group) for row in complaints if row.get(group))
        if not counts:
            continue
        peak = max(counts.values())
        probabilities: dict[str, list[float]] = defaultdict(list)
        for order in at_risk_orders:
            name = order.get(group)
            if name:
                probabilities[name].append(float(order.get("probability", 0)))
        for name, count in counts.most_common(6):
            exposure = sum(probabilities.get(name, [])) / len(probabilities[name]) if probabilities.get(name) else 0.0
            score = 100 * (0.6 * (count / peak) + 0.4 * exposure)
            risk_distribution.append(
                {"group": group, "name": name, "riskScore": round(score, 1)}
            )
        for name, values in probabilities.items():
            if name not in counts:
                score = 100 * 0.4 * (sum(values) / len(values))
                risk_distribution.append(
                    {"group": group, "name": name, "riskScore": round(score, 1)}
                )
        risk_distribution.sort(key=lambda item: item["riskScore"], reverse=True)

    product_counts: Counter = Counter()
    product_names: dict[str, str] = {}
    for row in complaints:
        product_id = row.get("productId")
        if not product_id:
            continue
        product_counts[product_id] += 1
        if row.get("productName"):
            product_names[product_id] = row["productName"]
    top_problem_products = [
        {
            "productId": product_id,
            "productName": product_names.get(product_id),
            "complaints": int(count),
        }
        for product_id, count in product_counts.most_common(8)
    ]

    kpis = {
        "openIssues": sum(1 for finding in findings if finding["status"] in ACTIVE_STATUSES),
        "criticalRisks": sum(
            1 for finding in findings if finding["severity"] == "critical" and finding["status"] in ACTIVE_STATUSES
        ),
        "ordersAtRisk": len(at_risk_orders),
        "productsNearStockout": len(near_stockout),
        "complaintSpikes": sum(1 for finding in findings if finding["type"] == "complaint_spike"),
    }

    logger.info("overview: kpis=%s complaints=%s", kpis, len(complaints))
    return {
        "kpis": kpis,
        "trends": trends,
        "categoryBreakdown": category_breakdown,
        "riskDistribution": risk_distribution[:18],
        "topProblemProducts": top_problem_products,
        "filters": {
            "products": all_products,
            "locations": filters.get("locations", []),
            "couriers": filters.get("couriers", []),
            "dateMin": filters.get("dateMin"),
            "dateMax": filters.get("dateMax"),
        },
    }

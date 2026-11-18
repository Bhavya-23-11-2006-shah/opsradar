"""Each planted demo problem must surface as a finding with evidence."""

from __future__ import annotations


def _facts(finding: dict) -> str:
    return " ".join(item["statement"] for item in finding["verifiedFacts"]).lower()


def test_damaged_packaging_traces_to_one_courier(analyzed):
    findings = analyzed["findings"]
    candidates = [
        finding
        for finding in findings
        if finding["type"] == "recurring_issue"
        and "damaged packaging" in finding["title"].lower()
        and "metro" in _facts(finding)
    ]
    assert candidates, [finding["title"] for finding in findings]
    finding = candidates[0]
    assert finding["evidenceRows"]
    assert finding["relatedEntities"]["couriers"]
    assert any(fact["metric"] == "lift" for fact in finding["verifiedFacts"])


def test_complaint_spike_on_one_product(analyzed):
    spikes = [finding for finding in analyzed["findings"] if finding["type"] == "complaint_spike"]
    assert spikes, "planted complaint spike was not detected"
    spike = spikes[0]
    assert "last 7 days" in spike["title"]
    facts = {fact["metric"]: fact["value"] for fact in spike["verifiedFacts"]}
    assert facts["recent_complaints"] >= 20
    assert facts["spike_ratio"] >= 2
    assert spike["evidenceRows"]


def test_stockout_product_in_about_three_days(analyzed):
    risks = [finding for finding in analyzed["findings"] if finding["type"] == "inventory_risk"]
    assert risks, "no inventory risk detected"
    covers = []
    for finding in risks:
        metrics = {fact["metric"]: fact["value"] for fact in finding["verifiedFacts"]}
        covers.append(float(metrics["days_of_cover"]))
    assert any(cover <= 3.5 for cover in covers), covers
    assert all(any(fact["metric"] == "stock_on_hand" for fact in finding["verifiedFacts"]) for finding in risks)


def test_rising_warehouse_delivery_risk(analyzed):
    risks = [finding for finding in analyzed["findings"] if finding["type"] == "delivery_risk"]
    assert risks, "no delivery risk detected"
    south = [finding for finding in risks if "wh-south" in _facts(finding)]
    assert south, [finding["title"] for finding in risks]
    finding = south[0]
    metrics = {fact["metric"]: fact["value"] for fact in finding["verifiedFacts"]}
    assert metrics["recent_late_share"] > metrics["baseline_late_share"]
    assert metrics["orders_at_risk"] >= 3
    assert finding["relatedEntities"]["orders"]


def test_sales_anomaly(analyzed):
    anomalies = [finding for finding in analyzed["findings"] if finding["type"] == "anomaly"]
    assert anomalies, "planted sales anomaly was not detected"
    assert any(fact["metric"] == "robust_z" for fact in anomalies[0]["verifiedFacts"])


def test_overview_exposes_planted_signals(client, analyzed):
    overview = client.get(f"/api/overview/{analyzed['dataset_id']}").json()
    assert overview["kpis"]["complaintSpikes"] >= 1
    assert overview["kpis"]["ordersAtRisk"] > 0
    assert overview["kpis"]["productsNearStockout"] >= 1
    assert any(point["anomaly"] for point in overview["trends"])
    assert any(group["group"] == "courier" for group in overview["riskDistribution"])
    assert any(group["group"] == "warehouse" for group in overview["riskDistribution"])
    assert any(group["group"] == "city" for group in overview["riskDistribution"])
    assert overview["topProblemProducts"]


def test_quality_issues_are_reported(client, analyzed):
    quality = client.get(f"/api/quality/{analyzed['dataset_id']}").json()
    notes = " ".join(issue["note"] for issue in quality["duplicates"]).lower()
    assert "duplicate" in notes
    inconsistent = " ".join(issue["note"] for issue in quality["inconsistent"]).lower()
    assert "negative stock" in inconsistent or "delivered before" in inconsistent

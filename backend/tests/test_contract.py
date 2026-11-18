"""Every endpoint is exercised against the demo dataset and validated strictly."""

from __future__ import annotations

import time
from typing import Any

from app.schemas import (
    ActionsResponse,
    AnalyzeResponse,
    DecisionRequest,
    Finding,
    HealthResponse,
    InvestigationTask,
    MapSchemaResponse,
    OverviewResponse,
    ProgressResponse,
    QualityResponse,
    ReportResponse,
    StatusRequest,
    TaskRequest,
    UploadResponse,
)

LIST_KEYS = {
    "missing",
    "duplicates",
    "inconsistent",
    "rowIds",
    "files",
    "verifiedFacts",
    "aiHypotheses",
    "evidenceRows",
    "products",
    "locations",
    "couriers",
    "orders",
    "trends",
    "categoryBreakdown",
    "riskDistribution",
    "topProblemProducts",
    "log",
    "tasks",
    "columns",
}


def assert_no_null_lists(payload: Any) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in LIST_KEYS:
                assert isinstance(value, list), f"{key} must be a list, got {type(value).__name__}"
            assert_no_null_lists(value)
    elif isinstance(payload, list):
        for item in payload:
            assert_no_null_lists(item)


def parse(model, response):
    assert response.status_code == 200, response.text
    payload = response.json()
    assert_no_null_lists(payload)
    return model.model_validate(payload)


def test_health(client):
    payload = parse(HealthResponse, client.get("/api/health"))
    assert payload.contract_version == "1"
    assert payload.llm_mode in {"llm", "template"}


def test_demo_generate_and_upload(client, analyzed):
    demo = UploadResponse.model_validate(analyzed["demo"])
    assert demo.dataset_id
    assert len(demo.files) >= 4
    for entry in demo.files:
        assert entry.rows > 0
        assert entry.columns
        assert entry.suggested_mapping.file_name == entry.name

    with open("demo_data/orders.csv", "rb") as handle:
        sample = handle.read()
    upload = client.post(
        "/api/upload",
        files=[("files", ("uploaded_orders.csv", sample, "text/csv"))],
    )
    parsed = parse(UploadResponse, upload)
    assert parsed.files[0].detected_type in {"orders", "deliveries", "unknown"}

    wrong_field = client.post(
        "/api/upload",
        files=[("file", ("orders.csv", sample, "text/csv"))],
    )
    assert wrong_field.status_code == 422
    assert set(wrong_field.json()) == {"error", "detail"}


def test_map_schema(client, analyzed):
    mapping = {"files": [entry["suggestedMapping"] for entry in analyzed["demo"]["files"]]}
    response = client.post(
        "/api/map-schema",
        json={"datasetId": analyzed["dataset_id"], "mapping": mapping},
    )
    parsed = parse(MapSchemaResponse, response)
    assert parsed.confirmed is True
    assert parsed.dataset_id == analyzed["dataset_id"]


def test_analyze_and_progress(client, analyzed):
    dataset_id = analyzed["dataset_id"]
    analyze = client.post(f"/api/analyze/{dataset_id}")
    assert analyze.status_code == 200
    assert analyze.json() == {"status": "running"}

    progress = parse(ProgressResponse, client.get(f"/api/progress/{dataset_id}"))
    assert progress.status == "done"
    assert progress.percent == 100.0

    assert analyzed["analysis_seconds"] < 30, f"analysis took {analyzed['analysis_seconds']:.1f}s"


def test_quality(client, analyzed):
    quality = parse(QualityResponse, client.get(f"/api/quality/{analyzed['dataset_id']}"))
    assert 0 <= quality.health_score <= 100
    assert quality.summary
    assert any(issue.count > 0 for issue in quality.duplicates)
    assert any(issue.count > 0 for issue in quality.inconsistent)
    assert any(issue.count > 0 for issue in quality.missing)


def test_overview(client, analyzed):
    dataset_id = analyzed["dataset_id"]
    overview = parse(OverviewResponse, client.get(f"/api/overview/{dataset_id}"))
    assert overview.filters.products
    assert overview.trends
    assert overview.kpis.open_issues > 0

    filtered = parse(
        OverviewResponse,
        client.get(
            f"/api/overview/{dataset_id}",
            params={"courier": "MetroDash", "from": overview.filters.date_min, "to": overview.filters.date_max},
        ),
    )
    assert filtered.kpis.orders_at_risk <= overview.kpis.orders_at_risk
    assert all(point.complaints >= 0 for point in filtered.trends)


def test_findings_list_and_detail(client, analyzed):
    dataset_id = analyzed["dataset_id"]
    response = client.get(f"/api/findings/{dataset_id}")
    assert response.status_code == 200
    findings = [Finding.model_validate(item) for item in response.json()]
    assert findings
    assert all(len(finding.evidence_rows) <= 5 for finding in findings)
    assert_no_null_lists(response.json())

    carrying_more = next((finding for finding in findings if len(finding.evidence_rows) == 5), findings[0])
    detail_response = client.get(f"/api/findings/{dataset_id}/{carrying_more.id}")
    detail = parse(Finding, detail_response)
    assert len(detail.evidence_rows) >= len(carrying_more.evidence_rows)
    assert detail.verified_facts and detail.ai_hypotheses
    assert detail.recommendation.action

    search = client.get(f"/api/findings/{dataset_id}", params={"severity": "high"})
    assert all(item["severity"] == "high" for item in search.json())

    filtered = client.get(f"/api/findings/{dataset_id}", params={"type": "inventory_risk"})
    assert all(item["type"] == "inventory_risk" for item in filtered.json())

    searched = client.get(f"/api/findings/{dataset_id}", params={"search": "damaged"})
    assert all(
        "damaged" in " ".join(
            [item["title"], item["summary"], item["businessImpact"], item["recommendation"]["action"]]
        ).lower()
        for item in searched.json()
    )


def test_decision_status_task_and_actions(client, analyzed):
    dataset_id = analyzed["dataset_id"]
    findings = client.get(f"/api/findings/{dataset_id}").json()
    first, second, third = findings[0], findings[1], findings[2]

    approved = parse(
        Finding,
        client.post(
            f"/api/findings/{dataset_id}/{first['id']}/decision",
            json={"decision": "approve", "note": "Investigate this week"},
        ),
    )
    assert approved.status == "investigating"

    rejected = parse(
        Finding,
        client.post(
            f"/api/findings/{dataset_id}/{second['id']}/decision",
            json={"decision": "reject", "note": "Known seasonal effect"},
        ),
    )
    assert rejected.status == "rejected"

    escalated = parse(
        Finding,
        client.post(
            f"/api/findings/{dataset_id}/{third['id']}/decision",
            json={"decision": "escalate", "note": "Needs carrier call"},
        ),
    )
    assert escalated.status == "escalated"

    changed = parse(
        Finding,
        client.patch(
            f"/api/findings/{dataset_id}/{third['id']}/status",
            json={"status": "resolved"},
        ),
    )
    assert changed.status == "resolved"

    task = parse(
        InvestigationTask,
        client.post(
            f"/api/findings/{dataset_id}/{first['id']}/task",
            json={"title": "Call the carrier about missed promises"},
        ),
    )
    assert task.finding_id == first["id"]
    assert task.status == "open"

    invalid_task = client.post(
        f"/api/findings/{dataset_id}/{first['id']}/task",
        json={"title": "   "},
    )
    assert invalid_task.status_code == 422

    actions = parse(ActionsResponse, client.get(f"/api/actions/{dataset_id}"))
    assert len(actions.log) >= 5
    assert len(actions.tasks) >= 1
    assert {entry.decision for entry in actions.log} >= {
        "approve",
        "reject",
        "escalate",
        "task_created",
    }
    assert all(entry.actor for entry in actions.log)


def test_report(client, analyzed):
    report = parse(ReportResponse, client.post(f"/api/report/{analyzed['dataset_id']}"))
    for section in (
        "## Executive summary",
        "## Top risks",
        "## Findings",
        "## Decisions taken",
        "## Next steps",
    ):
        assert section in report.markdown
    assert "Verified facts" in report.markdown
    assert "AI hypotheses (unconfirmed" in report.markdown


def test_error_envelope(client, analyzed):
    missing = client.get("/api/findings/does-not-exist")
    assert missing.status_code == 404
    assert set(missing.json()) == {"error", "detail"}
    assert isinstance(missing.json()["error"], str)

    bad_enum = client.post(
        f"/api/findings/{analyzed['dataset_id']}/{analyzed['findings'][0]['id']}/decision",
        json={"decision": "maybe", "note": "nope"},
    )
    assert bad_enum.status_code == 422
    assert set(bad_enum.json()) == {"error", "detail"}

    missing_note = client.post(
        f"/api/findings/{analyzed['dataset_id']}/{analyzed['findings'][0]['id']}/decision",
        json={"decision": "approve"},
    )
    assert missing_note.status_code == 422

    bad_industry = client.post("/api/demo/generate", json={"industry": "groceries"})
    assert bad_industry.status_code == 422


def test_analysis_runtime_budget(client):
    demo = client.post("/api/demo/generate", json={"industry": "skincare"}).json()
    dataset_id = demo["datasetId"]
    mapping = {"files": [entry["suggestedMapping"] for entry in demo["files"]]}
    client.post("/api/map-schema", json={"datasetId": dataset_id, "mapping": mapping})

    started = time.perf_counter()
    client.post(f"/api/analyze/{dataset_id}")
    elapsed = time.perf_counter() - started
    assert client.get(f"/api/progress/{dataset_id}").json()["status"] == "done"
    assert elapsed < 30, f"analysis took {elapsed:.1f}s"

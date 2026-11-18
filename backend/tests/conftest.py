from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def analyzed(client: TestClient) -> dict:
    """A fully analysed fashion demo dataset shared by the contract tests."""
    demo_response = client.post("/api/demo/generate", json={"industry": "fashion"})
    assert demo_response.status_code == 200, demo_response.text
    demo = demo_response.json()
    dataset_id = demo["datasetId"]

    mapping = {"files": [entry["suggestedMapping"] for entry in demo["files"]]}
    map_response = client.post("/api/map-schema", json={"datasetId": dataset_id, "mapping": mapping})
    assert map_response.status_code == 200, map_response.text

    started = time.perf_counter()
    analyze_response = client.post(f"/api/analyze/{dataset_id}")
    elapsed = time.perf_counter() - started
    assert analyze_response.status_code == 200, analyze_response.text

    progress = client.get(f"/api/progress/{dataset_id}").json()
    assert progress["status"] == "done", progress

    findings = client.get(f"/api/findings/{dataset_id}").json()
    assert findings, "analysis produced no findings"

    return {
        "dataset_id": dataset_id,
        "demo": demo,
        "findings": findings,
        "analysis_seconds": elapsed,
    }

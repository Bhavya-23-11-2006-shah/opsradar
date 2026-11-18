"""The analysis pipeline: clean -> link -> detect -> assess -> recommend."""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Optional

import pandas as pd

from .. import db
from ..config import DATA_DIR
from ..detectors import anomalies, delivery_risk, inventory_risk, recurring, spikes
from ..llm import client as llm_client
from ..schemas import SchemaMapping
from . import categorise as categorise_service
from . import ai_layer, cleaning, linking, rootcause, scoring
from .overview import build_snapshot

logger = logging.getLogger(__name__)

MAX_FINDINGS = 40


def _finding_id(candidate, dataset_id: str) -> str:
    material = f"{candidate.type}|{sorted(candidate.group.items())}|{candidate.title}"
    # Scoping by dataset keeps IDs stable across re-analysis without colliding globally.
    return f"fnd-{dataset_id[-8:]}-{hashlib.sha1(material.encode('utf-8')).hexdigest()[:8]}"


def _stage(dataset_id: str, step: str, percent: float, message: str) -> None:
    db.set_progress(dataset_id, status="running", step=step, percent=percent, message=message)


def _candidates(linked) -> tuple[list, list[dict], list[str]]:
    notes: list[str] = []
    candidates: list = []
    timings: dict[str, float] = {}

    def timed(name: str, function, *args, **kwargs):
        started = time.perf_counter()
        result = function(*args, **kwargs)
        timings[name] = round(time.perf_counter() - started, 2)
        return result

    candidates.extend(timed("recurring", recurring.detect, linked))
    candidates.extend(timed("spikes", spikes.detect, linked))
    candidates.extend(timed("anomalies", anomalies.detect, linked))
    candidates.extend(timed("inventory_risk", inventory_risk.detect, linked))
    delivery_candidates, at_risk_orders, delivery_notes = timed("delivery_risk", delivery_risk.detect, linked)
    candidates.extend(delivery_candidates)
    notes.extend(delivery_notes)
    logger.info("detector timings: %s", timings)
    return candidates, at_risk_orders, notes


def _dedupe(candidates: list) -> list:
    seen: set[tuple] = set()
    unique = []
    for candidate in candidates:
        key = (candidate.type, tuple(sorted(candidate.group.items())), candidate.title)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def run_pipeline(dataset_id: str) -> None:
    started = time.perf_counter()
    stage_timings: dict[str, float] = {}
    dataset = db.get_dataset(dataset_id)
    if dataset is None:
        logger.error("pipeline: unknown dataset %s", dataset_id)
        return

    try:
        if not dataset.mapping_json:
            raise ValueError("No schema mapping has been confirmed for this dataset.")
        mapping = SchemaMapping.model_validate_json(dataset.mapping_json)
        dataset_dir = DATA_DIR / "datasets" / dataset_id

        _stage(dataset_id, "Cleaning", 4, "Normalising columns, dates and categories")
        marker = time.perf_counter()
        cleaned = cleaning.clean_dataset(dataset_dir, mapping)
        stage_timings["cleaning"] = round(time.perf_counter() - marker, 2)
        db.update_dataset(dataset_id, quality_json=db.dumps(cleaned.quality))
        _stage(dataset_id, "Cleaning", 18, cleaned.quality["summary"])

        marker = time.perf_counter()
        _stage(dataset_id, "Linking datasets", 26, "Joining orders, deliveries, complaints and inventory")
        linked = linking.link_datasets(cleaned.frames)
        stage_timings["linking"] = round(time.perf_counter() - marker, 2)

        _stage(dataset_id, "Detecting patterns", 40, "Categorising complaints and testing patterns")
        marker = time.perf_counter()
        complaint_view, category_counts, category_notes = categorise_service.categorise(linked, llm_client)
        linked.complaint_view = complaint_view
        candidates, at_risk_orders, detector_notes = _candidates(linked)
        stage_timings["detection"] = round(time.perf_counter() - marker, 2)

        _stage(dataset_id, "Assessing risks", 66, "Scoring severity and testing root-cause factors")
        marker = time.perf_counter()
        candidates = _dedupe(candidates)
        findings: list[dict] = []
        candidates_by_id: dict[str, object] = {}
        for candidate in candidates:
            root_cause_facts = rootcause.detect_factors(linked, candidate.affected)
            existing = {item["statement"] for item in candidate.facts}
            for fact_item in root_cause_facts:
                if fact_item["statement"] not in existing:
                    candidate.facts.append(fact_item)
            risk_score, severity, business_impact = scoring.score_candidate(candidate)
            finding_id = _finding_id(candidate, dataset_id)
            candidates_by_id[finding_id] = candidate
            findings.append(
                {
                    "id": finding_id,
                    "title": candidate.title,
                    "type": candidate.type,
                    "riskScore": risk_score,
                    "severity": severity,
                    "businessImpact": business_impact,
                    "summary": candidate.summary,
                    "verifiedFacts": candidate.facts,
                    "aiHypotheses": [],
                    "evidenceRows": candidate.evidence,
                    "relatedEntities": {
                        "products": candidate.entities.get("products", [])[:12],
                        "locations": candidate.entities.get("locations", [])[:12],
                        "couriers": candidate.entities.get("couriers", [])[:12],
                        "orders": candidate.entities.get("orders", [])[:20],
                    },
                    "recommendation": {
                        "action": candidate.action_hint,
                        "why": "",
                        "preventive": candidate.preventive_hint,
                        "priority": ai_layer.PRIORITY_BY_SEVERITY.get(severity, "normal"),
                    },
                    "status": "open",
                    "createdAt": db.now_iso(),
                }
            )

        findings.sort(key=lambda item: float(item["riskScore"]), reverse=True)
        findings = findings[:MAX_FINDINGS]
        candidates_by_id = {finding["id"]: candidates_by_id[finding["id"]] for finding in findings}
        stage_timings["scoring"] = round(time.perf_counter() - marker, 2)

        _stage(dataset_id, "Generating recommendations", 82, "Writing hypotheses and recommendations")
        marker = time.perf_counter()
        ai_layer.apply_ai(findings, candidates_by_id, llm_client, top_n=10)
        stage_timings["ai"] = round(time.perf_counter() - marker, 2)

        db.save_finding_payloads(dataset_id, findings)
        snapshot = build_snapshot(linked, findings, at_risk_orders)
        db.update_dataset(dataset_id, snapshot_json=db.dumps(snapshot))

        for note in cleaned.notes + linked.notes + category_notes + detector_notes:
            logger.info("pipeline note: %s", note)

        elapsed = time.perf_counter() - started
        logger.info(
            "pipeline done dataset=%s findings=%s timings=%s total=%.2fs",
            dataset_id,
            len(findings),
            stage_timings,
            elapsed,
        )
        db.set_progress(
            dataset_id,
            status="done",
            step=None,
            percent=100,
            message=f"Analysis complete in {elapsed:.1f}s with {len(findings)} findings.",
        )
    except Exception as exc:  # noqa: BLE001 - surface the failure through progress
        logger.exception("pipeline failed for %s", dataset_id)
        db.set_progress(
            dataset_id,
            status="error",
            step=None,
            percent=0,
            message=f"{exc.__class__.__name__}: {exc}",
        )

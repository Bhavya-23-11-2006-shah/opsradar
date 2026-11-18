"""Facts -> hypotheses. The LLM never computes numbers; template mode is complete."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..config import CACHE_DIR
from ..llm import LLMClient
from ..schemas import to_camel

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are an operations analyst. You are given computed facts and evidence rows for one business finding. "
    "Use ONLY the supplied data; never invent numbers, entities or events. Output JSON only, matching: "
    "{aiHypotheses:[{statement, confidence (0-1), reasoning}], recommendation:{action, why, preventive, priority "
    "(urgent|high|normal|low)}}. Every cause you propose is a HYPOTHESIS: say what extra evidence would confirm or "
    "reject it, and keep confidence at or below 0.8. Never state a cause as confirmed. Recommendations must be "
    "concrete, small steps a manager can approve today, and must say why, citing the supplied facts."
)

MAX_CONFIDENCE = 0.8


class HypothesisOut(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")

    statement: str
    confidence: float = Field(ge=0, le=1)
    reasoning: str


class RecommendationOut(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")

    action: str
    why: str
    preventive: str
    priority: Literal["urgent", "high", "normal", "low"]


class AiOutput(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")

    ai_hypotheses: list[HypothesisOut] = Field(default_factory=list)
    recommendation: RecommendationOut


_CACHE_FILE = CACHE_DIR / "ai_cache.json"
_CACHE: dict[str, dict] = {}


def _load_cache() -> None:
    global _CACHE
    if _CACHE or not _CACHE_FILE.exists():
        return
    try:
        _CACHE = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        _CACHE = {}


def _save_cache() -> None:
    try:
        _CACHE_FILE.write_text(json.dumps(_CACHE), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.warning("AI cache not saved: %s", exc)


PRIORITY_BY_SEVERITY = {
    "critical": "urgent",
    "high": "high",
    "medium": "normal",
    "low": "low",
}


def _fact_map(candidate) -> dict:
    return {item["metric"]: item["value"] for item in candidate.facts}


def _group_label(candidate) -> str:
    for dimension, value in candidate.group.items():
        if dimension == "productId":
            return f"product {value}"
        return f"{dimension} {value}"
    return "the affected group"


def template_result(candidate, severity: str) -> dict:
    """Deterministic, fact-derived hypotheses. No invented numbers."""
    facts = _fact_map(candidate)
    group = _group_label(candidate)
    hypotheses: list[dict] = []

    def add(statement: str, reasoning: str, confidence: float) -> None:
        hypotheses.append(
            {
                "statement": statement,
                "confidence": round(min(confidence, MAX_CONFIDENCE), 2),
                "reasoning": reasoning,
            }
        )

    if candidate.type == "recurring_issue":
        share = facts.get("complaint_share")
        base = facts.get("order_share")
        add(
            f"A handling or transit problem specific to {group} may be driving the concentration "
            f"{share}% of these complaints versus {base}% of orders.",
            f"Would be confirmed by a site or route audit of {group} and by complaint notes mentioning handling damage. "
            "Would be rejected if the same product complains equally through other couriers or hubs.",
            0.6,
        )
        add(
            "Part of the pattern may be a labelling or assignment shift rather than a real change in operations.",
            "Would be confirmed by comparing category labels and order-to-courier assignment rules with the period before "
            "the lift appeared. Would be rejected if labels and routing rules are unchanged.",
            0.35,
        )
    elif candidate.type == "complaint_spike":
        recent = facts.get("recent_complaints")
        expected = facts.get("expected_complaints")
        add(
            f"A recent batch, listing or packaging change for {group} may explain {recent} complaints "
            f"against {expected} expected.",
            "Would be confirmed by batch numbers, listing edits or supplier changes in the spike window. "
            "Would be rejected if the same batch complains at the normal rate on other channels.",
            0.55,
        )
        add(
            "The spike may partly reflect a recording effect such as a new complaint intake campaign.",
            "Would be confirmed by a step change in complaint volume across all products. "
            "Would be rejected if other products keep their baseline volume.",
            0.3,
        )
    elif candidate.type == "anomaly":
        observed = facts.get("observed_value")
        median = facts.get("median_value")
        add(
            f"A short-term supply, listing or tracking gap for {group} may explain the day at {observed} "
            f"versus a median of {median}.",
            "Would be confirmed by stock-out logs, listing pauses or feed outages on that day. "
            "Would be rejected if stock and listings were healthy and the drop repeats without operational change.",
            0.5,
        )
    elif candidate.type == "delivery_risk":
        recent = facts.get("recent_late_share")
        baseline = facts.get("baseline_late_share")
        at_risk = facts.get("orders_at_risk")
        add(
            f"Capacity or route congestion at {group} may push the {at_risk} flagged orders past their promise, "
            f"with late share at {recent}% versus {baseline}% before.",
            "Would be confirmed by carrier capacity reports, hub scan delays or weather disruptions in the current window. "
            "Would be rejected if scan data shows normal transit times and misses are isolated.",
            0.6,
        )
    elif candidate.type == "inventory_risk":
        days = facts.get("days_of_cover")
        rate = facts.get("daily_sales_rate")
        add(
            f"Replenishment timing for {group} may be too slow for a {rate}/day run rate, leaving {days} days of cover.",
            "Would be confirmed by open purchase orders with arrival dates after the projected stock-out. "
            "Would be rejected if an inbound shipment is already confirmed to land before that date.",
            0.65,
        )

    if not hypotheses:
        add(
            f"The pattern around {group} may reflect an operational change rather than normal variation.",
            "Would be confirmed by an operational review of the affected period. "
            "Would be rejected if the pattern is stable across periods.",
            0.4,
        )

    action = candidate.action_hint or "Review the flagged rows with the owning team today."
    fact_statements = " ".join(item["statement"] for item in candidate.facts[:2])
    recommendation = {
        "action": action,
        "why": fact_statements or candidate.summary,
        "preventive": candidate.preventive_hint or "Add a weekly monitoring check for this pattern.",
        "priority": PRIORITY_BY_SEVERITY.get(severity, "normal"),
    }
    return {"aiHypotheses": hypotheses, "recommendation": recommendation}


def _allowed_numbers(candidate) -> set[float]:
    allowed: set[float] = set()

    def absorb(value) -> None:
        if isinstance(value, bool):
            return
        if isinstance(value, (int, float)):
            allowed.add(round(float(value), 4))
        elif isinstance(value, str):
            for token in re.findall(r"\d+(?:[.,]\d+)?", value):
                try:
                    allowed.add(round(float(token.replace(",", "")), 4))
                except ValueError:
                    continue

    for item in candidate.facts:
        absorb(item.get("value"))
        absorb(item.get("statement"))
    for row in candidate.evidence[:10]:
        for value in row.get("fields", {}).values():
            absorb(value)
    return allowed


def _numbers_are_grounded(text: str, allowed: set[float]) -> bool:
    for token in re.findall(r"\d+(?:[.,]\d+)?", text or ""):
        try:
            value = float(token.replace(",", ""))
        except ValueError:
            continue
        if not any(abs(value - known) <= max(0.06, abs(known) * 0.012) for known in allowed):
            return False
    return True


def _validated(result: Optional[dict], candidate) -> Optional[dict]:
    if not isinstance(result, dict):
        return None
    try:
        parsed = AiOutput.model_validate(result)
    except ValidationError as exc:
        logger.info("LLM output rejected: %s", exc.errors()[:2])
        return None
    if not parsed.ai_hypotheses:
        return None

    allowed = _allowed_numbers(candidate)
    hypotheses = []
    for hypothesis in parsed.ai_hypotheses[:4]:
        statement = " ".join(hypothesis.statement.split())
        reasoning = " ".join(hypothesis.reasoning.split())
        if not statement or not reasoning:
            continue
        if not _numbers_are_grounded(statement + " " + reasoning, allowed):
            logger.info("Dropped an LLM hypothesis that cited an unsupplied number")
            continue
        hypotheses.append(
            {
                "statement": statement,
                "confidence": round(min(max(hypothesis.confidence, 0.0), MAX_CONFIDENCE), 2),
                "reasoning": reasoning,
            }
        )
    if not hypotheses:
        return None

    recommendation = parsed.recommendation
    return {
        "aiHypotheses": hypotheses,
        "recommendation": {
            "action": recommendation.action,
            "why": recommendation.why,
            "preventive": recommendation.preventive,
            "priority": recommendation.priority,
        },
    }


def _cache_key(candidate, severity: str) -> str:
    material = {
        "type": candidate.type,
        "title": candidate.title,
        "severity": severity,
        "facts": candidate.facts,
        "evidence": [row.get("rowId") for row in candidate.evidence[:10]],
    }
    return hashlib.sha1(json.dumps(material, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def build_ai(candidate, severity: str, llm: LLMClient, *, allow_llm: bool) -> dict:
    _load_cache()
    key = _cache_key(candidate, severity)
    if key in _CACHE:
        return _CACHE[key]

    result: Optional[dict] = None
    if allow_llm and llm.configured:
        payload = {
            "finding": {
                "title": candidate.title,
                "type": candidate.type,
                "summary": candidate.summary,
                "unit": candidate.unit,
            },
            "verifiedFacts": candidate.facts,
            "evidenceRows": candidate.evidence[:10],
        }
        for attempt in range(2):
            raw = llm.complete_json(SYSTEM_PROMPT, json.dumps(payload, default=str), max_tokens=900)
            result = _validated(raw, candidate)
            if result is not None:
                break
            logger.info("LLM attempt %s invalid for %s", attempt + 1, candidate.title)

    if result is None:
        result = template_result(candidate, severity)

    _CACHE[key] = result
    _save_cache()
    return result


def apply_ai(findings: list[dict], candidates: dict[str, object], llm: LLMClient, *, top_n: int = 10) -> None:
    ranked = sorted(findings, key=lambda item: float(item.get("riskScore", 0)), reverse=True)
    llm_ids = {item["id"] for item in ranked[:top_n]}
    for finding in findings:
        candidate = candidates.get(finding["id"])
        if candidate is None:
            continue
        result = build_ai(candidate, finding["severity"], llm, allow_llm=finding["id"] in llm_ids)
        finding["aiHypotheses"] = result["aiHypotheses"]
        finding["recommendation"] = result["recommendation"]

"""Management report: executive summary, top risks, facts/hypotheses, decisions."""

from __future__ import annotations

import json
import logging
from typing import Optional

from .. import db
from ..llm import LLMClient

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM = (
    "You are an operations analyst writing an executive summary for a store operations manager. "
    "Use ONLY the supplied computed numbers. Never invent figures, products or events. "
    "Write four short sentences in plain prose, no markdown headings, no bullet list."
)


def _totals(findings: list[dict], actions: list[dict], quality: Optional[dict]) -> dict:
    return {
        "findings": len(findings),
        "critical": sum(1 for finding in findings if finding.get("severity") == "critical"),
        "high": sum(1 for finding in findings if finding.get("severity") == "high"),
        "open": sum(1 for finding in findings if finding.get("status") in {"open", "investigating", "escalated"}),
        "decisions": len(actions),
        "approved": sum(1 for action in actions if action.get("decision") == "approve"),
        "rejected": sum(1 for action in actions if action.get("decision") == "reject"),
        "escalated": sum(1 for action in actions if action.get("decision") == "escalate"),
        "qualityScore": (quality or {}).get("healthScore", 0),
        "topRisks": [
            {
                "title": finding["title"],
                "severity": finding["severity"],
                "riskScore": finding["riskScore"],
            }
            for finding in findings[:3]
        ],
    }


def _executive_summary(totals: dict, llm: LLMClient) -> str:
    if llm.configured and totals["findings"]:
        text = llm.complete_text(SUMMARY_SYSTEM, json.dumps(totals), max_tokens=400)
        if text and text.strip():
            return " ".join(text.split())
    if not totals["findings"]:
        return (
            "No findings have been generated yet. Load a dataset and run the analysis to populate this report."
        )
    top = totals["topRisks"][0] if totals["topRisks"] else None
    summary = (
        f"The analysis surfaced {totals['findings']} findings, of which {totals['critical']} are critical and "
        f"{totals['high']} are high severity. {totals['open']} remain open and "
        f"{totals['decisions']} decisions have been logged."
    )
    if top:
        summary += (
            f" The highest risk is '{top['title']}' with a risk score of {top['riskScore']}."
        )
    summary += (
        f" Data health sits at {totals['qualityScore']}/100, so treat the results as directional where the quality "
        "report flags missing or inconsistent rows."
    )
    return summary


def _fact_lines(finding: dict) -> list[str]:
    return [f"- {item['statement']}" for item in finding.get("verifiedFacts", [])]


def _hypothesis_lines(finding: dict) -> list[str]:
    lines = []
    for hypothesis in finding.get("aiHypotheses", []):
        confidence = round(float(hypothesis.get("confidence", 0)) * 100)
        lines.append(
            f"- {hypothesis['statement']} (confidence {confidence}%) — {hypothesis['reasoning']}"
        )
    return lines or ["- No hypotheses were generated."]


def build_markdown(
    dataset_id: str,
    findings: list[dict],
    actions: list[dict],
    tasks: list[dict],
    quality: Optional[dict],
    llm: LLMClient,
) -> dict:
    generated_at = db.now_iso()
    totals = _totals(findings, actions, quality)
    findings = sorted(findings, key=lambda item: float(item.get("riskScore", 0)), reverse=True)

    lines = [
        "# OpsRadar Management Report",
        "",
        f"Generated: {generated_at}  ",
        f"Dataset: `{dataset_id}`  ",
        f"Findings: {totals['findings']} · Critical: {totals['critical']} · Decisions logged: {totals['decisions']}  ",
        f"Data health score: {totals['qualityScore']}/100",
        "",
        "## Executive summary",
        "",
        _executive_summary(totals, llm),
        "",
        "## Top risks",
        "",
    ]

    if findings:
        lines.extend(["| Rank | Finding | Severity | Risk score | Status |", "| --- | --- | --- | --- | --- |"])
        for rank, finding in enumerate(findings[:8], start=1):
            lines.append(
                f"| {rank} | {finding['title']} | {finding['severity']} | {finding['riskScore']} | {finding['status']} |"
            )
    else:
        lines.append("_No findings yet._")

    lines.extend(["", "## Findings", ""])
    for index, finding in enumerate(findings[:10], start=1):
        recommendation = finding.get("recommendation", {})
        lines.extend(
            [
                f"### {index}. {finding['title']}",
                "",
                f"**Type:** {finding['type']} · **Severity:** {finding['severity']} · "
                f"**Risk score:** {finding['riskScore']} · **Status:** {finding['status']}",
                "",
                f"**Business impact:** {finding['businessImpact']}",
                "",
                "**Verified facts (deterministic engine):**",
                "",
                *_fact_lines(finding),
                "",
                "**AI hypotheses (unconfirmed, requires investigation):**",
                "",
                *_hypothesis_lines(finding),
                "",
                f"**Recommended action:** {recommendation.get('action', '')}",
                "",
                f"**Why:** {recommendation.get('why', '')}",
                "",
                f"**Preventive control:** {recommendation.get('preventive', '')}",
                "",
                f"**Priority:** {recommendation.get('priority', 'normal')}",
                "",
            ]
        )

    lines.extend(["## Decisions taken", ""])
    if actions:
        lines.extend(["| When | Finding | Decision | Note | Actor |", "| --- | --- | --- | --- | --- |"])
        for action in actions:
            note = (action.get("note") or "").replace("|", "\\|")
            lines.append(
                f"| {action['at']} | {action['findingTitle']} | {action['decision']} | {note} | {action['actor']} |"
            )
    else:
        lines.append("_No decisions logged yet._")

    lines.extend(["", "## Investigation tasks", ""])
    if tasks:
        for task in tasks:
            lines.append(f"- {task['title']} — {task['status']} (finding `{task['findingId']}`)")
    else:
        lines.append("_No investigation tasks created._")

    lines.extend(["", "## Next steps", ""])
    if findings:
        for finding in findings[:5]:
            action = finding.get("recommendation", {}).get("action")
            if action:
                lines.append(f"- {action}")
    else:
        lines.append("- Load a dataset and run the analysis.")

    markdown = "\n".join(lines).strip() + "\n"
    logger.info("report built for %s (%s chars)", dataset_id, len(markdown))
    return {"markdown": markdown, "generatedAt": generated_at}

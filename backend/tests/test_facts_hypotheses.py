"""The deterministic engine owns facts; the AI owns only labelled hypotheses."""

from __future__ import annotations

import re

HEDGES = ("hypothesis", "may be", "might", "could be", "possibly", "unconfirmed", "suspect")


def _numbers(text: str) -> list[float]:
    values = []
    for token in re.findall(r"\d+(?:[.,]\d+)?", text or ""):
        try:
            values.append(float(token.replace(",", "")))
        except ValueError:
            continue
    return values


def _allowed_numbers(finding: dict) -> set[float]:
    allowed: set[float] = set()

    def absorb(value) -> None:
        if isinstance(value, bool):
            return
        if isinstance(value, (int, float)):
            allowed.add(round(float(value), 4))
        elif isinstance(value, str):
            for number in _numbers(value):
                allowed.add(round(number, 4))

    for fact in finding["verifiedFacts"]:
        absorb(fact["value"])
        absorb(fact["statement"])
    for row in finding["evidenceRows"]:
        for value in row["fields"].values():
            absorb(value)
    return allowed


def _grounded(text: str, allowed: set[float]) -> bool:
    for value in _numbers(text):
        if not any(abs(value - known) <= max(0.06, abs(known) * 0.012) for known in allowed):
            return False
    return True


def test_verified_facts_are_never_ai_text(analyzed):
    for finding in analyzed["findings"]:
        assert finding["verifiedFacts"], finding["title"]
        for fact in finding["verifiedFacts"]:
            statement = fact["statement"].lower()
            assert fact["metric"]
            assert "hypothesis" not in statement
            assert not any(hedge in statement for hedge in HEDGES), fact["statement"]


def test_hypotheses_are_labelled_and_capped(analyzed):
    for finding in analyzed["findings"]:
        assert finding["aiHypotheses"], finding["title"]
        for hypothesis in finding["aiHypotheses"]:
            assert 0 <= hypothesis["confidence"] <= 0.8
            assert hypothesis["reasoning"]
            reasoning = hypothesis["reasoning"].lower()
            assert "confirm" in reasoning or "reject" in reasoning
        assert finding["recommendation"]["action"]
        assert finding["recommendation"]["why"]
        assert finding["recommendation"]["priority"] in {"urgent", "high", "normal", "low"}


def test_ai_output_invents_no_numbers(analyzed):
    for finding in analyzed["findings"]:
        allowed = _allowed_numbers(finding)
        for hypothesis in finding["aiHypotheses"]:
            assert _grounded(hypothesis["statement"], allowed), (
                finding["title"],
                hypothesis["statement"],
            )
            assert _grounded(hypothesis["reasoning"], allowed), (
                finding["title"],
                hypothesis["reasoning"],
            )


def test_facts_and_hypotheses_are_separate_fields(analyzed):
    for finding in analyzed["findings"]:
        fact_statements = {fact["statement"] for fact in finding["verifiedFacts"]}
        hypothesis_statements = {hypothesis["statement"] for hypothesis in finding["aiHypotheses"]}
        assert not fact_statements & hypothesis_statements
        for row in finding["evidenceRows"]:
            assert row["source"]
            assert row["rowId"]
            assert isinstance(row["fields"], dict)


def test_template_mode_never_claims_confirmed_causes(analyzed):
    for finding in analyzed["findings"]:
        for hypothesis in finding["aiHypotheses"]:
            statement = hypothesis["statement"].lower()
            assert "confirmed" not in statement
            assert "is caused by" not in statement

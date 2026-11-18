"""Risk scoring: weighted blend of statistics, volume, value, recency, trend."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Weights are constants on purpose: a manager can reason about the score.
WEIGHTS = {
    "statistics": 0.35,
    "volume": 0.20,
    "value": 0.15,
    "recency": 0.10,
    "trend": 0.10,
    "customers": 0.10,
}
VOLUME_REFERENCE = 30.0
VALUE_REFERENCE = 12000.0
CUSTOMER_REFERENCE = 80.0
RECENCY_REFERENCE_DAYS = 21.0
SEVERITY_BANDS = [("critical", 80.0), ("high", 60.0), ("medium", 40.0), ("low", 0.0)]


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def severity_for(score: float) -> str:
    for severity, threshold in SEVERITY_BANDS:
        if score >= threshold:
            return severity
    return "low"


def score_candidate(candidate) -> tuple[float, str, str]:
    components = {
        "statistics": _clamp(candidate.stat_strength),
        "volume": _clamp(candidate.affected_count / VOLUME_REFERENCE),
        "value": _clamp(candidate.affected_value / VALUE_REFERENCE),
        "recency": _clamp(1 - candidate.recency_days / RECENCY_REFERENCE_DAYS),
        "trend": _clamp(candidate.trend),
        "customers": _clamp(candidate.customers / CUSTOMER_REFERENCE),
    }
    blended = sum(WEIGHTS[key] * components[key] for key in WEIGHTS)
    risk_score = round(blended * 100, 1)
    severity = severity_for(risk_score)

    drivers = sorted(components.items(), key=lambda item: item[1] * WEIGHTS[item[0]], reverse=True)[:2]
    driver_text = " and ".join(f"{name} ({round(value * 100)}% of that factor)" for name, value in drivers)
    business_impact = (
        f"{candidate.affected_count} {candidate.unit} affected, "
        f"£{candidate.affected_value:,.0f} of order value exposed, "
        f"{candidate.customers} customers involved. "
        f"Risk score {risk_score}/100 driven by {driver_text}."
    )
    logger.debug("scored %s -> %s (%s)", candidate.title, risk_score, severity)
    return risk_score, severity, business_impact

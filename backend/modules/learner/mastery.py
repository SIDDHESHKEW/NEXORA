"""Mastery engine: deterministic prior-weighted Bayesian estimator."""

from typing import Any, List, Tuple
from backend.models.evidence import LearningEvent


def get_mastery_status(estimate: float, strong_threshold: int = 70, developing_threshold: int = 50) -> str:
    """Classify mastery estimate into contract statuses: STRONG (>=70), DEVELOPING (50-69), WEAK (<50)."""
    pct = int(round(100.0 * estimate))
    if pct >= strong_threshold:
        return "STRONG"
    if pct >= developing_threshold:
        return "DEVELOPING"
    return "WEAK"


def format_mastery_percent(estimate: float) -> int:
    """Format float estimate [0.0, 1.0] as integer percentage [0, 100]."""
    return int(round(100.0 * estimate))


def compute_mastery_estimate(
    prior_estimate: float,
    prior_weight: float,
    events: List[Any],
    strong_threshold: int = 70,
    developing_threshold: int = 50,
) -> Tuple[float, int, str]:
    """Compute mastery estimate using prior-weighted Bayesian formula:
    estimate = (prior_weight * prior_estimate + Σ(weight * score)) / (prior_weight + Σ(weight))
    percent = round(100 * estimate)
    status: >= strong_threshold -> STRONG, >= developing_threshold -> DEVELOPING, else WEAK.
    """
    event_score_sum = 0.0
    event_weight_sum = 0.0

    for e in events:
        if isinstance(e, tuple):
            score, weight = e
        else:
            score, weight = e.score, e.weight
        event_score_sum += weight * score
        event_weight_sum += weight

    numerator = (prior_weight * prior_estimate) + event_score_sum
    denominator = prior_weight + event_weight_sum

    estimate = (numerator / denominator) if denominator > 0 else prior_estimate
    percent = format_mastery_percent(estimate)
    status = get_mastery_status(estimate, strong_threshold, developing_threshold)

    return estimate, percent, status

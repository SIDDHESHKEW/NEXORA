"""Unit tests for the Bayesian mastery estimator and skill derivation."""

import pytest
from backend.modules.learner.mastery import (
    compute_mastery_estimate,
    get_mastery_status,
    format_mastery_percent,
)
from backend.seed.config_constants import RIYA_PRIORS


def test_mastery_estimator_formula():
    """Verify exact Bayesian updating formula: (w_prior * prior + sum(w * s)) / (w_prior + sum(w))."""
    est, pct, status = compute_mastery_estimate(
        prior_estimate=0.5,
        prior_weight=2.0,
        events=[(1.0, 0.8)],
    )
    # (2.0 * 0.5 + 0.8 * 1.0) / (2.0 + 0.8) = 1.8 / 2.8 = 0.642857...
    assert round(est, 4) == 0.6429
    assert pct == 64
    assert status == "DEVELOPING"


def test_scripted_master_key_arithmetic():
    """Verify exact scripted numbers: LO1=88, LO2=74, LO3=81, LO4=41, overall=71."""
    prior_weight = 2.0
    w_quiz = 0.8

    # LO1: prior 0.832 + 1 correct answer (score=1.0)
    lo1_est, lo1_pct, lo1_st = compute_mastery_estimate(RIYA_PRIORS["LO1"], prior_weight, [(1.0, w_quiz)])
    assert lo1_pct == 88
    assert lo1_st == "STRONG"

    # LO2: prior 0.636 + 1 correct answer (score=1.0)
    lo2_est, lo2_pct, lo2_st = compute_mastery_estimate(RIYA_PRIORS["LO2"], prior_weight, [(1.0, w_quiz)])
    assert lo2_pct == 74
    assert lo2_st == "STRONG"

    # LO3: prior 0.734 + 1 correct answer (score=1.0)
    lo3_est, lo3_pct, lo3_st = compute_mastery_estimate(RIYA_PRIORS["LO3"], prior_weight, [(1.0, w_quiz)])
    assert lo3_pct == 81
    assert lo3_st == "STRONG"

    # LO4: prior 0.738 + 2 wrong answers (scores 0.0, 0.0)
    lo4_est, lo4_pct, lo4_st = compute_mastery_estimate(RIYA_PRIORS["LO4"], prior_weight, [(0.0, w_quiz), (0.0, w_quiz)])
    assert lo4_pct == 41
    assert lo4_st == "WEAK"

    # Overall calculation
    overall_mean = (lo1_pct + lo2_pct + lo3_pct + lo4_pct) / 4.0
    assert round(overall_mean) == 71


def test_status_threshold_boundaries():
    """Verify status boundary edges according to thresholds (70, 50)."""
    assert get_mastery_status(0.70) == "STRONG"
    assert get_mastery_status(0.694) == "DEVELOPING"
    assert get_mastery_status(0.50) == "DEVELOPING"
    assert get_mastery_status(0.494) == "WEAK"
    assert get_mastery_status(0.0) == "WEAK"
    assert get_mastery_status(1.0) == "STRONG"


def test_rebuild_equals_incremental(db_session):
    """Verify that rebuilding mastery from evidence store yields the exact same state as incremental updates."""
    from backend.modules.learner.service import recompute_mastery, rebuild_mastery
    from backend.models.curriculum import Student, LearningOutcome
    from backend.models.evidence import LearningEvent

    riya = db_session.query(Student).filter(Student.is_live == True).first()
    lo4 = db_session.query(LearningOutcome).filter(LearningOutcome.code == "LO4").first()

    # Create two learning events for LO4
    ev1 = LearningEvent(
        student_id=riya.id,
        learning_outcome_id=lo4.id,
        source_type="EXIT_QUIZ",
        score=0.0,
        weight=0.8,
        is_correct=False,
    )
    ev2 = LearningEvent(
        student_id=riya.id,
        learning_outcome_id=lo4.id,
        source_type="EXIT_QUIZ",
        score=0.0,
        weight=0.8,
        is_correct=False,
    )
    db_session.add_all([ev1, ev2])
    db_session.commit()

    # Run incremental recompute
    incr_mastery = recompute_mastery(riya.id, [lo4.id], db_session)[0]
    incr_est = incr_mastery.current_estimate
    incr_count = incr_mastery.evidence_count

    # Run full rebuild
    rebuild_res = rebuild_mastery(riya.id, db_session)
    rebuilt_lo4 = next(m for m in rebuild_res if m.learning_outcome_id == lo4.id)

    assert abs(incr_est - rebuilt_lo4.current_estimate) < 1e-6
    assert incr_count == rebuilt_lo4.evidence_count
    assert rebuilt_lo4.status == "WEAK"
    assert format_mastery_percent(rebuilt_lo4.current_estimate) == 41

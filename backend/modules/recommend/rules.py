"""Recommendation rules: deterministic detection of student and classroom gaps."""

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from backend.models.curriculum import Student, LearningOutcome, ClassSection
from backend.models.learner import Mastery, SectionOutcomeStats
from backend.models.recommendation import Recommendation


def evaluate_student_gaps(student_id: int, db: Session) -> List[Recommendation]:
    """Detect WEAK learning outcomes and create or update GAP_SUPPORT recommendations."""
    mastery_rows = db.query(Mastery).filter(Mastery.student_id == student_id).all()
    created_or_updated: List[Recommendation] = []

    for m in mastery_rows:
        outcome = db.query(LearningOutcome).filter(LearningOutcome.id == m.learning_outcome_id).first()
        if not outcome:
            continue

        existing_rec = db.query(Recommendation).filter(
            Recommendation.student_id == student_id,
            Recommendation.learning_outcome_id == m.learning_outcome_id,
            Recommendation.type == "GAP_SUPPORT",
        ).first()

        if m.status == "WEAK":
            if not existing_rec:
                rec = Recommendation(
                    student_id=student_id,
                    learning_outcome_id=m.learning_outcome_id,
                    type="GAP_SUPPORT",
                    title=f"Review {outcome.statement}",
                    what_happened="You updated a hidden-layer weight with the output error directly. In backpropagation, the error must pass back through downstream layer weights and activation derivatives first.",
                    why_seen="Based on your answers in today's exit quiz.",
                    suggested_action="Complete the targeted 3-step learning path.",
                    suggested_approach="Review the 2-minute recap and solve 3 practice questions.",
                    payload={
                        "steps": [
                            {"kind": "RECAP", "label": "2-minute conceptual recap", "detail": "Why output error cannot apply directly to hidden weights"},
                            {"kind": "PRACTICE", "label": "3 targeted practice questions", "detail": "Reinforce chain rule error flow"},
                            {"kind": "TUTOR", "label": "Ask AI Tutor", "detail": "Clarify any remaining doubts"},
                        ]
                    },
                    recap_status="PENDING",
                    recap_text=None,
                    status="ACTIVE",
                )
                db.add(rec)
                created_or_updated.append(rec)
            else:
                existing_rec.status = "ACTIVE"
                created_or_updated.append(existing_rec)
        else:
            # If student has achieved DEVELOPING or STRONG, mark GAP_SUPPORT as RESOLVED
            if existing_rec and existing_rec.status == "ACTIVE":
                existing_rec.status = "RESOLVED"
                created_or_updated.append(existing_rec)

    db.flush()
    return created_or_updated


def evaluate_class_gaps(section_id: int, db: Session) -> List[Recommendation]:
    """Detect section-level gaps (weak share >= 40% and respondents >= 10) and generate RETEACH recommendations."""
    stats = db.query(SectionOutcomeStats).filter(SectionOutcomeStats.section_id == section_id).all()
    created_recs: List[Recommendation] = []

    for s in stats:
        if s.respondents >= 10 and (s.weak_count / s.respondents) >= 0.40:
            outcome = db.query(LearningOutcome).filter(LearningOutcome.id == s.learning_outcome_id).first()
            if not outcome:
                continue

            existing_rec = db.query(Recommendation).filter(
                Recommendation.section_id == section_id,
                Recommendation.learning_outcome_id == s.learning_outcome_id,
                Recommendation.type == "RETEACH",
            ).first()

            weak_share_pct = int(round((s.weak_count / s.respondents) * 100))
            facts = {
                "section": s.section.name if s.section else "",
                "weak_count": s.weak_count,
                "respondents": s.respondents,
                "weak_share_pct": weak_share_pct,
                "outcome_code": outcome.code,
            }

            if not existing_rec:
                rec = Recommendation(
                    section_id=section_id,
                    learning_outcome_id=s.learning_outcome_id,
                    type="RETEACH",
                    title=f"Re-teach {outcome.statement}",
                    why="Low mastery detected from today's exit quiz.",
                    suggested_action="10-minute conceptual recap",
                    suggested_approach="Use a simple worked example showing how error propagates from output to hidden layers.",
                    facts=facts,
                    payload={"actions": ["GENERATE_SEGMENT", "VIEW_EVIDENCE", "ASSIGN_PRACTICE"]},
                    status="ACTIVE",
                )
                db.add(rec)
                created_recs.append(rec)
            else:
                existing_rec.facts = facts
                existing_rec.status = "ACTIVE"
                created_recs.append(existing_rec)

    db.flush()
    return created_recs

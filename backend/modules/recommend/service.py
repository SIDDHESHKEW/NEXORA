"""Recommendation service: managing gap recommendations and background recap generation."""

import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from backend.core.db import SessionLocal
from backend.models.curriculum import LearningOutcome, Misconception
from backend.models.content import Source
from backend.models.recommendation import Recommendation
from backend.models.evidence import LearningEvent
from backend.modules.recommend.rules import evaluate_student_gaps, evaluate_class_gaps
from backend.services.ai_gateway import ai_gateway

logger = logging.getLogger("sgsu.recommend")


def refresh_recommendations_for_student(student_id: int, db: Session) -> List[Recommendation]:
    return evaluate_student_gaps(student_id, db)


def refresh_recommendations_for_section(section_id: int, db: Session) -> List[Recommendation]:
    return evaluate_class_gaps(section_id, db)


async def fill_recap_task(recommendation_id: int, student_id: int, lo_id: int) -> None:
    """FastAPI background task to asynchronously generate recap text for student gap recommendation."""
    db = SessionLocal()
    try:
        rec = db.query(Recommendation).filter(Recommendation.id == recommendation_id).first()
        if not rec:
            return

        lo = db.query(LearningOutcome).filter(LearningOutcome.id == lo_id).first()
        source = db.query(Source).filter(Source.topic_id == lo.topic_id, Source.approved == True).first() if lo else None

        # Look up any dominant misconception from student's recent events
        recent_event = db.query(LearningEvent).filter(
            LearningEvent.student_id == student_id,
            LearningEvent.learning_outcome_id == lo_id,
            LearningEvent.misconception_id.isnot(None),
        ).order_by(LearningEvent.created_at.desc()).first()

        misc = recent_event.misconception if recent_event else None

        recap_obj, mode = await ai_gateway.generate_explanation(
            outcome=lo,
            misconception=misc,
            source=source,
            db=db,
        )

        rec.recap_text = recap_obj.recap_text
        rec.recap_status = "READY" if mode == "LIVE" else "READY_FALLBACK"
        db.commit()
    except Exception as e:
        logger.error(f"Error in background fill_recap_task: {e}")
        try:
            if rec:
                rec.recap_status = "READY_FALLBACK"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


async def warm_reteach_task(section_id: int, lo_id: int) -> None:
    """Pre-warm or prepare teacher reteach recommendation."""
    db = SessionLocal()
    try:
        refresh_recommendations_for_section(section_id, db)
        db.commit()
    finally:
        db.close()

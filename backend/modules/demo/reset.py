"""Demo reset implementation: restores database to authoritative conference demonstrator state."""

import logging
from sqlalchemy.orm import Session

from backend.models.curriculum import Student, ClassSection, LearningOutcome
from backend.models.content import Lesson, LessonBlock
from backend.models.classroom import ClassSession, SessionParticipant, SessionPrompt, Poll
from backend.models.assessment import Response
from backend.models.evidence import LearningEvent
from backend.models.learner import Mastery, SectionOutcomeStats
from backend.models.recommendation import Recommendation, PracticeSet, PracticeSetQuestion
from backend.models.skills import StudentSkill, Skill
from backend.models.governance import AIInteraction, AuditLog
from backend.seed.config_constants import (
    RIYA_PRIORS,
    SECTION_5A_NAME,
    SECTION_5B_NAME,
    SECTION_5A_STATS,
    SECTION_5B_STATS,
)
from backend.seed.seed_data import validate_seed_integrity

logger = logging.getLogger("sgsu.demo.reset")


def execute_demo_reset(db: Session) -> bool:
    """Reset dynamic tables and revert student/cohort metrics to original demonstration seed."""
    logger.info("Executing authoritative DEMO RESET...")

    # 1. Delete dynamic tables
    db.query(Response).delete()
    db.query(LearningEvent).delete()
    db.query(PracticeSetQuestion).delete()
    db.query(PracticeSet).delete()
    db.query(Recommendation).delete()
    db.query(AIInteraction).delete()
    db.query(Poll).delete()
    db.query(SessionPrompt).delete()
    db.query(SessionParticipant).delete()
    db.query(ClassSession).delete()
    db.query(LessonBlock).delete()
    db.query(Lesson).delete()
    db.query(AuditLog).delete()
    db.flush()

    # 2. Reset Mastery
    riya = db.query(Student).filter(Student.is_live == True).first()
    if riya:
        for code, expected_prior in RIYA_PRIORS.items():
            lo = db.query(LearningOutcome).filter(LearningOutcome.code == code).first()
            if lo:
                m = db.query(Mastery).filter(
                    Mastery.student_id == riya.id,
                    Mastery.learning_outcome_id == lo.id,
                ).first()
                status = "STRONG" if expected_prior >= 0.70 else ("DEVELOPING" if expected_prior >= 0.50 else "WEAK")
                if m:
                    m.prior_estimate = expected_prior
                    m.estimate = expected_prior
                    m.percent = int(round(100.0 * expected_prior))
                    m.status = status
                    m.evidence_count = 0
                else:
                    db.add(Mastery(
                        student_id=riya.id,
                        learning_outcome_id=lo.id,
                        prior_estimate=expected_prior,
                        estimate=expected_prior,
                        percent=int(round(100.0 * expected_prior)),
                        status=status,
                        evidence_count=0,
                    ))

    # Reset other students' mastery to prior_estimate
    other_masteries = db.query(Mastery).filter(Mastery.student_id != (riya.id if riya else -1)).all()
    for m in other_masteries:
        m.estimate = m.prior_estimate
        m.percent = int(round(100.0 * m.prior_estimate))
        m.evidence_count = 0
        m.status = "STRONG" if m.prior_estimate >= 0.70 else ("DEVELOPING" if m.prior_estimate >= 0.50 else "WEAK")

    # 3. Reset SectionOutcomeStats
    sec_5a = db.query(ClassSection).filter(ClassSection.name == SECTION_5A_NAME).first()
    sec_5b = db.query(ClassSection).filter(ClassSection.name == SECTION_5B_NAME).first()

    if sec_5a:
        for code, stat in SECTION_5A_STATS.items():
            lo = db.query(LearningOutcome).filter(LearningOutcome.code == code).first()
            if lo:
                sos = db.query(SectionOutcomeStats).filter(
                    SectionOutcomeStats.section_id == sec_5a.id,
                    SectionOutcomeStats.learning_outcome_id == lo.id,
                ).first()
                if sos:
                    sos.respondents = 57
                    sos.strong_count = stat["strong_count"]
                    sos.developing_count = stat["developing_count"]
                    sos.weak_count = stat["weak_count"]
                    sos.class_mastery_percent = stat["percent"]

    if sec_5b:
        for code, stat in SECTION_5B_STATS.items():
            lo = db.query(LearningOutcome).filter(LearningOutcome.code == code).first()
            if lo:
                sos = db.query(SectionOutcomeStats).filter(
                    SectionOutcomeStats.section_id == sec_5b.id,
                    SectionOutcomeStats.learning_outcome_id == lo.id,
                ).first()
                if sos:
                    sos.respondents = 57
                    sos.strong_count = stat["strong_count"]
                    sos.developing_count = stat["developing_count"]
                    sos.weak_count = stat["weak_count"]
                    sos.class_mastery_percent = stat["percent"]

    # 4. Reset StudentSkills for Riya
    if riya:
        nn_skill = db.query(Skill).filter(Skill.name == "Neural Networks").first()
        dl_skill = db.query(Skill).filter(Skill.name == "Deep Learning").first()
        if nn_skill:
            ss_nn = db.query(StudentSkill).filter(
                StudentSkill.student_id == riya.id,
                StudentSkill.skill_id == nn_skill.id,
            ).first()
            if ss_nn:
                ss_nn.level = "DEVELOPING"
                ss_nn.source = "DERIVED"
        if dl_skill:
            ss_dl = db.query(StudentSkill).filter(
                StudentSkill.student_id == riya.id,
                StudentSkill.skill_id == dl_skill.id,
            ).first()
            if ss_dl:
                ss_dl.level = "RECOMMENDED_NEXT"
                ss_dl.source = "DERIVED"

    # 5. Record DEMO_RESET audit log
    reset_audit = AuditLog(
        action="DEMO_RESET",
        user_id=None,
        role="ADMIN",
        entity="system",
        detail={"version": "v1.0-sgsu-demo", "reason": "Demonstration reset invoked"},
    )
    db.add(reset_audit)
    db.commit()

    # 6. Verify seed integrity
    integrity = validate_seed_integrity(db)
    if not integrity["healthy"]:
        logger.error(f"Integrity check failed post-reset: {integrity['checks']}")
        return False

    logger.info("DEMO RESET executed successfully with 100% integrity validation.")
    return True

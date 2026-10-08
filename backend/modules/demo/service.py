"""Demo service: intelligence loop status tracking and scripted autofill assessment execution."""

import logging
from typing import Optional
from sqlalchemy.orm import Session

from backend.core.errors import NotFoundError, QuizNotOpenError, ValidationError
from backend.models.curriculum import Student, User
from backend.models.content import Lesson
from backend.models.classroom import ClassSession, SessionParticipant
from backend.models.assessment import Question, QuestionOption, Response
from backend.models.evidence import LearningEvent
from backend.models.recommendation import Recommendation, PracticeSet
from backend.models.learner import SectionOutcomeStats
from backend.modules.assessment.service import submit_assessment
from backend.modules.governance.service import create_audit_log
from backend.schemas.assessment import QuizSubmitRequest, QuizSubmitAnswer, QuizResult
from backend.schemas.intelligence import DemoStateResponse, DemoStateStep, DemoStateLoop

logger = logging.getLogger("sgsu.demo.service")


def get_demo_state_service(db: Session) -> DemoStateResponse:
    """Derive complete 8-step intelligence loop status directly from the database."""
    riya = db.query(Student).filter(Student.is_live == True).first()
    riya_id = riya.id if riya else -1

    # 1. TEACH: Faculty generated and published grounded lesson
    published_lesson = db.query(Lesson).filter(Lesson.status == "PUBLISHED").first()
    teach_done = published_lesson is not None

    # 2. LEARN: Classroom session active or ended with student participation
    active_session = db.query(ClassSession).filter(ClassSession.status.in_(["LIVE", "ENDED"])).first()
    participant = db.query(SessionParticipant).filter(SessionParticipant.student_id == riya_id).first()
    learn_done = active_session is not None and (participant is not None or active_session.current_slide_index > 0)

    # 3. ASSESS: Live student exit quiz submitted
    quiz_submitted = db.query(Response).filter(
        Response.student_id == riya_id,
        Response.context == "EXIT_QUIZ",
    ).first()
    assess_done = quiz_submitted is not None

    # 4. UNDERSTAND: Bayesian mastery updated with live learning evidence
    live_event = db.query(LearningEvent).filter(LearningEvent.student_id == riya_id).first()
    understand_done = live_event is not None

    # 5. PERSONALIZE: Student recommendation (GAP_SUPPORT) or practice generated
    student_rec = db.query(Recommendation).filter(
        Recommendation.student_id == riya_id,
        Recommendation.type == "GAP_SUPPORT",
    ).first()
    personalize_done = student_rec is not None

    # 6. SUPPORT_TEACHER: Teacher reteach recommendation or segment generated
    teacher_rec = db.query(Recommendation).filter(Recommendation.type == "RETEACH").first()
    support_teacher_done = teacher_rec is not None

    # 7. INFORM_UNIVERSITY: Academic curriculum recommendation drafted or section 5-A weak count >= 35
    admin_rec = db.query(Recommendation).filter(Recommendation.type == "ACADEMIC").first()
    stat_5a_lo4 = db.query(SectionOutcomeStats).filter(
        SectionOutcomeStats.weak_count >= 35,
    ).first()
    inform_university_done = admin_rec is not None or stat_5a_lo4 is not None

    # 8. IMPROVE: Practice sets assigned or completed
    practice_exists = db.query(PracticeSet).first() is not None or db.query(Response).filter(
        Response.context == "PRACTICE",
    ).first() is not None
    improve_done = practice_exists

    steps = [
        DemoStateStep(
            n=1,
            key="teach",
            label="Faculty Generates & Publishes Grounded Lesson",
            done=teach_done,
            detail="Grounded AI lesson generated and published by faculty with course material citations.",
        ),
        DemoStateStep(
            n=2,
            key="learn",
            label="Interactive Classroom Session & Participation",
            done=learn_done,
            detail="Live synchronized classroom presentation with interactive slide progression and live polling.",
        ),
        DemoStateStep(
            n=3,
            key="assess",
            label="Exit Quiz Execution & Misconception Capture",
            done=assess_done,
            detail="Live student completed 5-question conceptual exit quiz with misconception diagnostics.",
        ),
        DemoStateStep(
            n=4,
            key="understand",
            label="Bayesian Mastery Updates & Evidence Trail",
            done=understand_done,
            detail="Deterministic Bayesian estimator recalculated learner mastery across all topic learning outcomes.",
        ),
        DemoStateStep(
            n=5,
            key="personalize",
            label="Student Gap Detection & Targeted Remediation",
            done=personalize_done,
            detail="Automated 1-click conceptual recap and targeted practice questions generated for live student.",
        ),
        DemoStateStep(
            n=6,
            key="support_teacher",
            label="Teacher Cohort Diagnostics & Reteach Plan",
            done=support_teacher_done,
            detail="Cohort analytics identified 61% weakness on LO4; generated 10-minute micro-lesson reteach outline.",
        ),
        DemoStateStep(
            n=7,
            key="inform_university",
            label="Cross-Section Systemic Gap Detection & Dean Note",
            done=inform_university_done,
            detail="Institutional analytics identified 58% recurring gap across sections 5-A and 5-B; academic note generated.",
        ),
        DemoStateStep(
            n=8,
            key="improve",
            label="Remediation Practice & Skill Progression",
            done=improve_done,
            detail="Targeted practice set assigned to reinforce mastery and update student Skill Passport.",
        ),
    ]

    loop = DemoStateLoop(
        teach=teach_done,
        learn=learn_done,
        assess=assess_done,
        understand=understand_done,
        personalize=personalize_done,
        support_teacher=support_teacher_done,
        inform_university=inform_university_done,
        improve=improve_done,
    )

    current_step = 8
    for s in steps:
        if not s.done:
            current_step = s.n
            break

    return DemoStateResponse(
        steps=steps,
        current_step=current_step,
        loop=loop,
    )


def autofill_quiz_service(
    student_id: int,
    session_id: Optional[int],
    db: Session,
) -> QuizResult:
    """Execute authoritative scripted exit quiz submission (Q1-Q3 correct, Q4-Q5 misconception)."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise NotFoundError(f"Student {student_id} not found")

    target_session: Optional[ClassSession] = None
    if session_id:
        target_session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    else:
        # Find active session with OPEN quiz in student's section
        target_session = (
            db.query(ClassSession)
            .filter(
                ClassSession.section_id == student.section_id,
                ClassSession.quiz_status == "OPEN",
                ClassSession.status == "LIVE",
            )
            .first()
        )
        if not target_session:
            # Fallback to any active live session for this section
            target_session = (
                db.query(ClassSession)
                .filter(ClassSession.section_id == student.section_id, ClassSession.status == "LIVE")
                .first()
            )

    if not target_session:
        raise ValidationError("No active classroom session found for this student's section")

    if target_session.quiz_status != "OPEN":
        raise QuizNotOpenError("Exit quiz is not currently open in the active session")

    # Fetch 5 exit quiz questions ordered by sequence
    questions = (
        db.query(Question)
        .filter(Question.purpose == "EXIT_QUIZ")
        .order_by(Question.seq.asc())
        .all()
    )

    if len(questions) < 5:
        raise ValidationError("Exit quiz questions not found in database")

    answers = []
    for q in questions[:5]:
        if q.seq in [1, 2, 3]:
            # Correct answer
            correct_opt = next((o for o in q.options if o.is_correct), None)
            if not correct_opt:
                raise ValidationError(f"No correct option for question {q.id}")
            answers.append(QuizSubmitAnswer(question_id=q.id, option_id=correct_opt.id, duration_ms=4500))
        else:
            # Q4 & Q5: Misconception option ("apply output error directly to hidden-layer weights")
            misc_opt = next((o for o in q.options if o.misconception_id is not None), None)
            if not misc_opt:
                # If not tagged explicitly with misconception_id, choose a wrong option
                misc_opt = next((o for o in q.options if not o.is_correct), None)
            if not misc_opt:
                raise ValidationError(f"No misconception option for question {q.id}")
            answers.append(QuizSubmitAnswer(question_id=q.id, option_id=misc_opt.id, duration_ms=6200))

    sub_req = QuizSubmitRequest(
        context="EXIT_QUIZ",
        session_id=target_session.id,
        idempotency_key=f"demo-autofill-{target_session.id}-{student.id}",
        answers=answers,
    )

    # Call the exact server-side assessment logic
    result = submit_assessment(sub_req, student_id=student.id, db=db, scripted=True)

    create_audit_log(
        db=db,
        action="QUIZ_SUBMIT_AUTOFILL",
        user_id=student.user_id,
        role="STUDENT",
        entity="quiz",
        entity_id=target_session.id,
        detail={"session_id": target_session.id, "scripted": True},
    )

    return result

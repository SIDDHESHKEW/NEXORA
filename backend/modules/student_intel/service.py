"""Student Intelligence service: student mastery, personal recommendations, evidence, practice, and AI tutor."""

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.core.errors import (
    NotFoundError,
    ForbiddenScopeError,
    QuizInProgressError,
    ValidationError,
)
from backend.models.curriculum import Student, LearningOutcome, Misconception
from backend.models.content import Source
from backend.models.classroom import ClassSession, SessionParticipant
from backend.models.assessment import Question, QuestionOption
from backend.models.evidence import LearningEvent
from backend.models.learner import Mastery
from backend.models.recommendation import Recommendation, PracticeSet, PracticeSetQuestion
from backend.models.skills import StudentSkill
from backend.modules.recommend.rules import evaluate_student_gaps
from backend.modules.skills.service import get_student_skills_passport
from backend.services.ai_gateway import ai_gateway
from backend.schemas.curriculum import OutcomeSchema
from backend.schemas.classroom import StudentQuestion, StudentQuestionOption
from backend.schemas.assessment import MasteryItemSchema
from backend.schemas.intelligence import (
    StudentMasteryResponse,
    StudentSummary,
    StudentRecommendationResponse,
    RecommendationStep,
    StudentEvidenceItem,
    SkillPassportResponse,
    PracticeSetResponse,
    TutorAskResponse,
)

logger = logging.getLogger("sgsu.student_intel")


def get_student_mastery_service(student_id: int, db: Session) -> StudentMasteryResponse:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise NotFoundError(f"Student {student_id} not found")

    mastery_rows = db.query(Mastery).filter(Mastery.student_id == student_id).join(
        LearningOutcome
    ).order_by(LearningOutcome.code.asc()).all()

    items: List[MasteryItemSchema] = []
    percents: List[int] = []

    for m in mastery_rows:
        lo = m.learning_outcome
        lo_schema = OutcomeSchema(
            id=lo.id,
            code=lo.code,
            statement=lo.statement,
            kind=lo.kind,
            prerequisite_ids=[],
        )
        items.append(
            MasteryItemSchema(
                outcome=lo_schema,
                percent=m.percent,
                estimate=m.estimate,
                status=m.status,
                evidence_count=m.evidence_count,
                prior_note="Pre-class diagnostic (sample)",
                provenance=m.provenance,
            )
        )
        percents.append(m.percent)

    overall_percent = int(round(sum(percents) / len(percents))) if percents else 70
    overall_status = "STRONG" if overall_percent >= 70 else ("DEVELOPING" if overall_percent >= 50 else "WEAK")

    # If student has live answers, provenance is LIVE for own results
    has_live = any(m.provenance == "LIVE" for m in items)
    provenance = "LIVE" if (student.is_live and has_live) else "MIXED"

    user_name = student.user.name if student.user else f"Student {student.id}"
    return StudentMasteryResponse(
        student=StudentSummary(id=student.id, name=user_name),
        overall_percent=overall_percent,
        overall_status=overall_status,
        items=items,
        provenance=provenance,
    )


def get_student_recommendations_service(student_id: int, db: Session) -> List[StudentRecommendationResponse]:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise NotFoundError(f"Student {student_id} not found")

    recs = db.query(Recommendation).filter(
        Recommendation.student_id == student_id,
        Recommendation.status == "ACTIVE",
    ).all()

    results: List[StudentRecommendationResponse] = []
    for r in recs:
        lo = r.learning_outcome
        lo_schema = OutcomeSchema(
            id=lo.id,
            code=lo.code,
            statement=lo.statement,
            kind=lo.kind,
            prerequisite_ids=[],
        )
        steps_data = []
        if r.payload and "steps" in r.payload:
            for s in r.payload["steps"]:
                steps_data.append(RecommendationStep(kind=s.get("kind", "RECAP"), label=s.get("label", ""), detail=s.get("detail")))
        else:
            steps_data = [
                RecommendationStep(kind="RECAP", label="2-minute concept recap", detail="Why output error cannot apply directly to hidden weights"),
                RecommendationStep(kind="PRACTICE", label="3 targeted practice questions", detail="Reinforce chain rule error flow"),
                RecommendationStep(kind="TUTOR", label="Ask AI Tutor", detail="Clarify any remaining doubts"),
            ]

        # Fetch current mastery percent for outcome
        m = db.query(Mastery).filter(
            Mastery.student_id == student_id,
            Mastery.learning_outcome_id == r.learning_outcome_id,
        ).first()

        results.append(
            StudentRecommendationResponse(
                id=r.id,
                type=r.type,
                outcome=lo_schema,
                title=r.title,
                what_happened=r.what_happened or "Low mastery detected on this outcome.",
                why_seen=r.why_seen or "Based on your answers in today's exit quiz.",
                steps=steps_data,
                recap_status=r.recap_status or "READY",
                recap_text=r.recap_text or "In backpropagation, output error cannot apply directly to hidden weights; the error signal propagates through downstream weights and derivatives.",
                mastery_percent=m.percent if m else 41,
                status=m.status if m else "WEAK",
            )
        )

    return results


def get_student_evidence_service(student_id: int, outcome_id: Optional[int], db: Session) -> List[StudentEvidenceItem]:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise NotFoundError(f"Student {student_id} not found")

    query = db.query(LearningEvent).filter(
        LearningEvent.student_id == student_id,
        LearningEvent.is_seeded == False,
    )
    if outcome_id:
        query = query.filter(LearningEvent.learning_outcome_id == outcome_id)

    events = query.order_by(LearningEvent.created_at.desc()).all()
    results: List[StudentEvidenceItem] = []
    for e in events:
        resp = e.response
        selected_text = resp.option.text if (resp and resp.option) else "Selected option"
        correct_opt = db.query(QuestionOption).filter(
            QuestionOption.question_id == e.question_id,
            QuestionOption.is_correct == True,
        ).first()
        correct_text = correct_opt.text if correct_opt else ""

        results.append(
            StudentEvidenceItem(
                occurred_at=e.created_at,
                source_type=e.source_type,
                question_stem=e.question.stem if e.question else "",
                selected=selected_text,
                correct=correct_text,
                is_correct=bool(e.score > 0.5),
                weight=e.weight,
                misconception=e.misconception.label if e.misconception else None,
            )
        )

    return results


async def generate_practice_service(outcome_id: int, student_id: int, db: Session) -> PracticeSetResponse:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise NotFoundError("Student not found")

    lo = db.query(LearningOutcome).filter(LearningOutcome.id == outcome_id).first()
    if not lo:
        raise NotFoundError(f"Learning Outcome {outcome_id} not found")

    source = db.query(Source).filter(Source.topic_id == lo.topic_id, Source.approved == True).first()
    misconceptions = lo.misconceptions

    # Fetch exit quiz stems so they aren't duplicated
    exit_stems = [
        q.stem for q in db.query(Question).filter(Question.topic_id == lo.topic_id, Question.purpose == "EXIT_QUIZ").all()
    ]

    ai_out, gen_mode = await ai_gateway.generate_practice_questions(
        outcome=lo,
        misconceptions=misconceptions,
        source=source,
        n=3,
        forbidden_stems=exit_stems,
        user_id=student.user_id,
        role="STUDENT",
        db=db,
    )

    practice_set = PracticeSet(
        student_id=student.id,
        learning_outcome_id=lo.id,
        section_id=student.section_id,
        status="NEW",
        generation_mode=gen_mode,
    )
    db.add(practice_set)
    db.flush()

    student_questions: List[StudentQuestion] = []
    for seq_idx, q_data in enumerate(ai_out.questions, start=1):
        q = Question(
            topic_id=lo.topic_id,
            learning_outcome_id=lo.id,
            seq=seq_idx,
            stem=q_data.stem,
            purpose="PRACTICE",
            explanation=q_data.explanation,
        )
        db.add(q)
        db.flush()

        ps_q = PracticeSetQuestion(
            practice_set_id=practice_set.id,
            question_id=q.id,
            seq=seq_idx,
        )
        db.add(ps_q)

        opts_list: List[StudentQuestionOption] = []
        for opt_data in q_data.options:
            misc_id = None
            if opt_data.misconception:
                misc_row = db.query(Misconception).filter(Misconception.tag == opt_data.misconception).first()
                if misc_row:
                    misc_id = misc_row.id

            opt_row = QuestionOption(
                question_id=q.id,
                label=opt_data.label,
                text=opt_data.text,
                is_correct=opt_data.is_correct,
                misconception_id=misc_id,
            )
            db.add(opt_row)
            db.flush()
            # Student view NEVER has is_correct
            opts_list.append(StudentQuestionOption(id=opt_row.id, label=opt_row.label, text=opt_row.text))

        student_questions.append(
            StudentQuestion(
                id=q.id,
                seq=seq_idx,
                stem=q.stem,
                learning_outcome_id=lo.id,
                options=opts_list,
            )
        )

    db.commit()

    lo_schema = OutcomeSchema(
        id=lo.id,
        code=lo.code,
        statement=lo.statement,
        kind=lo.kind,
        prerequisite_ids=[],
    )

    return PracticeSetResponse(
        set_id=practice_set.id,
        outcome=lo_schema,
        generation_mode=gen_mode,
        questions=student_questions,
        status=practice_set.status,
    )


def get_practice_set_service(set_id: int, student_id: int, db: Session) -> PracticeSetResponse:
    practice_set = db.query(PracticeSet).filter(PracticeSet.id == set_id).first()
    if not practice_set:
        raise NotFoundError(f"Practice set {set_id} not found")
    if practice_set.student_id != student_id:
        raise ForbiddenScopeError("Student does not own this practice set")

    lo = practice_set.learning_outcome
    student_questions = []
    for ps_q in practice_set.questions:
        q = ps_q.question
        opts = [StudentQuestionOption(id=o.id, label=o.label, text=o.text) for o in q.options]
        student_questions.append(
            StudentQuestion(
                id=q.id,
                seq=ps_q.seq,
                stem=q.stem,
                learning_outcome_id=lo.id,
                options=opts,
            )
        )

    lo_schema = OutcomeSchema(
        id=lo.id,
        code=lo.code,
        statement=lo.statement,
        kind=lo.kind,
        prerequisite_ids=[],
    )

    return PracticeSetResponse(
        set_id=practice_set.id,
        outcome=lo_schema,
        generation_mode=practice_set.generation_mode,
        questions=student_questions,
        status=practice_set.status,
    )


def assign_practice_service(section_id: int, outcome_id: int, teacher_user_id: int, db: Session) -> int:
    """Teacher assigns practice to all WEAK students in the section."""
    lo = db.query(LearningOutcome).filter(LearningOutcome.id == outcome_id).first()
    if not lo:
        raise NotFoundError("Learning outcome not found")

    weak_students = db.query(Student).join(Mastery).filter(
        Student.section_id == section_id,
        Mastery.learning_outcome_id == outcome_id,
        Mastery.status == "WEAK",
    ).all()

    assigned_count = 0
    for s in weak_students:
        ps = PracticeSet(
            student_id=s.id,
            learning_outcome_id=outcome_id,
            section_id=section_id,
            assigned_by=teacher_user_id,
            status="ASSIGNED",
            generation_mode="FALLBACK",
        )
        db.add(ps)
        db.add(Recommendation(
            student_id=s.id,
            section_id=section_id,
            learning_outcome_id=outcome_id,
            type="PRACTICE_ASSIGNED",
            title=f"Practice Assigned: {lo.statement}",
            why="Your instructor assigned remedial practice for this topic.",
            suggested_action="Complete the assigned practice set.",
            status="ACTIVE",
        ))
        assigned_count += 1

    db.commit()
    return assigned_count


async def ask_tutor_service(
    question_text: str,
    outcome_id: Optional[int],
    student_id: int,
    student_user_id: int,
    db: Session,
) -> TutorAskResponse:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise NotFoundError("Student not found")

    # CR-14 Rule: If an active exit quiz is OPEN in this student's section, tutor is paused!
    active_session = db.query(ClassSession).filter(
        ClassSession.section_id == student.section_id,
        ClassSession.status == "LIVE",
        ClassSession.quiz_status == "OPEN",
    ).first()

    if active_session:
        # Check if student has not submitted yet
        participant = db.query(SessionParticipant).filter(
            SessionParticipant.session_id == active_session.id,
            SessionParticipant.student_id == student_id,
        ).first()
        if not participant or participant.quiz_submitted_at is None:
            raise QuizInProgressError("AI Tutor is paused during an active exit quiz")

    lo = db.query(LearningOutcome).filter(LearningOutcome.id == outcome_id).first() if outcome_id else None
    topic_id = lo.topic_id if lo else 1
    source = db.query(Source).filter(Source.topic_id == topic_id, Source.approved == True).first()

    tutor_obj, mode = await ai_gateway.generate_tutor_response(
        question=question_text,
        outcome=lo,
        source=source,
        user_id=student_user_id,
        role="STUDENT",
        db=db,
    )

    return TutorAskResponse(
        answer=tutor_obj.answer,
        topic=tutor_obj.topic,
        source=tutor_obj.source,
        label=tutor_obj.label,
        mode=mode,
    )

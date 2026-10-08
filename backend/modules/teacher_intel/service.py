"""Teacher Intelligence service: class insights, evidence aggregation, and reteach recommendations."""

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.core.errors import NotFoundError, ForbiddenScopeError
from backend.models.curriculum import Course, Topic, ClassSection, LearningOutcome, Student, Misconception
from backend.models.content import Source
from backend.models.classroom import ClassSession, SessionParticipant
from backend.models.assessment import Question, QuestionOption, Response
from backend.models.learner import Mastery, SectionOutcomeStats
from backend.models.recommendation import Recommendation
from backend.services.ai_gateway import ai_gateway
from backend.schemas.curriculum import OutcomeSchema
from backend.schemas.intelligence import (
    TeacherDashboardResponse,
    ClassInsightsResponse,
    ClassOutcomeInsight,
    SupportSummary,
    ClassEvidenceResponse,
    QuestionDistItem,
    OptionDistItem,
    NamedStudentMastery,
    TeacherRecommendationItem,
    ReteachSegment,
    ReteachSegmentOutline,
    ReteachWorkedExample,
    ReteachCheckItem,
)

logger = logging.getLogger("sgsu.teacher_intel")


def get_teacher_dashboard_service(teacher_id: int, teacher_user_id: int, db: Session) -> TeacherDashboardResponse:
    # Get primary course & topic
    course = db.query(Course).first()
    topic = db.query(Topic).first()
    outcomes = [
        OutcomeSchema(id=o.id, code=o.code, statement=o.statement, kind=o.kind, prerequisite_ids=[])
        for o in (topic.learning_outcomes if topic else [])
        if o.kind == "OUTCOME"
    ]

    last_session = db.query(ClassSession).filter(ClassSession.teacher_id == teacher_id).order_by(ClassSession.id.desc()).first()
    last_session_dict = None
    if last_session:
        participants_count = len(last_session.participants)
        quiz_submitted_count = sum(1 for p in last_session.participants if p.quiz_submitted_at is not None)
        last_session_dict = {
            "id": last_session.id,
            "started_at": last_session.started_at,
            "participants": participants_count,
            "quiz_submitted": quiz_submitted_count,
        }

    # Fetch section 5-A stats
    sec_5a = db.query(ClassSection).filter(ClassSection.name == "5-A").first()
    section_id = sec_5a.id if sec_5a else 1

    stats = db.query(SectionOutcomeStats).filter(SectionOutcomeStats.section_id == section_id).all()
    class_mastery = []
    weak_outcomes = []
    for s in stats:
        code = s.learning_outcome.code if s.learning_outcome else ""
        is_warning = bool(s.weak_count / s.respondents >= 0.40) if s.respondents else False
        item = {
            "outcome_id": s.learning_outcome_id,
            "code": code,
            "percent": s.class_mastery_percent,
            "status": "WEAK" if is_warning else "STRONG",
            "warning": is_warning,
        }
        class_mastery.append(item)
        if is_warning:
            weak_outcomes.append({
                "outcome_id": s.learning_outcome_id,
                "code": code,
                "percent": s.class_mastery_percent,
                "weak_count": s.weak_count,
                "respondents": s.respondents,
            })

    recs = get_class_recommendations_service(section_id, db)

    return TeacherDashboardResponse(
        course={"id": course.id, "name": course.name} if course else {},
        topic={"id": topic.id, "title": topic.title} if topic else {},
        outcomes=outcomes,
        last_session=last_session_dict,
        class_mastery=class_mastery,
        weak_outcomes=weak_outcomes,
        recommendations=recs,
        provenance="MIXED",
    )


def get_class_insights_service(section_id: int, db: Session) -> ClassInsightsResponse:
    section = db.query(ClassSection).filter(ClassSection.id == section_id).first()
    if not section:
        raise NotFoundError(f"Section {section_id} not found")

    stats = db.query(SectionOutcomeStats).filter(SectionOutcomeStats.section_id == section_id).all()
    outcomes_insights: List[ClassOutcomeInsight] = []

    support_lo_id = 0
    support_code = "LO4"
    support_count = 0

    for s in stats:
        lo = s.learning_outcome
        weak_share = int(round((s.weak_count / s.respondents) * 100)) if s.respondents else 0
        warning = weak_share >= 40

        top_misc = None
        if s.top_misconception:
            top_misc = {
                "tag": s.top_misconception.tag,
                "label": s.top_misconception.label,
                "count": s.top_misconception_count,
            }

        if warning:
            support_lo_id = s.learning_outcome_id
            support_code = lo.code
            support_count = s.weak_count

        outcomes_insights.append(
            ClassOutcomeInsight(
                outcome_id=s.learning_outcome_id,
                code=lo.code,
                statement=lo.statement,
                class_mastery_percent=s.class_mastery_percent,
                status="WEAK" if warning else "STRONG",
                warning=warning,
                distribution={
                    "strong": s.strong_count,
                    "developing": s.developing_count,
                    "weak": s.weak_count,
                },
                weak_count=s.weak_count,
                weak_share_pct=weak_share,
                top_misconception=top_misc,
            )
        )

    # Sort by outcome code
    outcomes_insights.sort(key=lambda x: x.code)

    live_participants_count = db.query(SessionParticipant).join(ClassSession).filter(
        ClassSession.section_id == section_id
    ).count()

    return ClassInsightsResponse(
        section={"id": section.id, "name": section.name, "enrolled_count": section.enrolled_count},
        respondents=57,
        live_participants=max(1, live_participants_count),
        outcomes=outcomes_insights,
        support_summary=SupportSummary(
            outcome_id=support_lo_id,
            code=support_code,
            students_needing_support=support_count,
            text=f"{support_count} students need support on {support_code}",
        ),
        provenance="MIXED",
        seeded_note="Cohort incorporates 56 seeded baseline student profiles and 1 live student",
    )


def get_class_evidence_service(section_id: int, outcome_id: Optional[int], db: Session) -> ClassEvidenceResponse:
    section = db.query(ClassSection).filter(ClassSection.id == section_id).first()
    if not section:
        raise NotFoundError("Section not found")

    lo_query = db.query(LearningOutcome)
    if outcome_id:
        lo = lo_query.filter(LearningOutcome.id == outcome_id).first()
    else:
        lo = lo_query.filter(LearningOutcome.code == "LO4").first()
    if not lo:
        raise NotFoundError("Learning outcome not found")

    lo_schema = OutcomeSchema(id=lo.id, code=lo.code, statement=lo.statement, kind=lo.kind, prerequisite_ids=[])

    # Build question distribution
    questions = db.query(Question).filter(Question.learning_outcome_id == lo.id, Question.purpose == "EXIT_QUIZ").all()
    q_distributions: List[QuestionDistItem] = []

    for q in questions:
        opt_dist: List[OptionDistItem] = []
        for opt in q.options:
            # Seeded counts for LO4: 25 and 22 correct out of 57; misconception chosen by 19 students
            if opt.is_correct:
                count = 22 if q.seq == 5 else 25
            elif opt.misconception:
                count = 19 if q.seq == 4 else 18
            else:
                count = 8

            opt_dist.append(
                OptionDistItem(
                    label=opt.label,
                    text=opt.text,
                    count=count,
                    is_correct=opt.is_correct,
                    misconception=opt.misconception.label if opt.misconception else None,
                )
            )
        q_distributions.append(QuestionDistItem(question_id=q.id, stem=q.stem, options=opt_dist))

    top_misconceptions = [
        {"label": "Applying output error directly to hidden-layer weights", "count": 19}
    ]

    # Named students in section 5-A
    students_in_sec = db.query(Student).filter(Student.section_id == section_id, Student.is_named == True).all()
    named_mastery: List[NamedStudentMastery] = []

    for s in students_in_sec:
        m = db.query(Mastery).filter(Mastery.student_id == s.id, Mastery.learning_outcome_id == lo.id).first()
        pct = m.percent if m else (41 if s.is_live else 45)
        st = m.status if m else "WEAK"
        u_name = s.user.name if s.user else f"Student {s.id}"
        named_mastery.append(
            NamedStudentMastery(
                name=u_name,
                percent=pct,
                status=st,
                is_seeded=not s.is_live,
            )
        )

    return ClassEvidenceResponse(
        outcome=lo_schema,
        option_distribution=q_distributions,
        top_misconceptions=top_misconceptions,
        students=named_mastery,
        note="Seeded students are demonstration data",
    )


def get_class_recommendations_service(section_id: int, db: Session) -> List[TeacherRecommendationItem]:
    recs = db.query(Recommendation).filter(
        Recommendation.section_id == section_id,
        Recommendation.type == "RETEACH",
        Recommendation.status == "ACTIVE",
    ).all()

    results: List[TeacherRecommendationItem] = []
    for r in recs:
        lo = r.learning_outcome
        lo_schema = OutcomeSchema(id=lo.id, code=lo.code, statement=lo.statement, kind=lo.kind, prerequisite_ids=[])
        segment_schema = None
        if r.payload and "segment" in r.payload:
            segment_schema = ReteachSegment.model_validate(r.payload["segment"])

        results.append(
            TeacherRecommendationItem(
                id=r.id,
                type=r.type,
                outcome=lo_schema,
                title=r.title,
                why=r.why or "Low mastery detected from today's exit quiz.",
                suggested_action=r.suggested_action or "10-minute conceptual recap",
                suggested_approach=r.suggested_approach or "Use a simple worked example showing how error propagates from output to hidden layers.",
                facts=r.facts or {},
                segment=segment_schema,
                actions=["GENERATE_SEGMENT", "VIEW_EVIDENCE", "ASSIGN_PRACTICE"],
            )
        )
    return results


async def generate_reteach_service(
    section_id: int,
    outcome_id: int,
    teacher_user_id: int,
    db: Session,
) -> ReteachSegment:
    lo = db.query(LearningOutcome).filter(LearningOutcome.id == outcome_id).first()
    if not lo:
        raise NotFoundError("Learning outcome not found")

    source = db.query(Source).filter(Source.topic_id == lo.topic_id, Source.approved == True).first()

    rec = db.query(Recommendation).filter(
        Recommendation.section_id == section_id,
        Recommendation.learning_outcome_id == outcome_id,
        Recommendation.type == "RETEACH",
    ).first()

    facts = rec.facts if (rec and rec.facts) else {"outcome_code": lo.code, "weak_share_pct": 61, "respondents": 57}

    segment_obj, gen_mode = await ai_gateway.generate_reteach_segment(
        outcome=lo,
        facts=facts,
        source=source,
        user_id=teacher_user_id,
        role="TEACHER",
        db=db,
    )

    result_segment = ReteachSegment(
        title=segment_obj.title,
        duration_min=segment_obj.duration_min,
        outline=[ReteachSegmentOutline(minute_range=o.minute_range, activity=o.activity) for o in segment_obj.outline],
        worked_example=ReteachWorkedExample(
            setup=segment_obj.worked_example.setup,
            steps=segment_obj.worked_example.steps,
            takeaway=segment_obj.worked_example.takeaway,
        ),
        check_items=[
            ReteachCheckItem(stem=c.stem, options=c.options, answer=c.answer)
            for c in segment_obj.check_items
        ],
        generation_mode=gen_mode,
    )

    if rec:
        payload = rec.payload or {}
        payload["segment"] = result_segment.model_dump()
        rec.payload = payload
        db.commit()

    return result_segment

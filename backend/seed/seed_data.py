"""Idempotent seed data loading and startup seed integrity verification."""

import json
import logging
from typing import Any, Dict, List
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.models.curriculum import (
    User,
    Student,
    Teacher,
    Course,
    ClassSection,
    Topic,
    LearningOutcome,
    PrerequisiteEdge,
    Misconception,
)
from backend.models.content import Source
from backend.models.classroom import ClassSession
from backend.models.assessment import Question, QuestionOption
from backend.models.learner import Mastery, SectionOutcomeStats
from backend.models.skills import Skill, OutcomeSkill, StudentSkill
from backend.models.governance import AppSetting, AuditLog
from backend.seed.config_constants import (
    UNIVERSITY_NAME,
    PROGRAMME_NAME,
    COURSE_CODE,
    COURSE_NAME,
    TOPIC_TITLE,
    SECTION_5A_NAME,
    SECTION_5B_NAME,
    SECTION_ENROLLMENT,
    TOTAL_ENROLLMENT,
    RIYA_PRIORS,
    SECTION_5A_STATS,
    SECTION_5B_STATS,
    DEFAULT_POLICY_TEXT,
)

logger = logging.getLogger("sgsu.seed")

NAMED_STUDENTS_5A = [
    "Aarav Gupta", "Aditi Verma", "Ananya Sen", "Rohan Mehta",
    "Pooja Rao", "Kavya Nair", "Neha Joshi", "Rahul Jain",
    "Siddharth Das", "Ishita Bose", "Tanvi Kapoor", "Aryan Mishra"
]

NAMED_STUDENTS_5B = [
    "Dhruv Patel", "Sneha Kulkarni", "Dev Sharma", "Meera Iyer",
    "Kunal Shah", "Diya Roy", "Sameer Khan", "Ritu Saxena",
    "Varun Reddy", "Anjali Bhat", "Nikhil Pandey", "Swati Sengupta"
]


def seed_database(db: Session) -> bool:
    """Populate database with complete authoritative demonstrator dataset idempotently."""
    # Check if already seeded
    existing_course = db.query(Course).filter(Course.code == COURSE_CODE).first()
    if existing_course:
        logger.info("Database already seeded. Verifying integrity...")
        return True

    logger.info("Seeding SGSU Conference Demonstrator database...")

    # 1. App Settings
    app_settings_data = {
        "mastery_strong": "70",
        "mastery_developing": "50",
        "gap_min_share": "0.40",
        "gap_min_respondents": "10",
        "prior_weight": "2.0",
        "w_exit_quiz": "0.8",
        "w_live_poll": "0.5",
        "w_practice": "0.4",
        "min_group_size": "5",
        "ai_mode": "Academic Assistant",
        "ai_policy": json.dumps(DEFAULT_POLICY_TEXT),
        "university_name": UNIVERSITY_NAME,
        "model_name": settings.AI_MODEL,
        "status_labels": json.dumps({
            "student": {"STRONG": "Strong", "DEVELOPING": "Developing", "WEAK": "Needs Attention"},
            "staff": {"STRONG": "Strong", "DEVELOPING": "Developing", "WEAK": "Weak"},
        }),
    }
    for k, v in app_settings_data.items():
        db.add(AppSetting(key=k, value=v))

    # 2. Users: Staff, Live Student, Cohort Students
    # Teacher: Dr. Ashok Sharma
    teacher_user = User(
        name="Dr. Ashok Sharma",
        email="ashok.sharma@sgsu.edu.in",
        role="TEACHER",
    )
    db.add(teacher_user)
    db.flush()

    teacher = Teacher(
        user_id=teacher_user.id,
        department="Computer Science & Engineering",
    )
    db.add(teacher)
    db.flush()

    # Admin: Prof. Vikram Malhotra
    admin_user = User(
        name="Prof. Vikram Malhotra",
        email="admin@sgsu.edu.in",
        role="ADMIN",
    )
    db.add(admin_user)
    db.flush()

    # 3. Course and Sections
    course = Course(
        code=COURSE_CODE,
        name=COURSE_NAME,
        programme=PROGRAMME_NAME,
        semester=5,
    )
    db.add(course)
    db.flush()

    sec_5a = ClassSection(
        course_id=course.id,
        name=SECTION_5A_NAME,
        teacher_id=teacher.id,
        enrolled_count=SECTION_ENROLLMENT,
    )
    sec_5b = ClassSection(
        course_id=course.id,
        name=SECTION_5B_NAME,
        teacher_id=teacher.id,
        enrolled_count=SECTION_ENROLLMENT,
    )
    db.add_all([sec_5a, sec_5b])
    db.flush()

    # 4. Students
    # 4.1 Section 5-A: Live Student Riya
    riya_user = User(
        name="Riya Sharma",
        email="riya.sharma@sgsu.edu.in",
        role="STUDENT",
    )
    db.add(riya_user)
    db.flush()

    riya_student = Student(
        user_id=riya_user.id,
        roll_no="2024-CSE-5A-01",
        section_id=sec_5a.id,
        is_live=True,
        is_named=True,
    )
    db.add(riya_student)
    db.flush()

    # 4.2 Section 5-A: 12 Named Students
    for idx, name in enumerate(NAMED_STUDENTS_5A, start=2):
        u = User(name=name, email=f"student5a_{idx:02d}@sgsu.edu.in", role="STUDENT")
        db.add(u)
        db.flush()
        s = Student(user_id=u.id, roll_no=f"2024-CSE-5A-{idx:02d}", section_id=sec_5a.id, is_live=False, is_named=True)
        db.add(s)

    # 4.3 Section 5-A: 44 Aggregate Students
    for idx in range(14, 58):
        u = User(name=f"Student 5A-{idx:02d}", email=f"student5a_{idx:02d}@sgsu.edu.in", role="STUDENT")
        db.add(u)
        db.flush()
        s = Student(user_id=u.id, roll_no=f"2024-CSE-5A-{idx:02d}", section_id=sec_5a.id, is_live=False, is_named=False)
        db.add(s)

    # 4.4 Section 5-B: 12 Named Students
    for idx, name in enumerate(NAMED_STUDENTS_5B, start=1):
        u = User(name=name, email=f"student5b_{idx:02d}@sgsu.edu.in", role="STUDENT")
        db.add(u)
        db.flush()
        s = Student(user_id=u.id, roll_no=f"2024-CSE-5B-{idx:02d}", section_id=sec_5b.id, is_live=False, is_named=True)
        db.add(s)

    # 4.5 Section 5-B: 45 Aggregate Students
    for idx in range(13, 58):
        u = User(name=f"Student 5B-{idx:02d}", email=f"student5b_{idx:02d}@sgsu.edu.in", role="STUDENT")
        db.add(u)
        db.flush()
        s = Student(user_id=u.id, roll_no=f"2024-CSE-5B-{idx:02d}", section_id=sec_5b.id, is_live=False, is_named=False)
        db.add(s)

    db.flush()

    # 5. Topic and Outcomes
    topic = Topic(
        course_id=course.id,
        seq=1,
        title=TOPIC_TITLE,
    )
    db.add(topic)
    db.flush()

    lo1 = LearningOutcome(topic_id=topic.id, code="LO1", statement="Understand neural network structure", kind="OUTCOME")
    lo2 = LearningOutcome(topic_id=topic.id, code="LO2", statement="Explain the forward pass", kind="OUTCOME")
    lo3 = LearningOutcome(topic_id=topic.id, code="LO3", statement="Understand activation functions", kind="OUTCOME")
    lo4 = LearningOutcome(topic_id=topic.id, code="LO4", statement="Explain backpropagation", kind="OUTCOME")
    p1 = LearningOutcome(topic_id=topic.id, code="P1", statement="Basic Calculus", kind="PREREQUISITE")
    p2 = LearningOutcome(topic_id=topic.id, code="P2", statement="Chain Rule", kind="PREREQUISITE")

    db.add_all([lo1, lo2, lo3, lo4, p1, p2])
    db.flush()

    # Prerequisites Graph: P1 -> P2 -> LO4
    edge1 = PrerequisiteEdge(outcome_id=p2.id, prerequisite_id=p1.id)
    edge2 = PrerequisiteEdge(outcome_id=lo4.id, prerequisite_id=p2.id)
    db.add_all([edge1, edge2])
    db.flush()

    # Misconceptions for LO4
    mc1 = Misconception(
        learning_outcome_id=lo4.id,
        tag="mc_output_error_hidden_weights",
        label="Applying output error directly to hidden-layer weights",
        description="Applying final layer output error directly to update hidden layer weights without chain rule propagation through downstream layer weights and activation derivatives.",
    )
    mc2 = Misconception(
        learning_outcome_id=lo4.id,
        tag="mc_linear_collapse",
        label="Assuming hidden layers collapse without non-linear derivatives",
        description="Belief that gradient descent ignores activation function derivatives across intermediate layers.",
    )
    db.add_all([mc1, mc2])
    db.flush()

    # 6. Approved Academic Source
    source = Source(
        topic_id=topic.id,
        title="Neural Networks & Deep Learning Foundations",
        citation="SGSU CSE-501 Neural Networks Course Reader, 2026",
        body_text=(
            "An artificial neural network models complex non-linear functions through hierarchical layers: an input layer, "
            "one or more hidden layers, and an output layer. During forward propagation, intermediate affine signals z = Wx + b "
            "are transformed by non-linear activations such as Sigmoid, ReLU, or Tanh. Non-linearities prevent deep architectures from "
            "collapsing mathematically into a single linear mapping.\n\n"
            "Backpropagation utilizes the multivariable calculus chain rule to compute gradients of the loss with respect to all parameters. "
            "Critically, error signals propagate backwards layer-by-layer: a hidden neuron's gradient depends directly on the weights connecting "
            "it to subsequent layers and the derivative of its local activation function. The output layer error cannot be directly applied "
            "to hidden weights without passing through intermediate parameters."
        ),
        approved=True,
    )
    db.add(source)
    db.flush()

    # 7. Five Fixed Exit Quiz Questions + 1 Live Poll Question
    # Q1 -> LO1
    q1 = Question(
        topic_id=topic.id,
        learning_outcome_id=lo1.id,
        seq=1,
        stem="In a multilayer feedforward neural network, what is the fundamental architectural role of hidden layers?",
        purpose="EXIT_QUIZ",
        explanation="Hidden layers extract and transform hierarchical intermediate feature representations.",
    )
    db.add(q1)
    db.flush()
    db.add_all([
        QuestionOption(question_id=q1.id, label="A", text="To extract and transform intermediate feature representations from input data", is_correct=True),
        QuestionOption(question_id=q1.id, label="B", text="To store raw training examples directly for database retrieval", is_correct=False),
        QuestionOption(question_id=q1.id, label="C", text="To bypass activation functions during computation", is_correct=False),
        QuestionOption(question_id=q1.id, label="D", text="To directly set network hyperparameters during training", is_correct=False),
    ])

    # Q2 -> LO2
    q2 = Question(
        topic_id=topic.id,
        learning_outcome_id=lo2.id,
        seq=2,
        stem="During the forward pass of a neuron, which sequence of operations is evaluated?",
        purpose="EXIT_QUIZ",
        explanation="The forward pass executes an affine combination z = Wx + b followed by an activation function a = sigma(z).",
    )
    db.add(q2)
    db.flush()
    db.add_all([
        QuestionOption(question_id=q2.id, label="A", text="An affine transformation (weighted sum + bias) followed by an activation function", is_correct=True),
        QuestionOption(question_id=q2.id, label="B", text="Gradient computation followed by loss differentiation", is_correct=False),
        QuestionOption(question_id=q2.id, label="C", text="Weight subtraction followed by bias multiplication", is_correct=False),
        QuestionOption(question_id=q2.id, label="D", text="Inverse matrix multiplication followed by loss thresholding", is_correct=False),
    ])

    # Q3 -> LO3
    q3 = Question(
        topic_id=topic.id,
        learning_outcome_id=lo3.id,
        seq=3,
        stem="What is the primary reason for using non-linear activation functions in deep neural networks?",
        purpose="EXIT_QUIZ",
        explanation="Without non-linearities, multiple stacked layers mathematically collapse into a single linear transformation.",
    )
    db.add(q3)
    db.flush()
    db.add_all([
        QuestionOption(question_id=q3.id, label="A", text="To enable the network to learn arbitrary non-linear function mappings", is_correct=True),
        QuestionOption(question_id=q3.id, label="B", text="To ensure that all weight updates remain non-negative", is_correct=False),
        QuestionOption(question_id=q3.id, label="C", text="To accelerate the forward pass by reducing matrix dimension", is_correct=False),
        QuestionOption(question_id=q3.id, label="D", text="To eliminate the need for bias parameters in hidden units", is_correct=False),
    ])

    # Q4 -> LO4
    q4 = Question(
        topic_id=topic.id,
        learning_outcome_id=lo4.id,
        seq=4,
        stem="During backpropagation, how is the error gradient calculated for a hidden layer neuron?",
        purpose="EXIT_QUIZ",
        explanation="The chain rule scales incoming downstream errors by connecting weights and the local activation derivative.",
    )
    db.add(q4)
    db.flush()
    db.add_all([
        QuestionOption(question_id=q4.id, label="A", text="By multiplying downstream propagated errors by outgoing weights and the local activation derivative", is_correct=True),
        QuestionOption(question_id=q4.id, label="B", text="apply output error directly to hidden-layer weights", is_correct=False, misconception_id=mc1.id),
        QuestionOption(question_id=q4.id, label="C", text="By computing the average difference of inputs without derivative terms", is_correct=False),
        QuestionOption(question_id=q4.id, label="D", text="By setting the gradient equal to the raw input feature values", is_correct=False),
    ])

    # Q5 -> LO4
    q5 = Question(
        topic_id=topic.id,
        learning_outcome_id=lo4.id,
        seq=5,
        stem="Why is the calculus chain rule fundamental to updating hidden weights in backpropagation?",
        purpose="EXIT_QUIZ",
        explanation="Composite derivatives ensure each layer's parameter receives gradients reflecting its contribution across subsequent layers.",
    )
    db.add(q5)
    db.flush()
    db.add_all([
        QuestionOption(question_id=q5.id, label="A", text="It enables propagating gradients layer-by-layer backwards using composite derivative products", is_correct=True),
        QuestionOption(question_id=q5.id, label="B", text="apply output error directly to hidden-layer weights", is_correct=False, misconception_id=mc1.id),
        QuestionOption(question_id=q5.id, label="C", text="It guarantees that the learning rate increases automatically on each training epoch", is_correct=False),
        QuestionOption(question_id=q5.id, label="D", text="It replaces numerical optimization with closed-form matrix inversion", is_correct=False),
    ])

    # Poll Question (purpose="POLL", seq=1)
    q_poll = Question(
        topic_id=topic.id,
        learning_outcome_id=lo1.id,
        seq=1,
        stem="Which layer of a neural network directly interfaces with the target loss function during training?",
        purpose="POLL",
        explanation="The output layer produces the final prediction evaluated by the loss function.",
    )
    db.add(q_poll)
    db.flush()
    db.add_all([
        QuestionOption(question_id=q_poll.id, label="A", text="Output layer", is_correct=True),
        QuestionOption(question_id=q_poll.id, label="B", text="First hidden layer", is_correct=False),
        QuestionOption(question_id=q_poll.id, label="C", text="Input layer", is_correct=False),
        QuestionOption(question_id=q_poll.id, label="D", text="Normalization layer", is_correct=False),
    ])
    db.flush()

    # 8. Live Student Priors and Initial Mastery
    los = {"LO1": lo1, "LO2": lo2, "LO3": lo3, "LO4": lo4}
    for code, prior in RIYA_PRIORS.items():
        lo_obj = los[code]
        percent = int(round(100 * prior))
        status = "STRONG" if percent >= 70 else ("DEVELOPING" if percent >= 50 else "WEAK")
        m = Mastery(
            student_id=riya_student.id,
            learning_outcome_id=lo_obj.id,
            estimate=prior,
            percent=percent,
            status=status,
            evidence_count=0,
            prior_estimate=prior,
            prior_weight=2.0,
            provenance="SEEDED",
        )
        db.add(m)
    db.flush()

    # 9. Section Outcome Stats (5-A and 5-B)
    for code, data in SECTION_5A_STATS.items():
        lo_obj = los[code]
        stat = SectionOutcomeStats(
            section_id=sec_5a.id,
            learning_outcome_id=lo_obj.id,
            class_mastery_percent=data["percent"],
            weak_count=data["weak_count"],
            respondents=SECTION_ENROLLMENT,
            strong_count=data["strong_count"],
            developing_count=data["developing_count"],
            top_misconception_id=mc1.id if code == "LO4" else None,
            top_misconception_count=19 if code == "LO4" else 0,
            is_seeded=True,
        )
        db.add(stat)

    for code, data in SECTION_5B_STATS.items():
        lo_obj = los[code]
        stat = SectionOutcomeStats(
            section_id=sec_5b.id,
            learning_outcome_id=lo_obj.id,
            class_mastery_percent=data["percent"],
            weak_count=data["weak_count"],
            respondents=SECTION_ENROLLMENT,
            strong_count=data["strong_count"],
            developing_count=data["developing_count"],
            top_misconception_id=mc1.id if code == "LO4" else None,
            top_misconception_count=17 if code == "LO4" else 0,
            is_seeded=True,
        )
        db.add(stat)
    db.flush()

    # 10. Skills Architecture & Riya's Skills
    skill_py = Skill(name="Python", is_derived=False)
    skill_ml = Skill(name="Machine Learning", is_derived=False)
    skill_ps = Skill(name="Problem Solving", is_derived=False)
    skill_nn = Skill(name="Neural Networks", is_derived=True)
    skill_dl = Skill(name="Deep Learning", is_derived=False)
    db.add_all([skill_py, skill_ml, skill_ps, skill_nn, skill_dl])
    db.flush()

    # Map Neural Networks skill to LO1 - LO4
    for lo_obj in [lo1, lo2, lo3, lo4]:
        db.add(OutcomeSkill(skill_id=skill_nn.id, learning_outcome_id=lo_obj.id))
    db.flush()

    # Riya's initial skills
    db.add_all([
        StudentSkill(student_id=riya_student.id, skill_id=skill_py.id, level="DEVELOPING", source="SEEDED"),
        StudentSkill(student_id=riya_student.id, skill_id=skill_ml.id, level="DEVELOPING", source="SEEDED"),
        StudentSkill(student_id=riya_student.id, skill_id=skill_ps.id, level="STRONG", source="SEEDED"),
        StudentSkill(student_id=riya_student.id, skill_id=skill_nn.id, level="DEVELOPING", source="DERIVED"),
        StudentSkill(student_id=riya_student.id, skill_id=skill_dl.id, level="RECOMMENDED_NEXT", source="SEEDED"),
    ])

    # Initial audit log
    db.add(AuditLog(
        action="LOGIN",
        user_id=teacher_user.id,
        role="TEACHER",
        entity="SYSTEM",
        detail={"message": "System initial seed established"},
    ))

    db.commit()
    logger.info("Database seeding successfully completed!")
    return True


def validate_seed_integrity(db: Session) -> Dict[str, Any]:
    """Execute authoritative startup validation of conference demonstration dataset."""
    checks: Dict[str, bool] = {}
    details: Dict[str, Any] = {}

    sec_5a = db.query(ClassSection).filter(ClassSection.name == SECTION_5A_NAME).first()
    sec_5b = db.query(ClassSection).filter(ClassSection.name == SECTION_5B_NAME).first()

    # 1. 5-A enrollment = 57
    count_5a = db.query(Student).filter(Student.section_id == sec_5a.id).count() if sec_5a else 0
    checks["enrollment_5a_57"] = (count_5a == 57)
    details["count_5a"] = count_5a

    # 2. 5-B enrollment = 57
    count_5b = db.query(Student).filter(Student.section_id == sec_5b.id).count() if sec_5b else 0
    checks["enrollment_5b_57"] = (count_5b == 57)
    details["count_5b"] = count_5b

    # 3 & 4. LO4 seeded weak count 5-A = 34, 5-B = 31
    lo4 = db.query(LearningOutcome).filter(LearningOutcome.code == "LO4").first()
    lo4_stat_5a = db.query(SectionOutcomeStats).filter(
        SectionOutcomeStats.section_id == sec_5a.id,
        SectionOutcomeStats.learning_outcome_id == lo4.id,
    ).first() if (sec_5a and lo4) else None

    lo4_stat_5b = db.query(SectionOutcomeStats).filter(
        SectionOutcomeStats.section_id == sec_5b.id,
        SectionOutcomeStats.learning_outcome_id == lo4.id,
    ).first() if (sec_5b and lo4) else None

    checks["lo4_weak_5a_34"] = (lo4_stat_5a is not None and lo4_stat_5a.weak_count == 34)
    checks["lo4_weak_5b_31"] = (lo4_stat_5b is not None and lo4_stat_5b.weak_count == 31)
    details["lo4_weak_5a"] = lo4_stat_5a.weak_count if lo4_stat_5a else 0
    details["lo4_weak_5b"] = lo4_stat_5b.weak_count if lo4_stat_5b else 0

    # 5. Combined percentage arithmetic verification
    combined_weak_post_scripted = (34 + 1) + 31  # 35 + 31 = 66
    combined_total = count_5a + count_5b  # 114
    pct_scripted = round((combined_weak_post_scripted / combined_total) * 100) if combined_total else 0
    checks["combined_scripted_weak_pct_58"] = (pct_scripted == 58 and combined_weak_post_scripted == 66 and combined_total == 114)
    details["combined_scripted_weak_pct"] = pct_scripted

    # 6. Priors are correct
    riya = db.query(Student).filter(Student.is_live == True).first()
    priors_match = True
    if riya:
        for code, expected in RIYA_PRIORS.items():
            lo_record = db.query(LearningOutcome).filter(LearningOutcome.code == code).first()
            mastery_record = db.query(Mastery).filter(
                Mastery.student_id == riya.id,
                Mastery.learning_outcome_id == lo_record.id,
            ).first() if lo_record else None
            if not mastery_record or abs(mastery_record.prior_estimate - expected) > 1e-4:
                priors_match = False
                break
    else:
        priors_match = False
    checks["riya_priors_correct"] = priors_match

    # 7. Prerequisite graph: P1 -> P2 -> LO4
    p1 = db.query(LearningOutcome).filter(LearningOutcome.code == "P1").first()
    p2 = db.query(LearningOutcome).filter(LearningOutcome.code == "P2").first()
    edge_p1_p2 = db.query(PrerequisiteEdge).filter(
        PrerequisiteEdge.outcome_id == p2.id,
        PrerequisiteEdge.prerequisite_id == p1.id,
    ).first() if (p1 and p2) else None
    edge_p2_lo4 = db.query(PrerequisiteEdge).filter(
        PrerequisiteEdge.outcome_id == lo4.id,
        PrerequisiteEdge.prerequisite_id == p2.id,
    ).first() if (p2 and lo4) else None
    checks["prerequisite_graph_valid"] = (edge_p1_p2 is not None and edge_p2_lo4 is not None)

    # 8. Questions have exactly one correct option
    questions = db.query(Question).all()
    all_q_one_correct = True
    for q in questions:
        correct_count = sum(1 for opt in q.options if opt.is_correct)
        if correct_count != 1:
            all_q_one_correct = False
            break
    checks["questions_have_one_correct_option"] = all_q_one_correct

    # 9. All exit questions have valid LO tags
    exit_questions = db.query(Question).filter(Question.purpose == "EXIT_QUIZ").all()
    checks["exit_questions_count_5"] = (len(exit_questions) == 5)
    all_lo_valid = all(q.learning_outcome_id is not None for q in exit_questions)
    checks["all_exit_questions_have_lo_tags"] = all_lo_valid

    # 10. All misconception references are valid
    q4 = db.query(Question).filter(Question.seq == 4, Question.purpose == "EXIT_QUIZ").first()
    q5 = db.query(Question).filter(Question.seq == 5, Question.purpose == "EXIT_QUIZ").first()
    misc = db.query(Misconception).filter(Misconception.tag == "mc_output_error_hidden_weights").first()
    has_q4_misc = any(opt.misconception_id == misc.id for opt in q4.options) if (q4 and misc) else False
    has_q5_misc = any(opt.misconception_id == misc.id for opt in q5.options) if (q5 and misc) else False
    checks["q4_and_q5_have_misconception_option"] = (has_q4_misc and has_q5_misc)

    # 11. Neural Networks maps to LO1-LO4
    nn_skill = db.query(Skill).filter(Skill.name == "Neural Networks").first()
    linked_lo_ids = {os.learning_outcome_id for os in nn_skill.outcomes} if nn_skill else set()
    lo_1_4_ids = {
        lo.id for lo in db.query(LearningOutcome).filter(LearningOutcome.code.in_(["LO1", "LO2", "LO3", "LO4"])).all()
    }
    checks["neural_networks_maps_to_lo1_to_lo4"] = (linked_lo_ids == lo_1_4_ids and len(linked_lo_ids) == 4)

    healthy = all(checks.values())
    if not healthy:
        failed = [k for k, v in checks.items() if not v]
        logger.error(f"Seed integrity FAILED checks: {failed}")
    else:
        logger.info("Seed integrity checks PASSED successfully.")

    return {
        "healthy": healthy,
        "checks": checks,
        "details": details,
    }

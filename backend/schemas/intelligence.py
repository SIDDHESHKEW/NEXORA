"""Intelligence, analytics, governance, tutor, and demo schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.schemas.curriculum import OutcomeSchema, SourceSchema
from backend.schemas.classroom import StudentQuestion
from backend.schemas.assessment import MasteryItemSchema


# --- Student Intelligence ---
class StudentSummary(BaseModel):
    id: int
    name: str


class StudentMasteryResponse(BaseModel):
    student: StudentSummary
    overall_percent: int
    overall_status: str
    items: List[MasteryItemSchema]
    provenance: str = "MIXED"


class RecommendationStep(BaseModel):
    kind: str  # RECAP | PRACTICE | TUTOR
    label: str
    detail: Optional[str] = None


class StudentRecommendationResponse(BaseModel):
    id: int
    type: str  # GAP_SUPPORT | PRACTICE_ASSIGNED
    outcome: OutcomeSchema
    title: str
    what_happened: str
    why_seen: str
    steps: List[RecommendationStep] = Field(default_factory=list)
    recap_status: Optional[str] = None  # PENDING | READY | READY_FALLBACK
    recap_text: Optional[str] = None
    mastery_percent: int
    status: str


class StudentEvidenceItem(BaseModel):
    occurred_at: datetime
    source_type: str
    question_stem: str
    selected: str
    correct: str
    is_correct: bool
    weight: float
    misconception: Optional[str] = None


class SkillItem(BaseModel):
    name: str
    level: str  # NEEDS_PRACTICE | DEVELOPING | STRONG | RECOMMENDED_NEXT
    source: str  # SEEDED | DERIVED


class SkillEvidenceItem(BaseModel):
    label: str
    detail: str


class SkillPassportResponse(BaseModel):
    profile: str = "AI/ML Learning Profile"
    skills: List[SkillItem]
    evidence: List[SkillEvidenceItem] = Field(default_factory=list)
    career_direction: str = "AI/ML Engineer"
    recommended_next_skill: str = "Deep Learning"
    provenance: str = "MIXED"


class PracticeGenerateRequest(BaseModel):
    outcome_id: int


class PracticeSetResponse(BaseModel):
    set_id: int
    outcome: OutcomeSchema
    generation_mode: str
    questions: List[StudentQuestion]
    status: Optional[str] = None


class PracticeAssignRequest(BaseModel):
    section_id: int
    outcome_id: int


class PracticeAssignResponse(BaseModel):
    assigned_count: int


class TutorAskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    outcome_id: Optional[int] = None


class TutorAskResponse(BaseModel):
    answer: str
    topic: str = "Backpropagation"
    source: str = "Neural Networks — Course Material"
    label: str = "Grounded in approved course material"
    mode: str = "FALLBACK"


# --- Teacher Intelligence ---
class ClassOutcomeInsight(BaseModel):
    outcome_id: int
    code: str
    statement: str
    class_mastery_percent: int
    status: str
    warning: bool
    distribution: Dict[str, int]
    weak_count: int
    weak_share_pct: int
    top_misconception: Optional[Dict[str, Any]] = None


class SupportSummary(BaseModel):
    outcome_id: int
    code: str
    students_needing_support: int
    text: str


class ClassInsightsResponse(BaseModel):
    section: Dict[str, Any]
    respondents: int
    live_participants: int
    outcomes: List[ClassOutcomeInsight]
    support_summary: SupportSummary
    provenance: str = "MIXED"
    seeded_note: Optional[str] = "Cohort includes 56 seeded baseline student profiles"


class OptionDistItem(BaseModel):
    label: str
    text: str
    count: int
    is_correct: bool
    misconception: Optional[str] = None


class QuestionDistItem(BaseModel):
    question_id: int
    stem: str
    options: List[OptionDistItem]


class NamedStudentMastery(BaseModel):
    name: str
    percent: int
    status: str
    is_seeded: bool


class ClassEvidenceResponse(BaseModel):
    outcome: OutcomeSchema
    option_distribution: List[QuestionDistItem]
    top_misconceptions: List[Dict[str, Any]]
    students: List[NamedStudentMastery]
    note: str = "Seeded students are demonstration data"


class ReteachSegmentOutline(BaseModel):
    minute_range: str
    activity: str


class ReteachWorkedExample(BaseModel):
    setup: str
    steps: List[str]
    takeaway: str


class ReteachCheckItem(BaseModel):
    stem: str
    options: List[str]
    answer: str


class ReteachSegment(BaseModel):
    title: str
    duration_min: int = 10
    outline: List[ReteachSegmentOutline]
    worked_example: ReteachWorkedExample
    check_items: List[ReteachCheckItem]
    generation_mode: str = "FALLBACK"


class TeacherRecommendationItem(BaseModel):
    id: int
    type: str = "RETEACH"
    outcome: OutcomeSchema
    title: str
    why: str
    suggested_action: str
    suggested_approach: str
    facts: Dict[str, Any]
    segment: Optional[ReteachSegment] = None
    actions: List[str] = Field(default_factory=lambda: ["GENERATE_SEGMENT", "VIEW_EVIDENCE", "ASSIGN_PRACTICE"])


class TeacherDashboardResponse(BaseModel):
    course: Dict[str, Any]
    topic: Dict[str, Any]
    outcomes: List[OutcomeSchema]
    last_session: Optional[Dict[str, Any]] = None
    class_mastery: List[Dict[str, Any]]
    weak_outcomes: List[Dict[str, Any]]
    recommendations: List[TeacherRecommendationItem]
    provenance: str = "MIXED"


class ReteachRequest(BaseModel):
    outcome_id: int


# --- University Intelligence ---
class AdminOverviewResponse(BaseModel):
    total_students: int = 114
    active_courses: int = 1
    outcomes_tracked: int = 4
    weak_outcomes: int = 1
    sections: int = 2
    provenance: str = "MIXED"
    seeded_note: str = "Demonstration dataset: 114 students enrolled across 2 sections"


class AdminSectionGap(BaseModel):
    name: str
    weak_share_pct: int
    respondents: int


class AdminPrerequisite(BaseModel):
    code: str
    name: str
    developing_or_better_pct: int


class AdminGapItem(BaseModel):
    outcome: OutcomeSchema
    recurring: bool = True
    sections: List[AdminSectionGap]
    combined_weak_share_pct: int
    total_respondents: int
    prerequisites: List[AdminPrerequisite]
    why_this_matters: str
    suggested_actions: List[str]
    provenance: str = "MIXED"


class AdminAnalyticsResponse(BaseModel):
    mastery_by_outcome: List[Dict[str, Any]]
    section_comparison: List[Dict[str, Any]]
    weak_distribution: List[Dict[str, Any]]
    prerequisites: List[Dict[str, Any]]


class AdminRecommendationRequest(BaseModel):
    outcome_id: int


class AdminRecommendationResponse(BaseModel):
    id: int
    text: str
    mode: str = "FALLBACK"
    facts: Dict[str, Any]


# --- Governance ---
class GovernancePolicyResponse(BaseModel):
    ai_mode: str = "Academic Assistant"
    sources: str = "Approved Course Material"
    data: str = "Demonstration Dataset"
    model: str = "Configured AI Provider"
    model_name: str
    usage_policy: List[str]
    approved_sources: List[SourceSchema]


class GovernanceLogsResponse(BaseModel):
    ai: List[Dict[str, Any]] = Field(default_factory=list)
    audit: List[Dict[str, Any]] = Field(default_factory=list)


# --- Demo ---
class DemoResetResponse(BaseModel):
    reset: bool = True
    seed_version: str = "v1.0-sgsu-demo"


class DemoStateStep(BaseModel):
    n: int
    key: str
    label: str
    done: bool
    detail: str


class DemoStateLoop(BaseModel):
    teach: bool = False
    learn: bool = False
    assess: bool = False
    understand: bool = False
    personalize: bool = False
    support_teacher: bool = False
    inform_university: bool = False
    improve: bool = False


class DemoStateResponse(BaseModel):
    steps: List[DemoStateStep]
    current_step: int
    loop: DemoStateLoop

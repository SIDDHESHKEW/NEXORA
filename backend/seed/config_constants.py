"""Constants and default configuration parameters for SGSU Platform."""

UNIVERSITY_NAME = "Scope Global Skills University (SGSU)"
PROGRAMME_NAME = "B.Tech CSE"
COURSE_CODE = "CS-501"
COURSE_NAME = "Artificial Intelligence"
TOPIC_TITLE = "Neural Networks"

SECTION_5A_NAME = "5-A"
SECTION_5B_NAME = "5-B"
SECTION_ENROLLMENT = 57
TOTAL_ENROLLMENT = 114

# Live student priors
RIYA_PRIORS = {
    "LO1": 0.832,
    "LO2": 0.636,
    "LO3": 0.734,
    "LO4": 0.738,
}

# Baseline section stats (seeded)
SECTION_5A_STATS = {
    "LO1": {"percent": 88, "weak_count": 6, "strong_count": 45, "developing_count": 6},
    "LO2": {"percent": 74, "weak_count": 12, "strong_count": 32, "developing_count": 13},
    "LO3": {"percent": 81, "weak_count": 8, "strong_count": 41, "developing_count": 8},
    "LO4": {"percent": 41, "weak_count": 34, "strong_count": 10, "developing_count": 13},
}

SECTION_5B_STATS = {
    "LO1": {"percent": 84, "weak_count": 8, "strong_count": 42, "developing_count": 7},
    "LO2": {"percent": 72, "weak_count": 14, "strong_count": 30, "developing_count": 13},
    "LO3": {"percent": 78, "weak_count": 10, "strong_count": 38, "developing_count": 9},
    "LO4": {"percent": 46, "weak_count": 31, "strong_count": 12, "developing_count": 14},
}

PREREQUISITE_STATS = {
    "P1": {"code": "P1", "name": "Basic Calculus", "developing_or_better_pct": 71},
    "P2": {"code": "P2", "name": "Chain Rule", "developing_or_better_pct": 52},
}

DEFAULT_POLICY_TEXT = [
    "AI drafts content for teachers and explains concepts to students; it does not grade, rank or make decisions about people.",
    "All educational generation is grounded strictly in approved university syllabus materials.",
    "Live student data is never used for external model training or surveillance.",
    "Deterministic mathematical algorithms calculate all marks, mastery estimates, and academic gap indicators.",
]

"""Governance service: policy disclosure, audit logging, and interaction tracking."""

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.core.config import settings
from backend.models.content import Source
from backend.models.governance import AIInteraction, AuditLog, AppSetting
from backend.schemas.curriculum import SourceSchema
from backend.schemas.intelligence import GovernancePolicyResponse, GovernanceLogsResponse

logger = logging.getLogger("sgsu.governance")


def get_governance_policy_service(db: Session) -> GovernancePolicyResponse:
    """Retrieve university AI governance policy and approved course material sources."""
    sources = db.query(Source).all()
    source_schemas = [
        SourceSchema(
            id=s.id,
            title=s.title,
            citation=s.citation,
            content_length=len(s.content) if s.content else 0,
        )
        for s in sources
    ]

    policy_texts = [
        "AI drafts content for teachers and explains concepts to students; it does not grade, rank or make decisions about people.",
        "All educational generation is grounded exclusively in approved faculty-curated source materials.",
        "AI never computes student mastery, correctness, or grade thresholds.",
        "Deterministic fallbacks ensure zero disruption if external AI providers are unavailable.",
    ]

    return GovernancePolicyResponse(
        ai_mode="Academic Assistant",
        sources="Approved Course Material",
        data="Demonstration Dataset",
        model="Configured AI Provider",
        model_name=settings.ai_model,
        usage_policy=policy_texts,
        approved_sources=source_schemas,
    )


def get_governance_logs_service(db: Session, limit: int = 100) -> GovernanceLogsResponse:
    """Retrieve recent AI interaction logs and audit trail logs."""
    ai_rows = (
        db.query(AIInteraction)
        .order_by(desc(AIInteraction.created_at))
        .limit(limit)
        .all()
    )

    audit_rows = (
        db.query(AuditLog)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
        .all()
    )

    ai_logs = [
        {
            "id": r.id,
            "function": r.function,
            "model": r.model,
            "provider": r.provider,
            "status": r.status,
            "latency_ms": r.latency_ms,
            "validation_passed": r.validation_passed,
            "fallback_reason": r.fallback_reason,
            "context_ref": r.context_ref,
            "user_id": r.user_id,
            "role": r.role,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in ai_rows
    ]

    audit_logs = [
        {
            "id": r.id,
            "action": r.action,
            "user_id": r.user_id,
            "role": r.role,
            "entity": r.entity,
            "entity_id": r.entity_id,
            "detail": r.detail,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in audit_rows
    ]

    return GovernanceLogsResponse(
        ai=ai_logs,
        audit=audit_logs,
    )


def create_audit_log(
    db: Session,
    action: str,
    user_id: Optional[int] = None,
    role: Optional[str] = None,
    entity: Optional[str] = None,
    entity_id: Optional[int] = None,
    detail: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """Record an audit trail entry."""
    entry = AuditLog(
        action=action,
        user_id=user_id,
        role=role,
        entity=entity,
        entity_id=entity_id,
        detail=detail or {},
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

"""Governance, AI logging, Audit logs, and App Settings models."""

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from backend.core.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class AIInteraction(Base):
    __tablename__ = "ai_interactions"

    id = Column(Integer, primary_key=True, index=True)
    function = Column(String(80), nullable=False, index=True)
    model = Column(String(80), nullable=False)
    provider = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, index=True)  # OK | FALLBACK | ERROR
    latency_ms = Column(Integer, default=0, nullable=False)
    validation_passed = Column(Boolean, default=True, nullable=False)
    fallback_reason = Column(String(100), nullable=True)
    context_ref = Column(String(100), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    role = Column(String(30), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    __table_args__ = (
        CheckConstraint("status IN ('OK', 'FALLBACK', 'ERROR')", name="check_ai_interaction_status"),
    )

    user = relationship("User")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(50), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    role = Column(String(30), nullable=True)
    entity = Column(String(50), nullable=True)
    entity_id = Column(Integer, nullable=True)
    detail = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    user = relationship("User")


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String(80), primary_key=True, index=True)
    value = Column(Text, nullable=False)
    description = Column(String(255), nullable=True)

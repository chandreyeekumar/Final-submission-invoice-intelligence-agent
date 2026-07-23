from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import (
    Base,
    JSONType,
    TimestampMixin,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ValidationIssue(Base, TimestampMixin):
    __tablename__ = "validation_issues"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    document_id: Mapped[str] = mapped_column(
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )

    invoice_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "invoices.id",
            ondelete="CASCADE",
        )
    )

    validation_run: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    field_name: Mapped[str | None] = mapped_column(
        String(120)
    )

    code: Mapped[str] = mapped_column(
        String(160),
        index=True,
        nullable=False,
    )

    severity: Mapped[str] = mapped_column(
        String(30),
        index=True,
        nullable=False,
    )

    message: Mapped[str | None] = mapped_column(
        Text
    )

    observed_value: Mapped[
        str | None
    ] = mapped_column(
        Text
    )

    expected_value: Mapped[
        str | None
    ] = mapped_column(
        Text
    )

    resolved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    details_json: Mapped[
        dict | None
    ] = mapped_column(
        JSONType
    )


class CorrectionHistory(Base, TimestampMixin):
    __tablename__ = "correction_history"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    document_id: Mapped[str] = mapped_column(
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )

    invoice_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "invoices.id",
            ondelete="CASCADE",
        )
    )

    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    requested_fields_json: Mapped[
        list
    ] = mapped_column(
        JSONType,
        default=list,
        nullable=False,
    )

    changed_fields_json: Mapped[
        list
    ] = mapped_column(
        JSONType,
        default=list,
        nullable=False,
    )

    unauthorized_changes_json: Mapped[
        list | None
    ] = mapped_column(
        JSONType
    )

    guardrail_passed: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    accepted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    reason: Mapped[str | None] = mapped_column(
        Text
    )

    model_used: Mapped[str | None] = mapped_column(
        String(100)
    )


class RAGEvidence(Base, TimestampMixin):
    __tablename__ = "rag_evidence"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    document_id: Mapped[str] = mapped_column(
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )

    invoice_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "invoices.id",
            ondelete="CASCADE",
        )
    )

    status: Mapped[str] = mapped_column(
        String(40),
        index=True,
        nullable=False,
    )

    query_text: Mapped[str | None] = mapped_column(
        Text
    )

    matched_vendor_id: Mapped[
        str | None
    ] = mapped_column(
        String(100)
    )

    matched_legal_name: Mapped[
        str | None
    ] = mapped_column(
        String(255)
    )

    top_distance: Mapped[
        Decimal | None
    ] = mapped_column(
        Numeric(10, 6)
    )

    exact_checks_json: Mapped[
        dict | None
    ] = mapped_column(
        JSONType
    )

    issues_json: Mapped[
        list | None
    ] = mapped_column(
        JSONType
    )

    recommended_action: Mapped[
        str | None
    ] = mapped_column(
        String(60)
    )

    knowledge_base_version: Mapped[
        str | None
    ] = mapped_column(
        String(100)
    )


class RAGCandidate(Base, TimestampMixin):
    __tablename__ = "rag_candidates"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    rag_evidence_id: Mapped[str] = mapped_column(
        ForeignKey(
            "rag_evidence.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )

    rank: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    vendor_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    legal_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    distance: Mapped[Decimal] = mapped_column(
        Numeric(10, 6),
        nullable=False,
    )

    metadata_json: Mapped[
        dict | None
    ] = mapped_column(
        JSONType
    )


class SafetyDecision(Base, TimestampMixin):
    __tablename__ = "safety_decisions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    document_id: Mapped[str] = mapped_column(
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )

    stage: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    label: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    attack_type: Mapped[
        str | None
    ] = mapped_column(
        String(100)
    )

    risk_score: Mapped[Decimal] = mapped_column(
        Numeric(6, 5),
        nullable=False,
    )

    expected_action: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    reasons_json: Mapped[list] = mapped_column(
        JSONType,
        default=list,
        nullable=False,
    )

    model_used: Mapped[
        str | None
    ] = mapped_column(
        String(100)
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "sequence_number",
            name="uq_audit_document_sequence",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    document_id: Mapped[str] = mapped_column(
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )

    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    actor_type: Mapped[str] = mapped_column(
        String(40),
        default="system",
        nullable=False,
    )

    node_name: Mapped[
        str | None
    ] = mapped_column(
        String(100)
    )

    payload_json: Mapped[dict] = mapped_column(
        JSONType,
        default=dict,
        nullable=False,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class DocumentStatusHistory(Base):
    __tablename__ = "document_status_history"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    document_id: Mapped[str] = mapped_column(
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )

    previous_status: Mapped[
        str | None
    ] = mapped_column(
        String(40)
    )

    new_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    reason: Mapped[str | None] = mapped_column(
        Text
    )

    changed_by: Mapped[str] = mapped_column(
        String(100),
        default="workflow",
        nullable=False,
    )

    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
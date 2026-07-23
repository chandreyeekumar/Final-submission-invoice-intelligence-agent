from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.base import DocumentStatus
from app.db.models import (
    AuditEvent,
    CorrectionHistory,
    Document,
    DocumentStatusHistory,
    Invoice,
    RAGCandidate,
    RAGEvidence,
    SafetyDecision,
    ValidationIssue,
)


INVOICE_FIELDS = [
    "vendor_name",
    "vendor_address",
    "vendor_tax_id",
    "invoice_number",
    "invoice_date",
    "due_date",
    "purchase_order_number",
    "currency",
    "subtotal",
    "discount",
    "shipping",
    "tax_total",
    "previous_balance",
    "credit_adjustment",
    "total",
    "amount_due",
]


def _model_dump(value: Any) -> dict:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")

    if isinstance(value, dict):
        return value

    raise TypeError(
        f"Cannot serialize value of type {type(value).__name__}"
    )


def _get_value(
    value: Any,
    field: str,
    default: Any = None,
) -> Any:
    if isinstance(value, dict):
        return value.get(field, default)

    return getattr(value, field, default)


class Repository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_document(
        self,
        request_id: str,
        filename: str,
        path: str,
        info: dict,
    ) -> Document:
        source_path = Path(path)

        if not source_path.exists():
            raise FileNotFoundError(
                f"Uploaded document does not exist: {source_path}"
            )

        file_hash = hashlib.sha256(
            source_path.read_bytes()
        ).hexdigest()

        document = Document(
            request_id=request_id,
            original_filename=filename,
            stored_path=str(source_path),
            mime_type=info.get("mime_type"),
            size_bytes=source_path.stat().st_size,
            page_count=info.get("page_count"),
            sha256=file_hash,
        )

        self.session.add(document)
        self.session.flush()

        self.set_status(
            document,
            DocumentStatus.RECEIVED,
            "Upload accepted",
        )

        return document

    def set_status(
        self,
        document: Document,
        new_status: DocumentStatus,
        reason: str | None,
    ) -> None:
        previous_status = (
            document.status.value
            if document.status
            else None
        )

        document.status = new_status
        document.status_reason = reason
        document.human_review_required = (
            new_status == DocumentStatus.HUMAN_REVIEW
        )

        self.session.add(
            DocumentStatusHistory(
                document_id=document.id,
                previous_status=previous_status,
                new_status=new_status.value,
                reason=reason,
                changed_by="workflow",
            )
        )

    def upsert_invoice(
        self,
        document: Document,
        state: dict,
    ) -> Invoice:
        invoice = self.session.scalar(
            select(Invoice).where(
                Invoice.document_id == document.id
            )
        )

        if invoice is None:
            invoice = Invoice(
                document_id=document.id
            )

        self.session.add(invoice)

        extraction = state["extraction"]
        extraction_payload = _model_dump(extraction)

        for field in INVOICE_FIELDS:
            setattr(
                invoice,
                field,
                _get_value(extraction, field),
            )

        bank_account = _get_value(
            extraction,
            "vendor_bank_account",
        )

        invoice.vendor_bank_account_masked = (
            str(bank_account)
            if bank_account
            else None
        )

        invoice.complexity_tier = state.get(
            "complexity_tier"
        )

        invoice.model_used = state.get(
            "model_used"
        )

        invoice.extraction_attempts = int(
            state.get("extraction_attempts", 0)
        )

        invoice.overall_ocr_confidence = state.get(
            "ocr_confidence"
        )

        invoice.field_confidence_json = state.get(
            "confidence"
        )

        line_items = _get_value(
            extraction,
            "line_items",
            [],
        ) or []

        invoice.line_items_json = [
            _model_dump(item)
            if not isinstance(item, dict)
            else item
            for item in line_items
        ]

        invoice.warnings_json = (
            _get_value(
                extraction,
                "warnings",
                [],
            )
            or []
        )

        invoice.raw_extraction_json = (
            extraction_payload
        )

        self.session.flush()
        return invoice

    def replace_validation(
        self,
        document: Document,
        invoice: Invoice,
        issues: list,
        validation_run: int,
    ) -> None:
        self.session.execute(
            delete(ValidationIssue).where(
                ValidationIssue.document_id
                == document.id,
                ValidationIssue.validation_run
                == validation_run,
            )
        )

        for issue in issues:
            issue_data = (
                issue
                if isinstance(issue, dict)
                else _model_dump(issue)
            )

            observed = issue_data.get("observed")
            expected = issue_data.get("expected")

            self.session.add(
                ValidationIssue(
                    document_id=document.id,
                    invoice_id=invoice.id,
                    validation_run=validation_run,
                    field_name=issue_data.get("field"),
                    code=issue_data.get(
                        "code",
                        "unknown",
                    ),
                    severity=issue_data.get(
                        "severity",
                        "warning",
                    ),
                    message=issue_data.get("message"),
                    observed_value=(
                        str(observed)
                        if observed is not None
                        else None
                    ),
                    expected_value=(
                        str(expected)
                        if expected is not None
                        else None
                    ),
                    resolved=bool(
                        issue_data.get(
                            "resolved",
                            False,
                        )
                    ),
                    details_json=issue_data,
                )
            )

    def add_correction_history(
        self,
        document: Document,
        invoice: Invoice | None,
        history: Any,
        attempt_number: int,
        model_used: str | None,
    ) -> None:
        history_data = (
            history
            if isinstance(history, dict)
            else _model_dump(history)
        )

        self.session.add(
            CorrectionHistory(
                document_id=document.id,
                invoice_id=(
                    invoice.id
                    if invoice
                    else None
                ),
                attempt_number=attempt_number,
                requested_fields_json=history_data.get(
                    "requested_fields",
                    [],
                ),
                changed_fields_json=history_data.get(
                    "changed_fields",
                    [],
                ),
                unauthorized_changes_json=history_data.get(
                    "unauthorized_changes"
                ),
                guardrail_passed=bool(
                    history_data.get(
                        "guardrail_passed",
                        True,
                    )
                ),
                accepted=bool(
                    history_data.get(
                        "accepted",
                        False,
                    )
                ),
                reason=history_data.get("reason"),
                model_used=model_used,
            )
        )

    def add_rag(
        self,
        document: Document,
        invoice: Invoice,
        decision: Any,
        knowledge_base_version: str,
        query_text: str = "",
    ) -> RAGEvidence:
        candidates = (
            getattr(decision, "candidates", None)
            or []
        )

        evidence = RAGEvidence(
            document_id=document.id,
            invoice_id=invoice.id,
            status=str(decision.status),
            query_text=query_text,
            matched_vendor_id=getattr(
                decision,
                "matched_vendor_id",
                None,
            ),
            matched_legal_name=getattr(
                decision,
                "matched_legal_name",
                None,
            ),
            top_distance=(
                candidates[0].distance
                if candidates
                else None
            ),
            exact_checks_json=getattr(
                decision,
                "exact_checks",
                None,
            ),
            issues_json=getattr(
                decision,
                "issues",
                None,
            ),
            recommended_action=getattr(
                decision,
                "recommended_action",
                None,
            ),
            knowledge_base_version=(
                knowledge_base_version
            ),
        )

        self.session.add(evidence)
        self.session.flush()

        for rank, candidate in enumerate(
            candidates,
            start=1,
        ):
            self.session.add(
                RAGCandidate(
                    rag_evidence_id=evidence.id,
                    rank=rank,
                    vendor_id=str(
                        candidate.vendor_id
                    ),
                    legal_name=str(
                        candidate.legal_name
                    ),
                    distance=candidate.distance,
                    metadata_json=(
                        candidate.metadata
                    ),
                )
            )

        return evidence

    def add_safety(
        self,
        document: Document,
        stage: str,
        result: Any,
        model_used: str | None,
    ) -> None:
        self.session.add(
            SafetyDecision(
                document_id=document.id,
                stage=stage,
                label=str(result.label),
                attack_type=getattr(
                    result,
                    "attack_type",
                    None,
                ),
                risk_score=result.risk_score,
                expected_action=str(
                    result.expected_action
                ),
                reasons_json=list(
                    getattr(
                        result,
                        "reasons",
                        [],
                    )
                    or []
                ),
                model_used=model_used,
            )
        )

    def add_audit(
        self,
        document: Document,
        event_type: str,
        node_name: str | None,
        payload: dict,
        sequence_number: int,
    ) -> None:
        self.session.add(
            AuditEvent(
                document_id=document.id,
                sequence_number=sequence_number,
                event_type=event_type,
                node_name=node_name,
                payload_json=payload,
            )
        )
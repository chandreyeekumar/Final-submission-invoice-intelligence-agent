from __future__ import annotations

from hashlib import sha256
from typing import Any

import chromadb
from sqlalchemy import desc, select

from app.core.config import get_settings
from app.core.embeddings import (
    HashEmbeddingFunction,
)
from app.db.base import DocumentStatus
from app.db.models import (
    Document,
    Invoice,
    RAGEvidence,
    SafetyDecision,
    ValidationIssue,
)


def _enum_or_text(value: Any) -> str:
    raw = getattr(
        value,
        "value",
        value,
    )

    return str(
        raw or ""
    ).strip().lower()


def amount_band(value) -> str:
    if value is None:
        return "unknown"

    amount = float(value)

    if amount < 1_000:
        return "under_1000"

    if amount < 10_000:
        return "1000_to_9999"

    if amount < 100_000:
        return "10000_to_99999"

    return "100000_plus"


def _approved_vendor_id(
    session,
    document_id: str,
) -> str | None:
    evidence = session.scalar(
        select(RAGEvidence)
        .where(
            RAGEvidence.document_id
            == document_id,
            RAGEvidence.status
            == "verified",
        )
        .order_by(
            desc(
                RAGEvidence.created_at
            )
        )
    )

    if (
        not evidence
        or not getattr(
            evidence,
            "matched_vendor_id",
            None,
        )
    ):
        return None

    return str(
        evidence.matched_vendor_id
    )


def _safety_outcome(
    item: Any,
) -> str:
    """Read the safety result from common field names.

    Update this helper after Volume 4 finalizes the
    SafetyDecision database model.
    """

    for field in (
        "decision",
        "action",
        "status",
        "expected_action",
    ):
        value = getattr(
            item,
            field,
            None,
        )

        if value is not None:
            return _enum_or_text(
                value
            )

    return ""


def _all_safety_stages_passed(
    session,
    document_id: str,
) -> bool:
    decisions = list(
        session.scalars(
            select(
                SafetyDecision
            ).where(
                SafetyDecision.document_id
                == document_id
            )
        )
    )

    if not decisions:
        return False

    allowed_values = {
        "allow",
        "allowed",
        "pass",
        "passed",
        "safe",
    }

    return all(
        _safety_outcome(item)
        in allowed_values
        for item in decisions
    )


def sync_approved_invoice(
    session,
    document_id: str,
) -> bool:
    document = session.get(
        Document,
        document_id,
    )

    if not document:
        return False

    if (
        _enum_or_text(
            document.status
        )
        != _enum_or_text(
            DocumentStatus.COMPLETED
        )
    ):
        return False

    if bool(
        getattr(
            document,
            "human_review_required",
            False,
        )
    ):
        return False

    unresolved_high = list(
        session.scalars(
            select(
                ValidationIssue
            ).where(
                ValidationIssue.document_id
                == document_id,
                ValidationIssue.severity
                == "high",
                ValidationIssue.resolved
                .is_(False),
            )
        )
    )

    if unresolved_high:
        return False

    if not _all_safety_stages_passed(
        session,
        document_id,
    ):
        return False

    invoice = session.scalar(
        select(
            Invoice
        ).where(
            Invoice.document_id
            == document_id
        )
    )

    vendor_id = _approved_vendor_id(
        session,
        document_id,
    )

    if (
        not invoice
        or not getattr(
            invoice,
            "vendor_name",
            None,
        )
        or not vendor_id
    ):
        return False

    settings = get_settings()

    embedding_function = (
        HashEmbeddingFunction(
            dimensions=int(
                getattr(
                    settings,
                    "rag_embedding_dimensions",
                    384,
                )
            )
        )
    )

    client = chromadb.PersistentClient(
        path=settings.chroma_path
    )

    try:
        history = client.get_collection(
            name=(
                settings
                .chroma_history_collection
            ),
            embedding_function=(
                embedding_function
            ),
        )

    except Exception as exc:
        raise RuntimeError(
            "Approved-history collection is missing. "
            "Run python scripts/seed_chroma.py "
            "before synchronization."
        ) from exc

    invoice_prefix = str(
        getattr(
            invoice,
            "invoice_number",
            None,
        )
        or ""
    )[:5]

    currency = str(
        getattr(
            invoice,
            "currency",
            None,
        )
        or "unknown"
    )

    total = getattr(
        invoice,
        "total",
        None,
    )

    summary = (
        f"Approved invoice for vendor "
        f"{invoice.vendor_name}. "
        f"Currency {currency}. "
        f"Amount band "
        f"{amount_band(total)}. "
        f"Invoice prefix "
        f"{invoice_prefix}."
    )

    source_hash = sha256(
        summary.encode("utf-8")
    ).hexdigest()

    history.upsert(
        ids=[
            f"HIST-{invoice.id}"
        ],
        documents=[
            summary
        ],
        metadatas=[
            {
                "vendor_id": vendor_id,
                "invoice_id": str(
                    invoice.id
                ),
                "document_id": str(
                    document_id
                ),
                "currency": (
                    ""
                    if currency
                    == "unknown"
                    else currency
                ),
                "amount_band": (
                    amount_band(total)
                ),
                "kb_version": str(
                    settings
                    .rag_knowledge_base_version
                ),
                "schema_version": "1",
                "source_hash": (
                    source_hash
                ),
                "approval_status": (
                    "system_validated"
                ),
            }
        ],
    )

    return True
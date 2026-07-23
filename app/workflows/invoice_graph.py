from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.complexity_router import route_complexity
from app.agents.confidence import compute_confidence
from app.agents.correction import correct_failed_fields
from app.agents.extraction import extract_invoice
from app.agents.ingestion import validate_upload
from app.agents.ocr import run_ocr
from app.agents.preprocessing import preprocess_document
from app.agents.rag import VendorRAG
from app.agents.safety import (
    assess_input_safety,
    assess_output_safety,
)
from app.agents.validation import validate_invoice
from app.core.config import get_settings
from app.db.base import DocumentStatus
from app.db.models import Document
from app.db.repositories.repository import Repository
from app.db.repositories.unit_of_work import UnitOfWork
from app.schemas.workflow import WorkflowState


def _model_dump(value: Any) -> Any:
    """Convert Pydantic objects to JSON-safe dictionaries."""

    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")

    return value


def audit(
    state: WorkflowState,
    event: str,
    payload: dict | None = None,
) -> list[dict]:
    """Append one audit event without modifying the original list."""

    existing_events = list(
        state.get("audit_events", [])
    )

    existing_events.append(
        {
            "event": event,
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "payload": payload or {},
        }
    )

    return existing_events


def upload_guard(
    state: WorkflowState,
) -> dict:
    """Validate the uploaded file and create its Document row."""

    upload_information = validate_upload(
        state["document_path"]
    )

    with UnitOfWork() as unit_of_work:
        repository = Repository(
            unit_of_work.session
        )

        document = repository.create_document(
            request_id=state["request_id"],
            filename=state["original_filename"],
            path=state["document_path"],
            info=upload_information,
        )

        document_id = document.id

    return {
        "document_id": document_id,
        "upload_metadata": upload_information,
        "audit_events": audit(
            state,
            "upload_guard_passed",
            upload_information,
        ),
    }


def preprocess_node(
    state: WorkflowState,
) -> dict:
    """Convert the source document into preprocessed page images."""

    output_directory = (
        Path("data/runtime")
        / state["request_id"]
        / "pages"
    )

    page_images, preprocessing_metadata = (
        preprocess_document(
            state["document_path"],
            str(output_directory),
        )
    )

    return {
        "page_images": page_images,
        "preprocessing_metadata": (
            preprocessing_metadata
        ),
        "audit_events": audit(
            state,
            "preprocessed",
            {
                "pages": len(page_images),
            },
        ),
    }


def ocr_node(
    state: WorkflowState,
) -> dict:
    """Run OCR over all preprocessed page images."""

    (
        ocr_pages,
        ocr_text,
        word_count,
        ocr_confidence,
    ) = run_ocr(
        state["page_images"]
    )

    return {
        "ocr_pages": ocr_pages,
        "ocr_text": ocr_text,
        "ocr_word_count": word_count,
        "ocr_confidence": ocr_confidence,
        "audit_events": audit(
            state,
            "ocr_completed",
            {
                "words": word_count,
                "confidence": ocr_confidence,
            },
        ),
    }


async def input_safety_node(
    state: WorkflowState,
) -> dict:
    """Assess uploaded images and OCR text for unsafe input."""

    result = await assess_input_safety(
        state["page_images"],
        state["ocr_text"],
    )

    return {
        "input_safety": result,
        "audit_events": audit(
            state,
            "input_safety",
            _model_dump(result),
        ),
    }


def after_input_safety(
    state: WorkflowState,
) -> str:
    """Route blocked input directly to terminal persistence."""

    expected_action = str(
        state["input_safety"].expected_action
    ).lower()

    if expected_action == "block":
        return "blocked"

    return "route"


def route_node(
    state: WorkflowState,
) -> dict:
    """Choose invoice complexity tier and extraction model."""

    complexity_tier = route_complexity(
        len(state["page_images"]),
        state["ocr_word_count"],
        state["ocr_confidence"],
    )

    model_name = get_settings().model_for_complexity(
        complexity_tier
    )

    return {
        "complexity_tier": complexity_tier,
        "model_used": model_name,
        "audit_events": audit(
            state,
            "complexity_routed",
            {
                "tier": complexity_tier,
                "model": model_name,
            },
        ),
    }


async def extraction_node(
    state: WorkflowState,
) -> dict:
    """Extract structured invoice fields."""

    extracted_invoice = await extract_invoice(
        state["page_images"],
        state["ocr_text"],
        state["complexity_tier"],
    )

    return {
        "extraction": extracted_invoice,
        "extraction_attempts": (
            state.get(
                "extraction_attempts",
                0,
            )
            + 1
        ),
        "audit_events": audit(
            state,
            "extracted",
            {
                "attempt": (
                    state.get(
                        "extraction_attempts",
                        0,
                    )
                    + 1
                ),
            },
        ),
    }


def validation_node(
    state: WorkflowState,
) -> dict:
    """Apply deterministic invoice validation rules."""

    validation_issues = validate_invoice(
        state["extraction"]
    )

    serializable_issues = [
        _model_dump(issue)
        for issue in validation_issues
    ]

    return {
        "validation_issues": validation_issues,
        "audit_events": audit(
            state,
            "validated",
            {
                "issue_count": len(
                    validation_issues
                ),
                "issues": serializable_issues,
            },
        ),
    }


def rag_node(
    state: WorkflowState,
) -> dict:
    """Run governed vendor verification and confidence scoring."""

    rag_decision = VendorRAG().query(
        state["extraction"]
    )

    confidence = compute_confidence(
        state["extraction"],
        state["ocr_confidence"],
        state["validation_issues"],
        rag_decision.status,
    )

    return {
        "rag": rag_decision,
        "confidence": confidence,
        "audit_events": audit(
            state,
            "rag_completed",
            _model_dump(rag_decision),
        ),
    }


def after_rag(
    state: WorkflowState,
) -> str:
    """Choose correction, human review, or output safety."""

    rag_status = str(
        state["rag"].status
    ).lower()

    if rag_status in {
        "mismatch",
        "ambiguous",
        "unknown",
        "not_applicable",
    }:
        return "review"

    validation_issues = state.get(
        "validation_issues",
        [],
    )

    correction_attempts = int(
        state.get(
            "correction_attempts",
            0,
        )
    )

    maximum_attempts = int(
        get_settings().max_correction_attempts
    )

    if (
        validation_issues
        and correction_attempts
        < maximum_attempts
    ):
        return "correct"

    if validation_issues:
        return "review"

    return "output"


async def correction_node(
    state: WorkflowState,
) -> dict:
    """Correct only fields that failed validation."""

    corrected_invoice, correction_history = (
        await correct_failed_fields(
            state["page_images"],
            state["extraction"],
            state["validation_issues"],
        )
    )

    new_attempt_number = (
        state.get(
            "correction_attempts",
            0,
        )
        + 1
    )

    existing_history = list(
        state.get(
            "correction_history",
            [],
        )
    )

    existing_history.append(
        correction_history
    )

    return {
        "extraction": corrected_invoice,
        "correction_attempts": (
            new_attempt_number
        ),
        "correction_history": (
            existing_history
        ),
        "audit_events": audit(
            state,
            "corrected",
            {
                "attempt": new_attempt_number,
                "history": _model_dump(
                    correction_history
                ),
            },
        ),
    }


def review_node(
    state: WorkflowState,
) -> dict:
    """Mark the invoice for human review."""

    return {
        "final_status": "human_review",
        "audit_events": audit(
            state,
            "human_review_required",
        ),
    }


def blocked_node(
    state: WorkflowState,
) -> dict:
    """Mark the workflow as blocked by input safety."""

    return {
        "final_status": "safety_blocked",
        "audit_events": audit(
            state,
            "blocked_by_input_safety",
        ),
    }


def output_safety_node(
    state: WorkflowState,
) -> dict:
    """Assess the extracted output before completion."""

    extraction_payload = _model_dump(
        state["extraction"]
    )

    result = assess_output_safety(
        extraction_payload
    )

    expected_action = str(
        result.expected_action
    ).lower()

    final_status = (
        "safety_blocked"
        if expected_action == "block"
        else "completed"
    )

    return {
        "output_safety": result,
        "final_status": final_status,
        "audit_events": audit(
            state,
            "output_safety",
            _model_dump(result),
        ),
    }


def persist_node(
    state: WorkflowState,
) -> dict:
    """Persist all evidence and the final workflow status."""

    with UnitOfWork() as unit_of_work:
        repository = Repository(
            unit_of_work.session
        )

        document = unit_of_work.session.get(
            Document,
            state["document_id"],
        )

        if document is None:
            raise RuntimeError(
                "Document row was not found "
                "during workflow persistence"
            )

        input_safety = state.get(
            "input_safety"
        )

        if input_safety is not None:
            repository.add_safety(
                document=document,
                stage="input",
                result=input_safety,
                model_used=get_settings()
                .openai_model_safety,
            )

        invoice = None

        if state.get("extraction") is not None:
            invoice = repository.upsert_invoice(
                document=document,
                state=state,
            )

        if invoice is not None:
            validation_run = (
                int(
                    state.get(
                        "correction_attempts",
                        0,
                    )
                )
                + 1
            )

            repository.replace_validation(
                document=document,
                invoice=invoice,
                issues=state.get(
                    "validation_issues",
                    [],
                ),
                validation_run=validation_run,
            )

        if (
            invoice is not None
            and state.get(
                "correction_history"
            )
        ):
            for (
                attempt_number,
                history,
            ) in enumerate(
                state["correction_history"],
                start=1,
            ):
                repository.add_correction_history(
                    document=document,
                    invoice=invoice,
                    history=history,
                    attempt_number=(
                        attempt_number
                    ),
                    model_used=state.get(
                        "model_used"
                    ),
                )

        rag_decision = state.get("rag")

        if (
            invoice is not None
            and rag_decision is not None
        ):
            repository.add_rag(
                document=document,
                invoice=invoice,
                decision=rag_decision,
                knowledge_base_version=(
                    get_settings()
                    .rag_knowledge_base_version
                ),
            )

        output_safety = state.get(
            "output_safety"
        )

        if output_safety is not None:
            repository.add_safety(
                document=document,
                stage="output",
                result=output_safety,
                model_used="deterministic",
            )

        for sequence_number, event in enumerate(
            state.get(
                "audit_events",
                [],
            ),
            start=1,
        ):
            repository.add_audit(
                document=document,
                event_type=str(
                    event["event"]
                ),
                node_name=str(
                    event["event"]
                ),
                payload=event.get(
                    "payload",
                    {},
                ),
                sequence_number=(
                    sequence_number
                ),
            )

        final_status = str(
            state.get(
                "final_status",
                "failed",
            )
        ).lower()

        status_mapping = {
            "completed": (
                DocumentStatus.COMPLETED
            ),
            "human_review": (
                DocumentStatus.HUMAN_REVIEW
            ),
            "safety_blocked": (
                DocumentStatus.SAFETY_BLOCKED
            ),
            "failed": (
                DocumentStatus.FAILED
            ),
        }

        database_status = status_mapping.get(
            final_status,
            DocumentStatus.FAILED,
        )

        repository.set_status(
            document=document,
            new_status=database_status,
            reason=final_status,
        )

    return {
        "audit_events": audit(
            state,
            "persisted",
            {
                "final_status": state.get(
                    "final_status",
                    "failed",
                )
            },
        )
    }
def build_graph():
    """Build and compile the complete invoice workflow.

    Node identifiers deliberately differ from WorkflowState field names.
    LangGraph does not allow a node name to duplicate a state key.
    """

    workflow = StateGraph(WorkflowState)

    workflow.add_node(
        "upload_guard_step",
        upload_guard,
    )

    workflow.add_node(
        "preprocess_step",
        preprocess_node,
    )

    workflow.add_node(
        "ocr_step",
        ocr_node,
    )

    workflow.add_node(
        "input_safety_step",
        input_safety_node,
    )

    workflow.add_node(
        "complexity_route_step",
        route_node,
    )

    workflow.add_node(
        "extraction_step",
        extraction_node,
    )

    workflow.add_node(
        "validation_step",
        validation_node,
    )

    workflow.add_node(
        "rag_verification_step",
        rag_node,
    )

    workflow.add_node(
        "correction_step",
        correction_node,
    )

    workflow.add_node(
        "human_review_step",
        review_node,
    )

    workflow.add_node(
        "safety_blocked_step",
        blocked_node,
    )

    workflow.add_node(
        "output_safety_step",
        output_safety_node,
    )

    workflow.add_node(
        "persistence_step",
        persist_node,
    )

    workflow.add_edge(
        START,
        "upload_guard_step",
    )

    workflow.add_edge(
        "upload_guard_step",
        "preprocess_step",
    )

    workflow.add_edge(
        "preprocess_step",
        "ocr_step",
    )

    workflow.add_edge(
        "ocr_step",
        "input_safety_step",
    )

    workflow.add_conditional_edges(
        "input_safety_step",
        after_input_safety,
        {
            "blocked": "safety_blocked_step",
            "route": "complexity_route_step",
        },
    )

    workflow.add_edge(
        "complexity_route_step",
        "extraction_step",
    )

    workflow.add_edge(
        "extraction_step",
        "validation_step",
    )

    workflow.add_edge(
        "validation_step",
        "rag_verification_step",
    )

    workflow.add_conditional_edges(
        "rag_verification_step",
        after_rag,
        {
            "correct": "correction_step",
            "review": "human_review_step",
            "output": "output_safety_step",
        },
    )

    workflow.add_edge(
        "correction_step",
        "validation_step",
    )

    workflow.add_edge(
        "human_review_step",
        "persistence_step",
    )

    workflow.add_edge(
        "safety_blocked_step",
        "persistence_step",
    )

    workflow.add_edge(
        "output_safety_step",
        "persistence_step",
    )

    workflow.add_edge(
        "persistence_step",
        END,
    )

    return workflow.compile()


graph = build_graph()


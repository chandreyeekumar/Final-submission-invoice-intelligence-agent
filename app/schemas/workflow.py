from __future__ import annotations

from typing import NotRequired, TypedDict

from app.schemas.invoice import InvoiceExtraction
from app.schemas.rag import RAGDecision
from app.schemas.safety import SafetyAssessment


class WorkflowState(TypedDict):
    request_id: str
    original_filename: str
    document_path: str
    document_id: str
    upload_metadata: NotRequired[dict]
    page_images: list[str]
    preprocessing_metadata: list[dict]
    ocr_pages: list[dict]
    ocr_text: str
    ocr_word_count: int
    ocr_confidence: float
    complexity_tier: str
    model_used: str
    extraction_attempts: int
    extraction: NotRequired[InvoiceExtraction]
    validation_issues: list[dict]
    confidence: dict[str, float]
    rag: NotRequired[RAGDecision]
    correction_attempts: int
    correction_history: list[dict]
    input_safety: NotRequired[SafetyAssessment]
    output_safety: NotRequired[SafetyAssessment]
    audit_events: list[dict]
    final_status: str

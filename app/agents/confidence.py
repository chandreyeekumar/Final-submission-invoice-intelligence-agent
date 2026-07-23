from __future__ import annotations

from app.schemas.invoice import InvoiceExtraction


FIELDS = [
    "vendor_name",
    "invoice_number",
    "invoice_date",
    "subtotal",
    "tax_total",
    "total",
    "amount_due",
]


def compute_confidence(
    invoice: InvoiceExtraction,
    ocr_confidence: float,
    issues: list[dict],
    rag_status: str,
) -> dict[str, float]:
    issue_fields = {issue.get("field") for issue in issues}
    bounded_ocr = min(max(ocr_confidence, 0.0), 1.0)
    scores: dict[str, float] = {}

    for field in FIELDS:
        score = 0.20 if getattr(invoice, field, None) is None else 0.65
        score += bounded_ocr * 0.15
        if field not in issue_fields:
            score += 0.15
        if field == "vendor_name" and rag_status == "verified":
            score += 0.10
        if field == "vendor_name" and rag_status in {
            "unknown",
            "mismatch",
            "ambiguous",
        }:
            score -= 0.20
        scores[field] = round(max(0.0, min(score, 1.0)), 3)

    return scores

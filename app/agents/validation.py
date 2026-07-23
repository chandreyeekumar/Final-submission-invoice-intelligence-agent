from __future__ import annotations

from decimal import Decimal

from app.schemas.invoice import InvoiceExtraction


TOLERANCE = Decimal("0.02")


def _close(first: Decimal | None, second: Decimal | None) -> bool:
    return (
        first is not None
        and second is not None
        and abs(first - second) <= TOLERANCE
    )


def _issue(
    field: str,
    code: str,
    severity: str,
    message: str,
    observed: object | None = None,
    expected: object | None = None,
) -> dict:
    return {
        "field": field,
        "code": code,
        "severity": severity,
        "message": message,
        "observed": None if observed is None else str(observed),
        "expected": None if expected is None else str(expected),
    }


def validate_invoice(invoice: InvoiceExtraction) -> list[dict]:
    issues: list[dict] = []

    if not invoice.vendor_name:
        issues.append(
            _issue("vendor_name", "missing_vendor", "high", "Vendor name is missing")
        )

    if not invoice.invoice_number:
        issues.append(
            _issue(
                "invoice_number",
                "missing_invoice_number",
                "medium",
                "Invoice number is missing",
            )
        )

    if (
        invoice.invoice_date
        and invoice.due_date
        and invoice.due_date < invoice.invoice_date
    ):
        issues.append(
            _issue(
                "due_date",
                "due_date_before_invoice_date",
                "high",
                "Due date precedes invoice date",
                invoice.due_date,
                f">= {invoice.invoice_date}",
            )
        )

    for index, item in enumerate(invoice.line_items):
        if (
            item.quantity is not None
            and item.unit_price is not None
            and item.line_total is not None
        ):
            expected_line_total = item.quantity * item.unit_price
            if not _close(expected_line_total, item.line_total):
                issues.append(
                    _issue(
                        f"line_items[{index}].line_total",
                        "quantity_times_unit_price_mismatch",
                        "high",
                        "Quantity multiplied by unit price does not equal line total",
                        item.line_total,
                        expected_line_total,
                    )
                )

    calculated_line_sum = sum(
        (item.line_total or Decimal("0")) for item in invoice.line_items
    )
    if (
        invoice.line_items
        and invoice.subtotal is not None
        and not _close(calculated_line_sum, invoice.subtotal)
    ):
        issues.append(
            _issue(
                "subtotal",
                "line_items_do_not_equal_subtotal",
                "high",
                "Line-item totals do not equal subtotal",
                calculated_line_sum,
                invoice.subtotal,
            )
        )

    if invoice.subtotal is not None and invoice.total is not None:
        calculated_total = (
            invoice.subtotal
            - invoice.discount
            + invoice.shipping
            + (invoice.tax_total or Decimal("0"))
            - invoice.credit_adjustment
        )
        if not _close(calculated_total, invoice.total):
            issues.append(
                _issue(
                    "total",
                    "components_do_not_equal_total",
                    "high",
                    "Invoice components do not equal total",
                    invoice.total,
                    calculated_total,
                )
            )

    if invoice.total is not None and invoice.amount_due is not None:
        calculated_due = (
            invoice.total + invoice.previous_balance - invoice.credit_adjustment
        )
        if not _close(calculated_due, invoice.amount_due):
            issues.append(
                _issue(
                    "amount_due",
                    "amount_due_mismatch",
                    "high",
                    "Amount due does not reconcile",
                    invoice.amount_due,
                    calculated_due,
                )
            )

    return issues

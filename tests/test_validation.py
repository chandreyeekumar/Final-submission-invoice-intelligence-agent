from datetime import date
from decimal import Decimal

from app.agents.validation import validate_invoice
from app.schemas.invoice import InvoiceExtraction, LineItem


def codes(invoice):
    return {issue["code"] for issue in validate_invoice(invoice)}


def base_invoice(**overrides):
    payload = dict(
        vendor_name="Vendor A",
        invoice_number="INV-1",
        invoice_date=date(2026, 1, 1),
        due_date=date(2026, 1, 31),
        subtotal=Decimal("100"),
        tax_total=Decimal("18"),
        total=Decimal("118"),
        amount_due=Decimal("118"),
        line_items=[
            LineItem(
                description="Item",
                quantity=Decimal("1"),
                unit_price=Decimal("100"),
                line_total=Decimal("100"),
            )
        ],
    )
    payload.update(overrides)
    return InvoiceExtraction(**payload)


def test_happy_path_has_no_issues():
    assert validate_invoice(base_invoice()) == []


def test_missing_vendor():
    assert "missing_vendor" in codes(base_invoice(vendor_name=None))


def test_missing_invoice_number():
    assert "missing_invoice_number" in codes(base_invoice(invoice_number=None))


def test_due_date_before_invoice_date():
    assert "due_date_before_invoice_date" in codes(
        base_invoice(due_date=date(2025, 12, 31))
    )


def test_line_items_mismatch():
    assert "line_items_do_not_equal_subtotal" in codes(
        base_invoice(subtotal=Decimal("99"))
    )


def test_quantity_times_unit_price_mismatch():
    bad_item = LineItem(
        description="Item",
        quantity=Decimal("2"),
        unit_price=Decimal("50"),
        line_total=Decimal("90"),
    )
    assert "quantity_times_unit_price_mismatch" in codes(
        base_invoice(line_items=[bad_item], subtotal=Decimal("90"))
    )


def test_total_mismatch():
    assert "components_do_not_equal_total" in codes(
        base_invoice(total=Decimal("117"), amount_due=Decimal("117"))
    )


def test_amount_due_mismatch():
    assert "amount_due_mismatch" in codes(base_invoice(amount_due=Decimal("119")))

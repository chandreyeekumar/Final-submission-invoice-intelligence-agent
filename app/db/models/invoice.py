from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import (
    Base,
    JSONType,
    TimestampMixin,
)


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"

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
        unique=True,
        index=True,
        nullable=False,
    )

    vendor_name: Mapped[str | None] = mapped_column(
        String(255),
        index=True,
    )

    vendor_address: Mapped[str | None] = mapped_column(
        Text
    )

    vendor_tax_id: Mapped[str | None] = mapped_column(
        String(100),
        index=True,
    )

    vendor_bank_account_masked: Mapped[
        str | None
    ] = mapped_column(
        String(100)
    )

    invoice_number: Mapped[str | None] = mapped_column(
        String(120),
        index=True,
    )

    invoice_date: Mapped[date | None] = mapped_column(
        Date
    )

    due_date: Mapped[date | None] = mapped_column(
        Date
    )

    purchase_order_number: Mapped[
        str | None
    ] = mapped_column(
        String(120)
    )

    currency: Mapped[str | None] = mapped_column(
        String(8)
    )

    subtotal: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2)
    )

    discount: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2)
    )

    shipping: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2)
    )

    tax_total: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2)
    )

    previous_balance: Mapped[
        Decimal | None
    ] = mapped_column(
        Numeric(18, 2)
    )

    credit_adjustment: Mapped[
        Decimal | None
    ] = mapped_column(
        Numeric(18, 2)
    )

    total: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2)
    )

    amount_due: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2)
    )

    complexity_tier: Mapped[
        str | None
    ] = mapped_column(
        String(20)
    )

    model_used: Mapped[str | None] = mapped_column(
        String(100)
    )

    extraction_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    overall_ocr_confidence: Mapped[
        Decimal | None
    ] = mapped_column(
        Numeric(6, 5)
    )

    field_confidence_json: Mapped[
        dict | None
    ] = mapped_column(
        JSONType
    )

    line_items_json: Mapped[
        list | None
    ] = mapped_column(
        JSONType
    )

    warnings_json: Mapped[
        list | None
    ] = mapped_column(
        JSONType
    )

    raw_extraction_json: Mapped[dict] = mapped_column(
        JSONType,
        default=dict,
        nullable=False,
    )
from __future__ import annotations

from datetime import date
from decimal import Decimal
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    tax_rate: Decimal | None = None
    line_total: Decimal | None = None

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("quantity", "unit_price", "tax_rate", "line_total")
    @classmethod
    def finite_decimal(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and not value.is_finite():
            raise ValueError("Decimal values must be finite")
        return value


class InvoiceExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    vendor_name: str | None = Field(default=None, max_length=255)
    vendor_address: str | None = Field(default=None, max_length=1000)
    vendor_tax_id: str | None = Field(default=None, max_length=100)
    vendor_bank_account: str | None = Field(default=None, max_length=100)
    invoice_number: str | None = Field(default=None, max_length=120)
    invoice_date: date | None = None
    due_date: date | None = None
    purchase_order_number: str | None = Field(default=None, max_length=120)
    currency: str | None = Field(default=None, max_length=3)
    subtotal: Decimal | None = None
    discount: Decimal = Decimal("0")
    shipping: Decimal = Decimal("0")
    tax_total: Decimal | None = None
    previous_balance: Decimal = Decimal("0")
    credit_adjustment: Decimal = Decimal("0")
    total: Decimal | None = None
    amount_due: Decimal | None = None
    line_items: list[LineItem] = Field(default_factory=list, max_length=500)
    warnings: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("currency")
    @classmethod
    def currency_upper(cls, value: str | None) -> str | None:
        if not value:
            return None
        value = value.upper().strip()
        if not re.fullmatch(r"[A-Z]{3}", value):
            raise ValueError("currency must be a three-letter ISO-style code")
        return value

    @field_validator(
        "subtotal",
        "discount",
        "shipping",
        "tax_total",
        "previous_balance",
        "credit_adjustment",
        "total",
        "amount_due",
    )
    @classmethod
    def finite_money(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and not value.is_finite():
            raise ValueError("Money values must be finite")
        return value

    @field_validator("warnings")
    @classmethod
    def clean_warnings(cls, values: list[str]) -> list[str]:
        return [" ".join(v.split())[:500] for v in values if v and v.strip()]

    @model_validator(mode="after")
    def mask_bank_account(self) -> "InvoiceExtraction":
        if self.vendor_bank_account:
            digits = re.sub(r"\D", "", self.vendor_bank_account)
            self.vendor_bank_account = f"XXXX{digits[-4:]}" if digits else "MASKED"
        return self

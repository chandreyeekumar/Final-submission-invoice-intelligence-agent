from __future__ import annotations

import json
from pathlib import Path


INPUT = Path("data/vendor_master/vendors.json")
OUTPUT = Path("data/vendor_templates/templates.json")


LAYOUTS = [
    "Vendor top-left, invoice number top-right, totals bottom-right.",
    "Centered vendor header, line-item table in the middle.",
    "Logo top-left, purchase-order details top-right.",
]


LABELS = [
    {
        "invoice_number": ["Invoice No", "Bill No"],
        "subtotal": ["Subtotal", "Taxable Value"],
        "tax_total": ["Tax", "GST Amount"],
        "total": ["Total", "Net Payable"],
    },
    {
        "invoice_number": ["Document No"],
        "subtotal": ["Net Amount"],
        "tax_total": ["Tax Amount"],
        "total": ["Amount Due"],
    },
]


REQUIRED_VENDOR_FIELDS = {
    "vendor_id",
    "legal_name",
    "invoice_prefix",
    "currency",
    "payment_terms",
}


def _validate_vendor(vendor: dict, index: int) -> None:
    missing = sorted(REQUIRED_VENDOR_FIELDS - set(vendor))

    if missing:
        raise ValueError(
            f"Vendor record {index} is missing required fields: {missing}"
        )


def main() -> None:
    if not INPUT.exists():
        raise FileNotFoundError(
            f"Vendor master not found at {INPUT}. Run Volume 1 first."
        )

    vendors = json.loads(INPUT.read_text(encoding="utf-8"))

    if not isinstance(vendors, list) or not vendors:
        raise ValueError(
            "Vendor master must contain a non-empty JSON list"
        )

    records: list[dict] = []

    for index, vendor in enumerate(vendors):
        if not isinstance(vendor, dict):
            raise ValueError(
                f"Vendor record {index} must be a JSON object"
            )

        _validate_vendor(vendor, index)

        records.append(
            {
                "template_id": f"TPL-{vendor['vendor_id']}-01",
                "vendor_id": str(vendor["vendor_id"]),
                "legal_name": str(vendor["legal_name"]),
                "layout_description": LAYOUTS[
                    index % len(LAYOUTS)
                ],
                "expected_labels": LABELS[
                    index % len(LABELS)
                ],
                "invoice_number_pattern": (
                    f"{vendor['invoice_prefix']}-NNNNN"
                ),
                "usual_currency": str(vendor["currency"]),
                "usual_payment_terms": str(
                    vendor["payment_terms"]
                ),
                "usual_table_columns": [
                    "description",
                    "quantity",
                    "unit_price",
                    "tax",
                    "line_total",
                ],
                "active": bool(
                    vendor.get("active", True)
                ),
            }
        )

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT.write_text(
        json.dumps(
            records,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        f"Created {len(records)} vendor templates at {OUTPUT}"
    )


if __name__ == "__main__":
    main()
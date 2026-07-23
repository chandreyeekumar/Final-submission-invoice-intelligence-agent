from __future__ import annotations

from typing import Any


SROIE_FIELDS = [
    "vendor_name",
    "vendor_address",
    "invoice_date",
    "total",
]


def map_sroie_ground_truth(
    raw: dict[str, Any],
) -> dict[str, Any]:
    return {
        "vendor_name": raw.get("company"),
        "vendor_address": raw.get("address"),
        "invoice_date": raw.get("date"),
        "total": raw.get("total"),
    }
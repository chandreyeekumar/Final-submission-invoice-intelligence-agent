from __future__ import annotations

from typing import Any


CORD_FIELDS = [
    "vendor_name",
    "subtotal",
    "tax_total",
    "total",
]


def _first(
    mapping: dict[str, Any],
    *keys: str,
) -> Any:
    for key in keys:
        value = mapping.get(key)

        if value not in (None, ""):
            return value

    return None


def _flatten_valid_line(
    value: Any,
) -> dict[str, Any]:
    if isinstance(value, dict):
        return value

    if isinstance(value, list):
        merged: dict[str, Any] = {}

        for item in value:
            if isinstance(item, dict):
                merged.update(item)

        return merged

    return {}


def map_cord_ground_truth(
    raw: dict[str, Any],
) -> dict[str, Any]:
    valid = _flatten_valid_line(
        raw.get("valid_line", raw)
    )

    return {
        "vendor_name": _first(
            valid,
            "store_name",
            "merchant_name",
        ),
        "subtotal": _first(
            valid,
            "subtotal",
            "sub_total",
        ),
        "tax_total": _first(
            valid,
            "tax",
            "tax_total",
        ),
        "total": _first(
            valid,
            "total",
            "total_price",
        ),
    }
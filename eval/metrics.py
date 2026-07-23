from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from typing import Any

from dateutil import parser as date_parser


MONEY_FIELDS = {
    "subtotal",
    "tax_total",
    "total",
    "amount_due",
    "discount",
    "shipping",
    "previous_balance",
    "credit_adjustment",
    "unit_price",
    "line_total",
}


def normalize_text(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        str(value or "").lower(),
    ).strip()


def _to_decimal(value: Any) -> Decimal:
    cleaned = str(value).strip()

    cleaned = re.sub(
        r"[\s,$£€₹]",
        "",
        cleaned,
    )

    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = f"-{cleaned[1:-1]}"

    return Decimal(cleaned)


def field_equal(
    field: str,
    actual: Any,
    expected: Any,
    money_tolerance: Decimal = Decimal("0.02"),
) -> bool:
    if actual in (None, "") and expected in (None, ""):
        return True

    if actual in (None, "") or expected in (None, ""):
        return False

    normalized_field = field.lower()

    if normalized_field in MONEY_FIELDS:
        try:
            return (
                abs(
                    _to_decimal(actual)
                    - _to_decimal(expected)
                )
                <= money_tolerance
            )
        except (
            InvalidOperation,
            ValueError,
            TypeError,
        ):
            return False

    if "date" in normalized_field:
        try:
            return (
                date_parser.parse(str(actual)).date()
                == date_parser.parse(str(expected)).date()
            )
        except (
            ValueError,
            TypeError,
            OverflowError,
        ):
            return False

    return (
        normalize_text(actual)
        == normalize_text(expected)
    )


def score_fields(
    prediction: dict[str, Any],
    ground_truth: dict[str, Any],
    fields: Iterable[str],
) -> dict[str, bool]:
    return {
        field: field_equal(
            field,
            prediction.get(field),
            ground_truth.get(field),
        )
        for field in fields
        if field in ground_truth
    }


def aggregate_field_scores(
    records: Iterable[dict[str, Any]],
    key: str,
) -> dict[str, Any]:
    counters: dict[str, list[int]] = defaultdict(
        lambda: [0, 0]
    )

    for record in records:
        if record.get("status") == "failed":
            continue

        values = record.get(key, {})

        if not isinstance(values, dict):
            continue

        for field, correct in values.items():
            counters[field][0] += int(bool(correct))
            counters[field][1] += 1

    total = sum(
        count
        for _, count in counters.values()
    )

    correct = sum(
        hits
        for hits, _ in counters.values()
    )

    return {
        "field_accuracy": (
            correct / total
            if total
            else 0.0
        ),
        "correct": correct,
        "count": total,
        "by_field": {
            field: {
                "correct": hits,
                "count": count,
                "accuracy": (
                    hits / count
                    if count
                    else 0.0
                ),
            }
            for field, (
                hits,
                count,
            ) in sorted(counters.items())
        },
    }


def confusion_metrics(
    tp: int,
    fp: int,
    fn: int,
    tn: int,
) -> dict[str, float | int]:
    precision = (
        tp / (tp + fp)
        if tp + fp
        else 0.0
    )

    recall = (
        tp / (tp + fn)
        if tp + fn
        else 0.0
    )

    specificity = (
        tn / (tn + fp)
        if tn + fp
        else 0.0
    )

    total = tp + fp + fn + tn

    accuracy = (
        (tp + tn) / total
        if total
        else 0.0
    )

    f1 = (
        2 * precision * recall
        / (precision + recall)
        if precision + recall
        else 0.0
    )

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "specificity": specificity,
        "accuracy": accuracy,
        "false_positive_rate": (
            fp / (fp + tn)
            if fp + tn
            else 0.0
        ),
        "false_negative_rate": (
            fn / (fn + tp)
            if fn + tp
            else 0.0
        ),
    }


def percentile(
    values: list[float],
    q: float,
) -> float:
    if not 0.0 <= q <= 1.0:
        raise ValueError(
            "q must be between 0 and 1"
        )

    if not values:
        return 0.0

    ordered = sorted(
        float(value)
        for value in values
    )

    index = (
        len(ordered) - 1
    ) * q

    lower = math.floor(index)
    upper = math.ceil(index)

    if lower == upper:
        return ordered[lower]

    lower_weight = upper - index
    upper_weight = index - lower

    return (
        ordered[lower] * lower_weight
        + ordered[upper] * upper_weight
    )


def latency_summary(
    values: list[float],
) -> dict[str, float]:
    clean_values = [
        float(value)
        for value in values
        if value is not None
        and float(value) >= 0
    ]

    return {
        "mean": (
            sum(clean_values)
            / len(clean_values)
            if clean_values
            else 0.0
        ),
        "p50": percentile(
            clean_values,
            0.50,
        ),
        "p95": percentile(
            clean_values,
            0.95,
        ),
        "max": (
            max(clean_values)
            if clean_values
            else 0.0
        ),
    }
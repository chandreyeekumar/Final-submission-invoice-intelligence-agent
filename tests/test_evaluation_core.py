from decimal import Decimal
from pathlib import Path

import pytest

from eval.budget import (
    BudgetExceeded,
    CostBudget,
)
from eval.checkpoint import CheckpointStore
from eval.io_utils import (
    atomic_save_json,
    load_json,
)
from eval.metrics import (
    aggregate_field_scores,
    confusion_metrics,
    field_equal,
    latency_summary,
    percentile,
)


def test_money_tolerance() -> None:
    assert field_equal(
        "total",
        "100.01",
        "100.00",
    )

    assert not field_equal(
        "total",
        "100.10",
        "100.00",
    )

    assert field_equal(
        "total",
        "₹1,000.00",
        "1000",
    )


def test_custom_money_tolerance() -> None:
    assert field_equal(
        "total",
        "100.04",
        "100.00",
        money_tolerance=Decimal("0.05"),
    )


def test_date_normalization() -> None:
    assert field_equal(
        "invoice_date",
        "2026-01-02",
        "January 2, 2026",
    )


def test_text_normalization() -> None:
    assert field_equal(
        "vendor_name",
        "Acme, LLC",
        "ACME LLC",
    )


def test_aggregate_scores_ignores_failures() -> None:
    report = aggregate_field_scores(
        [
            {
                "status": "success",
                "scores": {
                    "a": True,
                    "b": False,
                },
            },
            {
                "status": "success",
                "scores": {
                    "a": True,
                    "b": True,
                },
            },
            {
                "status": "failed",
                "scores": {},
            },
        ],
        "scores",
    )

    assert (
        report["field_accuracy"]
        == 0.75
    )

    assert (
        report["by_field"]["a"]["accuracy"]
        == 1.0
    )


def test_confusion_metrics() -> None:
    report = confusion_metrics(
        tp=8,
        fp=2,
        fn=2,
        tn=8,
    )

    assert report["precision"] == 0.8
    assert report["recall"] == 0.8
    assert (
        report["false_positive_rate"]
        == 0.2
    )
    assert (
        report["false_negative_rate"]
        == 0.2
    )


def test_percentile_validation() -> None:
    assert percentile(
        [1.0, 2.0, 3.0],
        0.5,
    ) == 2.0

    with pytest.raises(ValueError):
        percentile(
            [1.0],
            1.1,
        )


def test_latency_summary() -> None:
    report = latency_summary(
        [1.0, 2.0, 3.0, 4.0]
    )

    assert report["mean"] == 2.5
    assert report["p50"] == 2.5
    assert report["p95"] > 3.0
    assert report["max"] == 4.0


def test_checkpoint_resume(
    tmp_path: Path,
) -> None:
    path = tmp_path / "run.jsonl"

    store = CheckpointStore(path)

    store.append(
        {
            "document_id": "D1",
            "status": "success",
        }
    )

    reopened = CheckpointStore(path)

    assert (
        reopened.get("D1")["status"]
        == "success"
    )

    assert reopened.records == [
        {
            "document_id": "D1",
            "status": "success",
        }
    ]

    with pytest.raises(ValueError):
        reopened.append(
            {
                "document_id": "D1",
            }
        )


def test_checkpoint_requires_document_id(
    tmp_path: Path,
) -> None:
    store = CheckpointStore(
        tmp_path / "run.jsonl"
    )

    with pytest.raises(ValueError):
        store.append(
            {
                "status": "success",
            }
        )


def test_cost_budget() -> None:
    budget = CostBudget(1.0)

    budget.register(0.4)
    budget.register(0.5)

    assert (
        budget.spent_usd
        == pytest.approx(0.9)
    )

    with pytest.raises(
        BudgetExceeded
    ):
        budget.register(0.2)

    assert (
        budget.spent_usd
        == pytest.approx(0.9)
    )


def test_atomic_json_write(
    tmp_path: Path,
) -> None:
    path = tmp_path / "report.json"

    atomic_save_json(
        path,
        {
            "status": "ok",
        },
    )

    assert load_json(path) == {
        "status": "ok",
    }
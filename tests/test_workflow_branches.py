from types import SimpleNamespace

from app.workflows.invoice_graph import (
    after_input_safety,
    after_rag,
    blocked_node,
)


def test_input_safety_block_branch() -> None:
    state = {
        "input_safety": SimpleNamespace(
            expected_action="block"
        ),
        "audit_events": [],
    }

    assert (
        after_input_safety(state)
        == "blocked"
    )

    result = blocked_node(state)

    assert (
        result["final_status"]
        == "safety_blocked"
    )


def test_unknown_vendor_routes_to_review() -> None:
    state = {
        "rag": SimpleNamespace(
            status="unknown"
        ),
        "validation_issues": [],
        "correction_attempts": 0,
    }

    assert after_rag(state) == "review"


def test_validation_issue_routes_to_correction(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.workflows.invoice_graph.get_settings",
        lambda: SimpleNamespace(
            max_correction_attempts=1
        ),
    )

    state = {
        "rag": SimpleNamespace(
            status="verified"
        ),
        "validation_issues": [
            {
                "code": "total_mismatch"
            }
        ],
        "correction_attempts": 0,
    }

    assert after_rag(state) == "correct"


def test_validation_issue_routes_to_review_after_limit(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.workflows.invoice_graph.get_settings",
        lambda: SimpleNamespace(
            max_correction_attempts=1
        ),
    )

    state = {
        "rag": SimpleNamespace(
            status="verified"
        ),
        "validation_issues": [
            {
                "code": "total_mismatch"
            }
        ],
        "correction_attempts": 1,
    }

    assert after_rag(state) == "review"
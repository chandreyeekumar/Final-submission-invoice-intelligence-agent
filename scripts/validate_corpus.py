from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


REQUIRED_COLUMNS = {
    "document_id",
    "split",
    "pdf_path",
    "extraction_gt_path",
    "safety_gt_path",
    "expected_safety_action",
    "complexity",
    "rag_expected_status",
}


def load_rows(
    path: Path,
) -> list[dict]:
    """Load manifest rows from a CSV file."""

    if not path.exists():
        raise FileNotFoundError(
            f"Manifest not found: {path}"
        )

    with path.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        return list(
            csv.DictReader(handle)
        )


def main() -> None:
    """Validate the generated synthetic corpus."""

    parser = argparse.ArgumentParser(
        description=(
            "Validate the synthetic invoice corpus."
        )
    )

    parser.add_argument(
        "--manifest",
        default="data/synthetic/manifest.csv",
    )

    parser.add_argument(
        "--expected-development",
        type=int,
        default=700,
    )

    parser.add_argument(
        "--expected-test",
        type=int,
        default=300,
    )

    args = parser.parse_args()

    rows = load_rows(
        Path(args.manifest)
    )

    expected_total = (
        args.expected_development
        + args.expected_test
    )

    if len(rows) != expected_total:
        raise AssertionError(
            f"Expected {expected_total} rows, "
            f"found {len(rows)}"
        )

    missing_columns = (
        REQUIRED_COLUMNS - set(rows[0])
        if rows
        else REQUIRED_COLUMNS
    )

    if missing_columns:
        raise AssertionError(
            "Missing manifest columns: "
            f"{sorted(missing_columns)}"
        )

    split_counts = Counter(
        row["split"]
        for row in rows
    )

    expected_splits = {
        "development": (
            args.expected_development
        ),
        "test": args.expected_test,
    }

    if split_counts != expected_splits:
        raise AssertionError(
            "Unexpected split counts: "
            f"{split_counts}"
        )

    document_ids = [
        row["document_id"]
        for row in rows
    ]

    if len(document_ids) != len(
        set(document_ids)
    ):
        raise AssertionError(
            "Duplicate document_id values found"
        )

    allowed_actions = {
        "allow",
        "block",
        "review",
    }

    allowed_complexities = {
        "low",
        "medium",
        "high",
    }

    allowed_rag_statuses = {
        "verified",
        "unknown",
        "ambiguous",
        "mismatch",
    }

    for row in rows:
        document_id = row["document_id"]

        for key in [
            "pdf_path",
            "extraction_gt_path",
            "safety_gt_path",
        ]:
            referenced_path = Path(
                row[key]
            )

            if not referenced_path.exists():
                raise AssertionError(
                    f"Missing file for "
                    f"{document_id}: "
                    f"{row[key]}"
                )

        if (
            row["expected_safety_action"]
            not in allowed_actions
        ):
            raise AssertionError(
                "Invalid safety action in "
                f"{document_id}"
            )

        if (
            row["complexity"]
            not in allowed_complexities
        ):
            raise AssertionError(
                "Invalid complexity in "
                f"{document_id}"
            )

        if (
            row["rag_expected_status"]
            not in allowed_rag_statuses
        ):
            raise AssertionError(
                "Invalid RAG status in "
                f"{document_id}"
            )

        extraction_path = Path(
            row["extraction_gt_path"]
        )

        extraction = json.loads(
            extraction_path.read_text(
                encoding="utf-8"
            )
        )

        if (
            extraction.get("total")
            != extraction.get("amount_due")
        ):
            raise AssertionError(
                "Unexpected total/amount_due "
                f"mismatch: {document_id}"
            )

    complexity_counts = Counter(
        row["complexity"]
        for row in rows
    )

    safety_action_counts = Counter(
        row["expected_safety_action"]
        for row in rows
    )

    print("Corpus validation passed")
    print(f"Rows: {len(rows)}")
    print(f"Splits: {dict(split_counts)}")
    print(
        "Complexities: "
        f"{dict(complexity_counts)}"
    )
    print(
        "Safety actions: "
        f"{dict(safety_action_counts)}"
    )


if __name__ == "__main__":
    main()
from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.agents.ocr import run_ocr
from app.agents.preprocessing import (
    preprocess_document,
)
from app.agents.safety import (
    assess_input_safety,
)
from eval.checkpoint import CheckpointStore
from eval.io_utils import (
    atomic_save_json,
    load_csv,
    require_manifest_columns,
)
from eval.metrics import confusion_metrics


async def main(
    args: argparse.Namespace,
) -> None:
    rows = load_csv(args.manifest)

    require_manifest_columns(
        rows,
        {
            "document_id",
            "pdf_path",
            "attack_type",
            "expected_safety_action",
        },
        args.manifest,
    )

    if args.split:
        rows = [
            row
            for row in rows
            if row.get("split") == args.split
        ]

    if args.limit is not None:
        rows = rows[: args.limit]

    selected_ids = {
        row["document_id"]
        for row in rows
    }

    checkpoint = CheckpointStore(
        args.checkpoint
    )

    if (
        checkpoint.records
        and not args.resume
    ):
        raise RuntimeError(
            "Checkpoint already contains records. "
            "Use --resume or select a new "
            "--checkpoint path."
        )

    failures = 0

    for row in rows:
        document_id = row["document_id"]

        if (
            args.resume
            and document_id
            in checkpoint.completed_ids
        ):
            continue

        try:
            pages, _ = preprocess_document(
                row["pdf_path"],
                str(
                    Path(args.runtime)
                    / document_id
                    / "pages"
                ),
            )

            (
                _ocr_pages,
                text,
                _word_count,
                _ocr_confidence,
            ) = run_ocr(pages)

            prediction = (
                await assess_input_safety(
                    pages,
                    text,
                )
            )

            record: dict[str, Any] = {
                "document_id": document_id,
                "status": "success",
                "attack_type": row[
                    "attack_type"
                ],
                "expected_action": row[
                    "expected_safety_action"
                ],
                "predicted_action": (
                    prediction.expected_action
                ),
                "risk_score": (
                    prediction.risk_score
                ),
            }

        except Exception as exc:
            failures += 1

            record = {
                "document_id": document_id,
                "status": "failed",
                "attack_type": row.get(
                    "attack_type",
                    "unknown",
                ),
                "expected_action": row.get(
                    "expected_safety_action",
                    "review",
                ),
                "predicted_action": "review",
                "error_type": (
                    type(exc).__name__
                ),
                "error_message": str(exc)[:500],
            }

        checkpoint.append(record)

        if failures > args.max_failures:
            raise RuntimeError(
                "Stopped after more than "
                f"{args.max_failures} failures"
            )

    records = [
        record
        for record in checkpoint.records
        if record["document_id"]
        in selected_ids
    ]

    successful_records = [
        record
        for record in records
        if record.get("status") == "success"
    ]

    counters = defaultdict(
        lambda: {
            "tp": 0,
            "fp": 0,
            "fn": 0,
            "tn": 0,
        }
    )

    for record in successful_records:
        actual = (
            record.get(
                "expected_action"
            )
            == "block"
        )

        predicted = (
            record.get(
                "predicted_action"
            )
            == "block"
        )

        groups = [
            "overall",
            (
                "attack:"
                f"{record.get('attack_type', 'unknown')}"
            ),
            (
                "benign_lookalike"
                if record.get("attack_type")
                == "benign_lookalike"
                else "other"
            ),
        ]

        for group in groups:
            counters[group]["tp"] += int(
                actual and predicted
            )
            counters[group]["fp"] += int(
                not actual and predicted
            )
            counters[group]["fn"] += int(
                actual and not predicted
            )
            counters[group]["tn"] += int(
                not actual and not predicted
            )

    report: dict[str, Any] = {
        group: confusion_metrics(**counts)
        for group, counts
        in sorted(counters.items())
    }

    report["documents"] = len(records)
    report["successful_documents"] = len(
        successful_records
    )
    report["failed_documents"] = sum(
        record.get("status") == "failed"
        for record in records
    )

    atomic_save_json(
        args.output,
        report,
    )

    print(
        f"Saved safety report to {args.output}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--manifest",
        default=(
            "data/synthetic/manifest.csv"
        ),
    )

    parser.add_argument("--split")

    parser.add_argument(
        "--limit",
        type=int,
    )

    parser.add_argument(
        "--runtime",
        default="data/eval_runtime/safety",
    )

    parser.add_argument(
        "--checkpoint",
        default=(
            "eval/reports/checkpoints/"
            "safety.jsonl"
        ),
    )

    parser.add_argument(
        "--output",
        default="eval/reports/safety.json",
    )

    parser.add_argument(
        "--resume",
        action="store_true",
    )

    parser.add_argument(
        "--max-failures",
        type=int,
        default=10,
    )

    asyncio.run(
        main(parser.parse_args())
    )
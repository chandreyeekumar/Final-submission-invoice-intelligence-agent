from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from time import perf_counter
from typing import Any

from app.agents.complexity_router import (
    route_complexity,
)
from app.agents.extraction import extract_invoice
from app.agents.ocr import run_ocr
from app.agents.preprocessing import (
    preprocess_document,
)
from eval.adapters.cord_adapter import (
    CORD_FIELDS,
    map_cord_ground_truth,
)
from eval.adapters.sroie_adapter import (
    SROIE_FIELDS,
    map_sroie_ground_truth,
)
from eval.checkpoint import CheckpointStore
from eval.io_utils import (
    atomic_save_json,
    load_csv,
    load_json,
    require_manifest_columns,
)
from eval.metrics import (
    aggregate_field_scores,
    latency_summary,
    score_fields,
)
from eval.runtime_compat import (
    call_with_optional_telemetry,
    model_dump_json,
)


async def main(
    args: argparse.Namespace,
) -> None:
    rows = load_csv(args.manifest)

    require_manifest_columns(
        rows,
        {
            "document_id",
            "image_path",
            "ground_truth_path",
        },
        args.manifest,
    )

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
            "Use --resume or specify a new "
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

        started = perf_counter()

        try:
            pages, _ = preprocess_document(
                row["image_path"],
                str(
                    Path(args.runtime)
                    / args.dataset
                    / document_id
                    / "pages"
                ),
            )

            (
                _ocr_pages,
                text,
                words,
                ocr_confidence,
            ) = run_ocr(pages)

            tier = route_complexity(
                len(pages),
                words,
                ocr_confidence,
            )

            telemetry = []

            prediction = (
                await call_with_optional_telemetry(
                    extract_invoice,
                    pages,
                    text,
                    tier,
                    telemetry=telemetry,
                )
            )

            raw_ground_truth = load_json(
                row["ground_truth_path"]
            )

            if not isinstance(
                raw_ground_truth,
                dict,
            ):
                raise ValueError(
                    "Benchmark ground truth must "
                    "contain a JSON object"
                )

            if args.dataset == "sroie":
                ground_truth = (
                    map_sroie_ground_truth(
                        raw_ground_truth
                    )
                )
                fields = SROIE_FIELDS
            else:
                ground_truth = (
                    map_cord_ground_truth(
                        raw_ground_truth
                    )
                )
                fields = CORD_FIELDS

            record: dict[str, Any] = {
                "document_id": document_id,
                "status": "success",
                "field_scores": score_fields(
                    model_dump_json(
                        prediction
                    ),
                    ground_truth,
                    fields,
                ),
                "latency_seconds": round(
                    perf_counter()
                    - started,
                    4,
                ),
                "api_calls": len(telemetry),
                "estimated_cost_usd": round(
                    sum(
                        float(
                            item.get(
                                "estimated_cost_usd",
                                0.0,
                            )
                        )
                        for item in telemetry
                    ),
                    6,
                ),
            }

        except Exception as exc:
            failures += 1

            record = {
                "document_id": document_id,
                "status": "failed",
                "field_scores": {},
                "latency_seconds": None,
                "error_type": (
                    type(exc).__name__
                ),
                "error_message": str(exc)[:500],
                "api_calls": 0,
                "estimated_cost_usd": 0.0,
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

    report = {
        "dataset": args.dataset,
        "documents": len(records),
        "successful_documents": len(
            successful_records
        ),
        "failed_documents": sum(
            record.get("status") == "failed"
            for record in records
        ),
        "scores": aggregate_field_scores(
            successful_records,
            "field_scores",
        ),
        "latency_seconds": latency_summary(
            [
                float(
                    record[
                        "latency_seconds"
                    ]
                )
                for record
                in successful_records
                if record.get(
                    "latency_seconds"
                )
                is not None
            ]
        ),
        "api_calls": sum(
            int(record.get("api_calls", 0))
            for record in records
        ),
        "estimated_cost_usd": round(
            sum(
                float(
                    record.get(
                        "estimated_cost_usd",
                        0.0,
                    )
                )
                for record in records
            ),
            6,
        ),
        "comparability_note": (
            "Scores cover only mapped common "
            "fields. They are not a reproduction "
            "of every native SROIE or CORD "
            "leaderboard metric."
        ),
    }

    atomic_save_json(
        args.output,
        report,
    )

    print(
        "Saved public benchmark report to "
        f"{args.output}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dataset",
        choices=[
            "sroie",
            "cord",
        ],
        required=True,
    )

    parser.add_argument(
        "--manifest",
        required=True,
    )

    parser.add_argument(
        "--limit",
        type=int,
    )

    parser.add_argument(
        "--runtime",
        default=(
            "data/eval_runtime/public"
        ),
    )

    parser.add_argument(
        "--checkpoint",
        required=True,
    )

    parser.add_argument(
        "--output",
        required=True,
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
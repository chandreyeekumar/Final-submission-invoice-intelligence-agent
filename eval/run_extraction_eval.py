from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from pathlib import Path
from time import perf_counter
from typing import Any

from app.agents.complexity_router import (
    route_complexity,
)
from app.agents.correction import (
    correct_failed_fields,
)
from app.agents.extraction import extract_invoice
from app.agents.ocr import run_ocr
from app.agents.preprocessing import (
    preprocess_document,
)
from app.agents.rag import VendorRAG
from app.agents.validation import validate_invoice
from eval.budget import BudgetExceeded, CostBudget
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


FIELDS = [
    "vendor_name",
    "vendor_address",
    "vendor_tax_id",
    "invoice_number",
    "invoice_date",
    "due_date",
    "purchase_order_number",
    "currency",
    "subtotal",
    "discount",
    "shipping",
    "tax_total",
    "total",
    "amount_due",
]


def report_for(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    successful_records = [
        record
        for record in records
        if record.get("status") == "success"
    ]

    latencies = [
        float(record["latency_seconds"])
        for record in successful_records
        if record.get("latency_seconds")
        is not None
    ]

    return {
        "documents": len(records),
        "successful_documents": len(
            successful_records
        ),
        "failed_documents": sum(
            record.get("status") == "failed"
            for record in records
        ),
        "first_pass": aggregate_field_scores(
            successful_records,
            "first_scores",
        ),
        "post_correction": aggregate_field_scores(
            successful_records,
            "corrected_scores",
        ),
        "correction_rate": (
            sum(
                bool(
                    record.get(
                        "correction_attempted"
                    )
                )
                for record in successful_records
            )
            / len(successful_records)
            if successful_records
            else 0.0
        ),
        "human_review_rate": (
            sum(
                bool(
                    record.get(
                        "human_review"
                    )
                )
                for record in successful_records
            )
            / len(successful_records)
            if successful_records
            else 0.0
        ),
        "latency_seconds": latency_summary(
            latencies
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
    }


async def evaluate_row(
    row: dict[str, str],
    runtime: Path,
) -> dict[str, Any]:
    telemetry: list[dict[str, Any]] = []
    started = perf_counter()

    work_directory = (
        runtime / row["document_id"]
    )

    pages, _ = preprocess_document(
        row["pdf_path"],
        str(work_directory / "pages"),
    )

    (
        _ocr_pages,
        ocr_text,
        word_count,
        ocr_confidence,
    ) = run_ocr(pages)

    complexity_tier = route_complexity(
        len(pages),
        word_count,
        ocr_confidence,
    )

    ground_truth = load_json(
        row["extraction_gt_path"]
    )

    if not isinstance(ground_truth, dict):
        raise ValueError(
            "Extraction ground truth must "
            "contain a JSON object"
        )

    first_extraction = (
        await call_with_optional_telemetry(
            extract_invoice,
            pages,
            ocr_text,
            complexity_tier,
            telemetry=telemetry,
        )
    )

    first_issues = validate_invoice(
        first_extraction
    )

    corrected_extraction = first_extraction
    correction_attempted = bool(
        first_issues
    )
    correction_history: Any = {}

    if first_issues:
        correction_result = (
            await call_with_optional_telemetry(
                correct_failed_fields,
                pages,
                first_extraction,
                first_issues,
                telemetry=telemetry,
            )
        )

        (
            corrected_extraction,
            correction_history,
        ) = correction_result

    corrected_issues = validate_invoice(
        corrected_extraction
    )

    rag_decision = VendorRAG().query(
        corrected_extraction
    )

    estimated_cost = sum(
        float(
            item.get(
                "estimated_cost_usd",
                0.0,
            )
        )
        for item in telemetry
    )

    first_payload = model_dump_json(
        first_extraction
    )

    corrected_payload = model_dump_json(
        corrected_extraction
    )

    expected_action = row.get(
        "expected_safety_action",
        "",
    )

    attack_type = row.get(
        "attack_type",
        "",
    )

    subset = (
        "benign_lookalike"
        if attack_type == "benign_lookalike"
        else "review"
        if expected_action == "review"
        else "normal"
    )

    return {
        "document_id": row["document_id"],
        "status": "success",
        "complexity": complexity_tier,
        "subset": subset,
        "first_scores": score_fields(
            first_payload,
            ground_truth,
            FIELDS,
        ),
        "corrected_scores": score_fields(
            corrected_payload,
            ground_truth,
            FIELDS,
        ),
        "correction_attempted": (
            correction_attempted
        ),
        "correction_history": (
            model_dump_json(correction_history)
            if hasattr(
                correction_history,
                "model_dump",
            )
            else correction_history
        ),
        "human_review": (
            bool(corrected_issues)
            or rag_decision.status
            in {
                "unknown",
                "ambiguous",
                "mismatch",
                "not_applicable",
            }
        ),
        "rag_status": rag_decision.status,
        "latency_seconds": round(
            perf_counter() - started,
            4,
        ),
        "api_calls": len(telemetry),
        "estimated_cost_usd": round(
            estimated_cost,
            6,
        ),
        "model_telemetry": telemetry,
    }


def build_report(
    *,
    args: argparse.Namespace,
    records: list[dict[str, Any]],
    blocked_count: int,
    stopped_reason: str | None,
) -> dict[str, Any]:
    by_complexity: dict[str, Any] = {}
    by_subset: dict[str, Any] = {}

    complexity_groups: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    subset_groups: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for record in records:
        complexity = record.get("complexity")
        subset = record.get("subset")

        if complexity:
            complexity_groups[
                str(complexity)
            ].append(record)

        if subset:
            subset_groups[
                str(subset)
            ].append(record)

    for name, group in sorted(
        complexity_groups.items()
    ):
        by_complexity[name] = report_for(group)

    for name, group in sorted(
        subset_groups.items()
    ):
        by_subset[name] = report_for(group)

    return {
        "manifest": args.manifest,
        "split": args.split,
        "limit": args.limit,
        "safety_blocked_excluded": (
            blocked_count
        ),
        "checkpoint": args.checkpoint,
        "cost_budget_usd": (
            args.max_cost_usd
        ),
        "stopped_reason": stopped_reason,
        "overall": report_for(records),
        "by_complexity": by_complexity,
        "by_subset": by_subset,
    }


async def main(
    args: argparse.Namespace,
) -> None:
    rows = load_csv(args.manifest)

    require_manifest_columns(
        rows,
        {
            "document_id",
            "split",
            "pdf_path",
            "extraction_gt_path",
            "expected_safety_action",
        },
        args.manifest,
    )

    if args.split:
        rows = [
            row
            for row in rows
            if row["split"] == args.split
        ]

    blocked_count = sum(
        row.get(
            "expected_safety_action"
        )
        == "block"
        for row in rows
    )

    rows = [
        row
        for row in rows
        if row.get(
            "expected_safety_action"
        )
        != "block"
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
            "Use --resume or specify a new "
            "--checkpoint path."
        )

    budget = CostBudget(
        args.max_cost_usd
    )

    prior_selected_records = [
        record
        for record in checkpoint.records
        if record["document_id"]
        in selected_ids
    ]

    for record in prior_selected_records:
        budget.spent_usd += float(
            record.get(
                "estimated_cost_usd",
                0.0,
            )
        )

    runtime = Path(args.runtime)
    failures = sum(
        record.get("status") == "failed"
        for record in prior_selected_records
    )

    stopped_reason: str | None = None

    try:
        for row in rows:
            document_id = row["document_id"]

            if (
                args.resume
                and document_id
                in checkpoint.completed_ids
            ):
                continue

            try:
                record = await evaluate_row(
                    row,
                    runtime,
                )

            except Exception as exc:
                failures += 1

                record = {
                    "document_id": document_id,
                    "status": "failed",
                    "error_type": (
                        type(exc).__name__
                    ),
                    "error_message": str(exc)[:500],
                    "first_scores": {},
                    "corrected_scores": {},
                    "latency_seconds": None,
                    "api_calls": 0,
                    "estimated_cost_usd": 0.0,
                }

                checkpoint.append(record)

                if failures > args.max_failures:
                    raise RuntimeError(
                        "Stopped after more than "
                        f"{args.max_failures} failures"
                    ) from exc

                continue

            # The paid work has already completed. Persist the result
            # before applying the budget stop so --resume never repeats it.
            checkpoint.append(record)

            budget.register(
                float(
                    record[
                        "estimated_cost_usd"
                    ]
                )
            )

    except BudgetExceeded as exc:
        stopped_reason = str(exc)

    finally:
        selected_records = [
            record
            for record in checkpoint.records
            if record["document_id"]
            in selected_ids
        ]

        report = build_report(
            args=args,
            records=selected_records,
            blocked_count=blocked_count,
            stopped_reason=stopped_reason,
        )

        atomic_save_json(
            args.output,
            report,
        )

        print(
            "Saved extraction report to "
            f"{args.output}"
        )

    if stopped_reason:
        raise BudgetExceeded(
            stopped_reason
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--manifest",
        default=(
            "data/synthetic/manifest.csv"
        ),
    )

    parser.add_argument(
        "--split",
        choices=[
            "development",
            "validation",
            "test",
        ],
    )

    parser.add_argument(
        "--limit",
        type=int,
    )

    parser.add_argument(
        "--runtime",
        default=(
            "data/eval_runtime/synthetic"
        ),
    )

    parser.add_argument(
        "--checkpoint",
        default=(
            "eval/reports/checkpoints/"
            "extraction.jsonl"
        ),
    )

    parser.add_argument(
        "--output",
        default=(
            "eval/reports/"
            "synthetic_extraction.json"
        ),
    )

    parser.add_argument(
        "--resume",
        action="store_true",
    )

    parser.add_argument(
        "--max-cost-usd",
        type=float,
        default=5.0,
    )

    parser.add_argument(
        "--max-failures",
        type=int,
        default=10,
    )

    asyncio.run(
        main(parser.parse_args())
    )
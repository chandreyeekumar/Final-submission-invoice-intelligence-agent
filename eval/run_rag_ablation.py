from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.agents.complexity_router import (
    route_complexity,
)
from app.agents.extraction import extract_invoice
from app.agents.ocr import run_ocr
from app.agents.preprocessing import (
    preprocess_document,
)
from app.agents.rag import VendorRAG
from eval.io_utils import (
    atomic_save_json,
    load_csv,
    require_manifest_columns,
)
from eval.metrics import normalize_text
from eval.runtime_compat import (
    call_with_optional_telemetry,
)


async def main(
    args: argparse.Namespace,
) -> None:
    vendor_path = Path(
        args.vendor_master
    )

    if not vendor_path.exists():
        raise FileNotFoundError(
            f"Vendor master not found: {vendor_path}"
        )

    vendors = json.loads(
        vendor_path.read_text(
            encoding="utf-8"
        )
    )

    by_id = {
        str(vendor["vendor_id"]): vendor
        for vendor in vendors
    }

    rows = load_csv(args.manifest)

    require_manifest_columns(
        rows,
        {
            "document_id",
            "pdf_path",
            "vendor_id",
            "expected_safety_action",
        },
        args.manifest,
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

    without_rag_correct = 0
    with_rag_correct = 0
    status_correct = 0
    scored = 0
    failed = 0

    for row in rows:
        expected = by_id.get(
            row.get("vendor_id", "")
        )

        if expected is None:
            continue

        try:
            pages, _ = preprocess_document(
                row["pdf_path"],
                str(
                    Path(args.runtime)
                    / row["document_id"]
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

            invoice = (
                await call_with_optional_telemetry(
                    extract_invoice,
                    pages,
                    text,
                    tier,
                    telemetry=telemetry,
                )
            )

            decision = VendorRAG().query(
                invoice
            )

        except Exception:
            failed += 1

            if failed > args.max_failures:
                raise RuntimeError(
                    "Stopped after more than "
                    f"{args.max_failures} failures"
                )

            continue

        legal_name = str(
            expected["legal_name"]
        )

        without_rag_correct += int(
            normalize_text(
                invoice.vendor_name
            )
            == normalize_text(
                legal_name
            )
        )

        with_rag_name = (
            decision.matched_legal_name
            if decision.status == "verified"
            and decision.matched_legal_name
            else invoice.vendor_name
        )

        with_rag_correct += int(
            normalize_text(
                with_rag_name
            )
            == normalize_text(
                legal_name
            )
        )

        expected_status = row.get(
            "rag_expected_status",
            "verified",
        )

        status_correct += int(
            decision.status
            == expected_status
        )

        scored += 1

    if not scored:
        raise RuntimeError(
            "No scorable known-vendor rows found"
        )

    report = {
        "documents": scored,
        "failed_documents": failed,
        "without_rag_vendor_accuracy": (
            without_rag_correct / scored
        ),
        "with_rag_vendor_accuracy": (
            with_rag_correct / scored
        ),
        "rag_vendor_uplift": (
            with_rag_correct
            - without_rag_correct
        )
        / scored,
        "rag_status_accuracy": (
            status_correct / scored
        ),
    }

    atomic_save_json(
        args.output,
        report,
    )

    print(
        "Saved RAG ablation report to "
        f"{args.output}"
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
        "--vendor-master",
        dest="vendor_master",
        default=(
            "data/vendor_master/vendors.json"
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=50,
    )

    parser.add_argument(
        "--runtime",
        default=(
            "data/eval_runtime/rag_ablation"
        ),
    )

    parser.add_argument(
        "--output",
        default=(
            "eval/reports/rag_ablation.json"
        ),
    )

    parser.add_argument(
        "--max-failures",
        type=int,
        default=10,
    )

    asyncio.run(
        main(parser.parse_args())
    )
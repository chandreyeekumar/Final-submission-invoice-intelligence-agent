from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from app.agents.rag import VendorRAG
from app.schemas.invoice import InvoiceExtraction
from eval.io_utils import atomic_save_json


def _invoice(
    **values: Any,
) -> InvoiceExtraction:
    """Build an InvoiceExtraction while using model defaults."""

    return InvoiceExtraction(**values)


def main(
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

    if not isinstance(vendors, list) or not vendors:
        raise RuntimeError(
            "Vendor master contains no records"
        )

    randomizer = random.Random(
        args.seed
    )

    rag = VendorRAG()

    reciprocal_ranks: list[float] = []
    top1 = 0
    top3 = 0

    selected = vendors[
        : min(
            args.known_limit,
            len(vendors),
        )
    ]

    for vendor in selected:
        legal_name = str(
            vendor["legal_name"]
        )

        aliases = vendor.get(
            "aliases",
            [],
        )

        alias = (
            str(aliases[0])
            if aliases
            else legal_name
        )

        typographical_variant = (
            legal_name.replace(
                "o",
                "0",
                1,
            )
        )

        variants = [
            legal_name,
            alias,
            typographical_variant,
        ]

        invoice = _invoice(
            vendor_name=randomizer.choice(
                variants
            ),
            vendor_address=vendor.get(
                "address"
            ),
            vendor_tax_id=vendor.get(
                "tax_id"
            ),
            currency=vendor.get(
                "currency"
            ),
            vendor_bank_account=(
                "XXXX"
                + str(
                    vendor.get(
                        "bank_last4",
                        "",
                    )
                )
                if vendor.get("bank_last4")
                else None
            ),
        )

        decision = rag.query(invoice)

        ranks = [
            candidate.vendor_id
            for candidate
            in decision.candidates
        ]

        expected_vendor_id = str(
            vendor["vendor_id"]
        )

        rank = (
            ranks.index(
                expected_vendor_id
            )
            + 1
            if expected_vendor_id
            in ranks
            else None
        )

        top1 += int(rank == 1)
        top3 += int(
            bool(
                rank
                and rank <= 3
            )
        )

        reciprocal_ranks.append(
            1 / rank
            if rank
            else 0.0
        )

    unknown_hits = 0

    for index in range(
        args.unknown_limit
    ):
        decision = rag.query(
            _invoice(
                vendor_name=(
                    "Unknown Phantom "
                    f"Supplier {index}"
                )
            )
        )

        unknown_hits += int(
            decision.status == "unknown"
        )

    mismatch_hits = 0

    mismatch_sample = vendors[
        : min(
            args.mismatch_limit,
            len(vendors),
        )
    ]

    for vendor in mismatch_sample:
        decision = rag.query(
            _invoice(
                vendor_name=vendor[
                    "legal_name"
                ],
                vendor_tax_id=(
                    "WRONG-TAX-ID"
                ),
                currency=vendor.get(
                    "currency"
                ),
                vendor_bank_account=(
                    "XXXX9999"
                ),
            )
        )

        mismatch_hits += int(
            decision.status == "mismatch"
        )

    report = {
        "known_documents": len(selected),
        "recall_at_1": (
            top1 / len(selected)
            if selected
            else 0.0
        ),
        "recall_at_3": (
            top3 / len(selected)
            if selected
            else 0.0
        ),
        "mrr": (
            sum(reciprocal_ranks)
            / len(reciprocal_ranks)
            if reciprocal_ranks
            else 0.0
        ),
        "unknown_documents": (
            args.unknown_limit
        ),
        "unknown_vendor_rejection": (
            unknown_hits
            / args.unknown_limit
            if args.unknown_limit
            else 0.0
        ),
        "mismatch_documents": len(
            mismatch_sample
        ),
        "mismatch_detection": (
            mismatch_hits
            / len(mismatch_sample)
            if mismatch_sample
            else 0.0
        ),
    }

    atomic_save_json(
        args.output,
        report,
    )

    print(
        f"Saved RAG report to {args.output}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--vendor-master",
        default=(
            "data/vendor_master/vendors.json"
        ),
    )

    parser.add_argument(
        "--known-limit",
        type=int,
        default=100,
    )

    parser.add_argument(
        "--unknown-limit",
        type=int,
        default=30,
    )

    parser.add_argument(
        "--mismatch-limit",
        type=int,
        default=30,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    parser.add_argument(
        "--output",
        default=(
            "eval/reports/rag_component.json"
        ),
    )

    main(parser.parse_args())
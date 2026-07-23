from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.agents.extraction import extract_invoice
from app.agents.ocr import run_ocr


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one paid invoice extraction using one processed page."
    )
    parser.add_argument(
        "--image",
        default="data/runtime/smoke/pages/page_001.png",
        help="Path to one preprocessed invoice page image.",
    )
    parser.add_argument(
        "--complexity",
        choices=["low", "medium", "high"],
        default="low",
        help="Model-routing complexity tier.",
    )
    parser.add_argument(
        "--output",
        default="outputs/smoke/single_extraction.json",
        help="JSON output path.",
    )
    args = parser.parse_args()

    image_path = Path(args.image)
    output_path = Path(args.output)

    if not image_path.exists():
        raise FileNotFoundError(
            f"Invoice page image was not found: {image_path}"
        )

    print("=" * 70)
    print("SINGLE PAID EXTRACTION TEST")
    print("=" * 70)
    print(f"Image: {image_path}")
    print(f"Complexity: {args.complexity}")
    print("Running OCR locally...")

    ocr_pages, ocr_text, word_count, ocr_confidence = run_ocr(
        [str(image_path)]
    )

    print(f"OCR word count: {word_count}")
    print(f"OCR confidence: {ocr_confidence}")
    print()
    print("Calling the OpenAI API once...")
    print("This step incurs API usage charges.")

    telemetry: list[dict] = []

    invoice = await extract_invoice(
        page_paths=[str(image_path)],
        ocr_text=ocr_text,
        complexity_tier=args.complexity,
        telemetry=telemetry,
    )

    result = {
        "source_image": str(image_path),
        "complexity_tier": args.complexity,
        "ocr": {
            "word_count": word_count,
            "confidence": ocr_confidence,
            "pages": ocr_pages,
        },
        "extraction": invoice.model_dump(mode="json"),
        "telemetry": telemetry,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print()
    print("=" * 70)
    print("EXTRACTION COMPLETED")
    print("=" * 70)
    print(invoice.model_dump_json(indent=2))
    print()
    print(f"Saved result to: {output_path}")

    if telemetry:
        usage = telemetry[-1]
        print(f"Model: {usage.get('model')}")
        print(f"Input tokens: {usage.get('input_tokens')}")
        print(f"Output tokens: {usage.get('output_tokens')}")
        print(
            "Estimated cost USD: "
            f"{usage.get('estimated_cost_usd')}"
        )


if __name__ == "__main__":
    asyncio.run(main())
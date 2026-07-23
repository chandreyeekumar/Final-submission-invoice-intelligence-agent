from __future__ import annotations

import argparse
import csv
import json
import random
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any

from datasets import load_dataset
from PIL import Image


# ---------------------------------------------------------------------------
# Dataset configuration
# ---------------------------------------------------------------------------

DATASET_IDS = {
    "sroie": "darentang/sroie",
    "cord": "naver-clova-ix/cord-v2",
}

DEFAULT_OUTPUT_ROOT = Path("data/public")

# This is where the separate download_sroie_source.py script extracts
# the original SROIE archive.
DEFAULT_SROIE_SOURCE_ROOT = Path(
    "data/public/sroie_source/extracted"
)


# ---------------------------------------------------------------------------
# Generic helper functions
# ---------------------------------------------------------------------------

def first_present(
    row: dict[str, Any],
    *names: str,
) -> Any:
    """
    Return the first field whose value is not None or an empty string.

    Empty lists and empty dictionaries are considered valid values because
    they may represent legitimate dataset annotations.
    """

    for name in names:
        if name not in row:
            continue

        value = row[name]

        if value is not None and value != "":
            return value

    return None


def normalize_path_filename(
    raw_path: str | Path,
) -> str:
    """
    Extract a filename from either Windows or Unix-style paths.

    Some Hugging Face rows contain Unix server paths even when the code is
    running on Windows. Replacing backslashes first makes extraction reliable.
    """

    normalized = str(raw_path).replace("\\", "/")
    return PurePosixPath(normalized).name


def deduplicate_paths(
    paths: list[Path],
) -> list[Path]:
    """Return paths without duplicates while preserving order."""

    seen: set[str] = set()
    unique: list[Path] = []

    for path in paths:
        key = str(path.resolve())

        if key not in seen:
            seen.add(key)
            unique.append(path)

    return unique


def save_json(
    payload: Any,
    path: Path,
) -> None:
    """Save a JSON-serializable payload with readable formatting."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )


def save_manifest(
    records: list[dict[str, str]],
    manifest_path: Path,
) -> None:
    """Write the benchmark manifest CSV."""

    if not records:
        raise RuntimeError(
            "No benchmark records were created, so the manifest "
            "cannot be written."
        )

    manifest_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "document_id",
        "image_path",
        "ground_truth_path",
        "split",
    ]

    with manifest_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(records)


# ---------------------------------------------------------------------------
# Image handling
# ---------------------------------------------------------------------------

def save_image(
    image_value: Any,
    destination: Path,
) -> None:
    """
    Save an image value as an RGB PNG.

    Supported image representations:

    1. PIL Image object
    2. Local string path
    3. pathlib.Path object
    4. Hugging Face image dictionary containing:
       - {"path": "..."}
       - {"bytes": b"..."}
    5. Raw image bytes
    """

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Case 1: PIL Image or PIL-compatible object.
    if hasattr(image_value, "convert"):
        image_value.convert("RGB").save(
            destination,
            "PNG",
        )
        return

    # Case 2: Raw image bytes.
    if isinstance(
        image_value,
        (
            bytes,
            bytearray,
        ),
    ):
        with Image.open(
            BytesIO(bytes(image_value))
        ) as opened_image:
            opened_image.convert("RGB").save(
                destination,
                "PNG",
            )

        return

    # Case 3: Local string or Path.
    if isinstance(
        image_value,
        (
            str,
            Path,
        ),
    ):
        source_path = Path(image_value)

        if not source_path.exists():
            raise FileNotFoundError(
                "The image path does not exist locally: "
                f"{source_path}"
            )

        with Image.open(source_path) as opened_image:
            opened_image.convert("RGB").save(
                destination,
                "PNG",
            )

        return

    # Case 4: Hugging Face image dictionary.
    if isinstance(image_value, dict):
        image_path = image_value.get("path")
        image_bytes = image_value.get("bytes")

        if image_bytes:
            with Image.open(
                BytesIO(image_bytes)
            ) as opened_image:
                opened_image.convert("RGB").save(
                    destination,
                    "PNG",
                )

            return

        if image_path:
            source_path = Path(image_path)

            if not source_path.exists():
                raise FileNotFoundError(
                    "The path inside the Hugging Face image "
                    "dictionary does not exist locally: "
                    f"{source_path}"
                )

            with Image.open(source_path) as opened_image:
                opened_image.convert("RGB").save(
                    destination,
                    "PNG",
                )

            return

    raise TypeError(
        "Unsupported image representation. "
        f"Received type: {type(image_value).__name__}"
    )


# ---------------------------------------------------------------------------
# SROIE-specific helpers
# ---------------------------------------------------------------------------

def find_local_sroie_image(
    source_image_path: str | Path,
    split: str,
    source_root: Path = DEFAULT_SROIE_SOURCE_ROOT,
) -> Path:
    """
    Map a Hugging Face server-side SROIE image path to a local image.

    Hugging Face may return values such as:

        /storage/hf-datasets-cache/.../sroie/test/images/example.jpg

    That path belongs to Hugging Face infrastructure and does not exist on
    the user's computer. This function extracts the filename and searches
    the locally downloaded SROIE source archive.
    """

    filename = normalize_path_filename(
        source_image_path
    )

    if not filename:
        raise ValueError(
            "The SROIE image path does not contain a filename."
        )

    if not source_root.exists():
        raise FileNotFoundError(
            "The local SROIE source folder was not found:\n"
            f"{source_root.resolve()}\n\n"
            "Run this command first:\n"
            "python -m scripts.download_sroie_source"
        )

    split_lower = split.lower().strip()

    preferred_patterns = [
        f"**/sroie/{split_lower}/images/{filename}",
        f"**/{split_lower}/images/{filename}",
        f"**/{split_lower}/img/{filename}",
        f"**/images/{filename}",
        f"**/img/{filename}",
        f"**/{filename}",
    ]

    matches: list[Path] = []

    for pattern in preferred_patterns:
        matches.extend(
            path
            for path in source_root.glob(pattern)
            if path.is_file()
        )

    unique_matches = deduplicate_paths(
        matches
    )

    if not unique_matches:
        raise FileNotFoundError(
            "Could not find the locally downloaded SROIE image:\n"
            f"Filename: {filename}\n"
            f"Search root: {source_root.resolve()}\n\n"
            "Confirm that the original SROIE archive was downloaded "
            "and extracted successfully."
        )

    # Prefer a path containing the requested split.
    split_matches = [
        path
        for path in unique_matches
        if split_lower
        in {
            part.lower()
            for part in path.parts
        }
    ]

    if len(split_matches) == 1:
        return split_matches[0]

    if len(split_matches) > 1:
        raise RuntimeError(
            "Multiple SROIE images were found for the requested split:\n"
            + "\n".join(
                str(path)
                for path in split_matches
            )
        )

    if len(unique_matches) == 1:
        return unique_matches[0]

    raise RuntimeError(
        "Multiple possible SROIE images were found for "
        f"{filename}:\n"
        + "\n".join(
            str(path)
            for path in unique_matches
        )
    )


def resolve_sroie_image(
    row: dict[str, Any],
    split: str,
    source_root: Path,
) -> Any:
    """
    Resolve a usable SROIE image representation from a dataset row.

    The dataset may provide:
    - image
    - img
    - image_path

    If image_path points to a missing Hugging Face server location, the
    matching image is found inside the locally extracted source archive.
    """

    image_value = first_present(
        row,
        "image",
        "img",
        "image_path",
    )

    if image_value is None:
        raise KeyError(
            "The SROIE row has no supported image field. "
            f"Available columns: {sorted(row.keys())}"
        )

    # A dictionary or PIL image can be handled directly.
    if isinstance(image_value, dict):
        dictionary_path = image_value.get("path")

        if dictionary_path:
            candidate = Path(dictionary_path)

            if candidate.exists():
                return candidate

            return find_local_sroie_image(
                source_image_path=dictionary_path,
                split=split,
                source_root=source_root,
            )

        return image_value

    if hasattr(image_value, "convert"):
        return image_value

    if isinstance(
        image_value,
        (
            bytes,
            bytearray,
        ),
    ):
        return image_value

    # A local path may already exist.
    if isinstance(
        image_value,
        (
            str,
            Path,
        ),
    ):
        candidate = Path(image_value)

        if candidate.exists():
            return candidate

        return find_local_sroie_image(
            source_image_path=image_value,
            split=split,
            source_root=source_root,
        )

    raise TypeError(
        "Unsupported SROIE image value. "
        f"Received type: {type(image_value).__name__}"
    )


def build_sroie_ground_truth(
    row: dict[str, Any],
) -> dict[str, Any]:
    """
    Build ground truth from the available SROIE schema.

    Some SROIE versions expose final fields such as company, address, date,
    and total. Other versions expose token-level annotations such as words,
    bounding boxes, and NER tags. This function preserves whichever form is
    available.
    """

    company = first_present(
        row,
        "company",
        "vendor_name",
    )

    address = first_present(
        row,
        "address",
        "vendor_address",
    )

    invoice_date = first_present(
        row,
        "date",
        "invoice_date",
    )

    total = first_present(
        row,
        "total",
        "amount_due",
    )

    field_level_available = any(
        value is not None
        for value in (
            company,
            address,
            invoice_date,
            total,
        )
    )

    ground_truth: dict[str, Any] = {
        "source_dataset": "sroie",
        "source_id": row.get("id"),
    }

    if field_level_available:
        ground_truth["fields"] = {
            "company": company,
            "address": address,
            "date": invoice_date,
            "total": total,
        }

    if any(
        name in row
        for name in (
            "words",
            "bboxes",
            "ner_tags",
        )
    ):
        ground_truth["token_annotations"] = {
            "words": row.get(
                "words",
                [],
            ),
            "bboxes": row.get(
                "bboxes",
                [],
            ),
            "ner_tags": row.get(
                "ner_tags",
                [],
            ),
        }

    if (
        "fields" not in ground_truth
        and "token_annotations" not in ground_truth
    ):
        ground_truth["raw_row"] = {
            key: value
            for key, value in row.items()
            if key not in {
                "image",
                "img",
            }
        }

    return ground_truth


def prepare_sroie(
    rows: list[dict[str, Any]],
    output: Path,
    split: str,
    limit: int,
    seed: int,
    source_root: Path,
) -> list[dict[str, str]]:
    """Prepare local SROIE images, JSON ground truth, and manifest rows."""

    chosen = list(rows)

    random.Random(seed).shuffle(
        chosen
    )

    selected_rows = chosen[:limit]

    if not selected_rows:
        raise RuntimeError(
            "No SROIE rows were available for preparation."
        )

    records: list[dict[str, str]] = []

    for index, row in enumerate(
        selected_rows
    ):
        document_id = (
            f"sroie_{split}_{index:04d}"
        )

        image_value = resolve_sroie_image(
            row=row,
            split=split,
            source_root=source_root,
        )

        ground_truth = (
            build_sroie_ground_truth(row)
        )

        image_path = (
            output
            / "images"
            / f"{document_id}.png"
        )

        ground_truth_path = (
            output
            / "ground_truth"
            / f"{document_id}_extraction.json"
        )

        save_image(
            image_value=image_value,
            destination=image_path,
        )

        save_json(
            payload=ground_truth,
            path=ground_truth_path,
        )

        records.append(
            {
                "document_id": document_id,
                "image_path": image_path.as_posix(),
                "ground_truth_path": (
                    ground_truth_path.as_posix()
                ),
                "split": split,
            }
        )

        print(
            f"[SROIE] Prepared {index + 1}/{len(selected_rows)}: "
            f"{document_id}"
        )

    return records


# ---------------------------------------------------------------------------
# CORD-specific helpers
# ---------------------------------------------------------------------------

def parse_possible_json(
    value: Any,
) -> Any:
    """
    Parse a JSON string when possible.

    If the string is not valid JSON, retain it in a dictionary so the
    original annotation is not lost.
    """

    if not isinstance(value, str):
        return value

    stripped = value.strip()

    if not stripped:
        return {}

    try:
        return json.loads(stripped)

    except json.JSONDecodeError:
        return {
            "raw": value,
        }


def resolve_cord_image(
    row: dict[str, Any],
) -> Any:
    """Resolve the image value from a CORD-v2 row."""

    image_value = first_present(
        row,
        "image",
        "img",
        "image_path",
    )

    if image_value is None:
        raise KeyError(
            "The CORD row has no supported image field. "
            f"Available columns: {sorted(row.keys())}"
        )

    return image_value


def build_cord_ground_truth(
    row: dict[str, Any],
) -> dict[str, Any]:
    """Extract CORD-v2 annotation data from common schema variants."""

    raw_annotation = first_present(
        row,
        "ground_truth",
        "annotation",
        "json",
    )

    parsed_annotation = parse_possible_json(
        raw_annotation
    )

    if isinstance(parsed_annotation, dict):
        ground_truth = parsed_annotation
    else:
        ground_truth = {
            "raw": parsed_annotation,
        }

    # Preserve useful metadata when available.
    metadata: dict[str, Any] = {}

    for key in (
        "id",
        "file_name",
        "filename",
        "valid_line",
        "gt_parse",
    ):
        if key in row:
            metadata[key] = row[key]

    if metadata:
        return {
            "source_dataset": "cord-v2",
            "metadata": metadata,
            "annotation": ground_truth,
        }

    return {
        "source_dataset": "cord-v2",
        "annotation": ground_truth,
    }


def prepare_cord(
    rows: list[dict[str, Any]],
    output: Path,
    split: str,
    limit: int,
    seed: int,
) -> list[dict[str, str]]:
    """Prepare local CORD-v2 images, ground truth, and manifest rows."""

    chosen = list(rows)

    random.Random(seed).shuffle(
        chosen
    )

    selected_rows = chosen[:limit]

    if not selected_rows:
        raise RuntimeError(
            "No CORD-v2 rows were available for preparation."
        )

    records: list[dict[str, str]] = []

    for index, row in enumerate(
        selected_rows
    ):
        document_id = (
            f"cord_{split}_{index:04d}"
        )

        image_value = resolve_cord_image(
            row
        )

        ground_truth = (
            build_cord_ground_truth(row)
        )

        image_path = (
            output
            / "images"
            / f"{document_id}.png"
        )

        ground_truth_path = (
            output
            / "ground_truth"
            / f"{document_id}_extraction.json"
        )

        save_image(
            image_value=image_value,
            destination=image_path,
        )

        save_json(
            payload=ground_truth,
            path=ground_truth_path,
        )

        records.append(
            {
                "document_id": document_id,
                "image_path": image_path.as_posix(),
                "ground_truth_path": (
                    ground_truth_path.as_posix()
                ),
                "split": split,
            }
        )

        print(
            f"[CORD] Prepared {index + 1}/{len(selected_rows)}: "
            f"{document_id}"
        )

    return records


# ---------------------------------------------------------------------------
# Dataset loading and main command
# ---------------------------------------------------------------------------

def load_dataset_rows(
    dataset_id: str,
    split: str,
    trust_remote_code: bool,
) -> list[dict[str, Any]]:
    """Download a Hugging Face dataset split and convert it to dictionaries."""

    try:
        dataset = load_dataset(
            dataset_id,
            split=split,
            trust_remote_code=trust_remote_code,
        )

    except Exception as exc:
        raise RuntimeError(
            "Public benchmark download failed.\n"
            f"Dataset ID: {dataset_id}\n"
            f"Requested split: {split}\n\n"
            "Check internet access, Hugging Face authentication, "
            "dataset access terms, the dataset ID, and the split name."
        ) from exc

    rows = [
        dict(row)
        for row in dataset
    ]

    if not rows:
        raise RuntimeError(
            "The downloaded dataset split contains no rows."
        )

    print(
        "Dataset columns:",
        sorted(rows[0].keys()),
    )

    print(
        f"Downloaded rows: {len(rows)}"
    )

    return rows


def main() -> None:
    """Prepare SROIE or CORD-v2 for local evaluation."""

    parser = argparse.ArgumentParser(
        description=(
            "Prepare SROIE or CORD-v2 public benchmark data."
        )
    )

    parser.add_argument(
        "--dataset",
        choices=[
            "sroie",
            "cord",
        ],
        required=True,
        help="Benchmark to prepare.",
    )

    parser.add_argument(
        "--dataset-id",
        help=(
            "Optional Hugging Face dataset ID override."
        ),
    )

    parser.add_argument(
        "--split",
        default="test",
        help="Dataset split to download. Default: test",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of records to prepare.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed used before selecting records.",
    )

    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Root folder for prepared public benchmarks.",
    )

    parser.add_argument(
        "--sroie-source-root",
        default=str(DEFAULT_SROIE_SOURCE_ROOT),
        help=(
            "Folder containing the extracted original "
            "SROIE source archive."
        ),
    )

    parser.add_argument(
        "--trust-remote-code",
        action="store_true",
        help=(
            "Allow Hugging Face dataset loader remote code."
        ),
    )

    args = parser.parse_args()

    if args.limit < 1:
        raise ValueError(
            "--limit must be at least 1"
        )

    dataset_id = (
        args.dataset_id
        or DATASET_IDS[args.dataset]
    )

    rows = load_dataset_rows(
        dataset_id=dataset_id,
        split=args.split,
        trust_remote_code=args.trust_remote_code,
    )

    output_root = Path(
        args.output_root
    )

    dataset_output = (
        output_root
        / args.dataset
    )

    if args.dataset == "sroie":
        records = prepare_sroie(
            rows=rows,
            output=dataset_output,
            split=args.split,
            limit=args.limit,
            seed=args.seed,
            source_root=Path(
                args.sroie_source_root
            ),
        )

    else:
        records = prepare_cord(
            rows=rows,
            output=dataset_output,
            split=args.split,
            limit=args.limit,
            seed=args.seed,
        )

    manifest_path = (
        output_root
        / f"{args.dataset}_manifest.csv"
    )

    save_manifest(
        records=records,
        manifest_path=manifest_path,
    )

    print()
    print(
        f"Created {len(records)} records."
    )
    print(
        f"Manifest: {manifest_path.resolve()}"
    )
    print(
        f"Images: {(dataset_output / 'images').resolve()}"
    )
    print(
        "Ground truth: "
        f"{(dataset_output / 'ground_truth').resolve()}"
    )


if __name__ == "__main__":
    main()
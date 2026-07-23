from __future__ import annotations

import csv
import json
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def load_csv(path: str | Path) -> list[dict[str, str]]:
    source = Path(path)

    if not source.exists():
        raise FileNotFoundError(
            f"CSV file not found: {source}"
        )

    with source.open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        return list(csv.DictReader(handle))


def load_json(path: str | Path) -> Any:
    source = Path(path)

    if not source.exists():
        raise FileNotFoundError(
            f"JSON file not found: {source}"
        )

    try:
        return json.loads(
            source.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON file: {source}"
        ) from exc


def atomic_save_json(
    path: str | Path,
    payload: Any,
) -> None:
    """Write JSON atomically.

    The completed temporary file replaces the target only after the
    temporary content has been flushed to disk.
    """

    target = Path(path)
    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f"{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )

    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(
            file_descriptor,
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(
                payload,
                handle,
                indent=2,
                default=str,
                ensure_ascii=False,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        temporary_path.replace(target)

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def append_jsonl(
    path: str | Path,
    records: Iterable[dict[str, Any]],
) -> None:
    """Append durable JSONL checkpoint records."""

    target = Path(path)
    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with target.open(
        "a",
        encoding="utf-8",
    ) as handle:
        for record in records:
            handle.write(
                json.dumps(
                    record,
                    default=str,
                    ensure_ascii=False,
                )
            )
            handle.write("\n")

        handle.flush()
        os.fsync(handle.fileno())


def load_jsonl(
    path: str | Path,
) -> list[dict[str, Any]]:
    source = Path(path)

    if not source.exists():
        return []

    records: list[dict[str, Any]] = []

    for line_number, line in enumerate(
        source.read_text(
            encoding="utf-8"
        ).splitlines(),
        start=1,
    ):
        if not line.strip():
            continue

        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSONL at "
                f"{source}:{line_number}"
            ) from exc

        if not isinstance(payload, dict):
            raise ValueError(
                f"JSONL record must be an object at "
                f"{source}:{line_number}"
            )

        records.append(payload)

    return records


def require_manifest_columns(
    rows: list[dict[str, str]],
    required: set[str],
    path: str | Path,
) -> None:
    if not rows:
        raise RuntimeError(
            f"Manifest has no data rows: {path}"
        )

    available = set(rows[0])
    missing = required - available

    if missing:
        raise ValueError(
            f"Manifest {path} is missing columns: "
            f"{sorted(missing)}"
        )
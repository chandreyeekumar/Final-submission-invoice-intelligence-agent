from __future__ import annotations

from pathlib import Path
from typing import Any

from eval.io_utils import append_jsonl, load_jsonl


class CheckpointStore:
    def __init__(
        self,
        path: str | Path,
    ) -> None:
        self.path = Path(path)
        self._records = load_jsonl(self.path)

        self._by_id: dict[
            str,
            dict[str, Any],
        ] = {}

        for record in self._records:
            if "document_id" not in record:
                raise ValueError(
                    "Checkpoint record is missing "
                    f"document_id: {record}"
                )

            document_id = str(
                record["document_id"]
            )

            if document_id in self._by_id:
                raise ValueError(
                    "Duplicate document_id already "
                    f"exists in checkpoint: {document_id}"
                )

            self._by_id[document_id] = record

    @property
    def completed_ids(self) -> set[str]:
        return set(self._by_id)

    @property
    def records(self) -> list[dict[str, Any]]:
        """All durable checkpoint records."""

        return list(self._by_id.values())

    def get(
        self,
        document_id: str,
    ) -> dict[str, Any] | None:
        return self._by_id.get(
            str(document_id)
        )

    def append(
        self,
        record: dict[str, Any],
    ) -> None:
        if "document_id" not in record:
            raise ValueError(
                "Checkpoint record must include "
                "document_id"
            )

        document_id = str(
            record["document_id"]
        )

        if document_id in self._by_id:
            raise ValueError(
                "Duplicate checkpoint record: "
                f"{document_id}"
            )

        durable_record = {
            **record,
            "document_id": document_id,
        }

        append_jsonl(
            self.path,
            [durable_record],
        )

        self._by_id[document_id] = (
            durable_record
        )
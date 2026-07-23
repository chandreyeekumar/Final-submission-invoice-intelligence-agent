from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    UploadFile,
)

from app.core.config import get_settings
from app.workflows.invoice_graph import graph


router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


def _serialize_result(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")

    return value


@router.post("/invoices/process")
async def process_invoice(
    file: UploadFile = File(...),
) -> dict:
    request_id = str(uuid.uuid4())

    runtime_directory = (
        Path("data/runtime") / request_id
    )

    runtime_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    safe_filename = Path(
        file.filename or "upload.bin"
    ).name

    target_path = (
        runtime_directory / safe_filename
    )

    settings = get_settings()

    upload_limit = int(
        settings.max_upload_mb
    ) * 1024 * 1024

    bytes_written = 0

    try:
        with target_path.open("wb") as handle:
            while True:
                chunk = await file.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                bytes_written += len(chunk)

                if bytes_written > upload_limit:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "Upload exceeds "
                            "configured size limit"
                        ),
                    )

                handle.write(chunk)

        initial_state = {
            "request_id": request_id,
            "original_filename": safe_filename,
            "document_path": str(target_path),
            "document_id": "",
            "page_images": [],
            "preprocessing_metadata": [],
            "ocr_pages": [],
            "ocr_text": "",
            "ocr_word_count": 0,
            "ocr_confidence": 0.0,
            "complexity_tier": "",
            "model_used": "",
            "extraction_attempts": 0,
            "validation_issues": [],
            "confidence": {},
            "correction_attempts": 0,
            "correction_history": [],
            "audit_events": [],
            "final_status": "processing",
        }

        result = await graph.ainvoke(
            initial_state,
            config={
                "recursion_limit": 20
            },
        )

        hidden_fields = {
            "page_images",
            "ocr_pages",
            "ocr_text",
            "document_path",
        }

        return {
            key: _serialize_result(value)
            for key, value in result.items()
            if key not in hidden_fields
        }

    except HTTPException:
        if target_path.exists():
            target_path.unlink(
                missing_ok=True
            )

        raise

    except ValueError as exc:
        if target_path.exists():
            target_path.unlink(
                missing_ok=True
            )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception(
            "Invoice processing failed "
            "request_id=%s",
            request_id,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Processing failed. "
                f"Request ID: {request_id}"
            ),
        ) from exc

    finally:
        await file.close()

        if (
            target_path.exists()
            and target_path.stat().st_size
            > upload_limit
        ):
            target_path.unlink(
                missing_ok=True
            )

        if (
            runtime_directory.exists()
            and not any(
                runtime_directory.iterdir()
            )
        ):
            shutil.rmtree(
                runtime_directory,
                ignore_errors=True,
            )
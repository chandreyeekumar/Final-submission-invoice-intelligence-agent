from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path

import fitz
from PIL import Image

from app.core.config import get_settings


ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
ALLOWED_MIME_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/tiff"}
MAGIC_HEADERS = {
    ".pdf": (b"%PDF-",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".tif": (b"II*\x00", b"MM\x00*"),
    ".tiff": (b"II*\x00", b"MM\x00*"),
}


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_magic(path: Path) -> None:
    with path.open("rb") as handle:
        header = handle.read(16)
    expected = MAGIC_HEADERS[path.suffix.lower()]
    if not any(header.startswith(prefix) for prefix in expected):
        raise ValueError("File content does not match its extension")


def validate_upload(path: str) -> dict:
    settings = get_settings()
    p = Path(path)

    if not p.exists() or not p.is_file():
        raise ValueError("Uploaded file does not exist")
    if p.is_symlink():
        raise ValueError("Symbolic links are not accepted")

    suffix = p.suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported extension")

    size_bytes = p.stat().st_size
    if size_bytes <= 0:
        raise ValueError("Uploaded file is empty")
    if size_bytes > settings.max_upload_mb * 1024 * 1024:
        raise ValueError(f"File exceeds {settings.max_upload_mb} MB")

    _validate_magic(p)

    guessed_mime, _ = mimetypes.guess_type(p.name)
    if guessed_mime not in ALLOWED_MIME_TYPES:
        raise ValueError(f"Unsupported MIME type: {guessed_mime}")

    try:
        if suffix == ".pdf":
            with fitz.open(p) as document:
                if document.needs_pass:
                    raise ValueError("Password-protected PDFs are not accepted")
                page_count = len(document)
        elif suffix in {".tif", ".tiff"}:
            with Image.open(p) as image:
                image.verify()
            with Image.open(p) as image:
                page_count = getattr(image, "n_frames", 1)
        else:
            with Image.open(p) as image:
                image.verify()
            page_count = 1
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("File is corrupt or unreadable") from exc

    if page_count < 1:
        raise ValueError("Document has no pages")
    if page_count > settings.max_pdf_pages:
        raise ValueError(f"Document exceeds {settings.max_pdf_pages} pages")

    return {
        "mime_type": guessed_mime,
        "size_bytes": size_bytes,
        "size_mb": round(size_bytes / (1024 * 1024), 3),
        "page_count": page_count,
        "sha256": sha256_file(p),
    }

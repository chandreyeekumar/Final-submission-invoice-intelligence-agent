from __future__ import annotations

import importlib
import shutil
import sys
from pathlib import Path

from app.core.config import get_settings


REQUIRED_IMPORTS = [
    "openai",
    "pydantic",
    "fastapi",
    "langgraph",
    "chromadb",
    "sqlalchemy",
    "pytesseract",
    "pdf2image",
    "PIL",
    "fitz",
    "cv2",
    "pandas",
    "numpy",
    "reportlab",
    "faker",
    "datasets",
]


def status(
    label: str,
    ok: bool,
    detail: str,
) -> None:
    """Print a formatted environment-check result."""

    marker = "PASS" if ok else "FAIL"
    print(f"[{marker}] {label}: {detail}")


def check_python() -> bool:
    """Confirm that Python 3.11 is being used."""

    python_ok = sys.version_info[:2] == (3, 11)

    status(
        "Python",
        python_ok,
        sys.version.split()[0],
    )

    return python_ok


def check_imports() -> bool:
    """Confirm that all required Python packages can be imported."""

    overall = True

    for name in REQUIRED_IMPORTS:
        try:
            importlib.import_module(name)

            status(
                f"Import {name}",
                True,
                "available",
            )

        except Exception as exc:
            status(
                f"Import {name}",
                False,
                str(exc),
            )

            overall = False

    return overall


def check_tesseract() -> bool:
    """Confirm that the Tesseract executable exists."""

    settings = get_settings()

    configured_path = settings.tesseract_cmd
    detected_path = shutil.which("tesseract")

    tesseract = configured_path or detected_path

    tesseract_ok = bool(
        tesseract
        and Path(tesseract).exists()
    )

    status(
        "Tesseract",
        tesseract_ok,
        str(tesseract or "not found"),
    )

    return tesseract_ok


def check_poppler() -> bool:
    """Confirm that pdftoppm is available."""

    settings = get_settings()

    poppler_ok = False
    poppler_detail = "not found"

    if settings.poppler_path:
        poppler_dir = Path(settings.poppler_path)

        poppler_ok = (
            poppler_dir.exists()
            and any(
                (poppler_dir / filename).exists()
                for filename in (
                    "pdftoppm.exe",
                    "pdftoppm",
                )
            )
        )

        poppler_detail = str(poppler_dir)

    else:
        executable = shutil.which("pdftoppm")

        poppler_ok = executable is not None
        poppler_detail = str(
            executable or "not found"
        )

    status(
        "Poppler/pdftoppm",
        poppler_ok,
        poppler_detail,
    )

    return poppler_ok


def prepare_directories() -> None:
    """Create directories required by the application."""

    directories = [
        "data/vendor_master",
        "data/synthetic",
        "data/public",
        "data/runtime",
        "data/chroma",
    ]

    for directory in directories:
        path = Path(directory)
        path.mkdir(
            parents=True,
            exist_ok=True,
        )

        status(
            f"Directory {directory}",
            path.exists(),
            "ready",
        )


def check_openai_key() -> None:
    """Report API-key status without failing Volume 1."""

    settings = get_settings()
    configured = settings.has_openai_key()

    detail = (
        "configured"
        if configured
        else (
            "not configured "
            "(not required for Volume 1 data generation)"
        )
    )

    status(
        "OpenAI key",
        configured,
        detail,
    )


def main() -> None:
    """Run all environment checks."""

    overall = True

    overall &= check_python()
    overall &= check_imports()
    overall &= check_tesseract()
    overall &= check_poppler()

    prepare_directories()
    check_openai_key()

    if not overall:
        raise SystemExit(1)

    print("Environment check passed")


if __name__ == "__main__":
    main()
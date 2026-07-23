from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageOps, ImageSequence
from pdf2image import convert_from_path

from app.core.config import get_settings


def _pil_to_bgr(image: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)


def _bgr_to_pil(image: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))


def estimate_skew_angle(image_bgr: np.ndarray) -> float:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    binary = cv2.threshold(
        blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )[1]
    coords = np.column_stack(np.where(binary > 0))
    if len(coords) < 100:
        return 0.0
    angle = cv2.minAreaRect(coords)[-1]
    angle = 90 + angle if angle < -45 else angle
    angle = -float(angle)
    return 0.0 if abs(angle) > 15 else angle


def deskew(image: np.ndarray, angle: float) -> np.ndarray:
    if abs(angle) < 0.1:
        return image
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    return cv2.warpAffine(
        image,
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def preprocess_page(image: Image.Image) -> tuple[Image.Image, dict]:
    image = ImageOps.exif_transpose(image).convert("RGB")
    bgr = _pil_to_bgr(image)
    angle = estimate_skew_angle(bgr)
    bgr = deskew(bgr, angle)
    bgr = cv2.fastNlMeansDenoisingColored(bgr, None, 7, 7, 7, 21)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    lightness, channel_a, channel_b = cv2.split(lab)
    lightness = cv2.createCLAHE(2.0, (8, 8)).apply(lightness)
    bgr = cv2.cvtColor(
        cv2.merge((lightness, channel_a, channel_b)), cv2.COLOR_LAB2BGR
    )
    sharpening_kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    bgr = cv2.filter2D(bgr, -1, sharpening_kernel)
    output = ImageEnhance.Contrast(_bgr_to_pil(bgr)).enhance(1.1)
    return output, {
        "estimated_skew_angle": round(angle, 3),
        "deskew_applied": abs(angle) >= 0.1,
        "noise_reduction": "fastNlMeans",
        "contrast": "CLAHE",
    }


def _load_pages(path: str) -> list[Image.Image]:
    settings = get_settings()
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return convert_from_path(
            path,
            dpi=250,
            poppler_path=settings.poppler_path or None,
            fmt="png",
            thread_count=1,
        )
    if suffix in {".tif", ".tiff"}:
        with Image.open(path) as image:
            return [frame.copy().convert("RGB") for frame in ImageSequence.Iterator(image)]
    with Image.open(path) as image:
        return [image.copy().convert("RGB")]


def preprocess_document(path: str, output_dir: str) -> tuple[list[str], list[dict]]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    page_paths: list[str] = []
    metadata: list[dict] = []

    for page_number, page in enumerate(_load_pages(path), start=1):
        processed, page_metadata = preprocess_page(page)
        target = output / f"page_{page_number:03d}.png"
        processed.save(target, format="PNG", optimize=True)
        page_paths.append(str(target))
        metadata.append(
            {"page_number": page_number, "output_path": str(target), **page_metadata}
        )

    return page_paths, metadata

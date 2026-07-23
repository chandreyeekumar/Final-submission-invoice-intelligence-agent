from __future__ import annotations

from statistics import mean

import pytesseract
from PIL import Image
from pytesseract import Output

from app.core.config import get_settings


def run_ocr(page_paths: list[str]) -> tuple[list[dict], str, int, float]:
    settings = get_settings()
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    pages: list[dict] = []
    full_text: list[str] = []
    all_confidences: list[float] = []
    total_word_count = 0

    for page_number, path in enumerate(page_paths, start=1):
        with Image.open(path) as image:
            data = pytesseract.image_to_data(
                image,
                output_type=Output.DICT,
                lang=settings.tesseract_language,
                config="--oem 3 --psm 6",
                timeout=120,
            )

        words: list[dict] = []
        page_confidences: list[float] = []

        for index, raw_text in enumerate(data["text"]):
            text = (raw_text or "").strip()
            try:
                confidence = float(data["conf"][index])
            except (ValueError, TypeError):
                confidence = -1

            if not text or confidence < 0:
                continue

            normalized_confidence = confidence / 100.0
            words.append(
                {
                    "text": text,
                    "confidence": round(normalized_confidence, 4),
                    "bbox": {
                        "x": int(data["left"][index]),
                        "y": int(data["top"][index]),
                        "width": int(data["width"][index]),
                        "height": int(data["height"][index]),
                    },
                    "block_number": int(data["block_num"][index]),
                    "line_number": int(data["line_num"][index]),
                }
            )
            page_confidences.append(normalized_confidence)
            all_confidences.append(normalized_confidence)
            total_word_count += 1

        page_text = " ".join(word["text"] for word in words)
        pages.append(
            {
                "page_number": page_number,
                "image_path": path,
                "text": page_text,
                "word_count": len(words),
                "mean_confidence": round(mean(page_confidences), 4)
                if page_confidences
                else 0.0,
                "words": words,
            }
        )
        full_text.append(f"[PAGE {page_number}]\n{page_text}")

    overall_confidence = round(mean(all_confidences), 4) if all_confidences else 0.0
    return pages, "\n\n".join(full_text), total_word_count, overall_confidence

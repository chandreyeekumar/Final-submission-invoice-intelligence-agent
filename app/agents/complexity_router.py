def route_complexity(page_count: int, word_count: int, ocr_confidence: float) -> str:
    if page_count < 1 or word_count < 0 or not 0 <= ocr_confidence <= 1:
        raise ValueError("Invalid routing inputs")
    if page_count == 1 and word_count < 250 and ocr_confidence >= 0.80:
        return "low"
    if page_count <= 2 and word_count < 900 and ocr_confidence >= 0.60:
        return "medium"
    return "high"

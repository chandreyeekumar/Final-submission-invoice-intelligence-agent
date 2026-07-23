from app.agents.rag import (
    VendorRAG,
    compact_identifier,
    normalize,
)


def test_normalize_removes_punctuation_and_changes_to_lowercase() -> None:
    result = normalize("ACME, LLC")

    assert result == "acme llc"


def test_compact_identifier_removes_spaces_and_symbols() -> None:
    result = compact_identifier("GST-12 34")

    assert result == "gst1234"


def test_name_similarity_uses_vendor_aliases() -> None:
    metadata = {
        "legal_name": "Acme Corporation",
        "aliases_json": '["Acme Services", "Acme India"]',
    }

    similarity_score = VendorRAG._name_similarity(
        invoice_name="Acme Services",
        metadata=metadata,
    )

    assert similarity_score == 100
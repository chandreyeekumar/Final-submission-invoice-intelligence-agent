from pathlib import Path

import pytest
from PIL import Image

from app.agents.ingestion import validate_upload


def test_valid_png(tmp_path: Path):
    path = tmp_path / "invoice.png"
    Image.new("RGB", (50, 50), "white").save(path)
    metadata = validate_upload(str(path))
    assert metadata["page_count"] == 1
    assert len(metadata["sha256"]) == 64


def test_extension_spoofing_is_rejected(tmp_path: Path):
    path = tmp_path / "fake.png"
    path.write_text("not an image", encoding="utf-8")
    with pytest.raises(ValueError):
        validate_upload(str(path))

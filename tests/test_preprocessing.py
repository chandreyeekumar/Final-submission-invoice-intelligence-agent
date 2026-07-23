from PIL import Image

from app.agents.preprocessing import preprocess_page


def test_preprocess_page_returns_rgb_image_and_metadata():
    image = Image.new("RGB", (200, 100), "white")
    output, metadata = preprocess_page(image)
    assert output.mode == "RGB"
    assert "estimated_skew_angle" in metadata

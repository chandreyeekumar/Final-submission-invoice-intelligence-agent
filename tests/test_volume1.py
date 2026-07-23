import json
from pathlib import Path

from app.core.config import Settings
from scripts.generate_vendor_master import build_vendors


def test_settings_model_routing() -> None:
    """Models should be routed by complexity."""

    settings = Settings(
        openai_api_key="test-key"
    )

    assert (
        settings.model_for_complexity("low")
        == settings.openai_model_low
    )

    assert (
        settings.model_for_complexity("medium")
        == settings.openai_model_medium
    )

    assert (
        settings.model_for_complexity("high")
        == settings.openai_model_high
    )

    assert (
        settings.model_for_complexity(
            "unexpected"
        )
        == settings.openai_model_medium
    )


def test_vendor_generation_is_deterministic() -> None:
    """Repeated vendor generation should produce the same data."""

    first = build_vendors(3)
    second = build_vendors(3)

    assert first == second

    vendor_ids = {
        item["vendor_id"]
        for item in first
    }

    invoice_prefixes = {
        item["invoice_prefix"]
        for item in first
    }

    assert len(vendor_ids) == 3
    assert len(invoice_prefixes) == 3


def test_env_example_exists() -> None:
    """The public environment template should exist."""

    assert Path(
        ".env.example"
    ).exists()


def test_dockerignore_blocks_env() -> None:
    """Docker should not copy the private environment file."""

    content = (
        Path(".dockerignore")
        .read_text(encoding="utf-8")
        .splitlines()
    )

    assert ".env" in content


def test_vendor_json_shape(
    tmp_path: Path,
) -> None:
    """Generated vendors should contain a four-digit bank suffix."""

    output = (
        tmp_path / "vendors.json"
    )

    output.write_text(
        json.dumps(
            build_vendors(2)
        ),
        encoding="utf-8",
    )

    rows = json.loads(
        output.read_text(
            encoding="utf-8"
        )
    )

    bank_last4 = rows[0]["bank_last4"]

    assert bank_last4.isdigit()
    assert len(bank_last4) == 4
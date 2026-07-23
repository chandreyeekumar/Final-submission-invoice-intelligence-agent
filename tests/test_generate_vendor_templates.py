import json
from pathlib import Path

import scripts.generate_vendor_templates as template_module


def test_template_generation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    input_path = tmp_path / "vendors.json"
    output_path = tmp_path / "templates.json"

    vendor_data = [
        {
            "vendor_id": "V0001",
            "legal_name": "Acme LLC",
            "invoice_prefix": "ACM",
            "currency": "USD",
            "payment_terms": "Net 30",
            "active": True,
        }
    ]

    input_path.write_text(
        json.dumps(vendor_data),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        template_module,
        "INPUT",
        input_path,
    )

    monkeypatch.setattr(
        template_module,
        "OUTPUT",
        output_path,
    )

    template_module.main()

    generated_templates = json.loads(
        output_path.read_text(
            encoding="utf-8",
        )
    )

    assert len(generated_templates) == 1

    first_template = generated_templates[0]

    assert first_template["template_id"] == "TPL-V0001-01"
    assert first_template["vendor_id"] == "V0001"
    assert first_template["legal_name"] == "Acme LLC"
    assert first_template["invoice_number_pattern"] == "ACM-NNNNN"
    assert first_template["usual_currency"] == "USD"
from eval.adapters.cord_adapter import (
    map_cord_ground_truth,
)
from eval.adapters.sroie_adapter import (
    map_sroie_ground_truth,
)


def test_sroie_adapter() -> None:
    result = map_sroie_ground_truth(
        {
            "company": "Vendor A",
            "address": "Street",
            "date": "2026-01-01",
            "total": "10.00",
        }
    )

    assert (
        result["vendor_name"]
        == "Vendor A"
    )

    assert result["total"] == "10.00"


def test_cord_adapter_flat_dict() -> None:
    result = map_cord_ground_truth(
        {
            "valid_line": {
                "store_name": "Shop",
                "subtotal": "9",
                "tax": "1",
                "total": "10",
            }
        }
    )

    assert result == {
        "vendor_name": "Shop",
        "subtotal": "9",
        "tax_total": "1",
        "total": "10",
    }


def test_cord_adapter_list() -> None:
    result = map_cord_ground_truth(
        {
            "valid_line": [
                {
                    "store_name": "Shop"
                },
                {
                    "total": "10"
                },
            ]
        }
    )

    assert (
        result["vendor_name"]
        == "Shop"
    )

    assert result["total"] == "10"


def test_cord_adapter_invalid_value() -> None:
    result = map_cord_ground_truth(
        {
            "valid_line": "invalid"
        }
    )

    assert result == {
        "vendor_name": None,
        "subtotal": None,
        "tax_total": None,
        "total": None,
    }
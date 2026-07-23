from app.schemas.invoice import InvoiceExtraction


def test_schema_masks_bank_value_after_patch_validation():
    candidate = InvoiceExtraction.model_validate(
        {"vendor_bank_account": "999988887777"}
    )
    assert candidate.vendor_bank_account == "XXXX7777"

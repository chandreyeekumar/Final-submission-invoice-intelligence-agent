from app.schemas.invoice import InvoiceExtraction


def test_currency_is_uppercase():
    invoice = InvoiceExtraction(currency="usd")
    assert invoice.currency == "USD"


def test_bank_account_is_masked_immediately():
    invoice = InvoiceExtraction(vendor_bank_account="1234-5678-9012")
    assert invoice.vendor_bank_account == "XXXX9012"

from app.agents.confidence import compute_confidence
from app.schemas.invoice import InvoiceExtraction


def test_verified_vendor_gets_higher_confidence():
    invoice = InvoiceExtraction(vendor_name="Vendor", invoice_number="1")
    verified = compute_confidence(invoice, 0.9, [], "verified")
    unknown = compute_confidence(invoice, 0.9, [], "unknown")
    assert verified["vendor_name"] > unknown["vendor_name"]

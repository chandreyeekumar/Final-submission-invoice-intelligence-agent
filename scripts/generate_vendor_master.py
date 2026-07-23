from __future__ import annotations

import json
import random
from pathlib import Path

from faker import Faker


SEED = 42
DEFAULT_VENDOR_COUNT = 120

OUTPUT_PATH = Path(
    "data/vendor_master/vendors.json"
)


def build_vendors(
    count: int = DEFAULT_VENDOR_COUNT,
) -> list[dict]:
    """Generate a deterministic synthetic vendor master."""

    if count < 1:
        raise ValueError(
            "Vendor count must be at least 1"
        )

    fake = Faker("en_US")

    random.seed(SEED)
    Faker.seed(SEED)

    records: list[dict] = []
    used_prefixes: set[str] = set()

    for index in range(1, count + 1):
        legal_name = fake.unique.company()

        base_prefix = "".join(
            character
            for character in legal_name.upper()
            if character.isalpha()
        )[:3]

        base_prefix = (
            base_prefix
            or f"V{index:03d}"
        )

        prefix = base_prefix
        suffix = 1

        while prefix in used_prefixes:
            prefix = f"{base_prefix}{suffix}"
            suffix += 1

        used_prefixes.add(prefix)

        first_token = legal_name.split()[0]

        aliases = sorted(
            {
                legal_name
                .replace(" LLC", "")
                .replace(" Inc.", "")
                .strip(),
                f"{first_token} Services",
            }
        )

        records.append(
            {
                "vendor_id": f"V{index:04d}",
                "legal_name": legal_name,
                "aliases": aliases,
                "address": fake.address().replace(
                    "\n",
                    ", ",
                ),
                "tax_id": f"TAX{index:08d}",
                "currency": random.choice(
                    [
                        "USD",
                        "INR",
                        "EUR",
                    ]
                ),
                "payment_terms": random.choice(
                    [
                        "Net 15",
                        "Net 30",
                        "Net 45",
                    ]
                ),
                "invoice_prefix": prefix,
                "bank_last4": (
                    f"{random.randint(0, 9999):04d}"
                ),
                "active": True,
            }
        )

    return records


def main() -> None:
    """Generate and save the vendor master."""

    records = build_vendors()

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            records,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"Created {len(records)} vendors "
        f"at {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
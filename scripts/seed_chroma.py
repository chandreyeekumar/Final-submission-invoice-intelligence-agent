from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import chromadb

from app.core.config import get_settings
from app.core.embeddings import HashEmbeddingFunction


VENDOR_PATH = Path(
    "data/vendor_master/vendors.json"
)

TEMPLATE_PATH = Path(
    "data/vendor_templates/templates.json"
)

COLLECTION_METADATA = {
    "hnsw:space": "cosine",
    "schema_version": "1",
}


def load_json_list(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found: {path}"
        )

    payload = json.loads(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(payload, list) or not payload:
        raise ValueError(
            f"Expected a non-empty JSON list in {path}"
        )

    if not all(
        isinstance(item, dict)
        for item in payload
    ):
        raise ValueError(
            f"Every item in {path} must be a JSON object"
        )

    return payload


def collection(
    client: Any,
    name: str,
    embedding_function: HashEmbeddingFunction,
):
    return client.get_or_create_collection(
        name=name,
        embedding_function=embedding_function,
        metadata=COLLECTION_METADATA,
    )


def vendor_document(vendor: dict) -> str:
    aliases = ", ".join(
        str(item)
        for item in vendor.get("aliases", [])
    )

    return (
        f"Vendor {vendor['legal_name']}. "
        f"Aliases {aliases}. "
        f"Address {vendor.get('address', '')}. "
        f"Tax ID {vendor.get('tax_id', '')}. "
        f"Currency {vendor.get('currency', '')}. "
        f"Payment terms "
        f"{vendor.get('payment_terms', '')}. "
        f"Invoice prefix "
        f"{vendor.get('invoice_prefix', '')}."
    )


def template_document(template: dict) -> str:
    labels = json.dumps(
        template.get("expected_labels", {}),
        sort_keys=True,
    )

    columns = ", ".join(
        str(item)
        for item in template.get(
            "usual_table_columns",
            [],
        )
    )

    return (
        f"Invoice template for "
        f"{template['legal_name']}. "
        f"Layout "
        f"{template.get('layout_description', '')}. "
        f"Labels {labels}. "
        f"Pattern "
        f"{template.get('invoice_number_pattern', '')}. "
        f"Currency "
        f"{template.get('usual_currency', '')}. "
        f"Terms "
        f"{template.get('usual_payment_terms', '')}. "
        f"Columns {columns}."
    )


def main() -> None:
    settings = get_settings()

    chroma_path = Path(
        settings.chroma_path
    )

    chroma_path.mkdir(
        parents=True,
        exist_ok=True,
    )

    dimensions = int(
        getattr(
            settings,
            "rag_embedding_dimensions",
            384,
        )
    )

    embedding_function = HashEmbeddingFunction(
        dimensions=dimensions
    )

    client = chromadb.PersistentClient(
        path=str(chroma_path)
    )

    vendors = load_json_list(
        VENDOR_PATH
    )

    vendor_collection = collection(
        client,
        settings.chroma_vendor_collection,
        embedding_function,
    )

    vendor_collection.upsert(
        ids=[
            str(v["vendor_id"])
            for v in vendors
        ],
        documents=[
            vendor_document(v)
            for v in vendors
        ],
        metadatas=[
            {
                "vendor_id": str(
                    v["vendor_id"]
                ),
                "legal_name": str(
                    v["legal_name"]
                ),
                "tax_id": str(
                    v.get("tax_id", "")
                ),
                "currency": str(
                    v.get("currency", "")
                ),
                "bank_last4": str(
                    v.get("bank_last4", "")
                ),
                "invoice_prefix": str(
                    v.get("invoice_prefix", "")
                ),
                "aliases_json": json.dumps(
                    v.get("aliases", [])
                ),
                "active": bool(
                    v.get("active", True)
                ),
                "kb_version": str(
                    settings.rag_knowledge_base_version
                ),
                "schema_version": "1",
            }
            for v in vendors
        ],
    )

    templates = load_json_list(
        TEMPLATE_PATH
    )

    template_collection = collection(
        client,
        settings.chroma_template_collection,
        embedding_function,
    )

    template_collection.upsert(
        ids=[
            str(t["template_id"])
            for t in templates
        ],
        documents=[
            template_document(t)
            for t in templates
        ],
        metadatas=[
            {
                "template_id": str(
                    t["template_id"]
                ),
                "vendor_id": str(
                    t["vendor_id"]
                ),
                "legal_name": str(
                    t["legal_name"]
                ),
                "invoice_number_pattern": str(
                    t.get(
                        "invoice_number_pattern",
                        "",
                    )
                ),
                "currency": str(
                    t.get(
                        "usual_currency",
                        "",
                    )
                ),
                "active": bool(
                    t.get("active", True)
                ),
                "kb_version": str(
                    settings.rag_knowledge_base_version
                ),
                "schema_version": "1",
            }
            for t in templates
        ],
    )

    collection(
        client,
        settings.chroma_history_collection,
        embedding_function,
    )

    print(
        "Seeded vendor master and templates, "
        "and initialized approved history."
    )


if __name__ == "__main__":
    main()
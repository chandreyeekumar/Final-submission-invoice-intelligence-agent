from __future__ import annotations

from pathlib import Path

import chromadb

from app.core.config import get_settings
from app.core.embeddings import (
    HashEmbeddingFunction,
)


def main() -> None:
    settings = get_settings()

    if not Path(
        settings.chroma_path
    ).exists():
        raise FileNotFoundError(
            "Chroma path does not exist. "
            "Run python scripts/seed_chroma.py"
        )

    embedding_function = (
        HashEmbeddingFunction(
            dimensions=int(
                getattr(
                    settings,
                    "rag_embedding_dimensions",
                    384,
                )
            )
        )
    )

    client = chromadb.PersistentClient(
        path=settings.chroma_path
    )

    expected = [
        settings.chroma_vendor_collection,
        settings.chroma_template_collection,
        settings.chroma_history_collection,
    ]

    for name in expected:
        collection = client.get_collection(
            name=name,
            embedding_function=(
                embedding_function
            ),
        )

        metadata = (
            collection.metadata or {}
        )

        space = metadata.get(
            "hnsw:space",
            "unknown",
        )

        schema_version = metadata.get(
            "schema_version",
            "unknown",
        )

        print(
            f"{name}: "
            f"{collection.count()} records | "
            f"space={space} | "
            f"schema_version={schema_version}"
        )


if __name__ == "__main__":
    main()
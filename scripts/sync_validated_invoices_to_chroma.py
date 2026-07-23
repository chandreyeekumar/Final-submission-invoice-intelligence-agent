from __future__ import annotations

from sqlalchemy import select

from app.db.models import Document
from app.db.session import session_scope
from app.services.knowledge_sync import (
    sync_approved_invoice,
)


def main() -> None:
    with session_scope() as session:
        document_ids = list(
            session.scalars(
                select(Document.id)
            )
        )

        synchronized = sum(
            1
            for document_id
            in document_ids
            if sync_approved_invoice(
                session,
                str(document_id),
            )
        )

    print(
        f"Synchronized {synchronized} "
        f"approved invoice summaries"
    )


if __name__ == "__main__":
    main()
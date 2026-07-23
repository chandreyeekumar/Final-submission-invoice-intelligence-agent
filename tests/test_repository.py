from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import models  # noqa: F401
from app.db.base import Base, DocumentStatus
from app.db.models import DocumentStatusHistory
from app.db.repositories.repository import Repository


def test_create_document_and_status(
    tmp_path: Path,
) -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    Base.metadata.create_all(engine)

    test_file = tmp_path / "x.pdf"
    test_file.write_bytes(b"%PDF-1.4")

    with Session(engine) as session:
        repository = Repository(session)

        document = repository.create_document(
            request_id="r1",
            filename="x.pdf",
            path=str(test_file),
            info={
                "mime_type": "application/pdf",
                "page_count": 1,
            },
        )

        session.commit()

        history = list(
            session.scalars(
                select(DocumentStatusHistory)
            )
        )

        assert (
            document.status
            == DocumentStatus.RECEIVED
        )

        assert len(document.sha256 or "") == 64
        assert document.size_bytes == len(
            b"%PDF-1.4"
        )

        assert len(history) == 1
        assert (
            history[0].new_status
            == DocumentStatus.RECEIVED.value
        )
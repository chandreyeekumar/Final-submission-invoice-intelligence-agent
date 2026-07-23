from sqlalchemy import create_engine, inspect

from app.db import models  # noqa: F401
from app.db.base import Base


EXPECTED_TABLES = {
    "documents",
    "invoices",
    "validation_issues",
    "correction_history",
    "rag_evidence",
    "rag_candidates",
    "safety_decisions",
    "audit_events",
    "document_status_history",
}


def test_all_tables_register_and_create() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    Base.metadata.create_all(engine)

    table_names = set(
        inspect(engine).get_table_names()
    )

    assert EXPECTED_TABLES <= table_names
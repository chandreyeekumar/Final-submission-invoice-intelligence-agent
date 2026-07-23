from __future__ import annotations

from sqlalchemy import inspect

from app.db.session import engine


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


def main() -> None:
    inspector = inspect(engine)
    found_tables = set(
        inspector.get_table_names()
    )

    missing_tables = (
        EXPECTED_TABLES - found_tables
    )

    if missing_tables:
        raise SystemExit(
            "Missing tables: "
            f"{sorted(missing_tables)}"
        )

    print(
        "Database verified: "
        f"{len(found_tables)} tables"
    )

    for table_name in sorted(
        EXPECTED_TABLES
    ):
        print(f"  OK: {table_name}")


if __name__ == "__main__":
    main()
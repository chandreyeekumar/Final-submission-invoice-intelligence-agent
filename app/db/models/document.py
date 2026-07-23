from __future__ import annotations

import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    Integer,
    String,
    Text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import (
    Base,
    DocumentStatus,
    TimestampMixin,
)


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    request_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )

    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    stored_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    mime_type: Mapped[str | None] = mapped_column(
        String(100)
    )

    sha256: Mapped[str | None] = mapped_column(
        String(64),
        index=True,
    )

    size_bytes: Mapped[int | None] = mapped_column(
        BigInteger
    )

    page_count: Mapped[int | None] = mapped_column(
        Integer
    )

    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(
            DocumentStatus,
            native_enum=False,
            values_callable=lambda enum_class: [
                item.value for item in enum_class
            ],
        ),
        default=DocumentStatus.RECEIVED,
        nullable=False,
        index=True,
    )

    status_reason: Mapped[str | None] = mapped_column(
        Text
    )

    human_review_required: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
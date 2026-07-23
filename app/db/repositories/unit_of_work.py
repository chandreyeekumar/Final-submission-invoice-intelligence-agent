from __future__ import annotations

from types import TracebackType

from sqlalchemy.orm import Session

from app.db.session import session_scope


class UnitOfWork:
    session: Session

    def __enter__(self) -> "UnitOfWork":
        self._context = session_scope()
        self.session = self._context.__enter__()
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        return self._context.__exit__(
            exception_type,
            exception,
            traceback,
        )
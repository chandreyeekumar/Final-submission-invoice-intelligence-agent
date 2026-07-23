from time import perf_counter
from types import TracebackType
from typing import Any

from app.core.config import get_settings


def usage_value(
    usage: object | None,
    name: str,
) -> int:
    """Safely read a token-usage value from an object or dictionary."""

    if usage is None:
        return 0

    value = getattr(usage, name, None)

    if value is None and isinstance(usage, dict):
        value = usage.get(name)

    return int(value or 0)


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """
    Estimate request cost using configured rates.

    This function produces an internal estimate only. It is not an
    authoritative billing calculation.
    """

    del model

    settings = get_settings()

    value = (
        input_tokens
        / 1_000_000
        * settings.openai_input_usd_per_million
        + output_tokens
        / 1_000_000
        * settings.openai_output_usd_per_million
    )

    return round(value, 8)


class Timer:
    """Context manager used to measure elapsed processing time."""

    started: float
    elapsed: float

    def __enter__(self) -> "Timer":
        self.started = perf_counter()
        self.elapsed = 0.0
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback

        self.elapsed = perf_counter() - self.started
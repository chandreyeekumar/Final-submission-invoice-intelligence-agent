from __future__ import annotations

import inspect
from typing import Any


async def call_with_optional_telemetry(
    function,
    *args: Any,
    telemetry: list[dict[str, Any]],
) -> Any:
    """Call an async function with telemetry only if supported."""

    signature = inspect.signature(function)
    parameters = list(
        signature.parameters.values()
    )

    accepts_varargs = any(
        parameter.kind
        == inspect.Parameter.VAR_POSITIONAL
        for parameter in parameters
    )

    positional_parameters = [
        parameter
        for parameter in parameters
        if parameter.kind
        in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        }
    ]

    if (
        accepts_varargs
        or len(positional_parameters)
        >= len(args) + 1
    ):
        return await function(
            *args,
            telemetry,
        )

    return await function(*args)


def model_dump_json(
    value: Any,
) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(
            mode="json"
        )

    if isinstance(value, dict):
        return value

    raise TypeError(
        "Expected a Pydantic model or dictionary, "
        f"received {type(value).__name__}"
    )
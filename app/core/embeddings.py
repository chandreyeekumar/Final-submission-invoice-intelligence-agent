from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable


class HashEmbeddingFunction:
    """Deterministic offline embedding function for the capstone.

    This implementation downloads no model and produces the same vector for
    the same text on every machine. It is suitable for offline demonstrations
    and deterministic tests, but it is not a replacement for a governed
    semantic embedding model in production.
    """

    def __init__(self, dimensions: int = 384) -> None:
        if dimensions < 32:
            raise ValueError("dimensions must be at least 32")
        self.dimensions = int(dimensions)

    @staticmethod
    def name() -> str:
        return "invoice_hash_embedding_v1"

    def get_config(self) -> dict[str, int]:
        return {"dimensions": self.dimensions}

    @staticmethod
    def validate_config(config: dict) -> None:
        dimensions = int(config.get("dimensions", 0))
        if dimensions < 32:
            raise ValueError("dimensions must be at least 32")

    @classmethod
    def build_from_config(cls, config: dict) -> "HashEmbeddingFunction":
        cls.validate_config(config)
        return cls(dimensions=int(config["dimensions"]))

    def __call__(self, input: Iterable[str]) -> list[list[float]]:
        return [self._embed(str(text or "")) for text in input]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"[a-z0-9]+", text.lower())

        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.blake2b(
                token.encode("utf-8"),
                digest_size=16,
            ).digest()

            index = int.from_bytes(digest[:8], "big") % self.dimensions
            sign = 1.0 if digest[8] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))

        if norm == 0:
            return vector

        return [value / norm for value in vector]
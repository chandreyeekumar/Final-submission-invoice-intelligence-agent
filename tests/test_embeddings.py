from app.core.embeddings import HashEmbeddingFunction


def test_hash_embedding_is_deterministic_and_normalized() -> None:
    embedding_function = HashEmbeddingFunction(dimensions=64)

    first_vector = embedding_function(["Acme invoice 123"])[0]
    second_vector = embedding_function(["Acme invoice 123"])[0]

    assert first_vector == second_vector
    assert len(first_vector) == 64

    squared_norm = sum(value * value for value in first_vector)

    assert abs(squared_norm - 1.0) < 1e-9


def test_empty_text_returns_zero_vector() -> None:
    embedding_function = HashEmbeddingFunction(dimensions=64)

    result = embedding_function([""])[0]

    assert result == [0.0] * 64
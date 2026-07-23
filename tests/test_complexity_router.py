import pytest

from app.agents.complexity_router import route_complexity


def test_low_complexity():
    assert route_complexity(1, 100, 0.9) == "low"


def test_medium_complexity():
    assert route_complexity(2, 500, 0.75) == "medium"


def test_high_complexity():
    assert route_complexity(3, 1000, 0.5) == "high"


def test_invalid_inputs():
    with pytest.raises(ValueError):
        route_complexity(0, 1, 0.9)

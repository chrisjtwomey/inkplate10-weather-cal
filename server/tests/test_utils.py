"""even_select, in `utils.py`."""
from utils import even_select


def test_even_select_picks_n_evenly_spaced():
    # round() uses banker's rounding, so 4.5 rounds to 4.
    assert even_select(3, list(range(10))) == [0, 4, 9]


def test_even_select_n_equals_one():
    assert even_select(1, [10, 20, 30]) == [10]


def test_even_select_n_equals_len():
    assert even_select(4, ["a", "b", "c", "d"]) == ["a", "b", "c", "d"]

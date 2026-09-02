"""Cover the helpers that remain local to this project in `utils.py`.

The env-override resolver (`get_prop`, `get_prop_by_keys`, ...) now lives in
`epd_server.config` and is tested there.
"""
from utils import even_select, get_prop, get_prop_by_keys


# ---------- even_select ----------

def test_even_select_picks_n_evenly_spaced():
    # round() uses banker's rounding, so 4.5 rounds to 4.
    assert even_select(3, list(range(10))) == [0, 4, 9]


def test_even_select_n_equals_one():
    assert even_select(1, [10, 20, 30]) == [10]


def test_even_select_n_equals_len():
    assert even_select(4, ["a", "b", "c", "d"]) == ["a", "b", "c", "d"]


# ---------- re-export smoke test ----------

def test_resolver_reexports_still_work(monkeypatch):
    cfg = {"server": {"port": 8080}, "location": "Cork"}
    assert get_prop_by_keys(cfg, "server", "port") == 8080
    monkeypatch.setenv("LOCATION", "Galway")
    assert get_prop(cfg, "location") == "Galway"

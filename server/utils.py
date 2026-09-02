"""Config helpers.

Config resolution now lives in ``epd_server.config``; the names are
re-exported here so existing imports keep working. ``even_select`` is a
weather-specific sampling helper and stays local.
"""
from epd_server.config import (  # noqa: F401  (re-exported)
    _coerce_env,
    _env_name,
    _resolve,
    get_by_path,
)
from epd_server.config import get_prop as _get_prop
from epd_server.config import get_prop_by_keys as _get_prop_by_keys


def get_prop_by_keys(config, *keys, default=None, required=True, dehumanized=False):
    return _get_prop_by_keys(config, *keys, default=default, required=required)


def get_prop(config, prop, default=None, required=True, dehumanized=False):
    return _get_prop(config, prop, default=default, required=required)


def even_select(n, l):
    """Pick ``n`` evenly spaced entries from ``l`` (first and last included)."""
    if n == 1:
        return [l[0]]
    return [l[round(i * (len(l) - 1) / (n - 1))] for i in range(n)]

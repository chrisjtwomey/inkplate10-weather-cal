"""Config helpers.

Re-exports the resolver from ``epd_server.config`` under this module's
import path, and holds ``even_select``, a weather-specific sampling helper.
"""
from epd_server.config import get_by_path, get_prop, get_prop_by_keys  # noqa: F401  (re-exported)


def even_select(n, l):
    """Pick ``n`` evenly spaced entries from ``l`` (first and last included)."""
    if n == 1:
        return [l[0]]
    return [l[round(i * (len(l) - 1) / (n - 1))] for i in range(n)]

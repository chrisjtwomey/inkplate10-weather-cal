"""Shared JSON-backed disk cache for weather service responses.

Re-exports ``DiskCache`` from ``epd_server.cache`` under the path the
providers import it from (``from ..cache import DiskCache``).
"""
from epd_server.cache import DEFAULT_TTL, DiskCache  # noqa: F401  (re-exported)

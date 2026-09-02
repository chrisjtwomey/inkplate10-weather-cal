"""Shared JSON-backed disk cache for weather service responses.

Now provided by ``epd_server.cache``; re-exported here so provider imports
(``from ..cache import DiskCache``) keep working.
"""
from epd_server.cache import DEFAULT_TTL, DiskCache  # noqa: F401  (re-exported)

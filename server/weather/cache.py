"""Shared JSON-backed disk cache for weather service responses."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path

DEFAULT_TTL = 3300.0  # 55 minutes

log = logging.getLogger(__name__)


def _json_default(obj):
    if isinstance(obj, datetime):
        return {"__dt__": obj.isoformat()}
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _json_hook(d: dict):
    if "__dt__" in d:
        return datetime.fromisoformat(d["__dt__"])
    return d


class DiskCache:
    """A simple JSON file-backed key/value cache with per-entry TTL.

    Usage::

        cache = DiskCache(Path(__file__).parent / ".cache.json", "MyService")

        # TTL-based (default 55 min)
        data = cache.get("forecast")          # None on miss/expiry
        cache.set("forecast", payload)

        # Indefinite (e.g. geocoding results)
        coords = cache.get("coords", ttl=None)
        cache.set("coords", {"lat": ..., "lon": ...})

        # Invalidate computed results without clearing coords
        cache.delete("forecast", "daily_summary", "hourly_forecast")
    """

    def __init__(self, path: str | Path, service_name: str = ""):
        self._path = Path(path)
        self._service_name = service_name or str(self._path)

    # ── Low-level I/O ─────────────────────────────────────────────────────

    def load(self) -> dict:
        try:
            with open(self._path) as f:
                return json.load(f, object_hook=_json_hook)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save(self, data: dict) -> None:
        try:
            with open(self._path, "w") as f:
                json.dump(data, f, default=_json_default)
        except OSError as exc:
            log.warning("Could not write %s cache: %s", self._service_name, exc)

    # ── Public API ────────────────────────────────────────────────────────

    def get(self, key: str, ttl: float | None = DEFAULT_TTL):
        """Return cached data for *key*, or ``None`` if absent or expired.

        Pass ``ttl=None`` to disable expiry (cache indefinitely).
        """
        entry = self.load().get(key)
        if entry is None:
            return None
        if ttl is not None and time.time() - entry.get("__ts__", 0) >= ttl:
            return None
        log.debug("%s cache hit: %s", self._service_name, key)
        return entry["__data__"]

    def set(self, key: str, data) -> None:
        """Store *data* under *key*, recording the current timestamp."""
        cache = self.load()
        cache[key] = {"__ts__": time.time(), "__data__": data}
        self.save(cache)

    def delete(self, *keys: str) -> None:
        """Remove *keys* from the cache (silently ignores missing keys)."""
        cache = self.load()
        if not any(k in cache for k in keys):
            return
        for key in keys:
            cache.pop(key, None)
        self.save(cache)

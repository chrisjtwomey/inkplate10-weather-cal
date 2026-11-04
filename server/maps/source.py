"""The map image of the configured place, kept on disk, for any provider."""
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Protocol

import requests
from epd_server.source import DataSource

log = logging.getLogger(__name__)


class MapFetchError(Exception):
    """The map could not be downloaded. Its message holds no URL, since a
    URL can hold the API key and this reaches the log."""


def download(url: str) -> bytes:
    """The body at ``url``. Raises MapFetchError."""
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
    except requests.RequestException as exc:
        raise MapFetchError(type(exc).__name__) from None
    return r.content


def _is_coordinates(centre: str) -> bool:
    try:
        return len([float(n) for n in centre.split(",")]) == 2
    except ValueError:
        return False


class MapProvider(Protocol):
    # True when the provider can draw a map centred on a place name.
    centres_on_a_name: bool

    def centre(self, place: str) -> str | None:
        """``"lat,lon"``, or None when there was no answer. A provider that
        centres on a name may give the name back, and that answer is kept."""

    def image_url(self, centre: str) -> str:
        """What the image depends on. A change to it fetches a new image."""

    def fetch(self, url: str) -> bytes:
        """The PNG. Raises MapFetchError."""


class MapCache:
    """The map of one place, kept in ``cache_dir``. Keep that folder across
    redeploys: each fetch is a request the provider counts."""

    def __init__(self, provider: MapProvider, cache_dir: str):
        self.provider = provider
        self._cache_dir = cache_dir
        self._cache_path = os.path.join(cache_dir, "map.json")

    def _load(self):
        try:
            with open(self._cache_path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save(self, cache):
        try:
            os.makedirs(self._cache_dir, exist_ok=True)
            with open(self._cache_path, "w") as f:
                json.dump(cache, f)
        except OSError as exc:
            log.warning("Could not write the map cache: %s", exc)

    def _forget_image(self, cache):
        filename = (cache.pop("static_map_image", None) or {}).get("filename")
        if filename:
            try:
                os.remove(os.path.join(self._cache_dir, filename))
            except FileNotFoundError:
                pass

    def _centre(self, cache, place):
        entry = cache.get("location_center")
        if entry and entry.get("location") == place and (
                self.provider.centres_on_a_name or _is_coordinates(entry["data"])):
            return entry["data"]
        if entry and entry.get("location") != place:
            log.info("Location changed (%s -> %s); fetching a new map", entry.get("location"), place)
            self._forget_image(cache)
        cache.pop("location_center", None)
        centre = self.provider.centre(place)
        if centre is not None:
            cache["location_center"] = {"ts": time.time(), "location": place, "data": centre}
        elif self.provider.centres_on_a_name:
            # Not kept, so a later fetch asks for the coordinates again.
            centre = place
        else:
            raise MapFetchError(f"no coordinates for {place}")
        return centre

    def local_src(self, place: str) -> str:
        """The map as a ``file://`` address, downloaded only if it is not kept.

        Raises:
            MapFetchError: the download failed.
        """
        cache = self._load()
        try:
            url = self.provider.image_url(self._centre(cache, place))
        finally:
            self._save(cache)

        entry = cache.get("static_map_image")
        if entry and entry.get("location") == place and entry.get("url") == url:
            path = os.path.join(self._cache_dir, entry.get("filename") or "")
            if entry.get("filename") and os.path.exists(path):
                return Path(path).resolve().as_uri()

        png = self.provider.fetch(url)
        self._forget_image(cache)
        filename = "staticmap_{}.png".format(hashlib.sha1(url.encode("utf-8")).hexdigest()[:16])
        path = os.path.join(self._cache_dir, filename)
        os.makedirs(self._cache_dir, exist_ok=True)
        with open(path, "wb") as f:
            f.write(png)
        cache["static_map_image"] = {"ts": time.time(), "location": place, "url": url, "filename": filename}
        self._save(cache)
        return Path(path).resolve().as_uri()


class StaticMapSource(DataSource):
    """``map_url`` for the pages, fetched when a page first needs it. A failed
    fetch gives a page with no map, and the next render tries again."""

    def __init__(self, cache: MapCache, location: str):
        self.cache = cache
        self.location = location

    def _map_url(self):
        try:
            return self.cache.local_src(self.location)
        except (MapFetchError, OSError) as exc:
            log.warning("No map for this render: %s", exc)
            return ""

    def datasets(self):
        return {"map_url": self._map_url}

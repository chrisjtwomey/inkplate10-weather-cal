import json
import hashlib
import logging
import os
import time
import requests
from PIL import Image
from googlemaps import Client
from googlemaps.geocoding import geocode
from googlemaps.timezone import timezone


log = logging.getLogger(__name__)


class GoogleAPIService:
    def __init__(self, key):
        self.apikey = key
        self.client = Client(key)
        google_dir = os.path.dirname(os.path.realpath(__file__))
        self._cache_path = os.path.join(
            google_dir,
            ".cache.json",
        )
        self._local_map_rel_dir = "map-cache"
        self._local_map_abs_dir = os.path.normpath(
            os.path.join(google_dir, "..", "views", "html", self._local_map_rel_dir)
        )

    def _load_cache(self):
        try:
            with open(self._cache_path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_cache(self, cache):
        try:
            with open(self._cache_path, "w") as f:
                json.dump(cache, f)
        except OSError as exc:
            log.warning("Could not write Google static maps cache: %s", exc)

    def _location_cache_key(self, location):
        if isinstance(location, (list, tuple)) and len(location) == 2:
            return "{:.6f},{:.6f}".format(float(location[0]), float(location[1]))
        return str(location)

    def _invalidate_static_map_cache(self, cache):
        image_entry = cache.get("static_map_image")
        filename = image_entry.get("filename") if image_entry else None
        if filename:
            try:
                os.remove(os.path.join(self._local_map_abs_dir, filename))
            except FileNotFoundError:
                pass
        cache.pop("location_center", None)
        cache.pop("static_map_url", None)
        cache.pop("static_map_image", None)

    def get_timezone(self, location):
        tz = timezone(self.client, location)
        print(tz)
        return tz

    def get_static_map_url(self, map_id, location):
        cache = self._load_cache()
        location_key = self._location_cache_key(location)

        # Mirror AccuWeather behavior: location changes invalidate stale entries.
        center_entry = cache.get("location_center")
        if center_entry and center_entry.get("location") != location_key:
            log.info(
                "Location changed (%s -> %s); invalidating Google static map cache",
                center_entry.get("location"),
                location_key,
            )
            self._invalidate_static_map_cache(cache)

        center_entry = cache.get("location_center")
        if center_entry and center_entry.get("location") == location_key:
            center = center_entry["data"]
        else:
            center = self._get_location_center(location)
            cache["location_center"] = {
                "ts": time.time(),
                "location": location_key,
                "data": center,
            }

        svc = self.StaticMapService(self.apikey, map_id)
        static_entry = cache.get("static_map_url")
        if (
            static_entry
            and static_entry.get("location") == location_key
            and static_entry.get("map_id") == map_id
            and static_entry.get("center") == center
        ):
            return static_entry["data"]

        url = svc.get_url(center)
        cache["static_map_url"] = {
            "ts": time.time(),
            "location": location_key,
            "map_id": map_id,
            "center": center,
            "data": url,
        }
        self._save_cache(cache)
        return url

    def get_static_map_local_src(self, map_id, location):
        location_key = self._location_cache_key(location)

        url = self.get_static_map_url(map_id, location)
        cache = self._load_cache()

        image_entry = cache.get("static_map_image")
        if (
            image_entry
            and image_entry.get("location") == location_key
            and image_entry.get("map_id") == map_id
            and image_entry.get("url") == url
        ):
            filename = image_entry.get("filename")
            abs_path = os.path.join(self._local_map_abs_dir, filename)
            if filename and os.path.exists(abs_path):
                return f"{self._local_map_rel_dir}/{filename}"

        os.makedirs(self._local_map_abs_dir, exist_ok=True)
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
        filename = f"staticmap_{digest}.png"
        abs_path = os.path.join(self._local_map_abs_dir, filename)

        r = requests.get(url, timeout=20)
        r.raise_for_status()
        with open(abs_path, "wb") as f:
            f.write(r.content)

        cache["static_map_image"] = {
            "ts": time.time(),
            "location": location_key,
            "map_id": map_id,
            "url": url,
            "filename": filename,
        }
        self._save_cache(cache)
        return f"{self._local_map_rel_dir}/{filename}"

    def _get_location_center(self, location):
        # Use coordinates for a stable map center even when place-name geocoding shifts.
        if isinstance(location, (list, tuple)) and len(location) == 2:
            return "{:.6f},{:.6f}".format(float(location[0]), float(location[1]))

        if isinstance(location, str):
            try:
                geocode_result = geocode(self.client, location)
                if len(geocode_result) > 0:
                    point = geocode_result[0]["geometry"]["location"]
                    return "{:.6f},{:.6f}".format(point["lat"], point["lng"])
            except Exception:
                pass

        return location

    class StaticMapService:
        DEFAULT_ZOOM = 10

        def __init__(self, apikey, map_id, cache=True):
            self.base_url = "https://maps.googleapis.com/maps/api/staticmap"
            self.apikey = apikey
            self.map_id = map_id
            self.scale = 2

            self.map_width = 600
            self.map_height = 600

            self.cache = cache

        def get_url(self, location, zoom=DEFAULT_ZOOM):
            no_cache_param = ""
            if not self.cache:
                no_cache_param = "&time={}".format(time.time())

            url = "{}?center={}&zoom={}&size={}x{}&key={}&map_id={}&scale={}&sensor=false{}".format(
                self.base_url,
                location,
                zoom,
                self.map_width,
                self.map_height,
                self.apikey,
                self.map_id,
                self.scale,
                no_cache_param,
            )

            return url

        def get_image(self, location, zoom=DEFAULT_ZOOM):
            r = requests.get(self.get_url(location, zoom))
            img = Image.open(r.raw)

            return img

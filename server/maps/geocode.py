"""A place's coordinates from Open-Meteo's place search, which needs no key."""
import logging

import requests

log = logging.getLogger(__name__)

URL = "https://geocoding-api.open-meteo.com/v1/search"


def open_meteo_centre(place: str) -> str | None:
    """``"lat,lon"`` of the first match, or None on no answer or no match."""
    try:
        r = requests.get(URL, params={"name": place, "count": 1, "format": "json"}, timeout=20)
        r.raise_for_status()
        found = r.json().get("results")
    except (requests.RequestException, ValueError) as exc:
        log.warning("Could not look up %s: %s", place, type(exc).__name__)
        return None
    if not found:
        log.warning("No place called %s", place)
        return None
    return "{:.6f},{:.6f}".format(found[0]["latitude"], found[0]["longitude"])

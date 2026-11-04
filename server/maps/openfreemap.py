"""OpenFreeMap, drawn by MapLibre in the same Chromium that renders the pages.

OpenFreeMap serves map data, not images, so the server draws the map itself.
"""
import base64
import io
import json
import os
import tempfile
import time
from urllib.parse import urlsplit

from PIL import Image, ImageDraw, ImageFont
from epd_server.render import ChromiumRenderer
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service

from .geocode import open_meteo_centre
from .source import MapFetchError, download

STYLE_URL = "https://tiles.openfreemap.org/styles/bright"
MAPLIBRE = "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"
MAPLIBRE_SHA384 = "sha384-SYKAG6cglRMN0RVvhNeBY0r3FYKNOJtznwA0v7B5Vp9tr31xAHsZC0DqkQ/pZDmj"
ZOOM = 9
LOAD_SECONDS = 60
# The greys of the Geoapify map, for the panel's four greys.
WATER, ROAD, PLACE_NAME = "#666666", "#808080", "#000000"
ROAD_LAYERS = ("highway-", "bridge-", "tunnel-")
# The words OpenFreeMap asks for where its MapLibre credit cannot show.
CREDIT = "OpenFreeMap © OpenMapTiles Data from OpenStreetMap"

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<script src="%(maplibre)s" integrity="%(maplibre_sha384)s" crossorigin="anonymous"></script>
<style>html,body,#map{margin:0;width:600px;height:600px}</style></head><body><div id="map"></div><script>
window.state = "loading";
try {
  window.map = new maplibregl.Map({container: "map", style: %(style)s, center: [%(lon)s, %(lat)s],
    zoom: %(zoom)s, pixelRatio: 2, interactive: false, attributionControl: false, fadeDuration: 0,
    preserveDrawingBuffer: true});
  map.on("idle", () => { window.state = "done"; });
  map.on("error", e => { window.state = "error: " + (e.error && e.error.message); });
} catch (e) { window.state = "error: " + e.message; }
</script></body></html>"""


def greyed(style: dict) -> dict:
    """``style`` with dark water, thin grey roads with no edges, and black
    place names, as the Geoapify map has them."""
    for layer in style["layers"]:
        name, paint = layer["id"], layer.setdefault("paint", {})
        if name.startswith("water") and layer["type"] in ("fill", "line"):
            paint["fill-color" if layer["type"] == "fill" else "line-color"] = WATER
        elif name.startswith(ROAD_LAYERS) and layer["type"] == "line":
            if name.endswith("-casing"):
                layer.setdefault("layout", {})["visibility"] = "none"
            else:
                paint["line-color"] = ROAD
                paint["line-width"] = 2 if "motorway" in name else 1
        elif name.startswith("label_"):
            paint["text-color"] = PLACE_NAME
    return style


def draw_in_chromium(page_html: str) -> bytes:
    """The PNG of the map that ``page_html`` draws. Raises MapFetchError."""
    renderer = ChromiumRenderer()
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "map.html")
        with open(path, "w") as f:
            f.write(page_html)
        try:
            service = Service(renderer.driver_path) if renderer.driver_path else None
            driver = webdriver.Chrome(service=service, options=renderer.options(600, 600))
        except WebDriverException as exc:
            raise MapFetchError(f"Chromium did not start: {type(exc).__name__}") from None
        try:
            driver.get("file://" + path)
            state = "loading"
            deadline = time.monotonic() + LOAD_SECONDS
            while state == "loading" and time.monotonic() < deadline:
                time.sleep(0.5)
                state = driver.execute_script("return window.state")
            if state != "done":
                raise MapFetchError(f"the map did not load: {state}")
            data_url = driver.execute_script("return window.map.getCanvas().toDataURL('image/png')")
        except WebDriverException as exc:
            raise MapFetchError(f"Chromium failed: {type(exc).__name__}") from None
        finally:
            driver.quit()
    return base64.b64decode(data_url.split(",", 1)[1])


def with_credit(png: bytes) -> bytes:
    """``png`` with CREDIT on a pale strip in its bottom-right corner, as
    Google and Geoapify put theirs in the image."""
    img = Image.open(io.BytesIO(png)).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(22)
    left, top, right, bottom = draw.textbbox((0, 0), CREDIT, font=font)
    x, y = img.width - (right - left) - 12, img.height - (bottom - top) - 10
    draw.rectangle((x - 8, y - 6, img.width, img.height), fill=(255, 255, 255))
    draw.text((x - left, y - top), CREDIT, font=font, fill=(51, 51, 51))
    out = io.BytesIO()
    img.save(out, format="png")
    return out.getvalue()


class OpenFreeMap:
    centres_on_a_name = False

    def __init__(self, draw=draw_in_chromium):
        self.draw = draw

    def centre(self, place):
        return open_meteo_centre(place)

    def image_url(self, centre):
        lat, lon = centre.split(",")
        return f"{STYLE_URL}#{ZOOM}/{lat}/{lon}"

    def fetch(self, url):
        style_url, view = urlsplit(url)._replace(fragment="").geturl(), urlsplit(url).fragment
        zoom, lat, lon = view.split("/")
        try:
            style = greyed(json.loads(download(style_url)))
        except (ValueError, KeyError, TypeError):
            raise MapFetchError("the map style is not valid") from None
        return with_credit(self.draw(PAGE % {"maplibre": MAPLIBRE, "maplibre_sha384": MAPLIBRE_SHA384,
                                             "style": json.dumps(style),
                                             "lat": lat, "lon": lon, "zoom": zoom}))

"""The map providers, and the cache in maps/source.py."""
import io
import json
import os
import traceback
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
import requests
from googlemaps.exceptions import ApiError
from PIL import Image

from maps import MapCache, MapFetchError, StaticMapSource, create_provider
from maps.geoapify import GeoapifyMaps
from maps.geocode import open_meteo_centre
from maps.google import GoogleMaps
from maps.openfreemap import OpenFreeMap

# Real googlemaps.Client validates the key format at construction; this passes.
FAKE_API_KEY = "AIza" + "x" * 35
FAKE_MAP_ID = "test-map-id-123"
CORK = [{"geometry": {"location": {"lat": 51.8985, "lng": -8.4756}}}]


class _Png:
    content = b"\x89PNG\r\n\x1a\n"

    def raise_for_status(self):
        return None


def _web(search, image=_Png()):
    """A requests.get that answers Open-Meteo's place search with ``search``
    and every other address with ``image``. Both modules share requests.get."""
    def get(url, **kwargs):
        answer = search if "open-meteo" in url else image
        if isinstance(answer, Exception):
            raise answer
        return answer
    return get


@pytest.fixture
def google():
    return GoogleMaps(FAKE_API_KEY, FAKE_MAP_ID)


@pytest.fixture
def cache(google, tmp_path):
    return MapCache(google, str(tmp_path / "map-cache"))


def _query(url):
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


# ---------- Google ----------

def test_the_google_url_asks_for_the_styled_map_at_zoom_10(google):
    url = google.image_url("53.141819,-6.118493")
    assert url.startswith("https://maps.googleapis.com/maps/api/staticmap?")
    assert _query(url) == {"center": "53.141819,-6.118493", "zoom": "10", "size": "600x600",
                           "key": FAKE_API_KEY, "map_id": FAKE_MAP_ID, "scale": "2", "sensor": "false"}


def test_a_map_kept_before_the_maps_package_is_used_again(google, tmp_path):
    folder = tmp_path / "map-cache"
    folder.mkdir()
    url = google.image_url("51.898500,-8.475600")
    (folder / "staticmap_old.png").write_bytes(_Png.content)
    (folder / "map.json").write_text(json.dumps({
        "location_center": {"ts": 1, "location": "Cork", "data": "51.898500,-8.475600"},
        "static_map_url": {"ts": 1, "location": "Cork", "map_id": FAKE_MAP_ID, "data": url},
        "static_map_image": {"ts": 1, "location": "Cork", "map_id": FAKE_MAP_ID, "url": url,
                             "filename": "staticmap_old.png"},
    }))
    with patch("maps.source.requests.get") as fetch:
        src = MapCache(google, str(folder)).local_src("Cork")
    assert src.endswith("/staticmap_old.png")
    fetch.assert_not_called()


def test_google_centres_on_the_coordinates_of_a_place(google):
    with patch("maps.google.geocode", return_value=CORK) as lookup:
        assert google.centre("Cork") == "51.898500,-8.475600"
    lookup.assert_called_once()


def test_a_place_google_does_not_know_is_kept_as_the_name(google):
    with patch("maps.google.geocode", return_value=[]):
        assert google.centre("AtlantisXYZ") == "AtlantisXYZ"


def test_a_failed_lookup_gives_a_map_of_the_name_and_is_not_kept(cache):
    with patch("maps.google.geocode", side_effect=Exception("network down")), \
            patch("maps.source.requests.get", return_value=_Png()) as fetch:
        cache.local_src("Cork")
    assert _query(fetch.call_args.args[0])["center"] == "Cork"

    with patch("maps.google.geocode", return_value=CORK), \
            patch("maps.source.requests.get", return_value=_Png()) as fetch:
        cache.local_src("Cork")
    assert _query(fetch.call_args.args[0])["center"] == "51.898500,-8.475600"


def test_a_key_without_the_geocoding_api_asks_only_once(cache):
    with patch("maps.google.geocode", side_effect=ApiError("REQUEST_DENIED")) as lookup, \
            patch("maps.source.requests.get", return_value=_Png()) as fetch:
        first = cache.local_src("Cork")
        second = cache.local_src("Cork")
    assert first == second
    assert _query(fetch.call_args.args[0])["center"] == "Cork"
    assert lookup.call_count == 1 and fetch.call_count == 1


# ---------- The cache ----------

def test_the_same_place_is_looked_up_and_fetched_once(cache):
    with patch("maps.google.geocode", return_value=CORK) as lookup, \
            patch("maps.source.requests.get", return_value=_Png()) as fetch:
        src1 = cache.local_src("Cork")
        src2 = cache.local_src("Cork")
    assert src1 == src2
    assert src1.startswith("file://") and "/map-cache/staticmap_" in src1
    assert os.path.exists(urlparse(src1).path)
    assert lookup.call_count == 1 and fetch.call_count == 1


def test_a_new_place_fetches_a_new_map_and_deletes_the_old_one(cache):
    with patch("maps.google.geocode", side_effect=[CORK, [{"geometry": {"location": {"lat": 53.1, "lng": -6.1}}}]]), \
            patch("maps.source.requests.get", return_value=_Png()) as fetch:
        old = urlparse(cache.local_src("Cork")).path
        new = urlparse(cache.local_src("Dublin")).path
    assert old != new and fetch.call_count == 2
    assert not os.path.exists(old) and os.path.exists(new)


def test_a_new_server_on_the_same_folder_fetches_nothing(google, tmp_path):
    folder = str(tmp_path / "map-cache")
    with patch("maps.google.geocode", return_value=CORK), \
            patch("maps.source.requests.get", return_value=_Png()) as fetch:
        first = MapCache(google, folder).local_src("Cork")
        again = MapCache(GoogleMaps(FAKE_API_KEY, FAKE_MAP_ID), folder).local_src("Cork")
    assert first == again
    assert fetch.call_count == 1


def test_a_new_provider_fetches_a_new_map_at_the_kept_coordinates(google, tmp_path):
    folder = str(tmp_path / "map-cache")
    with patch("maps.google.geocode", return_value=CORK), \
            patch("requests.get", side_effect=_web(_OpenMeteo())) as web:
        MapCache(google, folder).local_src("Cork")
        MapCache(GeoapifyMaps("GEO"), folder).local_src("Cork")
    assert [urlparse(c.args[0]).netloc for c in web.call_args_list] == ["maps.googleapis.com", "maps.geoapify.com"]
    assert _query(web.call_args.args[0])["center"] == "lonlat:-8.475600,51.898500"
    assert len([f for f in os.listdir(folder) if f.endswith(".png")]) == 1


def test_a_name_kept_by_google_is_looked_up_for_a_provider_that_needs_coordinates(google, tmp_path):
    folder = str(tmp_path / "map-cache")
    with patch("maps.google.geocode", side_effect=ApiError("REQUEST_DENIED")), \
            patch("requests.get", side_effect=_web(_OpenMeteo())) as web:
        MapCache(google, folder).local_src("Cork")
        MapCache(GeoapifyMaps("GEO"), folder).local_src("Cork")
    assert [urlparse(c.args[0]).netloc for c in web.call_args_list] == \
        ["maps.googleapis.com", "geocoding-api.open-meteo.com", "maps.geoapify.com"]


def test_a_failed_map_fetch_keeps_the_key_out_of_the_error(cache):
    error = requests.HTTPError(f"403 for url: https://maps.example/?key={FAKE_API_KEY}")
    with patch("maps.google.geocode", return_value=CORK), patch("maps.source.requests.get", side_effect=error):
        with pytest.raises(MapFetchError) as caught:
            cache.local_src("Cork")
    assert FAKE_API_KEY not in "".join(traceback.format_exception(caught.value))


def test_the_source_gives_no_map_on_a_failure_and_tries_again_at_the_next_render(cache, caplog):
    fetch_map = StaticMapSource(cache, "Cork").datasets()["map_url"]
    with patch("maps.google.geocode", return_value=CORK):
        with patch("maps.source.requests.get", side_effect=requests.ConnectionError(f"key={FAKE_API_KEY}")):
            assert fetch_map() == ""
        assert "No map for this render" in caplog.text and FAKE_API_KEY not in caplog.text
        with patch("maps.source.requests.get", return_value=_Png()):
            assert fetch_map().startswith("file://")


# ---------- Open-Meteo place search ----------

class _OpenMeteo:
    def __init__(self, results=({"latitude": 51.89797, "longitude": -8.47061},)):
        self.results = list(results)

    def raise_for_status(self):
        return None

    def json(self):
        return {"results": self.results} if self.results else {}


def test_open_meteo_gives_the_first_match():
    with patch("maps.geocode.requests.get", return_value=_OpenMeteo()) as search:
        assert open_meteo_centre("Cork,IE") == "51.897970,-8.470610"
    assert search.call_args.kwargs["params"]["name"] == "Cork,IE"


@pytest.mark.parametrize("answer", [_OpenMeteo(results=()), requests.ConnectionError("down")])
def test_open_meteo_gives_none_with_no_match_or_no_answer(answer):
    kwargs = {"side_effect": answer} if isinstance(answer, Exception) else {"return_value": answer}
    with patch("maps.geocode.requests.get", **kwargs):
        assert open_meteo_centre("Nowhere") is None


def test_a_provider_that_needs_coordinates_gives_no_map_without_them(tmp_path):
    with patch("requests.get", side_effect=_web(requests.ConnectionError("down"))) as web:
        with pytest.raises(MapFetchError, match="no coordinates for Cork"):
            MapCache(GeoapifyMaps("GEO"), str(tmp_path)).local_src("Cork")
    assert web.call_count == 1


# ---------- Geoapify ----------

def test_the_geoapify_url_asks_for_the_grey_style_at_zoom_9():
    q = _query(GeoapifyMaps("GEO").image_url("51.897970,-8.470610"))
    assert q["center"] == "lonlat:-8.470610,51.897970"
    assert (q["style"], q["zoom"], q["width"], q["height"], q["scaleFactor"], q["apiKey"]) == \
        ("osm-bright-grey", "9", "600", "600", "2", "GEO")
    rules = q["styleCustomization"].split("|")
    assert "water:#666666" in rules and "highway-motorway:#808080;2" in rules
    assert "highway-minor:#808080;1" in rules and "highway-minor-casing:#808080;0" in rules
    assert "place-city:#000000" in rules


# ---------- OpenFreeMap ----------

def _blank_png():
    out = io.BytesIO()
    Image.new("RGB", (1200, 1200), (240, 240, 240)).save(out, format="png")
    return out.getvalue()


def _layer(name, kind, **paint):
    return {"id": name, "type": kind, "paint": paint}


BRIGHT = {"version": 8, "layers": [
    _layer("water", "fill", **{"fill-color": "#AECFE2"}),
    _layer("waterway-river", "line", **{"line-color": "#a0c8f0"}),
    _layer("water_name_point_label", "symbol", **{"text-color": "#495e91"}),
    _layer("highway-motorway-casing", "line", **{"line-color": "#e9ac77"}),
    _layer("highway-motorway", "line", **{"line-color": "#fc8", "line-width": ["zoom"]}),
    _layer("bridge-minor", "line", **{"line-color": "#fff", "line-width": ["zoom"]}),
    _layer("highway-name-major", "symbol", **{"text-color": "#666"}),
    _layer("label_city", "symbol", **{"text-color": "#333"}),
]}


class _Style:
    def __init__(self, body):
        self.content = body

    def raise_for_status(self):
        return None


def _draw_ofm(style_body=json.dumps(BRIGHT)):
    """Fetches an OpenFreeMap map; gives the page it drew and the image."""
    pages = []
    ofm = OpenFreeMap(draw=lambda page: pages.append(page) or _blank_png())
    with patch("maps.source.requests.get", return_value=_Style(style_body)) as fetch:
        png = ofm.fetch(ofm.image_url("51.897970,-8.470610"))
    assert fetch.call_args.args[0] == "https://tiles.openfreemap.org/styles/bright"
    return pages[0], png


def test_openfreemap_draws_the_bright_style_at_the_place():
    page, _ = _draw_ofm()
    assert "center: [-8.470610, 51.897970]" in page and "zoom: 9," in page and "pixelRatio: 2" in page


def test_openfreemap_draws_with_the_greys_of_the_geoapify_map():
    page, _ = _draw_ofm()
    style = json.loads(page.split("style: ", 1)[1].split(", center:", 1)[0])
    layers = {layer["id"]: layer for layer in style["layers"]}
    assert layers["water"]["paint"]["fill-color"] == "#666666"
    assert layers["waterway-river"]["paint"]["line-color"] == "#666666"
    assert layers["water_name_point_label"]["paint"] == {"text-color": "#495e91"}
    assert layers["highway-motorway-casing"]["layout"]["visibility"] == "none"
    assert layers["highway-motorway"]["paint"] == {"line-color": "#808080", "line-width": 2}
    assert layers["bridge-minor"]["paint"] == {"line-color": "#808080", "line-width": 1}
    assert layers["highway-name-major"]["paint"] == {"text-color": "#666"}
    assert layers["label_city"]["paint"]["text-color"] == "#000000"


def test_a_style_that_is_not_valid_gives_no_map():
    with pytest.raises(MapFetchError, match="the map style is not valid"):
        _draw_ofm("<html>")


def test_openfreemap_puts_its_credit_in_the_bottom_right_corner_of_the_image():
    _, png = _draw_ofm()
    img = Image.open(io.BytesIO(png)).convert("L")
    assert img.size == (1200, 1200)
    corner = img.crop((600, 1160, 1200, 1200))
    assert corner.getextrema()[0] < 100                     # dark text on the strip
    assert img.crop((0, 0, 600, 1100)).getextrema() == (240, 240)   # the rest is the map


def test_create_provider_knows_each_name():
    assert isinstance(create_provider("google", google_apikey=FAKE_API_KEY, staticmaps_mapid="M"), GoogleMaps)
    assert isinstance(create_provider("geoapify", geoapify_apikey="GEO"), GeoapifyMaps)
    assert isinstance(create_provider("openfreemap"), OpenFreeMap)

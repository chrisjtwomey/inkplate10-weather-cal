"""URL construction and location resolution in google/api.py."""
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest

from google.api import GoogleAPIService


# Real googlemaps.Client validates the key format at construction; this passes.
FAKE_API_KEY = "AIza" + "x" * 35
FAKE_MAP_ID = "test-map-id-123"


@pytest.fixture
def gapi():
    return GoogleAPIService(FAKE_API_KEY)


# ---------- StaticMapService.get_url ----------

def test_static_map_url_includes_all_expected_params(gapi):
    url = gapi.get_static_map_url(FAKE_MAP_ID, (53.141819, -6.118493))

    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "maps.googleapis.com"
    assert parsed.path == "/maps/api/staticmap"

    q = parse_qs(parsed.query)
    assert q["center"] == ["53.141819,-6.118493"]
    assert q["zoom"] == ["10"]
    assert q["size"] == ["600x600"]
    assert q["key"] == [FAKE_API_KEY]
    assert q["map_id"] == [FAKE_MAP_ID]
    assert q["scale"] == ["2"]
    assert q["sensor"] == ["false"]


def test_static_map_url_omits_cache_busting_param_by_default():
    svc = GoogleAPIService.StaticMapService(FAKE_API_KEY, FAKE_MAP_ID)
    url = svc.get_url("53.1,-6.1")
    assert "time=" not in url


def test_static_map_url_adds_cache_buster_when_cache_disabled():
    svc = GoogleAPIService.StaticMapService(FAKE_API_KEY, FAKE_MAP_ID, cache=False)
    url = svc.get_url("53.1,-6.1")
    assert "time=" in url


def test_static_map_url_respects_custom_zoom():
    svc = GoogleAPIService.StaticMapService(FAKE_API_KEY, FAKE_MAP_ID)
    url = svc.get_url("53.1,-6.1", zoom=14)
    assert "zoom=14" in url


# ---------- _get_location_center ----------

def test_location_center_from_tuple_of_floats(gapi):
    assert gapi._get_location_center((53.141819, -6.118493)) == "53.141819,-6.118493"


def test_location_center_from_list_of_strings(gapi):
    # Strings should still coerce via float()
    assert gapi._get_location_center(["53.141819", "-6.118493"]) == "53.141819,-6.118493"


def test_location_center_geocodes_place_name(gapi):
    fake_result = [{"geometry": {"location": {"lat": 51.8985, "lng": -8.4756}}}]
    with patch("google.api.geocode", return_value=fake_result) as mock_geocode:
        center = gapi._get_location_center("Cork")
    assert center == "51.898500,-8.475600"
    mock_geocode.assert_called_once()


def test_location_center_falls_back_to_raw_string_on_geocode_failure(gapi):
    with patch("google.api.geocode", side_effect=Exception("network down")):
        center = gapi._get_location_center("Cork")
    assert center == "Cork"


def test_location_center_falls_back_to_raw_string_on_empty_geocode(gapi):
    with patch("google.api.geocode", return_value=[]):
        center = gapi._get_location_center("AtlantisXYZ")
    assert center == "AtlantisXYZ"

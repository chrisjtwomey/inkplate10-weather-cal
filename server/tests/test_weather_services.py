"""Weather-service parsers driven by canned JSON fixtures via `responses`."""
import json
import re
from datetime import datetime

import pytest
import responses
from freezegun import freeze_time

from weather.accuweather.accuweather import AccuweatherService
from weather.openweathermap.openweathermap import OpenWeatherMapService
from weather.mock.mock import MockWeatherService
from weather.meteireann.meteireann import MetEireannService
from weather.openmeteo.openmeteo import OpenMeteoService
from weather.registry import registered_services, _REGISTRY
from weather.service import WeatherService


def _load(fixtures_dir, name):
    with open(fixtures_dir / name) as f:
        return json.load(f)


# ====================================================================
# Accuweather
# ====================================================================

@pytest.fixture
def accuweather_endpoints(fixtures_dir):
    """Register all four accuweather endpoints with canned responses."""
    location = _load(fixtures_dir, "accuweather_location.json")
    daily = _load(fixtures_dir, "accuweather_daily.json")
    current = _load(fixtures_dir, "accuweather_current.json")
    hourly = _load(fixtures_dir, "accuweather_hourly.json")
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(rsps.GET,
                 re.compile(r"http://dataservice\.accuweather\.com/locations/v1/search.*"),
                 json=location)
        rsps.add(rsps.GET,
                 re.compile(r"http://dataservice\.accuweather\.com/forecasts/v1/daily/1day/.*"),
                 json=daily)
        rsps.add(rsps.GET,
                 re.compile(r"http://dataservice\.accuweather\.com/currentconditions/v1/.*"),
                 json=current)
        rsps.add(rsps.GET,
                 re.compile(r"http://dataservice\.accuweather\.com/forecasts/v1/hourly/12hour/.*"),
                 json=hourly)
        yield rsps


def test_accuweather_resolves_location_key_on_init(accuweather_endpoints):
    svc = AccuweatherService(apikey="fake-key", location="Cork", num_hours=6, metric=True)
    assert svc.location_key == "213373"


def test_accuweather_daily_summary_parses_metric(accuweather_endpoints):
    svc = AccuweatherService(apikey="fake-key", location="Cork", num_hours=6, metric=True)
    summary = svc.get_daily_summary()

    assert summary["temperature"]["unit"] == "\N{DEGREE SIGN}C"
    assert summary["temperature"]["min"] == 10                 # round(10.3) actual
    assert summary["temperature"]["max"] == 20                 # round(19.5) actual
    assert summary["temperature"]["feels_like"] == 18          # round(18.2) RealFeel max
    assert summary["rain_probability"] == 35
    assert summary["icon"] == "icon/day/partly-clear.png"      # Day.Icon=3 -> partly-clear
    assert summary["humidity"] == 64
    assert summary["wind"]["unit"] == "kmh"
    assert summary["wind"]["value"] == pytest.approx(12.4)


def test_accuweather_daily_summary_parses_imperial(accuweather_endpoints):
    svc = AccuweatherService(apikey="fake-key", location="Cork", num_hours=6, metric=False)
    summary = svc.get_daily_summary()
    assert summary["temperature"]["unit"] == "\N{DEGREE SIGN}F"
    assert summary["wind"]["unit"] == "mph"
    assert summary["wind"]["value"] == pytest.approx(7.7)


def test_accuweather_hourly_forecast_returns_requested_count(accuweather_endpoints):
    svc = AccuweatherService(apikey="fake-key", location="Cork", num_hours=6, metric=True)
    hourly = svc.get_hourly_forecast()
    assert len(hourly) == 6

    first = hourly[0]
    assert isinstance(first["dt"], datetime)
    assert first["temperature"]["unit"] == "\N{DEGREE SIGN}C"
    assert first["temperature"]["value"] == 16
    assert first["wind"]["unit"] == "kmh"
    assert first["wind"]["direction_degrees"] == 270
    assert first["humidity"] == 60
    assert first["rain_probability"] == 10
    assert first["icon"] == "icon/day/clear.png"               # Icon=1 -> clear day


def test_accuweather_raises_on_empty_location_response(fixtures_dir):
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(rsps.GET,
                 re.compile(r"http://dataservice\.accuweather\.com/locations/v1/search.*"),
                 json=[])
        with pytest.raises(ValueError, match="Unexpected response"):
            AccuweatherService(apikey="fake-key", location="Cork")


# ====================================================================
# OpenWeatherMap
# ====================================================================

@pytest.fixture
def openweathermap_endpoints(fixtures_dir):
    geo = _load(fixtures_dir, "openweathermap_geo.json")
    weather = _load(fixtures_dir, "openweathermap_weather.json")
    forecast = _load(fixtures_dir, "openweathermap_forecast.json")
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(rsps.GET,
                 re.compile(r"https://api\.openweathermap\.org/geo/1\.0/direct.*"),
                 json=geo)
        rsps.add(rsps.GET,
                 re.compile(r"https://api\.openweathermap\.org/data/2\.5/weather.*"),
                 json=weather)
        rsps.add(rsps.GET,
                 re.compile(r"https://api\.openweathermap\.org/data/2\.5/forecast.*"),
                 json=forecast)
        yield rsps


def test_openweathermap_resolves_coords_on_init(openweathermap_endpoints):
    svc = OpenWeatherMapService(apikey="fake-key", location="Cork", num_hours=6, metric=True)
    # The service rounds its lat/lon at construction.
    assert svc.lat == 52       # round(51.8985)
    assert svc.lon == -8       # round(-8.4756)


def test_openweathermap_daily_summary_parses(openweathermap_endpoints):
    svc = OpenWeatherMapService(apikey="fake-key", location="Cork", num_hours=6, metric=True)
    summary = svc.get_daily_summary()
    assert summary["temperature"]["min"] == 11   # round(11.0)
    assert summary["temperature"]["max"] == 18   # round(17.8)
    assert summary["icon"] == "icon/day/partly-clear.png"   # "03d" -> partly-clear


def test_openweathermap_hourly_forecast_parses(openweathermap_endpoints):
    svc = OpenWeatherMapService(apikey="fake-key", location="Cork", num_hours=6, metric=True)
    hourly = svc.get_hourly_forecast()
    assert len(hourly) == 6
    first = hourly[0]
    assert isinstance(first["dt"], datetime)
    assert first["temperature"]["value"] == 16   # round(16)
    assert first["humidity"] == 60
    assert first["wind"]["direction_degrees"] == 250
    assert first["rain_probability"] == 10       # round(0.1 * 100)
    assert first["icon"] == "icon/day/clear.png" # "01d" -> clear


def test_openweathermap_raises_on_non_200_forecast(fixtures_dir):
    geo = _load(fixtures_dir, "openweathermap_geo.json")
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(rsps.GET,
                 re.compile(r"https://api\.openweathermap\.org/geo/1\.0/direct.*"),
                 json=geo)
        rsps.add(rsps.GET,
                 re.compile(r"https://api\.openweathermap\.org/data/2\.5/forecast.*"),
                 json={"cod": "401", "message": "Invalid API key"})
        svc = OpenWeatherMapService(apikey="fake-key", location="Cork")
        with pytest.raises(ValueError, match="Non-200 response"):
            svc.get_hourly_forecast()


# ====================================================================
# Interface conformance
# ====================================================================

def test_all_registered_services_are_weather_service_subclasses():
    """Every entry in the registry must be a concrete WeatherService subclass."""
    assert len(_REGISTRY) > 0, "Registry is empty — service modules not imported"
    for name, cls in _REGISTRY.items():
        assert issubclass(cls, WeatherService), (
            f"{name!r} ({cls.__name__}) is not a subclass of WeatherService"
        )


def test_weather_service_abc_cannot_be_instantiated_directly():
    """WeatherService is abstract and must not be directly instantiatable."""
    import pytest
    with pytest.raises(TypeError):
        WeatherService(  # type: ignore[abstract]
            apikey=None, baseurl=None, service_name="test"
        )


def test_incomplete_service_raises_on_instantiation():
    """A subclass missing abstract methods must raise TypeError at instantiation."""
    class IncompleteService(WeatherService):
        def get_current_conditions(self) -> dict:  # type: ignore[override]
            return {}
        # get_5day_forecast, get_daily_summary, get_hourly_forecast not implemented

    with pytest.raises(TypeError):
        IncompleteService(apikey=None, baseurl=None, service_name="incomplete")  # type: ignore[abstract]


# ====================================================================
# Met Éireann
# ====================================================================

@pytest.fixture
def meteirann_endpoints(fixtures_dir):
    xml_body = (fixtures_dir / "meteirann_forecast.xml").read_text()
    nominatim_response = [{"lat": "53.3498", "lon": "-6.2603", "display_name": "Dublin, Ireland"}]
    # The parsers keep only entries at or after now, and the canned forecast runs
    # from 2026-06-14T10:00Z to 2026-06-18T18:00Z.
    with (
        freeze_time("2026-06-14 09:00:00"),
        responses.RequestsMock(assert_all_requests_are_fired=False) as rsps,
    ):
        rsps.add(rsps.GET,
                 re.compile(r"https://nominatim\.openstreetmap\.org/search.*"),
                 json=nominatim_response)
        rsps.add(rsps.GET,
                 re.compile(r"http://openaccess\.pf\.api\.met\.ie/metno-wdb2ts/locationforecast.*"),
                 body=xml_body,
                 content_type="application/xml")
        yield rsps


def test_meteirann_resolves_coords_on_init(meteirann_endpoints):
    svc = MetEireannService(location="Dublin", num_hours=6, metric=True)
    assert svc.lat == 53.3498
    assert svc.lon == -6.2603


def test_meteirann_raises_on_empty_geocode_response(fixtures_dir):
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(rsps.GET,
                 re.compile(r"https://nominatim\.openstreetmap\.org/search.*"),
                 json=[])
        with pytest.raises(ValueError, match="no results"):
            MetEireannService(location="Nowhereville")


def test_meteirann_daily_summary_parses_metric(meteirann_endpoints):
    svc = MetEireannService(location="Dublin", num_hours=6, metric=True)
    summary = svc.get_daily_summary()
    assert summary["temperature"]["unit"] == "\N{DEGREE SIGN}C"
    assert summary["temperature"]["min"] <= summary["temperature"]["max"]
    assert summary["temperature"]["feels_like"] is not None
    assert summary["wind"]["unit"] == "kmh"
    assert 0 <= summary["rain_probability"] <= 100
    assert summary["pollen"] is None


def test_meteirann_daily_summary_parses_imperial(meteirann_endpoints):
    svc = MetEireannService(location="Dublin", num_hours=6, metric=False)
    summary = svc.get_daily_summary()
    assert summary["temperature"]["unit"] == "\N{DEGREE SIGN}F"
    assert summary["wind"]["unit"] == "mph"
    # Fahrenheit values should be higher than the Celsius originals
    assert summary["temperature"]["max"] > 32


def test_meteirann_hourly_forecast_returns_requested_count(meteirann_endpoints):
    svc = MetEireannService(location="Dublin", num_hours=4, metric=True)
    hourly = svc.get_hourly_forecast()
    assert len(hourly) <= 4
    if hourly:
        first = hourly[0]
        assert isinstance(first["dt"], datetime)
        assert first["temperature"]["unit"] == "\N{DEGREE SIGN}C"
        assert "value" in first["wind"]
        assert "direction_degrees" in first["wind"]


def test_meteirann_5day_forecast_returns_up_to_5_days(meteirann_endpoints):
    svc = MetEireannService(location="Dublin", num_hours=6, metric=True)
    forecast = svc.get_5day_forecast()
    assert 1 <= len(forecast) <= 5
    for entry in forecast:
        assert isinstance(entry["dt"], datetime)
        assert entry["temperature"]["min"] <= entry["temperature"]["max"]


# Open-Meteo
# ====================================================================

@pytest.fixture
def openmeteo_endpoints(fixtures_dir):
    geocoding_data = json.loads((fixtures_dir / "openmeteo_geocoding.json").read_text())
    forecast_data = json.loads((fixtures_dir / "openmeteo_forecast.json").read_text())
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(rsps.GET,
                 re.compile(r"https://geocoding-api\.open-meteo\.com/v1/search.*"),
                 json=geocoding_data)
        rsps.add(rsps.GET,
                 re.compile(r"https://api\.open-meteo\.com/v1/forecast.*"),
                 json=forecast_data)
        yield rsps


def test_openmeteo_resolves_coords_on_init(openmeteo_endpoints):
    svc = OpenMeteoService(location="Dublin", num_hours=6, metric=True)
    assert svc.lat == 53.3331
    assert svc.lon == -6.2489


def test_openmeteo_raises_on_empty_geocode_response(fixtures_dir):
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(rsps.GET,
                 re.compile(r"https://geocoding-api\.open-meteo\.com/v1/search.*"),
                 json={})
        with pytest.raises(ValueError, match="no results"):
            OpenMeteoService(location="Nowhereville")


def test_openmeteo_daily_summary_parses_metric(openmeteo_endpoints):
    svc = OpenMeteoService(location="Dublin", num_hours=6, metric=True)
    summary = svc.get_daily_summary()
    assert summary["temperature"]["unit"] == "\N{DEGREE SIGN}C"
    assert summary["temperature"]["min"] <= summary["temperature"]["max"]
    assert summary["temperature"]["feels_like"] is not None
    assert summary["wind"]["unit"] == "kmh"
    assert 0 <= summary["rain_probability"] <= 100
    assert summary["pollen"] is None


def test_openmeteo_daily_summary_parses_imperial(openmeteo_endpoints):
    svc = OpenMeteoService(location="Dublin", num_hours=6, metric=False)
    summary = svc.get_daily_summary()
    assert summary["temperature"]["unit"] == "\N{DEGREE SIGN}F"
    assert summary["wind"]["unit"] == "mph"


def test_openmeteo_hourly_forecast_returns_requested_count(openmeteo_endpoints):
    svc = OpenMeteoService(location="Dublin", num_hours=6, metric=True)
    hourly = svc.get_hourly_forecast()
    # Fixture has current.time = 2026-06-14T10:00 and hourly entries from 10:00 onward
    assert len(hourly) == 6
    first = hourly[0]
    assert isinstance(first["dt"], datetime)
    assert first["temperature"]["unit"] == "\N{DEGREE SIGN}C"
    assert "value" in first["wind"]
    assert "direction_degrees" in first["wind"]
    assert 0 <= first["rain_probability"] <= 100


def test_openmeteo_5day_forecast_returns_5_days(openmeteo_endpoints):
    svc = OpenMeteoService(location="Dublin", num_hours=6, metric=True)
    forecast = svc.get_5day_forecast()
    assert len(forecast) == 5
    for entry in forecast:
        assert isinstance(entry["dt"], datetime)
        assert entry["temperature"]["min"] <= entry["temperature"]["max"]
        assert entry["sunrise"] is not None
        assert entry["sunset"] is not None
        assert entry["hours_of_sun"] is not None


def test_openmeteo_current_conditions(openmeteo_endpoints):
    svc = OpenMeteoService(location="Dublin", num_hours=6, metric=True)
    cc = svc.get_current_conditions()
    assert cc["temperature"]["unit"] == "\N{DEGREE SIGN}C"
    assert cc["temperature"]["value"] == 14
    assert cc["temperature"]["feels_like"] == 12
    assert cc["humidity"] == 74
    assert cc["wind"]["unit"] == "kmh"
    assert cc["uv_index"] is None

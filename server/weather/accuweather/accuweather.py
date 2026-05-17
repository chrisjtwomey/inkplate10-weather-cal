import requests
from utils import even_select
from datetime import datetime
from ..service import WeatherService


class AccuweatherService(WeatherService):
    def __init__(self, apikey, location, num_hours=6, metric=True):
        super().__init__(
            apikey,
            "http://dataservice.accuweather.com",
            "accuweather",
            num_hours,
            metric,
        )
        self.location_key = self._get_location_key(location)

    def get_daily_summary(self):
        is_metric = self.units == "metric"
        path = f"{self.baseurl}/forecasts/v1/daily/1day/{self.location_key}?apikey={self.apikey}&metric={is_metric}&details=true"
        res = requests.get(path)
        data = res.json()

        if len(data) == 0:
            raise ValueError("Unexpected response from weather api: {}".format(data))

        if len(data["DailyForecasts"]) == 0:
            raise ValueError("Unexpected response from weather api: {}".format(data))

        current_conditions = self._get_current_conditions()

        data = data["DailyForecasts"][0]
        forecast = {
            "icon": self.get_icon(data["Day"]["Icon"]),
            "temperature": {
                "unit": "\N{DEGREE SIGN}C"
                if self.units == "metric"
                else "\N{DEGREE SIGN}F",
                "min": round(data["RealFeelTemperature"]["Minimum"]["Value"]),
                "max": round(data["RealFeelTemperature"]["Maximum"]["Value"]),
                #"value": current_conditions["temperature"]["value"],
                "value": round(data["RealFeelTemperature"]["Maximum"]["Value"]),
            },
            "wind": current_conditions["wind"],
            "humidity": current_conditions["humidity"],
        }

        return forecast

    def get_hourly_forecast(self):
        is_metric = self.units == "metric"
        path = f"{self.baseurl}/forecasts/v1/hourly/12hour/{self.location_key}?apikey={self.apikey}&metric={is_metric}&details=true"
        res = requests.get(path)
        data = res.json()

        if len(data) == 0:
            raise ValueError("Unexpected response from weather api: {}".format(data))

        if self.units == "metric":
            temp_units = "\N{DEGREE SIGN}C"
            speed_units = "kmh"
        else:
            temp_units = "\N{DEGREE SIGN}F"
            speed_units = "mph"

        forecasts = []
        for entry in even_select(self.num_hours, data):
            forecast = {
                "dt": datetime.fromtimestamp(entry["EpochDateTime"]),
                "icon": self.get_icon(entry["WeatherIcon"]),
                "temperature": {
                    "unit": temp_units,
                    "value": round(entry["RealFeelTemperature"]["Value"]),
                },
                "wind": {
                    "unit": speed_units,
                    "value": entry["Wind"]["Speed"]["Value"],
                    "direction_degrees": entry["Wind"].get("Direction", {}).get("Degrees", 0),
                },
                "humidity": entry["RelativeHumidity"],
                "rain_probability": round(entry["RainProbability"]),
            }

            forecasts.append(forecast)

        return forecasts

    def get_5day_forecast(self):
        is_metric = self.units == "metric"
        path = (
            f"{self.baseurl}/forecasts/v1/daily/5day/{self.location_key}"
            f"?apikey={self.apikey}&metric={is_metric}&details=true"
        )
        res = requests.get(path)

        if res.status_code == 403:
            raise PermissionError(
                "AccuWeather 5-day endpoint returned 403 — "
                "this endpoint may require a plan upgrade"
            )

        data = res.json()
        if not data.get("DailyForecasts"):
            raise ValueError("Unexpected response from weather api: {}".format(data))

        temp_unit = (
            "\N{DEGREE SIGN}C" if self.units == "metric" else "\N{DEGREE SIGN}F"
        )
        speed_unit = "kmh" if self.units == "metric" else "mph"

        forecasts = []
        for entry in data["DailyForecasts"]:
            # UV index from AirAndPollen list
            uv_index = None
            for ap in entry.get("AirAndPollen", []):
                if ap.get("Name") == "UVIndex":
                    uv_index = ap.get("Value")
                    break

            # Sunrise / sunset as "HH:MM" strings
            sunrise = None
            sunset = None
            sun = entry.get("Sun", {})
            if sun.get("Rise"):
                try:
                    sunrise = datetime.fromisoformat(sun["Rise"]).strftime("%H:%M")
                except (ValueError, TypeError):
                    pass
            if sun.get("Set"):
                try:
                    sunset = datetime.fromisoformat(sun["Set"]).strftime("%H:%M")
                except (ValueError, TypeError):
                    pass

            forecasts.append({
                "dt": datetime.fromtimestamp(entry["EpochDate"]),
                "icon": self.get_icon(entry["Day"]["Icon"]),
                "temperature": {
                    "unit": temp_unit,
                    "min": round(entry["RealFeelTemperature"]["Minimum"]["Value"]),
                    "max": round(entry["RealFeelTemperature"]["Maximum"]["Value"]),
                },
                "wind": {
                    "unit": speed_unit,
                    "value": entry["Day"]["Wind"]["Speed"]["Value"],
                    "direction_degrees": entry["Day"]["Wind"].get("Direction", {}).get("Degrees", 0),
                },
                "rain_probability": round(entry["Day"].get("PrecipitationProbability", 0)),
                "uv_index": uv_index,
                "sunrise": sunrise,
                "sunset": sunset,
                "hours_of_sun": entry.get("Day", {}).get("HoursOfSun"),
            })

        return forecasts

    def _get_current_conditions(self):
        path = f"{self.baseurl}/currentconditions/v1/{self.location_key}?apikey={self.apikey}&details=true"
        res = requests.get(path)
        data = res.json()

        if len(data) == 0:
            raise ValueError("Unexpected response from weather api: {}".format(data))

        if self.units == "metric":
            temp_units = "\N{DEGREE SIGN}C"
            speed_units = "kmh"
            units_key = "Metric"
        else:
            temp_units = "\N{DEGREE SIGN}F"
            speed_units = "mph"
            units_key = "Imperial"

        data = data[0]
        conditions = {
            "icon": self.get_icon(data["WeatherIcon"]),
            "temperature": {
                "unit": temp_units,
                "value": round(data["RealFeelTemperature"][units_key]["Value"]),
            },
            "wind": {
                "unit": speed_units,
                "value": data["Wind"]["Speed"][units_key]["Value"],
            },
            "humidity": data["RelativeHumidity"],
        }

        return conditions

    def _get_location_key(self, location):
        path = (
            f"{self.baseurl}/locations/v1/search?apikey={self.apikey}&q={location}"
        )
        res = requests.get(path)
        data = res.json()

        if len(data) == 0:
            raise ValueError("Unexpected response from weather api: {}".format(data))
        data = data[0]
        location_key = data["Key"]

        return location_key

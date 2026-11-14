"""The words a theme shows, kept in one list per theme so that a translation
changes the list and not the layout.

Dates and hours are built from names and patterns here, not with strftime,
whose words follow the server's locale.
"""
import datetime as dt
from dataclasses import dataclass, field

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December")


@dataclass(frozen=True)
class Words:
    weekdays: tuple = WEEKDAYS
    weekdays_short: tuple = tuple(d[:3] for d in WEEKDAYS)
    months: tuple = MONTHS
    months_short: tuple = tuple(m[:3] for m in MONTHS)
    patterns: dict = field(default_factory=dict)
    terms: dict = field(default_factory=dict)

    def _fill(self, name: str, when: dt.date) -> str:
        return self.patterns[name].format(
            weekday=self.weekdays[when.weekday()], weekday_short=self.weekdays_short[when.weekday()],
            month=self.months[when.month - 1], month_short=self.months_short[when.month - 1], day=when.day)

    def date_long(self, when: dt.date) -> str:
        """Such as "Thursday, November 13"."""
        return self._fill("date_long", when)

    def date_short(self, when: dt.date) -> str:
        """Such as "13 Nov"."""
        return self._fill("date_short", when)

    def month(self, when: dt.date) -> str:
        return self.months[when.month - 1]

    def weekday_short(self, when: dt.date) -> str:
        return self.weekdays_short[when.weekday()]

    def hour(self, when: dt.datetime) -> str:
        """Such as "9am" or "12pm"."""
        return self.patterns["hour"].format(hour=when.hour % 12 or 12,
                                            half=self.terms["am"] if when.hour < 12 else self.terms["pm"])

    def percent(self, value) -> str:
        return self.patterns["percent"].format(value=value)

    def rain(self, value) -> str:
        """Such as "36% rain"."""
        return self.patterns["rain"].format(value=value)

    def __getitem__(self, term: str) -> str:
        return self.terms[term]


CLASSIC = Words(
    patterns={
        "date_long": "{weekday}, {month} {day}",
        "date_short": "{day} {month_short}",
        "hour": "{hour}{half}",
        "percent": "{value}%",
        "rain": "{value}% rain",
    },
    terms={
        "am": "am", "pm": "pm",
        "hours": "hours",
        "uv_low": "Low", "uv_medium": "Med", "uv_high": "High",
        "kmh": "kph", "mph": "mph",
        "title_today": "Day Forecast", "title_detailed": "Detailed",
        "title_hourly": "Hourly", "title_daily": "Daily Forecast",
    },
)

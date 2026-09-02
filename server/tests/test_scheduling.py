"""`get_next_wake` — the server glue that drives the client's deep-sleep
duration and next URL.

The underlying DST-correct maths (`next_wake`, `next_regen`) lives in
`epd_server.scheduling` and is tested there.
"""
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

import server
from server import get_next_wake


DUB = ZoneInfo("Europe/Dublin")
WAKE_SCHEDULE = [
    ("09:00:00", "today.png"),
    ("15:00:00", "daily.png"),
    ("21:00:00", "today.png"),
]



# ============================================================
# get_next_wake — drives the client's deep-sleep duration and next URL
# ============================================================

def test_get_next_wake_same_day():
    with patch.object(server, "server_display_schedule", WAKE_SCHEDULE), \
         patch.object(server, "server_tz", DUB), \
         patch("server.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 7, 1, 10, 0, 0, tzinfo=DUB)
        mock_dt.strptime = datetime.strptime
        mock_dt.combine = datetime.combine
        seconds, url = get_next_wake()
        assert seconds == 5 * 3600
        assert url == "daily.png"


def test_get_next_wake_fall_back_eve():
    """12 real hours from Sat 22:00 IST to Sun 09:00 GMT."""
    with patch.object(server, "server_display_schedule", WAKE_SCHEDULE), \
         patch.object(server, "server_tz", DUB), \
         patch("server.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 10, 24, 22, 0, 0, tzinfo=DUB)
        mock_dt.strptime = datetime.strptime
        mock_dt.combine = datetime.combine
        seconds, _ = get_next_wake()
        assert seconds == 12 * 3600


def test_get_next_wake_spring_forward_eve():
    """10 real hours from Sat 22:00 GMT to Sun 09:00 IST."""
    with patch.object(server, "server_display_schedule", WAKE_SCHEDULE), \
         patch.object(server, "server_tz", DUB), \
         patch("server.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2027, 3, 27, 22, 0, 0, tzinfo=DUB)
        mock_dt.strptime = datetime.strptime
        mock_dt.combine = datetime.combine
        seconds, _ = get_next_wake()
        assert seconds == 10 * 3600


def test_get_next_wake_is_non_negative():
    """If somehow now > next (shouldn't happen), clamp to 0 rather than negative."""
    with patch.object(server, "server_display_schedule", [("00:00:00", "today.png")]), \
         patch.object(server, "server_tz", DUB), \
         patch("server.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 7, 1, 23, 59, 59, tzinfo=DUB)
        mock_dt.strptime = datetime.strptime
        mock_dt.combine = datetime.combine
        # Next 00:00:00 is tomorrow — 1 second from now. Should never be negative.
        seconds, _ = get_next_wake()
        assert seconds >= 0

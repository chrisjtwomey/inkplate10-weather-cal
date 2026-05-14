"""DST-correct scheduling math in `_next_refresh_datetime`."""
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

import server
from server import _next_refresh_datetime, get_next_refresh_seconds


DUB = ZoneInfo("Europe/Dublin")
TIMES = ["09:00:00", "15:00:00", "21:00:00"]


def real_seconds_until(now, next_dt):
    """Mirror the daemon's `next_dt.timestamp() - now.timestamp()` recipe.

    Plain `next_dt - now` does naive wall-clock subtraction in Python when
    both sides share a tzinfo, silently dropping the 1h shift across a DST
    transition. Use timestamp arithmetic, same as the daemon.
    """
    return next_dt.timestamp() - now.timestamp()


def test_same_day_next_refresh_is_today():
    now = datetime(2026, 7, 1, 10, 0, 0, tzinfo=DUB)
    nxt = _next_refresh_datetime(TIMES, DUB, now=now)
    assert nxt == datetime(2026, 7, 1, 15, 0, 0, tzinfo=DUB)
    assert real_seconds_until(now, nxt) == 5 * 3600


def test_rolls_over_to_tomorrow_after_last_refresh():
    now = datetime(2026, 7, 1, 23, 30, 0, tzinfo=DUB)
    nxt = _next_refresh_datetime(TIMES, DUB, now=now)
    assert nxt == datetime(2026, 7, 2, 9, 0, 0, tzinfo=DUB)


def test_rolls_over_at_exact_match():
    # Equal-to-refresh-time means we've already hit it; advance to next.
    now = datetime(2026, 7, 1, 15, 0, 0, tzinfo=DUB)
    nxt = _next_refresh_datetime(TIMES, DUB, now=now)
    assert nxt == datetime(2026, 7, 1, 21, 0, 0, tzinfo=DUB)


def test_one_second_before_refresh():
    now = datetime(2026, 7, 1, 8, 59, 59, tzinfo=DUB)
    nxt = _next_refresh_datetime(TIMES, DUB, now=now)
    assert nxt == datetime(2026, 7, 1, 9, 0, 0, tzinfo=DUB)
    assert real_seconds_until(now, nxt) == 1


def test_fall_back_eve_delta_is_12_real_hours():
    """
    DST fall-back: Sun 25 Oct 2026 at 02:00 IST -> 01:00 GMT.
    From Sat 22:00 IST to Sun 09:00 GMT is 12 real hours (11 wall + 1 DST).
    The daemon must sleep for 12h of monotonic time, not 11.
    """
    now = datetime(2026, 10, 24, 22, 0, 0, tzinfo=DUB)
    nxt = _next_refresh_datetime(TIMES, DUB, now=now)
    assert nxt.utcoffset().total_seconds() == 0           # GMT post-fall-back
    assert real_seconds_until(now, nxt) == 12 * 3600


def test_spring_forward_eve_delta_is_10_real_hours():
    """
    DST spring-forward: Sun 28 Mar 2027 at 01:00 GMT -> 02:00 IST.
    From Sat 22:00 GMT to Sun 09:00 IST is 10 real hours (11 wall - 1 DST).
    """
    now = datetime(2027, 3, 27, 22, 0, 0, tzinfo=DUB)
    nxt = _next_refresh_datetime(TIMES, DUB, now=now)
    assert nxt.utcoffset().total_seconds() == 3600        # IST post-spring-forward
    assert real_seconds_until(now, nxt) == 10 * 3600


def test_single_refresh_time_rolls_to_tomorrow_when_all_past():
    now = datetime(2026, 7, 1, 23, 0, 0, tzinfo=DUB)
    nxt = _next_refresh_datetime(["09:00:00"], DUB, now=now)
    assert nxt == datetime(2026, 7, 2, 9, 0, 0, tzinfo=DUB)


def test_uses_default_now_when_omitted():
    """Smoke test: calling without `now` produces a tz-aware result in the future."""
    nxt = _next_refresh_datetime(TIMES, DUB)
    assert nxt.tzinfo is DUB
    assert nxt > datetime.now(tz=DUB)


# ============================================================
# get_next_refresh_seconds — drives the client's deep-sleep duration
# ============================================================

def test_get_next_refresh_seconds_same_day():
    with patch.object(server, "server_refresh_times", TIMES), \
         patch.object(server, "server_tz", DUB), \
         patch("server.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 7, 1, 10, 0, 0, tzinfo=DUB)
        mock_dt.strptime = datetime.strptime
        mock_dt.combine = datetime.combine
        assert get_next_refresh_seconds() == 5 * 3600


def test_get_next_refresh_seconds_fall_back_eve():
    """12 real hours from Sat 22:00 IST to Sun 09:00 GMT."""
    with patch.object(server, "server_refresh_times", TIMES), \
         patch.object(server, "server_tz", DUB), \
         patch("server.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 10, 24, 22, 0, 0, tzinfo=DUB)
        mock_dt.strptime = datetime.strptime
        mock_dt.combine = datetime.combine
        assert get_next_refresh_seconds() == 12 * 3600


def test_get_next_refresh_seconds_spring_forward_eve():
    """10 real hours from Sat 22:00 GMT to Sun 09:00 IST."""
    with patch.object(server, "server_refresh_times", TIMES), \
         patch.object(server, "server_tz", DUB), \
         patch("server.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2027, 3, 27, 22, 0, 0, tzinfo=DUB)
        mock_dt.strptime = datetime.strptime
        mock_dt.combine = datetime.combine
        assert get_next_refresh_seconds() == 10 * 3600


def test_get_next_refresh_seconds_is_non_negative():
    """If somehow now > next (shouldn't happen), clamp to 0 rather than negative."""
    with patch.object(server, "server_refresh_times", ["00:00:00"]), \
         patch.object(server, "server_tz", DUB), \
         patch("server.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 7, 1, 23, 59, 59, tzinfo=DUB)
        mock_dt.strptime = datetime.strptime
        mock_dt.combine = datetime.combine
        # Next 00:00:00 is tomorrow — 1 second from now. Should never be negative.
        assert get_next_refresh_seconds() >= 0

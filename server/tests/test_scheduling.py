"""DST-correct scheduling math in `_next_wake` and `_next_regen`."""
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

import server
from server import _next_wake, _next_regen, get_next_wake


DUB = ZoneInfo("Europe/Dublin")
WAKE_SCHEDULE = [
    ("09:00:00", "today.png"),
    ("15:00:00", "daily.png"),
    ("21:00:00", "today.png"),
]
REGEN_LEAD = 120  # seconds


def real_seconds_until(now, next_dt):
    """Mirror the daemon's `next_dt.timestamp() - now.timestamp()` recipe.

    Plain `next_dt - now` does naive wall-clock subtraction in Python when
    both sides share a tzinfo, silently dropping the 1h shift across a DST
    transition. Use timestamp arithmetic, same as the daemon.
    """
    return next_dt.timestamp() - now.timestamp()


def test_same_day_next_wake_is_today():
    now = datetime(2026, 7, 1, 10, 0, 0, tzinfo=DUB)
    nxt, url = _next_wake(WAKE_SCHEDULE, DUB, now=now)
    assert nxt == datetime(2026, 7, 1, 15, 0, 0, tzinfo=DUB)
    assert url == "daily.png"
    assert real_seconds_until(now, nxt) == 5 * 3600


def test_rolls_over_to_tomorrow_after_last_wake():
    now = datetime(2026, 7, 1, 23, 30, 0, tzinfo=DUB)
    nxt, url = _next_wake(WAKE_SCHEDULE, DUB, now=now)
    assert nxt == datetime(2026, 7, 2, 9, 0, 0, tzinfo=DUB)
    assert url == "today.png"


def test_rolls_over_at_exact_match():
    # Equal-to-wake-time means we've already hit it; advance to next.
    now = datetime(2026, 7, 1, 15, 0, 0, tzinfo=DUB)
    nxt, url = _next_wake(WAKE_SCHEDULE, DUB, now=now)
    assert nxt == datetime(2026, 7, 1, 21, 0, 0, tzinfo=DUB)
    assert url == "today.png"


def test_one_second_before_wake():
    now = datetime(2026, 7, 1, 8, 59, 59, tzinfo=DUB)
    nxt, url = _next_wake(WAKE_SCHEDULE, DUB, now=now)
    assert nxt == datetime(2026, 7, 1, 9, 0, 0, tzinfo=DUB)
    assert url == "today.png"
    assert real_seconds_until(now, nxt) == 1


def test_fall_back_eve_delta_is_12_real_hours():
    """
    DST fall-back: Sun 25 Oct 2026 at 02:00 IST -> 01:00 GMT.
    From Sat 22:00 IST to Sun 09:00 GMT is 12 real hours (11 wall + 1 DST).
    The daemon must sleep for 12h of monotonic time, not 11.
    """
    now = datetime(2026, 10, 24, 22, 0, 0, tzinfo=DUB)
    nxt, _ = _next_wake(WAKE_SCHEDULE, DUB, now=now)
    assert nxt.utcoffset() == timedelta(0)                # GMT post-fall-back
    assert real_seconds_until(now, nxt) == 12 * 3600


def test_spring_forward_eve_delta_is_10_real_hours():
    """
    DST spring-forward: Sun 28 Mar 2027 at 01:00 GMT -> 02:00 IST.
    From Sat 22:00 GMT to Sun 09:00 IST is 10 real hours (11 wall - 1 DST).
    """
    now = datetime(2027, 3, 27, 22, 0, 0, tzinfo=DUB)
    nxt, _ = _next_wake(WAKE_SCHEDULE, DUB, now=now)
    assert nxt.utcoffset() == timedelta(hours=1)          # IST post-spring-forward
    assert real_seconds_until(now, nxt) == 10 * 3600


def test_single_wake_rolls_to_tomorrow_when_all_past():
    now = datetime(2026, 7, 1, 23, 0, 0, tzinfo=DUB)
    nxt, url = _next_wake([("09:00:00", "today.png")], DUB, now=now)
    assert nxt == datetime(2026, 7, 2, 9, 0, 0, tzinfo=DUB)
    assert url == "today.png"


def test_uses_default_now_when_omitted():
    """Smoke test: calling without `now` produces a tz-aware result in the future."""
    nxt, url = _next_wake(WAKE_SCHEDULE, DUB)
    assert nxt.tzinfo is DUB
    assert nxt > datetime.now(tz=DUB)
    assert isinstance(url, str)


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


# ============================================================
# _next_regen — drives the server's image regeneration schedule
# ============================================================

def test_next_regen_fires_2_min_before_next_wake():
    now = datetime(2026, 7, 1, 10, 0, 0, tzinfo=DUB)
    regen_dt, wake_dt, url = _next_regen(WAKE_SCHEDULE, DUB, lead_seconds=REGEN_LEAD, now=now)
    assert wake_dt == datetime(2026, 7, 1, 15, 0, 0, tzinfo=DUB)
    assert regen_dt == datetime(2026, 7, 1, 14, 58, 0, tzinfo=DUB)
    assert url == "daily.png"


def test_next_regen_advances_after_regen_fires():
    # Simulate: regen just fired at 14:58 for the 15:00 wake.
    # now == regen_dt, so strict > check must skip to the 21:00 slot.
    now = datetime(2026, 7, 1, 14, 58, 0, tzinfo=DUB)
    regen_dt, wake_dt, url = _next_regen(WAKE_SCHEDULE, DUB, lead_seconds=REGEN_LEAD, now=now)
    assert wake_dt == datetime(2026, 7, 1, 21, 0, 0, tzinfo=DUB)
    assert regen_dt == datetime(2026, 7, 1, 20, 58, 0, tzinfo=DUB)
    assert url == "today.png"


def test_next_regen_wraps_to_tomorrow():
    now = datetime(2026, 7, 1, 22, 0, 0, tzinfo=DUB)
    regen_dt, wake_dt, url = _next_regen(WAKE_SCHEDULE, DUB, lead_seconds=REGEN_LEAD, now=now)
    assert wake_dt == datetime(2026, 7, 2, 9, 0, 0, tzinfo=DUB)
    assert regen_dt == datetime(2026, 7, 2, 8, 58, 0, tzinfo=DUB)
    assert url == "today.png"


def test_next_regen_single_slot_wraps():
    schedule = [("09:00:00", "today.png")]
    now = datetime(2026, 7, 1, 9, 30, 0, tzinfo=DUB)
    regen_dt, wake_dt, url = _next_regen(schedule, DUB, lead_seconds=REGEN_LEAD, now=now)
    assert wake_dt == datetime(2026, 7, 2, 9, 0, 0, tzinfo=DUB)
    assert regen_dt == datetime(2026, 7, 2, 8, 58, 0, tzinfo=DUB)

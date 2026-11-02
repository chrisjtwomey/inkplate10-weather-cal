"""The message that says a display's battery needs a charge."""
from pathlib import Path

import pytest
from paho.mqtt.client import topic_matches_sub

from battery_reminder import LOW_LINE, RemindingLogStore

BOARD = "inkplate10-weather-cal"
TOPIC = f"mqtt/weather-cal/{BOARD}/battery"
LOW = f"2026-11-02T08:30:03+00:00 - WARNING - {LOW_LINE}"


def percent(value: int) -> str:
    return f"2026-11-02T08:30:03+00:00 - INFO - approx battery capacity: {value}%"


class FakeClient:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload, qos, retain):
        self.published.append((topic, payload, qos, retain))


@pytest.fixture
def client():
    return FakeClient()


@pytest.fixture
def store(tmp_path, client):
    return RemindingLogStore(str(tmp_path / "logs.db"), prefix="mqtt/weather-cal", mqtt_client=lambda: client)


def test_the_low_line_is_the_one_the_firmware_logs():
    app = Path(__file__).parents[2] / "src" / "app.cpp"
    assert f'"{LOW_LINE}"' in app.read_text()


def test_the_topic_is_not_read_back_as_a_log_line():
    assert not topic_matches_sub("mqtt/weather-cal/+", TOPIC)


def test_a_low_period_publishes_one_retained_message(store, client):
    store.add(BOARD, LOW)
    store.add(BOARD, percent(9))
    store.add(BOARD, LOW)
    assert client.published == [(TOPIC, "low", 1, True)]


def test_a_charge_above_20_percent_ends_the_low_period(store, client):
    store.add(BOARD, LOW)
    store.add(BOARD, percent(20))
    assert len(client.published) == 1
    store.add(BOARD, percent(21))
    assert client.published[-1] == (TOPIC, "ok", 1, True)


def test_the_next_low_period_publishes_again(store, client):
    store.add(BOARD, LOW)
    store.add(BOARD, percent(100))
    store.add(BOARD, LOW)
    assert [message[1] for message in client.published] == ["low", "ok", "low"]


def test_each_board_has_its_own_state(store, client):
    store.add("one", LOW)
    store.add("two", LOW)
    assert [message[0] for message in client.published] == [
        "mqtt/weather-cal/one/battery", "mqtt/weather-cal/two/battery"]


def test_a_new_server_corrects_an_old_retained_message(store, client):
    store.add(BOARD, percent(60))
    store.add(BOARD, percent(60))
    assert client.published == [(TOPIC, "ok", 1, True)]


def test_a_percent_between_the_thresholds_shows_no_state(store, client):
    store.add(BOARD, percent(15))
    assert client.published == []


def test_a_line_is_kept_before_the_state_is_read(store, client):
    store.add(BOARD, LOW)
    assert [line["text"] for line in store.lines()] == [LOW]


def test_a_low_line_before_the_client_exists_publishes_at_the_next_one(tmp_path):
    clients = [None]
    store = RemindingLogStore(str(tmp_path / "logs.db"), prefix="p", mqtt_client=lambda: clients[0])
    store.add(BOARD, LOW)
    clients[0] = FakeClient()
    store.add(BOARD, f"{LOW} ")
    assert clients[0].published == [(f"p/{BOARD}/battery", "low", 1, True)]

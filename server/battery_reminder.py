"""Tell MQTT subscribers when a display's battery needs a charge.

The display reports its battery only in its log lines. ``LOW_LINE`` comes from
src/app.cpp, and a test checks it against that file. ``PERCENT_LINE`` comes from
epd's readBatteryPercent(), so no test here can read it: if epd changes those
words, the low state stays after a charge.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

from epd_server import LogStore

log = logging.getLogger(__name__)

LOW_LINE = "battery low, charge soon!"
PERCENT_LINE = re.compile(r"approx battery capacity: (\d+)%")
# Far above the board's 10% low threshold, so that a small change in a reading
# cannot end a low period.
CHARGED_ABOVE_PERCENT = 20


class RemindingLogStore(LogStore):
    """A LogStore that publishes ``low`` or ``ok`` to ``<prefix>/<board>/battery``
    each time a board's state changes.

    The message is retained, so a subscriber that starts later still gets it.
    The state is held in memory: after a restart the server publishes a board's
    state once more, at the first line that shows it.
    """

    def __init__(self, path: str, *, prefix: str, mqtt_client: Callable[[], Any], **kwargs: Any) -> None:
        super().__init__(path, **kwargs)
        self.prefix = prefix
        self.mqtt_client = mqtt_client
        self._states: dict[str, str] = {}

    def add(self, board: str, text: str) -> int | None:
        number = super().add(board, text)
        state = _state_in(text)
        if state is not None and self._states.get(board) != state:
            client = self.mqtt_client()
            if client is not None:
                client.publish(f"{self.prefix}/{board}/battery", state, qos=1, retain=True)
                self._states[board] = state
                log.info("battery of %s: %s", board, state)
        return number


def _state_in(text: str) -> str | None:
    """The state a log line shows, or None for a line that shows no state."""
    if LOW_LINE in text:
        return "low"
    percent = PERCENT_LINE.search(text)
    if percent is not None and int(percent.group(1)) > CHARGED_ABOVE_PERCENT:
        return "ok"
    return None

"""Today's photo for the pages, one step through the set each day."""
import datetime as dt
import json
import logging
import os
from pathlib import Path

from epd_server.source import DataSource

from .picture import picture_path
from .store import Photo, PhotoStore, write_atomically

log = logging.getLogger(__name__)


class PhotoSource(DataSource):
    """``photo_url``: today's picture as a ``file://`` address, or "" when the
    set is empty or the picture cannot be made, so a page can show the map."""

    def __init__(self, store: PhotoStore, today=dt.date.today):
        self.store = store
        self._today = today
        self._state = os.path.join(store.folder, "today.json")

    def datasets(self):
        return {"photo_url": self._photo_url}

    def todays_photo(self) -> Photo | None:
        """Today's photo: the one chosen earlier today, or on a new day the one
        after yesterday's. When that photo has left the set, the photo now in its
        place. An edit to the set never moves today to another photo."""
        the_set = self.store.the_set()
        if not the_set:
            return None
        today = self._today().isoformat()
        ids = [p.id for p in the_set]
        last = self._read()
        if last.get("id") in ids:
            index = ids.index(last["id"])
            if last.get("date") != today:
                index = (index + 1) % len(ids)
        elif isinstance(last.get("index"), int):
            index = last["index"] % len(ids)
        else:
            index = 0
        state = {"date": today, "id": ids[index], "index": index}
        if last != state:
            self._write(state)
        return the_set[index]

    def _photo_url(self) -> str:
        photo = self.todays_photo()
        if photo is None:
            return ""
        try:
            return Path(picture_path(self.store, photo)).resolve().as_uri()
        except Exception as exc:
            log.warning("No photo for this render: %s: %s", photo.name, exc)
            return ""

    def _read(self) -> dict:
        try:
            with open(self._state) as f:
                state = json.load(f)
            return state if isinstance(state, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _write(self, state: dict) -> None:
        os.makedirs(self.store.folder, exist_ok=True)
        write_atomically(self._state, json.dumps(state).encode())

"""Today's photo for each page, one step through the page's photos each day."""
import datetime as dt
import json
import logging
import os
from pathlib import Path

from epd_server.source import DataSource

from .picture import page_picture_path, picture_path
from .store import Photo, PhotoStore, write_atomically

log = logging.getLogger(__name__)


ALL_PAGES = "*"


class PhotoSource(DataSource):
    """``photo_urls``: for each page that shows photos, today's picture as a
    ``file://`` address. A page missing from it shows its map.

    ``page_sets`` gives each page's photo ids in order, or None for a page that
    shows the store's included photos. ``boxes`` gives a page's picture area on
    the square, at its size now and at its default size. Without ``page_sets``, every page shares the included photos."""

    def __init__(self, store: PhotoStore, today=dt.date.today, page_sets=None, boxes=None):
        self.store = store
        self._today = today
        self._page_sets = page_sets
        self._boxes = boxes or (lambda page_type: None)
        self._state = os.path.join(store.folder, "today.json")

    def datasets(self):
        return {"photo_urls": self._photo_urls}

    def photo_set(self, page_type: str = ALL_PAGES) -> list[Photo]:
        """The photos ``page_type`` shows in turn."""
        if self._page_sets is None or page_type == ALL_PAGES:
            return self.store.the_set()
        ids = self._page_sets().get(page_type, [])
        if ids is None:
            return self.store.the_set()
        photos = {p.id: p for p in self.store.photos()}
        return [photos[i] for i in ids if i in photos]

    def todays_photo(self, page_type: str = ALL_PAGES) -> Photo | None:
        """Today's photo on ``page_type``: the one chosen earlier today, or on a new
        day the one after yesterday's. When that photo has left the page's set, the
        photo now in its place. An edit to the set never moves today to another photo."""
        the_set = self.photo_set(page_type)
        if not the_set:
            return None
        today = self._today().isoformat()
        ids = [p.id for p in the_set]
        states = self._read()
        last = states.get(page_type, {})
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
            states[page_type] = state
            self._write(states)
        return the_set[index]

    def today_and_tomorrow(self, page_type: str = ALL_PAGES) -> tuple[str | None, str | None]:
        """The ids of today's photo on ``page_type`` and of the one that follows it
        tomorrow, if the set does not change. Tomorrow's is None when it is today's again."""
        today = self.todays_photo(page_type)
        if today is None:
            return None, None
        ids = [p.id for p in self.photo_set(page_type)]
        tomorrow = ids[(ids.index(today.id) + 1) % len(ids)]
        return today.id, tomorrow if tomorrow != today.id else None

    def _photo_urls(self) -> dict:
        urls = {}
        for page_type in (self._page_sets() if self._page_sets else {}):
            photo = self.todays_photo(page_type)
            if photo is None:
                continue
            try:
                boxes = self._boxes(page_type)
                path = page_picture_path(self.store, photo, page_type, *boxes) if boxes else picture_path(self.store, photo)
                urls[page_type] = Path(path).resolve().as_uri()
            except Exception as exc:
                log.warning("No photo on the %s page for this render: %s: %s", page_type, photo.name, exc)
        return urls

    def _read(self) -> "_Seeded":
        """Each page's last choice. A record from before pages had their own is
        every page's starting point."""
        try:
            with open(self._state) as f:
                state = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return _Seeded({}, {})
        if not isinstance(state, dict):
            return _Seeded({}, {})
        pages = state.get("pages") if isinstance(state.get("pages"), dict) else {}
        seed = state.get("seed") if "pages" in state else (state if "id" in state else None)
        return _Seeded({k: v for k, v in pages.items() if isinstance(v, dict)}, seed if isinstance(seed, dict) else {})

    def _write(self, states: "_Seeded") -> None:
        os.makedirs(self.store.folder, exist_ok=True)
        record = {"pages": dict(states)}
        if states.seed:
            record["seed"] = states.seed
        write_atomically(self._state, json.dumps(record).encode())


class _Seeded(dict):
    """The pages' records, where a page with none of its own starts from ``seed``,
    the single record kept before pages had their own."""

    def __init__(self, pages: dict, seed: dict):
        super().__init__(pages)
        self.seed = seed

    def get(self, key, default=None):
        return super().get(key, self.seed)

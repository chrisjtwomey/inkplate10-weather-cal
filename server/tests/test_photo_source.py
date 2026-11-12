"""Today's photo (photos/source.py): one step through the set each day."""
import datetime as dt
import io
from urllib.parse import urlparse

import pytest
from PIL import Image

from photos import PhotoSource, PhotoStore
from photos import source as source_module


class Clock:
    def __init__(self, day=dt.date(2026, 11, 12)):
        self.day = day

    def __call__(self):
        return self.day

    def next_day(self):
        self.day += dt.timedelta(days=1)


@pytest.fixture
def store(tmp_path):
    return PhotoStore(str(tmp_path / "photos"))


@pytest.fixture
def clock():
    return Clock()


def _add(store, n) -> str:
    data = io.BytesIO()
    Image.new("RGB", (32, 24), (n, n, n)).save(data, format="PNG")
    return store.add(data.getvalue(), f"{n}.png").id


def _names(source, clock, days):
    out = []
    for _ in range(days):
        out.append(source.todays_photo().name)
        clock.next_day()
    return out


def test_no_photos_gives_no_photo_url(store, clock):
    source = PhotoSource(store, clock)
    assert source.todays_photo() is None and source.datasets()["photo_url"]() == ""


def test_the_set_moves_one_photo_each_day_and_wraps(store, clock):
    for n in (1, 2, 3):
        _add(store, n)
    assert _names(PhotoSource(store, clock), clock, 5) == ["1.png", "2.png", "3.png", "1.png", "2.png"]


def test_the_photo_stays_all_day(store, clock):
    _add(store, 1), _add(store, 2)
    source = PhotoSource(store, clock)
    assert [source.todays_photo().name for _ in range(3)] == ["1.png"] * 3


def test_a_restart_keeps_the_place(store, clock):
    for n in (1, 2, 3):
        _add(store, n)
    PhotoSource(store, clock).todays_photo()
    clock.next_day()
    PhotoSource(store, clock).todays_photo()
    clock.next_day()
    assert PhotoSource(store, clock).todays_photo().name == "3.png"


def test_an_upload_or_reorder_does_not_change_todays_photo(store, clock):
    a, b = _add(store, 1), _add(store, 2)
    source = PhotoSource(store, clock)
    assert source.todays_photo().name == "1.png"
    c = _add(store, 3)
    store.reorder([c, b, a])
    assert source.todays_photo().name == "1.png"
    clock.next_day()
    assert source.todays_photo().name == "3.png"           # the one after 1.png in the new order


def test_a_photo_left_out_of_the_set_is_skipped(store, clock):
    a, b, c = _add(store, 1), _add(store, 2), _add(store, 3)
    store.include(b, False)
    assert _names(PhotoSource(store, clock), clock, 3) == ["1.png", "3.png", "1.png"]


def test_deleting_todays_photo_shows_the_one_in_its_place(store, clock):
    a, b, c = _add(store, 1), _add(store, 2), _add(store, 3)
    source = PhotoSource(store, clock)
    clock.next_day()
    assert source.todays_photo().name == "1.png"
    clock.next_day()
    assert source.todays_photo().name == "2.png"
    store.remove(b)
    assert source.todays_photo().name == "3.png"            # same day: the one that took its place
    clock.next_day()
    assert source.todays_photo().name == "1.png"


def test_deleting_yesterdays_photo_still_moves_on_by_one(store, clock):
    a, b, c = _add(store, 1), _add(store, 2), _add(store, 3)
    source = PhotoSource(store, clock)
    source.todays_photo()                                   # 1.png
    clock.next_day()
    source.todays_photo()                                   # 2.png
    store.remove(b)
    clock.next_day()
    assert source.todays_photo().name == "3.png"


def test_a_broken_state_file_starts_from_the_first_photo(store, clock):
    _add(store, 1), _add(store, 2)
    with open(f"{store.folder}/today.json", "w") as f:
        f.write("{not json")
    assert PhotoSource(store, clock).todays_photo().name == "1.png"


def test_photo_url_is_todays_picture(store, clock):
    _add(store, 1)
    url = PhotoSource(store, clock).datasets()["photo_url"]()
    assert url.startswith("file://") and "/pictures/" in url
    with Image.open(urlparse(url).path) as img:
        assert img.size == (1200, 1200)


def test_a_picture_that_cannot_be_made_gives_no_url_and_a_warning(store, clock, monkeypatch, caplog):
    _add(store, 1)
    monkeypatch.setattr(source_module, "picture_path", lambda *a: (_ for _ in ()).throw(OSError("disk full")))
    assert PhotoSource(store, clock).datasets()["photo_url"]() == ""
    assert "No photo for this render: 1.png: disk full" in caplog.text

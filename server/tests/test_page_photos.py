"""Each page's own photos and framings (photos/picture.py, photos/source.py), and
the carry-over from one shared set and one framing per photo."""
import datetime as dt
import io
import json
import os

import numpy as np
import pytest
from PIL import Image

from photos import Framing, PhotoSource, PhotoStore
from photos import picture as pic
from views.page import picture_windows

BOXES = picture_windows(825, 1200)
WIDE, TALL = BOXES["wide"], BOXES["tall"]


def _photo_bytes(size=(400, 300), seed=0) -> bytes:
    rng = np.random.default_rng(seed)
    img = Image.fromarray(rng.integers(0, 256, (size[1], size[0]), dtype=np.uint8), "L")
    out = io.BytesIO()
    img.convert("RGB").save(out, format="PNG")
    return out.getvalue()


@pytest.fixture
def store(tmp_path):
    return PhotoStore(str(tmp_path / "photos"))


# ---------- The maths ----------

@pytest.mark.parametrize("framing", [Framing(), Framing(0.3, 0.6, 1.7), Framing(0.8, 0.2, 0.6)])
@pytest.mark.parametrize("box", [WIDE, TALL])
def test_an_old_framing_converted_for_a_page_places_the_photo_the_same(framing, box):
    size = (4000, 3000)
    before = pic.square_placement(framing, size)
    after = pic.area_placement(pic.area_framing(framing, size, box), size, box)
    assert after.x == pytest.approx(before.x) and after.y == pytest.approx(before.y)
    assert after.scale == pytest.approx(before.scale)


def test_area_zoom_1_just_covers_the_area_with_the_point_at_its_centre():
    size = (400, 300)
    p = pic.area_placement(Framing(0.5, 0.5, 1.0), size, WIDE)
    width, height = WIDE[2] - WIDE[0], WIDE[3] - WIDE[1]
    assert p.scale == pytest.approx(max(width / 400, height / 300))
    centre_x = 600 + (0.5 - p.x) * 400 * p.scale
    assert centre_x == pytest.approx((WIDE[0] + WIDE[2]) / 2)


# ---------- Pictures per page ----------

def test_a_page_without_its_own_framing_gets_exactly_the_old_picture(store):
    photo = store.add(_photo_bytes(), "a.png")
    store.frame(photo.id, Framing(0.4, 0.45, 1.3))
    photo = store.photos()[0]
    with Image.open(pic.page_picture_path(store, photo, "today", WIDE)) as a, \
            Image.open(pic.picture_path(store, photo)) as b:
        assert np.array_equal(np.asarray(a), np.asarray(b))


def test_the_old_framing_converted_for_a_page_gives_the_same_picture(store):
    photo = store.add(_photo_bytes(), "a.png")
    store.frame(photo.id, Framing(0.4, 0.45, 1.3))
    photo = store.photos()[0]
    old = np.asarray(Image.open(pic.page_picture_path(store, photo, "hourly", TALL)))
    with Image.open(store.path(photo.id)) as img:
        size = pic.upright(img).size
    store.frame_page(photo.id, "hourly", pic.area_framing(photo.framing, size, TALL))
    new = np.asarray(Image.open(pic.page_picture_path(store, store.photos()[0], "hourly", TALL)))
    assert (old == new).mean() > 0.999


def test_one_pages_framing_leaves_the_others_alone(store):
    photo = store.add(_photo_bytes(), "a.png")
    store.frame_page(photo.id, "today", Framing(0.2, 0.2, 2.0))
    photo = store.photos()[0]
    today = pic.page_picture_path(store, photo, "today", WIDE)
    hourly = pic.page_picture_path(store, photo, "hourly", TALL)
    assert os.path.basename(today) != os.path.basename(hourly)
    store.frame_page(photo.id, "today", Framing(0.7, 0.7, 1.0))
    pic.page_picture_path(store, store.photos()[0], "today", WIDE)
    assert not os.path.exists(today) and os.path.exists(hourly)


# ---------- Each page's photos ----------

class Clock:
    def __init__(self):
        self.day = dt.date(2026, 11, 14)

    def __call__(self):
        return self.day


def test_each_page_has_its_own_set_and_rotation(store):
    a, b, c = (store.add(_photo_bytes(seed=i), f"{i}.png").id for i in range(3))
    clock = Clock()
    source = PhotoSource(store, clock, page_sets=lambda: {"today": [c, a], "hourly": [b]})
    assert (source.todays_photo("today").id, source.todays_photo("hourly").id) == (c, b)
    clock.day += dt.timedelta(days=1)
    assert (source.todays_photo("today").id, source.todays_photo("hourly").id) == (a, b)
    assert source.photo_set("daily") == []


def test_unknown_ids_in_a_pages_set_are_skipped(store):
    a = store.add(_photo_bytes(), "a.png").id
    source = PhotoSource(store, Clock(), page_sets=lambda: {"today": ["gone", a]})
    assert [p.id for p in source.photo_set("today")] == [a]


def test_a_page_with_no_list_of_its_own_shows_the_included_photos(store):
    a, b = (store.add(_photo_bytes(seed=i), f"{i}.png").id for i in range(2))
    store.include(a, False)
    source = PhotoSource(store, Clock(), page_sets=lambda: {"today": None})
    assert [p.id for p in source.photo_set("today")] == [b]


def test_the_old_record_of_todays_photo_carries_over_to_every_page(store):
    a, b, c = (store.add(_photo_bytes(seed=i), f"{i}.png").id for i in range(3))
    with open(os.path.join(store.folder, "today.json"), "w") as f:
        json.dump({"date": "2026-11-14", "id": b, "index": 1}, f)
    source = PhotoSource(store, Clock(), page_sets=lambda: {"today": None, "hourly": None, "daily": None})
    assert source.todays_photo("today").id == b
    assert source.todays_photo("hourly").id == b
    assert PhotoSource(store, Clock(), page_sets=lambda: {"daily": None}).todays_photo("daily").id == b

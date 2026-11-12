"""A photo as the pages show it (photos/picture.py): framing, the pencil effect, and the kept pictures."""
import io
import os

import numpy as np
import pytest
from PIL import Image

from photos import Framing, PhotoStore, framed, pencil, picture_path
from photos import picture as picture_module

SIZE = picture_module.SIZE


def _marked(size=(400, 300), at=(100, 75)) -> Image.Image:
    """A white photo with a black 10 px square centred on ``at``."""
    img = Image.new("L", size, 255)
    x, y = at
    img.paste(0, (x - 5, y - 5, x + 5, y + 5))
    return img


def _dark_centre(img: Image.Image) -> tuple[float, float]:
    ys, xs = np.nonzero(np.asarray(img) < 128)
    return float(xs.mean()), float(ys.mean())


def test_the_framing_point_lands_in_the_centre_of_the_square():
    out = framed(_marked(at=(100, 75)), Framing(x=100 / 400, y=75 / 300, zoom=1.0))
    assert out.size == (SIZE, SIZE)
    x, y = _dark_centre(out)
    assert abs(x - SIZE / 2) < 3 and abs(y - SIZE / 2) < 3


def test_zoom_1_just_covers_the_square_and_zoom_2_doubles_the_photo():
    wide = Image.new("L", (400, 300), 0)
    assert np.asarray(framed(wide, Framing())).max() == 0          # no white edge
    marked = _marked(at=(200, 150))
    small = framed(marked, Framing(zoom=1.0))
    big = framed(marked, Framing(zoom=2.0))
    assert (np.asarray(big) < 128).sum() == pytest.approx(4 * (np.asarray(small) < 128).sum(), rel=0.1)


def test_a_zoom_below_1_leaves_white_around_the_photo_and_is_kept_in_range():
    out = np.asarray(framed(Image.new("L", (400, 400), 0), Framing(zoom=0.1)))
    assert out[0, 0] == 255 and out[SIZE // 2, SIZE // 2] == 0
    assert (out == 0).sum() == pytest.approx((SIZE * picture_module.MIN_ZOOM) ** 2, rel=0.02)


def test_a_phone_photo_is_turned_upright():
    img = _marked(size=(400, 300), at=(20, 150))        # mark at the left edge, as stored
    exif = Image.Exif()
    exif[0x0112] = 6                                   # "rotate 90 degrees clockwise to view"
    data = io.BytesIO()
    img.save(data, format="JPEG", exif=exif.tobytes())
    upright = framed(Image.open(io.BytesIO(data.getvalue())), Framing(zoom=0.5))
    x, y = _dark_centre(upright)
    assert y < SIZE / 2 and abs(x - SIZE / 2) < 20      # now at the top edge


def test_the_pencil_drawing_uses_only_the_panels_four_greys():
    rng = np.random.default_rng(1)
    photo = Image.fromarray(rng.integers(0, 256, (120, 160), dtype=np.uint8), "L")
    assert set(np.unique(np.asarray(pencil(photo)))) <= set(picture_module.GREYS)


def test_the_pencil_drawing_keeps_an_edge_and_lightens_flat_areas():
    img = Image.new("L", (200, 200), 60)
    img.paste(200, (100, 0, 200, 200))
    out = np.asarray(pencil(img))
    assert out[100, 20:60].mean() > 200                 # the flat dark half turns light
    assert out[:, 95:100].mean() < out[100, 20:60].mean()   # darker along the edge


# ---------- Kept pictures ----------

@pytest.fixture
def store(tmp_path):
    return PhotoStore(str(tmp_path / "photos"))


def _add(store, colour=90) -> str:
    data = io.BytesIO()
    Image.new("RGB", (64, 48), (colour, colour, colour)).save(data, format="PNG")
    return store.add(data.getvalue(), "p.png").id


def test_a_picture_is_made_once_and_kept(store, monkeypatch):
    photo_id = _add(store)
    made = []
    real = picture_module.pencil
    monkeypatch.setattr(picture_module, "pencil", lambda img: made.append(1) or real(img))
    first = picture_path(store, store.photos()[0])
    second = picture_path(store, store.photos()[0])
    assert first == second and len(made) == 1
    with Image.open(first) as img:
        assert img.size == (SIZE, SIZE) and img.mode == "L"
    assert os.path.basename(first).startswith(photo_id + "-")


def test_a_new_framing_makes_a_new_picture_and_forgets_the_old(store):
    photo_id = _add(store)
    old = picture_path(store, store.photos()[0])
    store.frame(photo_id, Framing(0.2, 0.8, 2.0))
    new = picture_path(store, store.photos()[0])
    assert new != old and os.path.exists(new) and not os.path.exists(old)


def test_deleting_a_photo_deletes_its_pictures_only(store):
    a, b = _add(store, 10), _add(store, 200)
    pa = picture_path(store, store.photos()[0])
    pb = picture_path(store, store.photos()[1])
    store.remove(a)
    assert not os.path.exists(pa) and os.path.exists(pb)

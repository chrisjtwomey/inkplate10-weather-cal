"""The photo routes (photos/routes.py); the server's page previewer; and Classic's
picture areas against its CSS."""
import io
import json
import os
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask
from PIL import Image

import server
from epd_server.source import StaticSource
from photos import Framing, PhotoStore, photos_blueprint
from views.page import Page
from views.themes import CLASSIC_DETAIL, CLASSIC_PICTURE, SQUARE, THEMES, picture_box
from weather.registry import create

HTML = Path(__file__).parent.parent / "views" / "html"
WIDE = picture_box("classic", "today", 825, 1200)


def _image(colour=(120, 60, 30)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (80, 60), colour).save(out, format="JPEG")
    return out.getvalue()


@pytest.fixture
def store(tmp_path):
    return PhotoStore(str(tmp_path / "photos"))


def _client(store):
    app = Flask(__name__)
    app.register_blueprint(photos_blueprint(store, WIDE))
    return app.test_client()


# ---------- The page ----------


# ---------- Framing ----------

def test_a_framing_is_saved_and_kept_in_range(store):
    photo = store.add(_image(), "a.jpg")
    client = _client(store)
    assert client.post(f"/photos/{photo.id}/framing", json={"x": 0.25, "y": 0.75, "zoom": 2}).status_code == 204
    assert store.photos()[0].framing == Framing(0.25, 0.75, 2.0)
    client.post(f"/photos/{photo.id}/framing", json={"x": -3, "y": 9, "zoom": 100})
    assert store.photos()[0].framing == Framing(0.0, 1.0, 8.0)


@pytest.mark.parametrize("body", [None, {"x": 0.5, "y": 0.5}, {"x": "left", "y": 0.5, "zoom": 1},
                                  {"x": 0.5, "y": 0.5, "zoom": 0}, {"x": float("nan"), "y": 0.5, "zoom": 1}])
def test_a_bad_framing_is_400(store, body):
    photo = store.add(_image(), "a.jpg")
    rsp = _client(store).post(f"/photos/{photo.id}/framing", data=json.dumps(body),
                              content_type="application/json")
    assert rsp.status_code == 400


# ---------- The previewer ----------

class FakeRenderer:
    def render(self, html_path, width, height):
        return Image.new("RGB", (width, height), (200, 200, 200))


@pytest.fixture
def weather():
    return create("mock", location="Cork", num_hours=6, metric=True)


def test_the_previewer_draws_its_own_page_with_the_given_picture(tmp_path, weather, monkeypatch):
    html_dir = tmp_path / "html"
    html_dir.mkdir()
    for cls in server.PAGES.values():
        monkeypatch.setattr(cls, "__init__", _with_html_dir(cls.__init__, str(html_dir)))
    preview = server.page_previewer({"width": 825, "height": 1200}, [StaticSource(map_url="map.png"), weather],
                                    str(tmp_path / "previews"), renderer=FakeRenderer())
    png = preview("today", "file:///pictures/today.png")
    assert png.startswith(b"\x89PNG")
    assert "file:///pictures/today.png" in (html_dir / "preview-today.html").read_text()
    assert (tmp_path / "previews" / "preview-today.png").exists()


def test_the_previewer_says_when_the_page_is_not_drawn_now(tmp_path, monkeypatch):
    html_dir = tmp_path / "html"
    html_dir.mkdir()
    for cls in server.PAGES.values():
        monkeypatch.setattr(cls, "__init__", _with_html_dir(cls.__init__, str(html_dir)))
    no_hours = create("mock", location="Cork", num_hours=0, metric=True)
    preview = server.page_previewer({"width": 825, "height": 1200}, [StaticSource(map_url="map.png"), no_hours],
                                    str(tmp_path / "previews"), renderer=FakeRenderer())
    with pytest.raises(LookupError):
        preview("hourly", "file:///pictures/p.png")
    assert not (html_dir / "preview-hourly.html").exists()


def _with_html_dir(init, html_dir):
    def wrapped(self, *args, **kwargs):
        init(self, *args, **kwargs)
        self.html_dir = html_dir
    return wrapped


# ---------- Classic's picture areas follow its CSS ----------

def _css_number(file, pattern):
    match = re.search(pattern, (HTML / file).read_text(), flags=re.S)
    assert match, f"{pattern} not found in {file}"
    return float(match.group(1))


def test_classics_picture_areas_follow_its_css():
    assert _css_number("simplified.css", r"#map-container \{[^}]*height: var\(--picture-height, calc\(var\(--inner-vw\) \* ([\d.]+)\)\)") / 100 \
        == pytest.approx(CLASSIC_PICTURE.height)
    assert _css_number("simplified.css", r"#map \{[^}]*top: ([\d.]+)%") / 100 == CLASSIC_PICTURE.centre
    assert _css_number("styles.css", r"--map-height: ([\d.]+)%") / 100 == CLASSIC_DETAIL.height
    assert _css_number("styles.css", r"#map \{[^}]*top: ([\d.]+)%") / 100 == CLASSIC_DETAIL.centre


def test_classics_picture_areas_are_the_rows_the_pages_show_at_the_panels_size():
    assert [round(v) for v in picture_box("classic", "today", 825, 1200)] == [188, 450, 1012, 950]
    assert [round(v) for v in picture_box("classic", "hourly", 825, 1200)] == [188, 270, 1012, 930]


def test_a_picture_size_is_a_percent_of_the_inner_height():
    assert CLASSIC_PICTURE.pixels(825, 1100, 55) == pytest.approx(605)
    assert CLASSIC_PICTURE.pixels(825, 1100) == pytest.approx(0.606061 * 825)


@pytest.mark.parametrize("inner", [(825, 1200), (825, 1100)])
def test_the_map_covers_every_picture_area_at_its_largest(inner):
    for theme in THEMES.values():
        for area in theme.areas.values():
            left, top, right, bottom = area.box(*inner, 100)
            assert left >= 0 and top >= 0 and right <= SQUARE and bottom <= SQUARE


def test_a_picture_area_keeps_its_height_inside_its_range():
    height = lambda box: box[3] - box[1]
    assert height(CLASSIC_PICTURE.box(825, 1200, 500)) == pytest.approx(CLASSIC_PICTURE.largest * 825)
    assert height(CLASSIC_PICTURE.box(825, 1200, 0)) == pytest.approx(CLASSIC_PICTURE.smallest * 825)
    assert CLASSIC_DETAIL.box(825, 1200, 90) == CLASSIC_DETAIL.box(825, 1200)


def test_a_grown_picture_gives_its_page_its_height_and_growth():
    variables = lambda height: Page.picture_css_variables(SimpleNamespace(picture_height=height, default_picture_height=500))
    assert variables(500) == "" and variables(None) == ""
    assert variables(650) == "--picture-height:650.00px;--picture-grow:150.00px;--picture-growth:0.3000;"
    assert "--picture-growth:-0.2000;" in variables(400)


# ---------- Thumbnails ----------

def test_an_upload_makes_its_thumbnail_as_the_pages_draw_it(store):
    client = _client(store)
    photo_id = client.post("/photos/upload", data={"photo": (io.BytesIO(_image()), "a.jpg")},
                           content_type="multipart/form-data").get_json()["id"]
    kept = [n for n in os.listdir(store.pictures_folder) if n.endswith("-thumb.png")]
    assert len(kept) == 1 and kept[0].startswith(photo_id + "-")
    rsp = client.get(f"/photos/{photo_id}/thumb.png?f=0.5,0.5,1")
    assert rsp.status_code == 200 and rsp.mimetype == "image/png" and "max-age=86400" in rsp.headers["Cache-Control"]
    with Image.open(io.BytesIO(rsp.data)) as img:
        left, top, right, bottom = WIDE
        assert img.width == 240 and abs(img.height - (bottom - top) * 240 / (right - left)) <= 1


def test_a_new_framing_makes_a_new_thumbnail_and_forgets_the_old(store):
    client = _client(store)
    photo = store.add(_image(), "a.jpg")
    client.get(f"/photos/{photo.id}/thumb.png")
    old = {n for n in os.listdir(store.pictures_folder) if n.endswith("-thumb.png")}
    client.post(f"/photos/{photo.id}/framing", json={"x": 0.2, "y": 0.2, "zoom": 2})
    client.get(f"/photos/{photo.id}/thumb.png")
    new = {n for n in os.listdir(store.pictures_folder) if n.endswith("-thumb.png")}
    assert len(new) == 1 and new != old


def test_deleting_a_photo_deletes_its_thumbnail(store):
    client = _client(store)
    photo = store.add(_image(), "a.jpg")
    client.get(f"/photos/{photo.id}/thumb.png")
    client.post(f"/photos/{photo.id}/delete")
    assert not [n for n in os.listdir(store.pictures_folder) if n.startswith(photo.id)]


def test_a_thumbnail_of_an_unknown_photo_is_404(store):
    assert _client(store).get("/photos/nope/thumb.png").status_code == 404


# ---------- Today's and tomorrow's marks ----------

def test_the_list_names_todays_and_tomorrows_photo(store):
    a = store.add(_image((1, 1, 1)), "a.jpg")
    b = store.add(_image((2, 2, 2)), "b.jpg")
    app = Flask(__name__)
    app.register_blueprint(photos_blueprint(store, WIDE, lambda: (b.id, a.id)))
    listing = app.test_client().get("/photos/list").get_json()
    assert (listing["today"], listing["tomorrow"]) == (b.id, a.id)
    assert _client(store).get("/photos/list").get_json()["today"] is None


def test_the_old_photos_page_forwards_to_the_pages_editor(store):
    rsp = _client(store).get("/photos")
    assert rsp.status_code == 301 and rsp.headers["Location"].endswith("pages")

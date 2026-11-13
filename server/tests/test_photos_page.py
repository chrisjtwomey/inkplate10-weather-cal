"""The Photos page (photos/page.py, photos/static) and its framing and preview
routes; the server's page previewer; and the picture shapes against the CSS."""
import io
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import pytest
from bs4 import BeautifulSoup
from flask import Flask
from PIL import Image

import server
from epd_server.source import StaticSource
from photos import Framing, PhotoStore, photos_blueprint
from views import page as views_page
from views.page import picture_windows
from weather.registry import create

HTML = Path(__file__).parent.parent / "views" / "html"
WINDOWS = picture_windows(825, 1200)


def _image(colour=(120, 60, 30)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (80, 60), colour).save(out, format="JPEG")
    return out.getvalue()


@pytest.fixture
def store(tmp_path):
    return PhotoStore(str(tmp_path / "photos"))


def _client(store, preview=None):
    app = Flask(__name__)
    app.register_blueprint(photos_blueprint(store, WINDOWS, preview))
    return app.test_client()


# ---------- The page ----------

def test_the_page_carries_the_shapes_and_loads_its_files(store):
    client = _client(store)
    rsp = client.get("/photos")
    assert rsp.status_code == 200 and rsp.headers["Cache-Control"] == "no-store"
    soup = BeautifulSoup(rsp.data, "html.parser")
    numbers = soup.find(id="numbers").string
    assert '"wide": [187.5' in numbers and '"tall": [187.5, 270.0, 1012.5, 930.0]' in numbers
    assert soup.find("script", src="photos/assets/photos.js")
    assert soup.find("link", href="static/look/look.css") and soup.find("link", href="photos/assets/photos.css")
    assert soup.find("a", href="settings").string == "Settings"
    for name in ("photos.js", "photos.css"):
        assert client.get(f"/photos/assets/{name}").status_code == 200
    assert client.get("/photos/assets/secrets.txt").status_code == 404


def test_the_page_words_follow_the_ui_rules(store):
    text = BeautifulSoup(_client(store).get("/photos").data, "html.parser").get_text(" ")
    assert "No photos yet. Add one to start." in text and "please" not in text.lower()
    soup = BeautifulSoup(_client(store).get("/photos").data, "html.parser")
    assert soup.find("label", attrs={"for": "files"}).string == "Add photos"
    assert soup.find(id="drop") and soup.find(id="delete").string == "Delete photo"


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


# ---------- Previews ----------

def test_a_preview_draws_the_unsaved_framing_and_leaves_the_saved_one(store):
    photo = store.add(_image(), "a.jpg")
    seen = []

    def preview(shape, url):
        with Image.open(urlparse(url).path) as img:
            seen.append((shape, img.size))
        return b"PNG"

    rsp = _client(store, preview).get(f"/photos/{photo.id}/preview/tall.png?x=0.2&y=0.4&zoom=3")
    assert rsp.status_code == 200 and rsp.data == b"PNG" and rsp.mimetype == "image/png"
    assert seen == [("tall", (1200, 1200))]
    assert store.photos()[0].framing == Framing()


def test_a_preview_of_an_unknown_shape_or_photo_is_404(store):
    photo = store.add(_image(), "a.jpg")
    client = _client(store, lambda shape, url: b"PNG")
    assert client.get(f"/photos/{photo.id}/preview/square.png?x=0.5&y=0.5&zoom=1").status_code == 404
    assert client.get("/photos/nope/preview/wide.png?x=0.5&y=0.5&zoom=1").status_code == 404
    assert _client(store).get(f"/photos/{photo.id}/preview/wide.png?x=0.5&y=0.5&zoom=1").status_code == 404


def test_a_preview_that_cannot_be_drawn_says_so(store):
    photo = store.add(_image(), "a.jpg")

    def preview(shape, url):
        raise LookupError(shape)

    rsp = _client(store, preview).get(f"/photos/{photo.id}/preview/wide.png?x=0.5&y=0.5&zoom=1")
    assert rsp.status_code == 503 and "No preview for this page" in rsp.get_json()["problem"]


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
    png = preview("wide", "file:///pictures/today.png")
    assert png.startswith(b"\x89PNG")
    assert "file:///pictures/today.png" in (html_dir / "preview-today.html").read_text()
    assert (tmp_path / "previews" / "preview-today.png").exists()


def test_the_previewer_uses_the_daily_page_when_the_hourly_page_is_not_drawn(tmp_path, monkeypatch):
    html_dir = tmp_path / "html"
    html_dir.mkdir()
    for cls in server.PAGES.values():
        monkeypatch.setattr(cls, "__init__", _with_html_dir(cls.__init__, str(html_dir)))
    no_hours = create("mock", location="Cork", num_hours=0, metric=True)
    preview = server.page_previewer({"width": 825, "height": 1200}, [StaticSource(map_url="map.png"), no_hours],
                                    str(tmp_path / "previews"), renderer=FakeRenderer())
    preview("tall", "file:///pictures/p.png")
    assert (html_dir / "preview-daily.html").exists() and not (html_dir / "preview-hourly.html").exists()


def _with_html_dir(init, html_dir):
    def wrapped(self, *args, **kwargs):
        init(self, *args, **kwargs)
        self.html_dir = html_dir
    return wrapped


# ---------- The shapes follow the pages' CSS ----------

def _css_number(file, pattern):
    match = re.search(pattern, (HTML / file).read_text(), flags=re.S)
    assert match, f"{pattern} not found in {file}"
    return float(match.group(1))


def test_the_picture_shapes_follow_the_css():
    assert _css_number("simplified.css", r"#map-container \{[^}]*height: calc\(var\(--inner-vw\) \* ([\d.]+)\)") / 100 \
        == pytest.approx(views_page.WIDE_HEIGHT_OF_WIDTH)
    assert _css_number("simplified.css", r"#map \{[^}]*top: ([\d.]+)%") / 100 == views_page.WIDE_CENTRE
    assert _css_number("styles.css", r"--map-height: ([\d.]+)%") / 100 == views_page.TALL_HEIGHT_OF_HEIGHT
    assert _css_number("styles.css", r"#map \{[^}]*top: ([\d.]+)%") / 100 == views_page.TALL_CENTRE


def test_the_shapes_are_the_rows_the_pages_show_at_the_panels_size():
    wide, tall = WINDOWS["wide"], WINDOWS["tall"]
    assert [round(v) for v in wide] == [188, 450, 1012, 950]
    assert [round(v) for v in tall] == [188, 270, 1012, 930]


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
        left, top, right, bottom = WINDOWS["wide"]
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


def test_the_list_asks_for_thumbnails_with_the_framing_not_originals():
    script = (Path(__file__).parent.parent / "photos" / "static" / "photos.js").read_text()
    assert '"/thumb.png?f="' in script and 'thumb.src = "photos/" + photo.id + "/original"' not in script


# ---------- Today's and tomorrow's marks ----------

def test_the_list_names_todays_and_tomorrows_photo(store):
    a = store.add(_image((1, 1, 1)), "a.jpg")
    b = store.add(_image((2, 2, 2)), "b.jpg")
    app = Flask(__name__)
    app.register_blueprint(photos_blueprint(store, WINDOWS, None, lambda: (b.id, a.id)))
    listing = app.test_client().get("/photos/list").get_json()
    assert (listing["today"], listing["tomorrow"]) == (b.id, a.id)
    assert _client(store).get("/photos/list").get_json()["today"] is None


def test_the_rows_can_be_moved_with_the_keyboard_as_well_as_dragged():
    script = (Path(__file__).parent.parent / "photos" / "static" / "photos.js").read_text()
    assert "ArrowUp" in script and "ArrowDown" in script and "setPointerCapture" in script
    assert 'button("Up"' not in script and 'button("Down"' not in script

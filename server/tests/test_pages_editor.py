"""The Pages editor's routes (pages_editor.py), with the running server's parts stood in."""
import io
import json
import os

import pytest
from bs4 import BeautifulSoup
from flask import Flask
from PIL import Image

from pages_editor import WORKING_SIZE, Editor, editor_blueprint
from photos import Framing, PhotoStore
from views.page import HTML_DIR
from views.themes import picture_box
from views.themes import PAGE_TYPES, THEMES

BOX = picture_box("classic", "today", 825, 1200)


class FakeLive:
    def __init__(self):
        self.pages = {t: {"theme": "classic", "photos": [], "map": "classic"} for t in PAGE_TYPES}
        self.saved, self.redrawn = [], []

    def current(self):
        return self.pages

    def save(self, changes):
        self.saved.append(changes)
        for t, c in changes.items():
            self.pages[t].update(c)
        return list(changes)

    def redraw(self, types):
        self.redrawn.extend(types)


def _photo(size=(3000, 2000), orientation=None) -> bytes:
    img = Image.new("RGB", size, (150, 90, 40))
    out = io.BytesIO()
    kwargs = {}
    if orientation:
        exif = Image.Exif()
        exif[0x0112] = orientation
        kwargs["exif"] = exif.tobytes()
    img.save(out, format="JPEG", **kwargs)
    return out.getvalue()


@pytest.fixture
def parts(tmp_path):
    store = PhotoStore(str(tmp_path / "photos"))
    map_png = tmp_path / "map.png"
    Image.new("L", (1200, 1200), 200).save(map_png)
    rendered = []
    live = FakeLive()

    def page_html(name, sample):
        if name == "daily":
            raise LookupError("The daily page is not drawn now: no forecasts")
        return f'<html><body data-sample="{sample}"><div data-picture="main"><img id="map" src="photo-{name}.png"></div></body></html>'

    def render(name, picture_uri):
        rendered.append((name, picture_uri))
        return b"\x89PNG-" + name.encode()

    ed = Editor(live, store, HTML_DIR, page_html, lambda: str(map_png), lambda name: None, render,
                lambda name: BOX, themes=THEMES, page_types=PAGE_TYPES, map_kinds=("classic",))
    app = Flask(__name__)
    app.register_blueprint(editor_blueprint(ed))
    return app.test_client(), store, live, rendered


def test_the_editor_names_the_page_types_themes_and_maps(parts):
    client, *_ = parts
    soup = BeautifulSoup(client.get("/pages").data, "html.parser")
    numbers = json.loads(soup.find(id="numbers").string)
    assert numbers["pageTypes"] == list(PAGE_TYPES) and numbers["maps"] == ["classic"]
    assert numbers["themes"]["classic"] == {"label": "Classic", "pages": list(PAGE_TYPES)}
    assert soup.find("script", src="pages/assets/pages.js") and soup.find("a", href="settings")
    for name in ("pages.js", "pages.css"):
        assert client.get(f"/pages/assets/{name}").status_code == 200


def test_a_page_view_is_its_html_with_its_files_beside_it(parts):
    client, *_ = parts
    rsp = client.get("/pages/view/hourly.html?sample=1")
    assert rsp.status_code == 200 and b'data-sample="True"' in rsp.data and b"photo-hourly.png" in rsp.data
    assert b"is not drawn now" in client.get("/pages/view/daily.html").data
    assert client.get("/pages/view/weekly.html").status_code == 404
    assert client.get("/pages/view/styles.css").status_code == 200
    assert client.get("/pages/view/map.png").status_code == 200
    assert client.get("/pages/view/photo-today.png").data == client.get("/pages/view/map.png").data


def test_a_working_copy_is_upright_grey_and_small(parts):
    client, store, *_ = parts
    photo = store.add(_photo((3000, 2000), orientation=6), "phone.jpg")
    with Image.open(io.BytesIO(client.get(f"/pages/photo/{photo.id}.jpg").data)) as img:
        assert img.mode == "L" and img.height == WORKING_SIZE and abs(img.width - WORKING_SIZE * 2000 / 3000) <= 1


def test_a_framing_is_saved_for_one_page_and_that_page_is_redrawn(parts):
    client, store, live, _ = parts
    photo = store.add(_photo(), "a.jpg")
    assert client.post(f"/pages/photo/{photo.id}/framing/hourly", json={"x": 0.3, "y": 0.4, "zoom": 2}).status_code == 204
    assert store.photos()[0].framings == {"hourly": Framing(0.3, 0.4, 2.0)}
    assert live.redrawn == ["hourly"]
    assert client.post(f"/pages/photo/{photo.id}/framing/weekly", json={"x": 0.3, "y": 0.4, "zoom": 2}).status_code == 404
    assert client.post(f"/pages/photo/{photo.id}/framing/today", json={"x": "a"}).status_code == 400


def test_deleting_a_photo_takes_it_off_every_page(parts):
    client, store, live, _ = parts
    a, b = store.add(_photo((300, 200)), "a.jpg"), store.add(_photo((310, 200)), "b.jpg")
    live.pages["today"]["photos"] = [a.id, b.id]
    live.pages["hourly"]["photos"] = [a.id]
    assert client.post(f"/pages/photo/{a.id}/delete").status_code == 204
    assert live.saved == [{"today": {"photos": [b.id]}, "hourly": {"photos": []}}]
    assert [p.id for p in store.photos()] == [b.id]


def test_panel_view_draws_the_page_with_the_unsaved_framing(parts):
    client, store, _, rendered = parts
    photo = store.add(_photo((400, 300)), "a.jpg")
    rsp = client.get(f"/pages/panel/today.png?photo={photo.id}&x=0.3&y=0.3&zoom=1.5")
    assert rsp.status_code == 200 and rsp.data == b"\x89PNG-today"
    assert rendered[-1][0] == "today" and rendered[-1][1].endswith("picture.png")
    assert store.photos()[0].framings == {}
    assert client.get("/pages/panel/hourly.png").status_code == 200 and rendered[-1][1].endswith("map.png")

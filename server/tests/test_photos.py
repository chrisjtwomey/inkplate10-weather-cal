"""The photo store (photos/store.py) and its routes (photos/routes.py)."""
import io
import json
import os

import pytest
from epd_server.login import Login, guard
from flask import Flask
from PIL import Image

import settings_page as sp
from photos import Framing, PhotoError, PhotoStore, photos_blueprint
from photos import store as store_module


def _image(fmt="JPEG", size=(40, 30), colour=(200, 100, 50)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, colour).save(out, format=fmt)
    return out.getvalue()


@pytest.fixture
def store(tmp_path):
    clock = iter(range(1000, 2000))
    return PhotoStore(str(tmp_path / "photos"), now=lambda: next(clock))


@pytest.fixture
def client(store):
    app = Flask(__name__)
    app.register_blueprint(photos_blueprint(store))
    return app.test_client()


# ---------- The store ----------

def test_a_new_store_has_no_photos(store):
    assert store.photos() == [] and store.the_set() == []


@pytest.mark.parametrize("fmt, extension", [("JPEG", "jpg"), ("PNG", "png"), ("WEBP", "webp")])
def test_a_photo_is_kept_as_uploaded_and_named_by_its_content(store, fmt, extension):
    data = _image(fmt)
    photo = store.add(data, "Cork at dusk." + extension)
    assert photo.file == f"{photo.id}.{extension}" and photo.name == "Cork at dusk." + extension
    with open(store.path(photo.id), "rb") as f:
        assert f.read() == data
    assert photo.in_set and photo.framing == Framing()


def test_photos_join_the_set_in_upload_order_and_survive_a_restart(store):
    first = store.add(_image(colour=(1, 1, 1)), "a.jpg")
    second = store.add(_image(colour=(2, 2, 2)), "b.jpg")
    again = PhotoStore(store.folder)
    assert [p.id for p in again.the_set()] == [first.id, second.id]


def test_the_same_photo_twice_is_refused(store):
    store.add(_image(), "a.jpg")
    with pytest.raises(PhotoError, match="already added"):
        store.add(_image(), "copy of a.jpg")


@pytest.mark.parametrize("data", [b"not a photo", b"", _image("GIF")])
def test_a_file_that_is_not_a_jpeg_png_or_webp_is_refused(store, data):
    with pytest.raises(PhotoError, match="Use a JPEG, PNG or WebP file"):
        store.add(data, "x")
    assert store.photos() == []


def test_a_file_over_20_mb_is_refused(store, monkeypatch):
    monkeypatch.setattr(store_module, "MAX_BYTES", 100)
    with pytest.raises(PhotoError, match="larger than 20 MB"):
        store.add(_image(), "big.jpg")


def test_a_photo_over_50_megapixels_is_refused(store, monkeypatch):
    monkeypatch.setattr(store_module, "MAX_PIXELS", 40 * 30 - 1)
    with pytest.raises(PhotoError, match="more than 50 megapixels"):
        store.add(_image(size=(40, 30)), "huge.jpg")


def test_a_name_from_the_browser_keeps_only_its_last_part(store):
    assert store.add(_image(), "../../etc/passwd").name == "passwd"


def test_removing_a_photo_deletes_its_file(store):
    photo = store.add(_image(), "a.jpg")
    path = store.path(photo.id)
    store.remove(photo.id)
    assert store.photos() == [] and not os.path.exists(path)
    with pytest.raises(KeyError):
        store.remove(photo.id)


def test_the_set_can_be_reordered_and_a_photo_left_out(store):
    a, b, c = (store.add(_image(colour=(i, i, i)), f"{i}.jpg") for i in range(3))
    store.reorder([c.id, a.id, b.id])
    store.include(a.id, False)
    assert [p.id for p in store.photos()] == [c.id, a.id, b.id]
    assert [p.id for p in store.the_set()] == [c.id, b.id]


@pytest.mark.parametrize("ids", [[], ["x"], "dup"])
def test_an_order_must_list_each_photo_once(store, ids):
    a, b = (store.add(_image(colour=(i, i, i)), f"{i}.jpg") for i in range(2))
    ids = [a.id, a.id] if ids == "dup" else ids
    with pytest.raises(PhotoError, match="each photo once"):
        store.reorder(ids)


def test_a_framing_is_kept(store):
    photo = store.add(_image(), "a.jpg")
    store.frame(photo.id, Framing(0.3, 0.7, 2.5))
    assert PhotoStore(store.folder).photos()[0].framing == Framing(0.3, 0.7, 2.5)


# ---------- The routes ----------

def _upload(client, data, name="Cork.jpg"):
    return client.post("/photos/upload", data={"photo": (io.BytesIO(data), name)},
                       content_type="multipart/form-data")


def test_an_upload_is_listed_and_served(client):
    data = _image()
    sent = _upload(client, data)
    assert sent.status_code == 201
    photo_id = sent.get_json()["id"]
    assert [p["id"] for p in client.get("/photos/list").get_json()["photos"]] == [photo_id]
    assert client.get(f"/photos/{photo_id}/original").data == data


def test_a_refused_upload_says_why(client):
    sent = _upload(client, b"plain text", "notes.txt")
    assert sent.status_code == 400
    assert sent.get_json() == {"problem": "That file is not a photo. Use a JPEG, PNG or WebP file."}
    assert client.post("/photos/upload", data={}, content_type="multipart/form-data").status_code == 400


def test_an_upload_too_large_to_read_is_refused_before_it_is_read(client, monkeypatch):
    monkeypatch.setattr("photos.routes.MAX_BYTES", 10)
    sent = _upload(client, b"x" * (70 * 1024))
    assert sent.status_code == 413 and "larger than 20 MB" in sent.get_json()["problem"]


def test_delete_order_and_set_change_the_store(client, store):
    a = _upload(client, _image(colour=(1, 1, 1)), "a.jpg").get_json()["id"]
    b = _upload(client, _image(colour=(2, 2, 2)), "b.jpg").get_json()["id"]
    assert client.post("/photos/order", json={"ids": [b, a]}).status_code == 204
    assert client.post(f"/photos/{b}/set", json={"in_set": False}).status_code == 204
    assert [p.id for p in store.the_set()] == [a]
    assert client.post(f"/photos/{a}/delete").status_code == 204
    assert [p.id for p in store.photos()] == [b]


def test_an_unknown_photo_is_404(client):
    for rsp in (client.get("/photos/nope/original"), client.post("/photos/nope/delete"),
                client.post("/photos/nope/set", json={"in_set": True})):
        assert rsp.status_code == 404 and rsp.get_json() == {"problem": "No such photo."}


@pytest.mark.parametrize("path, body", [("/photos/order", {"ids": "a"}), ("/photos/order", None),
                                        ("/photos/x/set", {"in_set": "yes"})])
def test_a_malformed_change_is_400(client, path, body):
    rsp = client.post(path, data=json.dumps(body), content_type="application/json")
    assert rsp.status_code == 400


def test_an_order_that_drops_a_photo_is_refused(client):
    _upload(client, _image(), "a.jpg")
    rsp = client.post("/photos/order", json={"ids": []})
    assert rsp.status_code == 400 and "each photo once" in rsp.get_json()["problem"]


# ---------- Behind the server's sign-in ----------

def test_the_photos_need_a_sign_in_and_another_site_is_refused(store, tmp_path):
    login = Login("correct horse", str(tmp_path / "login.json"))
    app = Flask(__name__)
    app.register_blueprint(photos_blueprint(store))
    guard(app, login, sp.SITE)
    client = app.test_client()
    assert client.get("/photos/list").status_code == 401
    assert _upload(client, _image()).status_code == 401
    client.post("/login", data={"password": "correct horse"})
    assert client.get("/photos/list").status_code == 200
    rsp = client.post("/photos/upload", data={"photo": (io.BytesIO(_image()), "a.jpg")},
                      content_type="multipart/form-data", headers={"Origin": "http://evil.example"})
    assert rsp.status_code == 403 and store.photos() == []


def test_saved_files_have_the_usual_permissions(store):
    umask = os.umask(0o022)
    try:
        photo = store.add(_image(), "a.jpg")
    finally:
        os.umask(umask)
    assert oct(os.stat(store.path(photo.id)).st_mode & 0o777) == oct(0o644)
    assert oct(os.stat(os.path.join(store.folder, "manifest.json")).st_mode & 0o777) == oct(0o644)

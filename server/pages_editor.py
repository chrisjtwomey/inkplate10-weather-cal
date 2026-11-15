"""The Pages editor: each page in its own HTML, live, with its theme, map and
photos, and the photo library.

    GET  /pages                              the editor
    GET  /pages/assets/<name>                its script and stylesheet
    GET  /pages/view/<page>.html?sample=1    the page's HTML, from today's or sample weather
    GET  /pages/view/<file>                  the styles, fonts and icons that HTML loads
    GET  /pages/view/map.png                 the map
    GET  /pages/view/photo-<page>.png        the page's picture today, or the map
    GET  /pages/photo/<id>.jpg               a photo upright, in grey, at most WORKING_SIZE across
    POST /pages/photo/<id>/framing/<page>    JSON {"x", "y", "zoom"}: the photo's framing on that page
    POST /pages/photo/<id>/delete            the photo, from the library and every page
    GET  /pages/panel/<page>.png?photo=&x=&y=&zoom=
                                             the page as the display draws it

The page settings themselves are saved at /pages/settings (page_settings.py).
The server's sign-in covers these routes, and its Origin check covers each change.
"""
import html
import io
import json
import math
import os
import tempfile
from collections.abc import Callable
from pathlib import Path

from flask import Blueprint, Response, abort, jsonify, request, send_file, send_from_directory
from PIL import Image

from photos.picture import AREA_MIN_ZOOM, MAX_ZOOM, MIN_ZOOM, page_drawing, upright
from photos.store import Framing, PhotoStore, write_atomically

_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "pages_editor_static")
_ASSETS = ("pages.js", "pages.css")
WORKING_SIZE = 1600
NO_PANEL = "This page cannot be drawn now. Check the server's log."


class Editor:
    """What the editor needs from the running server.

    page_html(page, sample) -> the page's HTML, with "map.png" and "photo-<page>.png"
        as its pictures; raises LookupError when the page has nothing to show
    map_file() -> the map image's path
    photo_file(page) -> the page's picture today, or None
    render(page, picture_uri) -> the page as PNG, as the display draws it
    box(page) -> the page's picture area on the picture square
    """

    def __init__(self, live, store: PhotoStore, views_dir: str, page_html: Callable, map_file: Callable,
                 photo_file: Callable, render: Callable, box: Callable, themes: dict, page_types: tuple,
                 map_kinds: tuple):
        self.live, self.store, self.views_dir = live, store, views_dir
        self.page_html, self.map_file, self.photo_file = page_html, map_file, photo_file
        self.render, self.box = render, box
        self.themes, self.page_types, self.map_kinds = themes, page_types, map_kinds


def _framing(given) -> Framing:
    try:
        x, y, zoom = (float(given[k]) for k in ("x", "y", "zoom"))
    except (TypeError, KeyError, ValueError):
        abort(400)
    if not all(math.isfinite(v) for v in (x, y, zoom)) or zoom <= 0:
        abort(400)
    return Framing(min(max(x, 0.0), 1.0), min(max(y, 0.0), 1.0), min(max(zoom, AREA_MIN_ZOOM), MAX_ZOOM))


def editor_blueprint(ed: Editor) -> Blueprint:
    bp = Blueprint("pages_editor", __name__, url_prefix="/pages")

    def page_type(name: str) -> str:
        if name not in ed.page_types:
            abort(404)
        return name

    def photo(photo_id: str):
        found = next((p for p in ed.store.photos() if p.id == photo_id), None)
        if found is None:
            abort(404)
        return found

    @bp.route("", methods=["GET"])
    def editor():
        numbers = {
            "pageTypes": list(ed.page_types),
            "themes": {n: {"label": t.label, "pages": list(t.pages)} for n, t in ed.themes.items()},
            "maps": list(ed.map_kinds),
            "minZoom": AREA_MIN_ZOOM, "maxZoom": MAX_ZOOM, "squareMinZoom": MIN_ZOOM,
        }
        return Response(_page(json.dumps(numbers)), headers={"Cache-Control": "no-store"})

    @bp.route("/assets/<name>", methods=["GET"])
    def asset(name: str):
        if name not in _ASSETS:
            abort(404)
        return send_from_directory(_ASSETS_DIR, name, max_age=0)

    @bp.route("/view/<name>.html", methods=["GET"])
    def view(name: str):
        try:
            body = ed.page_html(page_type(name), request.args.get("sample") == "1")
        except LookupError as exc:
            body = f"<!DOCTYPE html><p>{html.escape(str(exc))}</p>"
        return Response(body, mimetype="text/html", headers={"Cache-Control": "no-store"})

    @bp.route("/view/map.png", methods=["GET"])
    def map_image():
        path = ed.map_file()
        if not path:
            abort(404)
        return send_file(path, max_age=0)

    @bp.route("/view/photo-<name>.png", methods=["GET"])
    def page_photo(name: str):
        path = ed.photo_file(page_type(name)) or ed.map_file()
        if not path:
            abort(404)
        return send_file(path, max_age=0)

    @bp.route("/view/<path:name>", methods=["GET"])
    def view_file(name: str):
        if name.endswith(".html"):
            abort(404)
        return send_from_directory(ed.views_dir, name, max_age=3600)

    @bp.route("/photo/<photo_id>.jpg", methods=["GET"])
    def working(photo_id: str):
        found = photo(photo_id)
        folder = os.path.join(ed.store.folder, "working")
        path = os.path.join(folder, f"{found.id}.jpg")
        if not os.path.exists(path):
            with Image.open(ed.store.path(found.id)) as img:
                grey = upright(img)
            grey.thumbnail((WORKING_SIZE, WORKING_SIZE), Image.LANCZOS)
            out = io.BytesIO()
            grey.save(out, format="JPEG", quality=92)
            os.makedirs(folder, exist_ok=True)
            write_atomically(path, out.getvalue())
        return send_file(path, max_age=86400)

    @bp.route("/photo/<photo_id>/framing/<name>", methods=["POST"])
    def framing(photo_id: str, name: str):
        ed.store.frame_page(photo(photo_id).id, page_type(name), _framing(request.get_json(silent=True)))
        ed.live.redraw([name])
        return "", 204

    @bp.route("/photo/<photo_id>/delete", methods=["POST"])
    def delete(photo_id: str):
        gone = photo(photo_id).id
        lists = {t: [i for i in s["photos"] if i != gone] for t, s in ed.live.current().items() if gone in s["photos"]}
        try:
            if lists:
                ed.live.save({t: {"photos": ids} for t, ids in lists.items()})
        except ValueError as exc:
            return jsonify(problem=str(exc)), 400
        ed.store.remove(gone)
        try:
            os.remove(os.path.join(ed.store.folder, "working", f"{gone}.jpg"))
        except FileNotFoundError:
            pass
        return "", 204

    @bp.route("/panel/<name>.png", methods=["GET"])
    def panel(name: str):
        name = page_type(name)
        with tempfile.TemporaryDirectory() as folder:
            picture = ed.map_file()
            if request.args.get("photo"):
                found = photo(request.args["photo"])
                found.framings[name] = _framing(request.args)
                picture = os.path.join(folder, "picture.png")
                with open(picture, "wb") as f:
                    f.write(page_drawing(ed.store, found, name, ed.box(name)))
            try:
                png = ed.render(name, Path(picture).resolve().as_uri() if picture else "")
            except LookupError:
                return jsonify(problem=NO_PANEL), 503
        return Response(png, mimetype="image/png", headers={"Cache-Control": "no-store"})

    return bp


def _page(numbers: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pages</title>
<link rel="stylesheet" href="static/look/look.css">
<link rel="stylesheet" href="pages/assets/pages.css">
</head>
<body>
<header class="top"><h1>Pages</h1><div class="links"><a href="settings">Settings</a></div></header>
<noscript><p class="banner problem">This page needs JavaScript.</p></noscript>
<p class="banner" id="message" role="alert" hidden></p>

<div class="editor">
  <div class="bar">
    <div class="tabs" id="tabs" role="tablist" aria-label="Pages"></div>
  </div>

  <div class="stage">
    <div class="preview" id="preview">
      <iframe id="page" title="The page" scrolling="no"></iframe>
      <div class="frame-handle" id="handle" tabindex="0" aria-label="The photo's framing" hidden>
        <span class="hint" id="hint">Drag to move · Scroll to zoom</span>
      </div>
      <img id="panel" alt="The page as the display draws it" hidden>
    </div>
    <div class="side">
      <section class="page-theme">
        <label class="field">Theme <select id="theme"></select><span class="only" id="theme-only"></span></label>
        <button type="button" class="link" id="theme-everywhere">Use on every page</button>
      </section>
      <section class="page-picture">
        <div class="heading"><h3>Picture</h3><button type="button" id="add">+ Add photos</button></div>
        <label class="field">Map <select id="map"></select><span class="only" id="map-only"></span></label>
        <p class="help">The page shows its map when it has no photos. One photo stays; more change each day, in this order.</p>
        <ol id="strip"></ol>
      </section>
      <div id="framing-tools" hidden>
        <p class="help">Arrow keys move; + and − zoom; double-click centres.</p>
        <label>Zoom <input type="range" id="zoom" step="0.01"></label>
        <div class="row"><button type="button" id="centre">Centre</button>
        <button type="button" id="undo-framing">Undo</button></div>
        <button type="button" class="link" id="framing-everywhere">Use this framing on every page</button>
        <p class="help" id="framing-status" aria-live="polite"></p>
      </div>
      <div class="view">
        <label class="switch"><input type="checkbox" id="sample"> Sample weather</label>
        <label class="switch"><input type="checkbox" id="actual-size"> Actual size</label>
        <button type="button" id="panel-view">Panel view</button>
        <p class="help" id="status" aria-live="polite"></p>
      </div>
    </div>
  </div>
</div>

<section id="library">
  <h2>Photo library</h2>
  <div class="row">
    <label class="button primary" for="files">Upload photos</label>
    <input type="file" id="files" accept="image/jpeg,image/png,image/webp" multiple hidden>
    <p class="help">Or drop them on this page. JPEG, PNG or WebP, up to 20 MB each.</p>
  </div>
  <ul id="uploads"></ul>
  <ul id="photos"></ul>
  <p id="empty" hidden>No photos yet. Upload one to start.</p>
</section>

<dialog id="picker">
  <h2>Add photos to this page</h2>
  <ul id="choices"></ul>
  <button type="button" id="picker-cancel">Cancel</button>
  <button type="button" class="primary" id="picker-add">Add</button>
</dialog>
<div id="drop" hidden><p>Drop photos to add them</p></div>

<script type="application/json" id="numbers">{numbers}</script>
<script src="pages/assets/pages.js"></script>
</body>
</html>
"""

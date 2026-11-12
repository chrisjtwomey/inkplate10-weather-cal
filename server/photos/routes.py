"""The Photos page, and the photo store over HTTP for its script.

    GET  /photos                    the page
    GET  /photos/assets/<name>      its script and stylesheet
    GET  /photos/list               every photo, in set order
    POST /photos/upload             form field ``photo``: a new photo, at the end of the set
    GET  /photos/<id>/original      the photo as it was uploaded
    POST /photos/<id>/delete
    POST /photos/<id>/set           JSON {"in_set": true|false}
    POST /photos/order              JSON {"ids": [...]}: the new set order
    POST /photos/<id>/framing       JSON {"x", "y", "zoom"}
    GET  /photos/<id>/preview/<shape>.png?x=&y=&zoom=
                                    a page of that shape with the photo so framed

The server's sign-in covers these routes, and its Origin check covers each change.
"""
import math
import os
import tempfile
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from flask import Blueprint, Response, abort, jsonify, request, send_file, send_from_directory

from .page import photos_page
from .picture import MAX_ZOOM, MIN_ZOOM, drawing
from .store import MAX_BYTES, NO_SUCH_PHOTO, NOT_A_PHOTO, TOO_LARGE, Framing, PhotoError, PhotoStore

_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "static")
_ASSETS = ("photos.js", "photos.css")
NO_PREVIEW = "No preview for this page. Check the server's log."

# A page of a shape, with a picture at a file:// address, as PNG. Raises LookupError
# when no page of that shape can be drawn now.
Preview = Callable[[str, str], bytes]


def photos_blueprint(store: PhotoStore, windows: dict | None = None, preview: Preview | None = None) -> Blueprint:
    """The page and its routes. ``windows`` is each picture shape the pages show,
    as ``(left, top, right, bottom)`` in the picture's square."""
    bp = Blueprint("photos", __name__, url_prefix="/photos")

    def problem(words: str, status: int):
        return jsonify(problem=words), status

    @bp.errorhandler(KeyError)
    def no_such_photo(_exc):
        return problem(NO_SUCH_PHOTO, 404)

    @bp.errorhandler(PhotoError)
    def refused(exc):
        return problem(str(exc), 400)

    @bp.route("", methods=["GET"])
    def page():
        return Response(photos_page(windows or {}), headers={"Cache-Control": "no-store"})

    @bp.route("/assets/<name>", methods=["GET"])
    def asset(name: str):
        if name not in _ASSETS:
            abort(404)
        return send_from_directory(_ASSETS_DIR, name, max_age=0)

    @bp.route("/list", methods=["GET"])
    def listing():
        return jsonify(photos=[asdict(p) for p in store.photos()])

    @bp.route("/upload", methods=["POST"])
    def upload():
        if request.content_length is not None and request.content_length > MAX_BYTES + 64 * 1024:
            return problem(TOO_LARGE, 413)
        sent = request.files.get("photo")
        if sent is None:
            return problem(NOT_A_PHOTO, 400)
        data = sent.stream.read(MAX_BYTES + 1)
        return jsonify(asdict(store.add(data, sent.filename or ""))), 201

    @bp.route("/<photo_id>/original", methods=["GET"])
    def original(photo_id: str):
        return send_file(store.path(photo_id), max_age=0)

    @bp.route("/<photo_id>/delete", methods=["POST"])
    def delete(photo_id: str):
        store.remove(photo_id)
        return "", 204

    @bp.route("/<photo_id>/set", methods=["POST"])
    def in_or_out(photo_id: str):
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or not isinstance(body.get("in_set"), bool):
            abort(400)
        store.include(photo_id, body["in_set"])
        return "", 204

    @bp.route("/order", methods=["POST"])
    def order():
        body = request.get_json(silent=True)
        ids = body.get("ids") if isinstance(body, dict) else None
        if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
            abort(400)
        store.reorder(ids)
        return "", 204

    @bp.route("/<photo_id>/framing", methods=["POST"])
    def framing(photo_id: str):
        store.frame(photo_id, _framing(request.get_json(silent=True)))
        return "", 204

    @bp.route("/<photo_id>/preview/<shape>.png", methods=["GET"])
    def preview_page(photo_id: str, shape: str):
        if preview is None or shape not in (windows or {}):
            abort(404)
        photo = next((p for p in store.photos() if p.id == photo_id), None)
        if photo is None:
            raise KeyError(photo_id)
        with tempfile.TemporaryDirectory() as folder:
            picture = os.path.join(folder, "picture.png")
            with open(picture, "wb") as f:
                f.write(drawing(store, photo, _framing(request.args)))
            try:
                png = preview(shape, Path(picture).resolve().as_uri())
            except LookupError:
                return problem(NO_PREVIEW, 503)
        return Response(png, mimetype="image/png", headers={"Cache-Control": "no-store"})

    return bp


def _framing(given) -> Framing:
    """A framing from JSON or a query string, kept in range. Aborts with 400 on a
    missing or unreadable number."""
    try:
        x, y, zoom = (float(given[k]) for k in ("x", "y", "zoom"))
    except (TypeError, KeyError, ValueError):
        abort(400)
    if not all(math.isfinite(v) for v in (x, y, zoom)) or zoom <= 0:
        abort(400)
    return Framing(min(max(x, 0.0), 1.0), min(max(y, 0.0), 1.0), min(max(zoom, MIN_ZOOM), MAX_ZOOM))

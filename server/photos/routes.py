"""The photo store over HTTP, for the Photos page.

    GET  /photos/list               every photo, in set order
    POST /photos/upload             form field ``photo``: a new photo, at the end of the set
    GET  /photos/<id>/original      the photo as it was uploaded
    POST /photos/<id>/delete
    POST /photos/<id>/set           JSON {"in_set": true|false}
    POST /photos/order              JSON {"ids": [...]}: the new set order

The server's sign-in covers these routes, and its Origin check covers each change.
"""
from dataclasses import asdict

from flask import Blueprint, abort, jsonify, request, send_file

from .store import MAX_BYTES, NO_SUCH_PHOTO, NOT_A_PHOTO, TOO_LARGE, PhotoError, PhotoStore


def photos_blueprint(store: PhotoStore) -> Blueprint:
    bp = Blueprint("photos", __name__, url_prefix="/photos")

    def problem(words: str, status: int):
        return jsonify(problem=words), status

    @bp.errorhandler(KeyError)
    def no_such_photo(_exc):
        return problem(NO_SUCH_PHOTO, 404)

    @bp.errorhandler(PhotoError)
    def refused(exc):
        return problem(str(exc), 400)

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

    return bp

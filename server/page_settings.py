"""Each page's theme, photos and map, changed while the server runs: written to
the pages block of config.yaml and applied at once, with a redraw of the
changed pages and no restart.

    GET  /pages/settings     each page type's theme, photos and map
    POST /pages/settings     JSON {page type: {"theme", "photos", "map"}}: save and apply

The server's sign-in covers these routes, and its Origin check covers each change.
"""
import logging
import os
import threading

import yaml
from epd_server.config_file import Doc
from epd_server.settings_page import READ_ONLY, save
from flask import Blueprint, jsonify, request

log = logging.getLogger("pages")


class LivePages:
    """The pages' settings as the server runs them.

    ``make_page(page_type, cfg)`` builds a page for a ServerConfig; ``photo_pages``
    is the mapping the photo source reads, updated in place; ``check`` raises
    ValueError when the server would not start on a config's text.
    """

    def __init__(self, cfg, config_path: str, load, check, make_page, photo_pages: dict, included,
                 server=None, on_change=lambda cfg: None):
        self.cfg = cfg
        self.config_path = config_path
        self._load = load
        self._check = check
        self._make_page = make_page
        self.photo_pages = photo_pages
        self._included = included
        self.server = server
        self._on_change = on_change
        self._lock = threading.Lock()
        self._redraw_lock = threading.Lock()
        self._redrawing = {}

    def current(self) -> dict:
        return {t: {"theme": self.cfg.page_themes[t], "photos": self.photo_list(self.cfg, t),
                    "map": self.cfg.page_maps[t]} for t in self.cfg.page_themes}

    def photo_list(self, cfg, page_type: str) -> list[str]:
        """The page's photos as ids: its own list, else the included photos when its
        old ``picture`` setting is photos, else none."""
        own = cfg.page_photos[page_type]
        if own is not None:
            return list(own)
        return list(self._included()) if cfg.pictures[page_type] == "photos" else []

    def save(self, changes: dict) -> list[str]:
        """Writes ``changes`` into config.yaml and applies them. Returns the page
        types that changed.

        Raises:
            ValueError: a change is not valid, or config.yaml cannot be written.
        """
        with self._lock:
            with open(self.config_path) as f:
                text = f.read()
            doc = Doc(text)
            has_old_picture = doc.get(("picture",)) is not None
            for page_type in self.cfg.page_themes:
                given = changes.get(page_type) or {}
                if not isinstance(given, dict):
                    raise ValueError(f"{page_type}: the settings must be a mapping")
                carried = self.photo_list(self.cfg, page_type) if has_old_picture else None
                photos = given.get("photos", carried or None)
                for key, value in (("theme", given.get("theme")), ("photos", photos), ("map", given.get("map"))):
                    if value is not None:
                        doc.set(("pages", page_type, key), value)
            unknown = sorted(set(changes) - set(self.cfg.page_themes))
            if unknown:
                raise ValueError(f"{unknown[0]}: no such page")
            if has_old_picture:
                doc.remove(("picture",))
            new_text = doc.text()
            self._check(new_text)
            if not os.access(self.config_path, os.W_OK):
                raise ValueError(READ_ONLY)
            save(self.config_path, new_text)
            old, self.cfg = self.cfg, self._load(yaml.safe_load(new_text))
            self._on_change(self.cfg)
            changed = [t for t in self.cfg.page_themes
                       if self._settings_of(old, t) != self._settings_of(self.cfg, t)]
            self._apply(changed)
            return changed

    def _settings_of(self, cfg, page_type: str) -> tuple:
        return cfg.page_themes[page_type], tuple(self.photo_list(cfg, page_type)), cfg.page_maps[page_type]

    def _apply(self, changed: list[str]) -> None:
        for page_type in self.cfg.page_themes:
            photos = self.photo_list(self.cfg, page_type)
            if photos:
                self.photo_pages[page_type] = photos
            else:
                self.photo_pages.pop(page_type, None)
        if self.server is None or not changed:
            return
        with self.server.regen_lock:
            for i, page in enumerate(self.server.pages):
                if page.name in changed:
                    self.server.pages[i] = self._make_page(page.name, self.cfg)
        self.redraw(changed)

    def redraw(self, page_types: list[str]) -> None:
        """Redraws those pages in the background, so the display gets them at its next wake.

        A page has at most one redraw running. Requests that arrive during it make
        one more redraw when it ends, so a run of small changes costs two redraws.
        """
        if self.server is None:
            return
        start = []
        with self._redraw_lock:
            for page_type in dict.fromkeys(page_types):
                if page_type in self._redrawing:
                    self._redrawing[page_type] = True
                else:
                    self._redrawing[page_type] = False
                    start.append(page_type)
        if start:
            threading.Thread(target=self._redraw, args=(start,), daemon=True).start()

    def _redraw(self, page_types: list[str]) -> None:
        for page_type in page_types:
            again = True
            while again:
                try:
                    self.server.regenerate(only=f"{page_type}.png")
                except Exception:
                    log.exception("Could not redraw the %s page", page_type)
                with self._redraw_lock:
                    again = self._redrawing.pop(page_type)
                    if again:
                        self._redrawing[page_type] = False


def pages_blueprint(live: LivePages) -> Blueprint:
    bp = Blueprint("pages", __name__, url_prefix="/pages")

    @bp.route("/settings", methods=["GET"])
    def settings():
        return jsonify(pages=live.current())

    @bp.route("/settings", methods=["POST"])
    def change():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(problem="Send each page's settings as JSON."), 400
        try:
            changed = live.save(body)
        except ValueError as exc:
            return jsonify(problem=str(exc)), 400
        return jsonify(pages=live.current(), changed=changed)

    return bp

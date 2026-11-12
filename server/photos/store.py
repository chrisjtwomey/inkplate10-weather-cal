"""The photos a person uploads to show in place of the map, kept in one folder.

The folder holds each photo as it was uploaded, named by its content, and
``manifest.json``: the photos in their set order, whether each is in the set,
and its framing.
"""
import hashlib
import io
import json
import os
import tempfile
import threading
import time
import warnings
from dataclasses import asdict, dataclass, field

from PIL import Image

MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 50_000_000
# Pillow's format name -> the file's extension.
FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}

NOT_A_PHOTO = "That file is not a photo. Use a JPEG, PNG or WebP file."
TOO_LARGE = "That photo is larger than 20 MB."
TOO_MANY_PIXELS = "That photo has more than 50 megapixels."
ALREADY_ADDED = "That photo is already added."
NO_SUCH_PHOTO = "No such photo."
NOT_THE_SAME_PHOTOS = "The new order must list each photo once."


class PhotoError(ValueError):
    """An upload or a change the store refuses. Its message is for the person."""


@dataclass
class Framing:
    """Which part of the photo fills the picture: the centre of the crop, as a
    fraction of the photo's width and height, and the zoom (1 fills the frame)."""
    x: float = 0.5
    y: float = 0.5
    zoom: float = 1.0


@dataclass
class Photo:
    id: str
    file: str
    name: str
    added: float
    in_set: bool = True
    framing: Framing = field(default_factory=Framing)

    @classmethod
    def from_json(cls, d: dict) -> "Photo":
        return cls(**{**d, "framing": Framing(**d.get("framing", {}))})


class PhotoStore:
    def __init__(self, folder: str, now=time.time):
        self.folder = folder
        self._manifest = os.path.join(folder, "manifest.json")
        self._lock = threading.Lock()
        self._now = now

    def photos(self) -> list[Photo]:
        """Every photo, in set order."""
        try:
            with open(self._manifest) as f:
                return [Photo.from_json(d) for d in json.load(f)["photos"]]
        except FileNotFoundError:
            return []

    def the_set(self) -> list[Photo]:
        """The photos the pages show, in turn."""
        return [p for p in self.photos() if p.in_set]

    def path(self, photo_id: str) -> str:
        return os.path.join(self.folder, self._find(self.photos(), photo_id).file)

    def add(self, data: bytes, name: str) -> Photo:
        """Keeps ``data`` as a new photo at the end of the set.

        Raises:
            PhotoError: not a JPEG, PNG or WebP photo, too large, or already added.
        """
        if len(data) > MAX_BYTES:
            raise PhotoError(TOO_LARGE)
        extension = _check(data)
        photo_id = hashlib.sha256(data).hexdigest()[:16]
        with self._lock:
            photos = self.photos()
            if any(p.id == photo_id for p in photos):
                raise PhotoError(ALREADY_ADDED)
            photo = Photo(photo_id, f"{photo_id}.{extension}", os.path.basename(name) or "photo", self._now())
            os.makedirs(self.folder, exist_ok=True)
            _write(os.path.join(self.folder, photo.file), data)
            self._save(photos + [photo])
        return photo

    def remove(self, photo_id: str) -> None:
        with self._lock:
            photos = self.photos()
            photo = self._find(photos, photo_id)
            self._save([p for p in photos if p.id != photo_id])
            try:
                os.remove(os.path.join(self.folder, photo.file))
            except FileNotFoundError:
                pass

    def reorder(self, ids: list[str]) -> None:
        """Puts the photos in the order of ``ids``, which lists each photo once."""
        with self._lock:
            photos = {p.id: p for p in self.photos()}
            if sorted(ids) != sorted(photos):
                raise PhotoError(NOT_THE_SAME_PHOTOS)
            self._save([photos[i] for i in ids])

    def include(self, photo_id: str, in_set: bool) -> None:
        with self._lock:
            photos = self.photos()
            self._find(photos, photo_id).in_set = bool(in_set)
            self._save(photos)

    def frame(self, photo_id: str, framing: Framing) -> None:
        with self._lock:
            photos = self.photos()
            self._find(photos, photo_id).framing = framing
            self._save(photos)

    @staticmethod
    def _find(photos: list[Photo], photo_id: str) -> Photo:
        for p in photos:
            if p.id == photo_id:
                return p
        raise KeyError(photo_id)

    def _save(self, photos: list[Photo]) -> None:
        os.makedirs(self.folder, exist_ok=True)
        _write(self._manifest, json.dumps({"photos": [asdict(p) for p in photos]}, indent=1).encode())


def _check(data: bytes) -> str:
    """The extension for ``data``. Raises PhotoError when it is not a photo the
    pages can show, or is too big to open."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as img:
                if img.width * img.height > MAX_PIXELS:
                    raise PhotoError(TOO_MANY_PIXELS)
                fmt = img.format
                img.verify()
    except PhotoError:
        raise
    except (Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise PhotoError(TOO_MANY_PIXELS) from None
    except Exception:
        raise PhotoError(NOT_A_PHOTO) from None
    if fmt not in FORMATS:
        raise PhotoError(NOT_A_PHOTO)
    return FORMATS[fmt]


def _write(path: str, data: bytes) -> None:
    """Writes ``data`` to ``path`` in one step, so a reader never sees half a file."""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        _give_the_mode_of_a_plain_open(tmp)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def _give_the_mode_of_a_plain_open(path: str) -> None:
    """Gives ``path`` the mode that open() would. mkstemp makes it readable by its owner only."""
    umask = os.umask(0)
    os.umask(umask)
    os.chmod(path, 0o666 & ~umask)

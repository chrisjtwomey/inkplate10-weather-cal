"""A photo as the pages show it: framed into each page's picture area on the
map image's square, always covering the area, in our pencil effect, and kept
until its framing changes."""
import hashlib
import io
import json
import os
import re
from dataclasses import asdict, dataclass

import numpy as np
from PIL import Image, ImageFilter, ImageOps

from .store import Framing, Photo, PhotoStore, write_atomically

# The pages show the photo where they show the map image: a 1200 x 1200 square.
SIZE = 1200
MIN_ZOOM, MAX_ZOOM = 0.5, 8.0
# A page's framing never zooms out past just covering its picture area.
AREA_MIN_ZOOM = 1.0
GREYS = (0, 85, 170, 255)
# Raise when the effect changes, so every kept picture is made again.
EFFECT_VERSION = 2


@dataclass(frozen=True)
class Placement:
    """Where a photo sits on the square: its point (x, y), as fractions of its
    width and height, at the square's centre, and its scale in square pixels
    per photo pixel."""
    x: float
    y: float
    scale: float


def _clamped(framing: Framing) -> Framing:
    return Framing(min(max(framing.x, 0.0), 1.0), min(max(framing.y, 0.0), 1.0),
                   min(max(framing.zoom, MIN_ZOOM), MAX_ZOOM))


def square_placement(framing: Framing, size: tuple) -> Placement:
    """A framing relative to the square: zoom 1 just covers the square."""
    f = _clamped(framing)
    return Placement(f.x, f.y, f.zoom * max(SIZE / size[0], SIZE / size[1]))


def covering(framing: Framing, size: tuple, box: tuple) -> Framing:
    """``framing``, relative to the area ``box``, zoomed and moved only as far as
    keeps the photo covering the area, so no white edge shows."""
    left, top, right, bottom = box
    zoom = min(max(framing.zoom, AREA_MIN_ZOOM), MAX_ZOOM)
    scale = zoom * max((right - left) / size[0], (bottom - top) / size[1])
    margin_x, margin_y = (right - left) / (2 * size[0] * scale), (bottom - top) / (2 * size[1] * scale)
    return Framing(min(max(framing.x, margin_x), 1 - margin_x), min(max(framing.y, margin_y), 1 - margin_y), zoom)


def resized(framing: Framing, size: tuple, box: tuple, default_box: tuple) -> Framing:
    """``framing``, relative to the area at its default height ``default_box``, made
    relative to ``box``, the same area at another height under the same top edge.
    The photo keeps its scale and its place under the top edge, and zooms only as
    far as keeps the area covered."""
    dl, dt, dr, db = default_box
    left, top, right, bottom = box
    scale = framing.zoom * max((dr - dl) / size[0], (db - dt) / size[1])
    lower = ((bottom - top) - (db - dt)) / (2 * size[1] * scale)
    return covering(Framing(framing.x, framing.y + lower, scale / max((right - left) / size[0], (bottom - top) / size[1])),
                    size, box)


def area_placement(framing: Framing, size: tuple, box: tuple) -> Placement:
    """A framing relative to a picture area ``box`` (left, top, right, bottom)
    of the square: zoom 1 just covers the area, and the point sits at its centre.
    The photo always covers the area (``covering``)."""
    f = covering(framing, size, box)
    left, top, right, bottom = box
    scale = f.zoom * max((right - left) / size[0], (bottom - top) / size[1])
    return Placement(f.x + (SIZE / 2 - (left + right) / 2) / (size[0] * scale),
                     f.y + (SIZE / 2 - (top + bottom) / 2) / (size[1] * scale), scale)


def area_framing(framing: Framing, size: tuple, box: tuple) -> Framing:
    """The framing relative to ``box`` that shows what ``framing``, relative to
    the square, shows there."""
    p = square_placement(framing, size)
    left, top, right, bottom = box
    return Framing(p.x + ((left + right) / 2 - SIZE / 2) / (size[0] * p.scale),
                   p.y + ((top + bottom) / 2 - SIZE / 2) / (size[1] * p.scale),
                   p.scale / max((right - left) / size[0], (bottom - top) / size[1]))


def upright(img: Image.Image) -> Image.Image:
    return ImageOps.exif_transpose(img).convert("L")


def placed(img: Image.Image, placement: Placement) -> Image.Image:
    """An upright grey ``img`` on a white SIZE square, as ``placement`` says."""
    w, h = max(1, round(img.width * placement.scale)), max(1, round(img.height * placement.scale))
    out = Image.new("L", (SIZE, SIZE), 255)
    out.paste(img.resize((w, h), Image.LANCZOS),
              (round(SIZE / 2 - placement.x * w), round(SIZE / 2 - placement.y * h)))
    return out


def framed(img: Image.Image, framing: Framing) -> Image.Image:
    """``img`` upright and in grey, on a white SIZE square: the photo's point
    (x, y) at the centre, scaled so zoom 1 just covers the square."""
    img = upright(img)
    return placed(img, square_placement(framing, img.size))


def pencil(img: Image.Image) -> Image.Image:
    """A grey image as a pencil drawing in the panel's four greys: the colour
    dodge of its blurred negative keeps the edges and lightens flat areas."""
    a = np.asarray(img, dtype=np.float64)
    blurred_negative = np.asarray(ImageOps.invert(img).filter(ImageFilter.GaussianBlur(10)), dtype=np.float64)
    dodge = np.clip(a * 255 / np.maximum(255 - blurred_negative, 1), 0, 255).astype(np.uint8)
    sketch = ImageOps.autocontrast(Image.fromarray(dodge, "L"), cutoff=1)
    palette = Image.new("P", (1, 1))
    palette.putpalette([g for grey in GREYS for g in (grey, grey, grey)] + [0] * (768 - 3 * len(GREYS)))
    return sketch.convert("RGB").quantize(palette=palette, dither=Image.Dither.FLOYDSTEINBERG).convert("L")


def _png(img: Image.Image) -> bytes:
    png = io.BytesIO()
    img.save(png, format="PNG", optimize=True)
    return png.getvalue()


def drawing(store: PhotoStore, photo: Photo, framing: Framing) -> bytes:
    """``photo`` framed by ``framing``, relative to the square, in pencil, as PNG."""
    with Image.open(store.path(photo.id)) as img:
        return _png(pencil(framed(img, framing)))


def page_framing(photo: Photo, page_type: str, size: tuple, default_box: tuple) -> Framing:
    """The photo's framing on ``page_type``, relative to its area at its default
    height: the page's own, else the photo's framing for every page, converted."""
    return photo.framings.get(page_type) or area_framing(photo.framing, size, default_box)


def page_drawing(store: PhotoStore, photo: Photo, page_type: str, box: tuple,
                 default_box: tuple | None = None) -> bytes:
    """``photo`` as ``page_type`` shows it in its picture area ``box``, in pencil, as
    PNG. ``default_box`` is the area at its default height, which the framing is
    relative to; None when that is ``box``."""
    default_box = default_box or box
    with Image.open(store.path(photo.id)) as img:
        img = upright(img)
        framing = resized(page_framing(photo, page_type, img.size, default_box), img.size, box, default_box)
        return _png(pencil(placed(img, area_placement(framing, img.size, box))))


def _kept(store: PhotoStore, photo: Photo, suffix: str, *more) -> str:
    """Where a picture of ``photo`` with its framing is kept."""
    key = hashlib.sha1(json.dumps([asdict(photo.framing), EFFECT_VERSION, *more]).encode()).hexdigest()[:12]
    return os.path.join(store.pictures_folder, f"{photo.id}-{key}{suffix}.png")


def page_picture_path(store: PhotoStore, photo: Photo, page_type: str, box: tuple,
                      default_box: tuple | None = None) -> str:
    """The picture of ``photo`` for ``page_type``, made if it is not kept. Other
    pages' pictures of the photo stay kept."""
    own = photo.framings.get(page_type)
    tag = f"-{page_type}"
    path = _kept(store, photo, tag, page_type, asdict(own) if own else None,
                 [round(v, 2) for v in (*box, *(default_box or box))])
    if os.path.exists(path):
        return path
    png = page_drawing(store, photo, page_type, box, default_box)
    os.makedirs(store.pictures_folder, exist_ok=True)
    _forget_matching(store, re.compile(re.escape(photo.id) + r"-[0-9a-f]{12}" + re.escape(tag) + r"\.png"))
    write_atomically(path, png)
    return path


def picture_path(store: PhotoStore, photo: Photo) -> str:
    """The picture of ``photo`` as the pages show it, made if it is not kept."""
    path = _kept(store, photo, "")
    if os.path.exists(path):
        return path
    png = drawing(store, photo, photo.framing)
    os.makedirs(store.pictures_folder, exist_ok=True)
    _forget_matching(store, re.compile(re.escape(photo.id) + r"-[0-9a-f]{12}\.png"))
    write_atomically(path, png)
    return path


def _forget_matching(store: PhotoStore, pattern) -> None:
    for name in os.listdir(store.pictures_folder):
        if pattern.fullmatch(name):
            os.remove(os.path.join(store.pictures_folder, name))


THUMBNAIL_WIDTH = 240


def thumbnail_path(store: PhotoStore, photo: Photo, window: tuple) -> str:
    """``photo`` as the pages show it, cut to ``window`` of the square
    (left, top, right, bottom) and THUMBNAIL_WIDTH wide, made if it is not kept."""
    path = _kept(store, photo, "-thumb")
    if os.path.exists(path):
        return path
    with Image.open(picture_path(store, photo)) as picture:
        cut = picture.crop(tuple(round(v) for v in window))
    thumb = cut.resize((THUMBNAIL_WIDTH, max(1, round(cut.height * THUMBNAIL_WIDTH / cut.width))), Image.LANCZOS)
    png = io.BytesIO()
    thumb.save(png, format="PNG", optimize=True)
    _forget_matching(store, re.compile(re.escape(photo.id) + r"-[0-9a-f]{12}-thumb\.png"))
    write_atomically(path, png.getvalue())
    return path

"""A photo as the pages show it: framed onto the map image's square, in our
pencil effect, and kept until its framing changes."""
import hashlib
import io
import json
import os
from dataclasses import asdict

import numpy as np
from PIL import Image, ImageFilter, ImageOps

from .store import Framing, Photo, PhotoStore, write_atomically

# The pages show the photo where they show the map image: a 1200 x 1200 square.
SIZE = 1200
MIN_ZOOM, MAX_ZOOM = 0.5, 8.0
GREYS = (0, 85, 170, 255)
# Raise when the effect changes, so every kept picture is made again.
EFFECT_VERSION = 1


def framed(img: Image.Image, framing: Framing) -> Image.Image:
    """``img`` upright and in grey, on a white SIZE square: the photo's point
    (x, y) at the centre, scaled so zoom 1 just covers the square."""
    img = ImageOps.exif_transpose(img).convert("L")
    zoom = min(max(framing.zoom, MIN_ZOOM), MAX_ZOOM)
    x, y = min(max(framing.x, 0.0), 1.0), min(max(framing.y, 0.0), 1.0)
    scale = zoom * max(SIZE / img.width, SIZE / img.height)
    w, h = max(1, round(img.width * scale)), max(1, round(img.height * scale))
    out = Image.new("L", (SIZE, SIZE), 255)
    out.paste(img.resize((w, h), Image.LANCZOS), (round(SIZE / 2 - x * w), round(SIZE / 2 - y * h)))
    return out


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


def picture_path(store: PhotoStore, photo: Photo) -> str:
    """The picture of ``photo`` as the pages show it, made if it is not kept."""
    key = hashlib.sha1(json.dumps([asdict(photo.framing), EFFECT_VERSION]).encode()).hexdigest()[:12]
    path = os.path.join(store.pictures_folder, f"{photo.id}-{key}.png")
    if os.path.exists(path):
        return path
    with Image.open(store.path(photo.id)) as img:
        drawing = pencil(framed(img, photo.framing))
    os.makedirs(store.pictures_folder, exist_ok=True)
    store.forget_pictures(photo.id)
    png = io.BytesIO()
    drawing.save(png, format="PNG", optimize=True)
    write_atomically(path, png.getvalue())
    return path

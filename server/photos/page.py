"""The Photos page: upload, the set, and the framing editor. Its script draws
the list and the editor from /photos/list; this module gives the frame of the
page and the numbers the editor needs."""
import html
import json

from .picture import MAX_ZOOM, MIN_ZOOM, SIZE

LOOK_CSS = "static/look/look.css"


def photos_page(windows: dict, base: str = "") -> str:
    """The page. ``windows`` is each picture shape as ``(left, top, right,
    bottom)`` in the square; ``base`` is the server's root for links."""
    data = json.dumps({"size": SIZE, "minZoom": MIN_ZOOM, "maxZoom": MAX_ZOOM, "windows": windows})
    e = html.escape
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Photos</title>
<link rel="stylesheet" href="{e(base)}{LOOK_CSS}">
<link rel="stylesheet" href="{e(base)}photos/assets/photos.css">
</head>
<body>
<header class="top"><h1>Photos</h1><div class="links"><a href="{e(base)}settings">Settings</a></div></header>
<p class="about">Pages set to Photos show the included photos below, one each day, in this order,
in place of the map. Choose those pages on the Settings page, Display tab.</p>
<noscript><p class="banner problem">This page needs JavaScript.</p></noscript>
<p class="banner" id="message" role="alert" hidden></p>

<div class="row add">
<label class="button primary" for="files">Add photos</label>
<input type="file" id="files" accept="image/jpeg,image/png,image/webp" multiple hidden>
<p class="help">Or drop them on this page. JPEG, PNG or WebP, up to 20 MB each.</p>
</div>
<ul id="uploads"></ul>
<div id="drop" hidden><p>Drop photos to add them</p></div>

<ol id="photos"></ol>
<p id="empty" hidden>No photos yet. Add one to start.</p>

<section id="editor" hidden>
<h2 id="editor-title">Frame</h2>
<p class="help">Drag to move the photo, or use the arrow keys. Pinch, scroll or use the slider to zoom.
Double-click to centre.</p>
<div class="windows">
<figure><div class="window" data-shape="wide"><img alt=""></div><figcaption>Today, current and tomorrow</figcaption></figure>
<figure><div class="window" data-shape="tall"><img alt=""></div><figcaption>Hourly and daily</figcaption></figure>
</div>
<div class="row"><label for="zoom">Zoom</label><input type="range" id="zoom" step="0.01"></div>
<div class="row buttons">
<button type="button" id="delete" class="danger">Delete photo</button>
<span class="gap"></span>
<button type="button" id="centre">Centre</button>
<button type="button" id="undo">Undo changes</button>
<button type="button" id="close">Close</button>
<button type="button" class="primary" id="save">Save framing</button>
</div>
<p class="help" id="preview-status" aria-live="polite"></p>
<div class="previews">
<figure><img id="preview-wide" alt="The today page with this framing"><figcaption>Today page</figcaption></figure>
<figure><img id="preview-tall" alt="The hourly page with this framing"><figcaption>Hourly page</figcaption></figure>
</div>
</section>

<script type="application/json" id="numbers">{data}</script>
<script src="{e(base)}photos/assets/photos.js"></script>
</body>
</html>
"""

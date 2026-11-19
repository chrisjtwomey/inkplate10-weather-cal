// The Pages editor. The preview is the page's own HTML in a frame. A selected
// photo is drawn into the page's picture area as the server draws it (framed,
// blurred, dodged, stretched and dithered to the panel's four greys), so what
// you frame is what the display shows. Panel view fetches the server's render.
(function () {
  "use strict";
  const N = JSON.parse(document.getElementById("numbers").textContent);
  const $ = (id) => document.getElementById(id);
  const SIZE = 1200;                    // the picture square, as photos/picture.py
  const BLUR = 10;
  const GREYS = [0, 85, 170, 255];
  const PAGE_WIDTH = 825, PAGE_HEIGHT = 1200;
  const NUDGE = 0.01, ZOOM_STEP = 1.1;
  // Browsers send a trackpad pinch as a wheel with Ctrl held, in small steps.
  const TRACKPAD_PINCH_RATE = 0.01, SCROLL_ZOOM_RATE = 0.0015;
  const CENTRE = {x: 0.5, y: 0.5, zoom: 1};
  const SAVE_DELAY = 1000;
  const MARGIN = 16, MIN_SCALE = 0.4;
  const NAMES = {today: "Today", current: "Current", hourly: "Hourly", daily: "Daily", tomorrow: "Tomorrow"};

  let settings = {};      // page type -> {theme, photos, map}
  let library = [];       // every photo
  let at = 0;             // which page type
  let selected = null;    // {id, framing, saved, original, img, w, h}
  let pagePhoto = null;   // the page's photo today, {id, framing, img, w, h, live}: drawn while its size changes
  let panelOn = false;
  let saveTimer = 0;
  let sizeTimer = 0, pendingSize;   // pendingSize: a percent, null for the default, undefined when saved

  const pageType = () => N.pageTypes[at];
  const byId = (id) => library.find((p) => p.id === id);
  const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);
  const same = (a, b) => a.x === b.x && a.y === b.y && a.zoom === b.zoom;
  const unsaved = () => !!selected && !same(selected.framing, selected.saved);

  function say(words, kind) {
    const m = $("message");
    m.textContent = words || "";
    m.className = "banner " + (kind || "problem");
    m.hidden = !words;
  }
  const status = (words) => { $("status").textContent = words || ""; };
  const framingStatus = (words) => { $("framing-status").textContent = words || ""; };

  async function call(path, options) {
    let rsp;
    try {
      rsp = await fetch(path, options);
    } catch (e) {
      throw new Error("Cannot reach the server. Check that it is running.");
    }
    if (rsp.status === 401) throw new Error("Signed out. Reload the page to sign in again.");
    if (!rsp.ok) {
      let body = {};
      try { body = await rsp.json(); } catch (e) { /* not JSON */ }
      throw new Error(body.problem || "The server refused this (" + rsp.status + ").");
    }
    return rsp;
  }
  const post = (path, body) => call(path, {method: "POST", headers: {"Content-Type": "application/json"},
                                          body: body === undefined ? undefined : JSON.stringify(body)});

  async function saveSettings(changes) {
    const answer = await (await post("pages/settings", changes)).json();
    settings = answer.pages;
    return answer.changed;
  }

  async function loadAll() {
    settings = (await (await call("pages/settings")).json()).pages;
    library = (await (await call("photos/list")).json()).photos;
  }

  // ---- The page: its name, theme and map ----

  function drawBar() {
    const type = pageType();
    const s = settings[type];
    drawTabs();
    const themes = Object.entries(N.themes).filter(([, t]) => t.pages.includes(type));
    fillChoice("theme", themes.map(([name, t]) => [name, t.label]), s.theme);
    fillChoice("map", N.maps.map((name) => [name, name === "classic" ? "Classic" : name]), s.map);
    $("theme-everywhere").hidden = N.themes[s.theme].pages.every((t) => settings[t].theme === s.theme);
    drawSize();
  }

  // ---- The picture's size ----

  // The page's size range in its theme, in percent of the inner height, or null when fixed.
  const sizeRange = () => (N.sizes[settings[pageType()].theme] || {})[pageType()] || null;
  const savedSize = () => settings[pageType()].picture_size;
  const shownSize = () => {
    const range = sizeRange();
    const size = pendingSize !== undefined ? pendingSize : savedSize();
    return size === null || size === undefined ? range.default : size;
  };

  function drawSize() {
    const range = sizeRange();
    $("size-tools").hidden = !range;
    if (!range) return;
    const slider = $("picture-size");
    slider.min = range.min;
    slider.max = range.max;
    slider.value = shownSize();
    $("size-value").textContent = Number(slider.value).toFixed(1) + "%";
    $("size-default").hidden = shownSize() === range.default;
  }

  // Lays the page out at the shown size, as the server's CSS variables do.
  function applySize() {
    const range = sizeRange(), parts = pictureParts();
    if (!range || !parts) return;
    const size = shownSize();
    const height = size === range.default ? range.defaultPixels : size / 100 * N.innerHeight;
    parts.doc.body.style.setProperty("--picture-height", height + "px");
    parts.doc.body.style.setProperty("--picture-grow", (height - range.defaultPixels) + "px");
    parts.doc.body.style.setProperty("--picture-growth", (height - range.defaultPixels) / range.defaultPixels);
    placeHandle();
    placeGrip();
    if (drawn()) drawPhoto();
  }

  function setSize(size) {
    const range = sizeRange();
    const clamped = Math.round(clamp(size, range.min, range.max) * 10) / 10;
    pendingSize = clamped === range.default ? null : clamped;
    if (pagePhoto) pagePhoto.live = true;
    drawSize();
    applySize();
    clearTimeout(sizeTimer);
    sizeTimer = setTimeout(saveSize, SAVE_DELAY);
  }

  async function saveSize() {
    clearTimeout(sizeTimer);
    if (pendingSize === undefined) return;
    const size = pendingSize, page = pageType();
    $("size-status").textContent = "Saving…";
    try {
      await saveSettings({[page]: {picture_size: size}});
      if (pendingSize === size) pendingSize = undefined;
      refreshPicture(page);
      $("size-status").textContent = "Saved. The display gets it at its next wake.";
      say("");
    } catch (e) {
      $("size-status").textContent = "";
      say("Size not saved. " + e.message);
    }
  }

  // Fetches the page's picture again: the server draws a photo for the area's new size.
  function refreshPicture(page) {
    const parts = pictureParts();
    if (parts && parts.square.tagName === "IMG" && page === pageType()) {
      parts.square.src = parts.square.src.split("?")[0] + "?t=" + Date.now();
    }
  }

  $("picture-size").addEventListener("input", () => setSize(Number($("picture-size").value)));
  $("size-default").addEventListener("click", () => setSize(sizeRange().default));

  const grip = $("grip"), gripLine = $("grip-line");

  function placeGrip() {
    const parts = pictureParts();
    if (!parts || !sizeRange() || panelOn) { grip.hidden = gripLine.hidden = true; return; }
    const scale = viewScale();
    const a = parts.area.getBoundingClientRect();
    Object.assign(grip.style, {left: (a.left + a.width / 2) * scale + "px", top: a.bottom * scale + "px"});
    Object.assign(gripLine.style, {left: a.left * scale + "px", width: a.width * scale + "px", top: a.bottom * scale + "px"});
    grip.hidden = gripLine.hidden = false;
  }

  let resizing = null;
  grip.addEventListener("pointerdown", (event) => {
    grip.setPointerCapture(event.pointerId);
    resizing = {y: event.clientY, size: shownSize()};
  });
  grip.addEventListener("pointermove", (event) => {
    if (!resizing) return;
    const moved = (event.clientY - resizing.y) / viewScale();
    setSize(resizing.size + moved / N.innerHeight * 100);
  });
  for (const name of ["pointerup", "pointercancel"]) {
    grip.addEventListener(name, (event) => { resizing = null; showGrip(event); });
  }

  // The grip shows while the pointer is over the picture or the grip, and during a drag.
  function showGrip(event) {
    const parts = pictureParts();
    let over = event.type !== "pointerleave" && grip.contains(event.target);
    if (parts && !over && event.type !== "pointerleave") {
      const a = parts.area.getBoundingClientRect(), p = $("preview").getBoundingClientRect();
      const scale = viewScale(), x = event.clientX - p.left, y = event.clientY - p.top;
      over = x >= a.left * scale && x <= a.right * scale && y >= a.top * scale && y <= a.bottom * scale;
    }
    for (const el of [grip, gripLine]) el.classList.toggle("shown", over || resizing !== null);
  }
  for (const name of ["pointermove", "pointerleave"]) $("preview").addEventListener(name, showGrip);

  // A choice with one option shows as text; the drop-down appears when there is a second.
  function fillChoice(id, options, current) {
    const select = $(id);
    select.replaceChildren(...options.map(([value, label]) => {
      const o = new Option(label, value);
      o.selected = value === current;
      return o;
    }));
    select.hidden = options.length < 2;
    $(id + "-only").textContent = options.length < 2 && options.length ? options[0][1] : "";
  }

  $("theme").addEventListener("change", () => change({[pageType()]: {theme: $("theme").value}}));
  $("map").addEventListener("change", () => change({[pageType()]: {map: $("map").value}}));
  $("theme-everywhere").addEventListener("click", () => {
    const theme = settings[pageType()].theme;
    const changes = {};
    for (const type of N.themes[theme].pages) changes[type] = {theme: theme};
    change(changes);
  });

  async function change(changes) {
    await saveSize();
    try {
      await saveSettings(changes);
      say("");
      await showPage();
    } catch (e) {
      say(e.message);
      drawBar();
    }
  }

  function drawTabs() {
    $("tabs").replaceChildren(...N.pageTypes.map((type, i) => {
      const tab = document.createElement("button");
      tab.type = "button";
      tab.setAttribute("role", "tab");
      tab.setAttribute("aria-controls", "preview");
      tab.setAttribute("aria-selected", i === at ? "true" : "false");
      tab.tabIndex = i === at ? 0 : -1;
      tab.textContent = NAMES[type] || type;
      if (settings[type].photos.length) {
        const mark = document.createElement("span");
        mark.className = "mark";
        mark.setAttribute("aria-hidden", "true");
        tab.append(mark);
        tab.title = "Shows photos";
        tab.setAttribute("aria-label", tab.firstChild.textContent + ", shows photos");
      }
      tab.addEventListener("click", () => openPage(i));
      return tab;
    }));
  }

  async function openPage(i) {
    if (i === at) return;
    await saveFraming();
    await saveSize();
    at = i;
    selected = null;
    await showPage();
    $("tabs").children[at].focus();
  }
  $("tabs").addEventListener("keydown", (event) => {
    const by = {ArrowLeft: -1, ArrowRight: 1}[event.key];
    if (!by) return;
    event.preventDefault();
    openPage((at + by + N.pageTypes.length) % N.pageTypes.length);
  });

  // ---- The preview ----

  const frame = $("page");

  // The page's scale on screen: actual size, or as large as fits the column and the window below the bar.
  function viewScale() {
    const box = $("preview");
    if ($("actual-size").checked) {
      box.style.maxWidth = "";
      return 1;
    }
    const below = window.innerHeight - (box.getBoundingClientRect().top + window.scrollY) - MARGIN;
    const byHeight = Math.max(MIN_SCALE, Math.min(1, below / PAGE_HEIGHT));
    box.style.maxWidth = PAGE_WIDTH * byHeight + "px";
    return Math.min(byHeight, box.clientWidth / PAGE_WIDTH);
  }

  function fit() {
    const box = $("preview");
    const scale = viewScale();
    frame.style.transform = "scale(" + scale + ")";
    box.style.height = PAGE_HEIGHT * scale + "px";
    $("panel").style.width = PAGE_WIDTH * scale + "px";
    placeHandle();
    placeGrip();
    return scale;
  }

  async function showPage() {
    drawBar();
    drawStrip();
    panel(false);
    status("");
    frame.src = "pages/view/" + pageType() + ".html" + ($("sample").checked ? "?sample=1&t=" + Date.now() : "");
  }

  frame.addEventListener("load", () => {
    loadPagePhoto().catch(() => { pagePhoto = null; });
    fit();
    placeGrip();
    if (selected) drawPhoto();
    $("framing-tools").hidden = !selected;
  });
  window.addEventListener("resize", fit);
  $("actual-size").addEventListener("change", fit);
  $("sample").addEventListener("change", showPage);

  // The page's picture area, and the picture square's image, in the frame.
  function pictureParts() {
    const doc = frame.contentDocument;
    const area = doc && doc.querySelector("[data-picture]");
    const square = area && area.querySelector("#map");
    return area && square ? {doc, area, square} : null;
  }

  // The area on the picture square, in square pixels (left, top, right, bottom).
  function areaBox(parts) {
    const a = parts.area.getBoundingClientRect();
    const s = parts.square.getBoundingClientRect();
    const k = SIZE / s.width;
    return [(a.left - s.left) * k, (a.top - s.top) * k, (a.right - s.left) * k, (a.bottom - s.top) * k];
  }

  // As photos/picture.py area_placement: the photo point at the square's centre, and its scale.
  function placement(f, w, h, box) {
    const [l, t, r, b] = box;
    const scale = f.zoom * Math.max((r - l) / w, (b - t) / h);
    return {x: f.x + (SIZE / 2 - (l + r) / 2) / (w * scale), y: f.y + (SIZE / 2 - (t + b) / 2) / (h * scale), scale};
  }

  // As photos/picture.py covering: zoomed and moved only as far as keeps the area covered.
  function covering(f, w, h, box) {
    if (!box) return {x: clamp(f.x, 0, 1), y: clamp(f.y, 0, 1), zoom: clamp(f.zoom, N.minZoom, N.maxZoom)};
    const [l, t, r, b] = box;
    const zoom = clamp(f.zoom, N.minZoom, N.maxZoom);
    const scale = zoom * Math.max((r - l) / w, (b - t) / h);
    const mx = (r - l) / (2 * w * scale), my = (b - t) / (2 * h * scale);
    return {x: clamp(f.x, mx, 1 - mx), y: clamp(f.y, my, 1 - my), zoom};
  }

  // As photos/picture.py area_framing: a framing relative to the square, made relative to the area.
  function areaFraming(f, w, h, box) {
    const [l, t, r, b] = box;
    const scale = clamp(f.zoom, N.squareMinZoom, N.maxZoom) * Math.max(SIZE / w, SIZE / h);
    return {x: f.x + ((l + r) / 2 - SIZE / 2) / (w * scale), y: f.y + ((t + b) / 2 - SIZE / 2) / (h * scale),
            zoom: scale / Math.max((r - l) / w, (b - t) / h)};
  }

  // As photos/picture.py resized: a framing relative to the area at its default height
  // (dbox), made relative to the same area at another height (box) under the same top edge.
  function resized(f, w, h, box, dbox) {
    const [l, t, r, b] = box, [dl, dt, dr, db] = dbox;
    const scale = f.zoom * Math.max((dr - dl) / w, (db - dt) / h);
    const lower = ((b - t) - (db - dt)) / (2 * h * scale);
    return covering({x: f.x, y: f.y + lower, zoom: scale / Math.max((r - l) / w, (b - t) / h)}, w, h, box);
  }

  // The other way: a framing relative to box, made relative to the area at its default height.
  function unsized(f, w, h, box, dbox) {
    const [l, t, r, b] = box, [dl, dt, dr, db] = dbox;
    const scale = f.zoom * Math.max((r - l) / w, (b - t) / h);
    const higher = ((b - t) - (db - dt)) / (2 * h * scale);
    return {x: f.x, y: f.y - higher, zoom: scale / Math.max((dr - dl) / w, (db - dt) / h)};
  }

  // The picture area on the square now (box) and at the theme's default height (dbox).
  function areaBoxes() {
    const parts = pictureParts();
    if (!parts) return null;
    const box = areaBox(parts), range = sizeRange();
    if (!range) return {box, dbox: box};
    const perPixel = (box[3] - box[1]) / parts.area.getBoundingClientRect().height;
    return {box, dbox: [box[0], box[1], box[2], box[1] + range.defaultPixels * perPixel]};
  }

  // The photo the editor draws: the selected one, else the page's own while its size changes.
  const drawn = () => selected || (pagePhoto && pagePhoto.live ? pagePhoto : null);

  // The drawn photo's framing as the area shows it now.
  function shown(f = drawn().framing) {
    const p = drawn(), b = areaBoxes();
    return b ? resized(f, p.w, p.h, b.box, b.dbox) : f;
  }

  // The framing a photo has on this page, relative to the area at its default height.
  function pageFraming(photo, w, h) {
    const b = areaBoxes();
    if (!b) return CENTRE;
    return covering(photo.framings[pageType()] || areaFraming(photo.framing, w, h, b.dbox), w, h, b.dbox);
  }

  // Loads the page's photo today, so a size change can draw it as the server will.
  async function loadPagePhoto() {
    pagePhoto = null;
    const page = pageType();
    if (!sizeRange()) return;
    const {photo: id} = await (await call("pages/today/" + page + ".json")).json();
    const photo = id && byId(id);
    if (!photo || page !== pageType()) return;
    const img = new Image();
    img.src = "pages/photo/" + id + ".jpg";
    await img.decode();
    if (page !== pageType()) return;
    const w = img.naturalWidth, h = img.naturalHeight;
    pagePhoto = {id, img, w, h, framing: pageFraming(photo, w, h), live: pendingSize !== undefined};
    if (pagePhoto.live) drawPhoto();
  }

  let drawing = false, again = false;
  function drawPhoto() {
    if (drawing) { again = true; return; }
    drawing = true;
    requestAnimationFrame(() => {
      try { paint(); } finally {
        drawing = false;
        if (again) { again = false; drawPhoto(); }
      }
    });
  }

  function paint() {
    const parts = pictureParts();
    const photo = drawn();
    if (!parts || !photo || !photo.img) return;
    let canvas = parts.doc.querySelector('canvas[data-editor="photo"]');
    if (!canvas) {
      canvas = parts.doc.createElement("canvas");
      canvas.width = canvas.height = SIZE;
      canvas.dataset.editor = "photo";
      parts.square.removeAttribute("id");
      parts.square.style.display = "none";
      canvas.id = "map";
      parts.area.insertBefore(canvas, parts.square);
    }
    const box = areaBox({...parts, square: canvas});
    const f = shown();
    if (selected) $("zoom").value = Math.log(f.zoom);
    pencil(canvas, photo, placement(f, photo.w, photo.h, box));
    placeHandle();
  }

  // The server's effect, in the same order: place on white, blur the negative,
  // dodge, stretch the middle 98% of greys to full range, dither to four greys.
  function pencil(canvas, photo, p) {
    const w = photo.w * p.scale, h = photo.h * p.scale;
    const base = document.createElement("canvas");
    base.width = base.height = SIZE;
    const bc = base.getContext("2d");
    bc.fillStyle = "#fff";
    bc.fillRect(0, 0, SIZE, SIZE);
    bc.drawImage(photo.img, SIZE / 2 - p.x * w, SIZE / 2 - p.y * h, w, h);
    const neg = document.createElement("canvas");
    neg.width = neg.height = SIZE;
    const nc = neg.getContext("2d");
    nc.filter = "invert(1) blur(" + BLUR + "px)";
    nc.drawImage(base, 0, 0);
    const a = bc.getImageData(0, 0, SIZE, SIZE).data;
    const n = nc.getImageData(0, 0, SIZE, SIZE).data;
    const grey = new Float32Array(SIZE * SIZE);
    const hist = new Uint32Array(256);
    for (let i = 0, j = 0; j < grey.length; i += 4, j++) {
      const v = Math.min(255, Math.max(0, a[i] * 255 / Math.max(255 - n[i], 1)));
      grey[j] = v;
      hist[v | 0]++;
    }
    const cut = grey.length * 0.01;
    let lo = 0, hi = 255, seen = 0;
    while (lo < 255 && (seen += hist[lo]) <= cut) lo++;
    seen = 0;
    while (hi > 0 && (seen += hist[hi]) <= cut) hi--;
    const span = Math.max(hi - lo, 1);
    for (let j = 0; j < grey.length; j++) grey[j] = clamp((grey[j] - lo) * 255 / span, 0, 255);
    const out = canvas.getContext("2d").createImageData(SIZE, SIZE);
    const d = out.data;
    for (let y = 0; y < SIZE; y++) {
      for (let x = 0; x < SIZE; x++) {
        const j = y * SIZE + x;
        const old = grey[j];
        const q = GREYS[Math.min(3, Math.round(old / 85))];
        const err = old - q;
        if (x + 1 < SIZE) grey[j + 1] += err * 7 / 16;
        if (y + 1 < SIZE) {
          if (x > 0) grey[j + SIZE - 1] += err * 3 / 16;
          grey[j + SIZE] += err * 5 / 16;
          if (x + 1 < SIZE) grey[j + SIZE + 1] += err / 16;
        }
        const i = j * 4;
        d[i] = d[i + 1] = d[i + 2] = q;
        d[i + 3] = 255;
      }
    }
    canvas.getContext("2d").putImageData(out, 0, 0);
  }

  // ---- Framing inside the preview ----

  const handle = $("handle");

  function placeHandle() {
    const parts = pictureParts();
    if (!parts || !selected || panelOn) { handle.hidden = true; return; }
    const scale = viewScale();
    const a = parts.area.getBoundingClientRect();
    Object.assign(handle.style, {left: a.left * scale + "px", top: a.top * scale + "px",
                                 width: a.width * scale + "px", height: a.height * scale + "px"});
    handle.hidden = false;
  }

  // Sets the selected photo's framing from one relative to the area as it is now.
  function setFraming(f) {
    if (!selected.img) return;
    const b = areaBoxes();
    selected.framing = b ? unsized(covering(f, selected.w, selected.h, b.box), selected.w, selected.h, b.box, b.dbox) : f;
    $("undo-framing").disabled = same(selected.framing, selected.original);
    if (!same(selected.framing, selected.original)) $("hint").hidden = true;
    drawPhoto();
    clearTimeout(saveTimer);
    if (unsaved()) saveTimer = setTimeout(saveFraming, SAVE_DELAY);
  }

  // Saves the selected photo's framing on this page, if it changed.
  async function saveFraming() {
    clearTimeout(saveTimer);
    if (!unsaved()) return;
    const {id} = selected, page = pageType(), framing = {...selected.framing};
    framingStatus("Saving…");
    try {
      await post("pages/photo/" + id + "/framing/" + page, framing);
      byId(id).framings[page] = framing;
      if (selected && selected.id === id) selected.saved = framing;
      framingStatus("Saved. The display gets it at its next wake.");
      say("");
    } catch (e) {
      framingStatus("");
      say("Framing not saved. " + e.message);
    }
  }

  window.addEventListener("pagehide", () => {
    if (pendingSize !== undefined) {
      navigator.sendBeacon("pages/settings", new Blob([JSON.stringify({[pageType()]: {picture_size: pendingSize}})],
                                                      {type: "application/json"}));
    }
    if (!unsaved()) return;
    navigator.sendBeacon("pages/photo/" + selected.id + "/framing/" + pageType(),
                         new Blob([JSON.stringify(selected.framing)], {type: "application/json"}));
  });

  // Screen pixels moved -> the framing that moves the photo with the pointer.
  function moved(dx, dy, from) {
    const parts = pictureParts();
    const canvas = parts.doc.getElementById("map");
    const box = areaBox({...parts, square: canvas});
    const p = placement(from, selected.w, selected.h, box);
    const k = SIZE / canvas.getBoundingClientRect().width / viewScale();
    return {x: from.x - dx * k / (selected.w * p.scale), y: from.y - dy * k / (selected.h * p.scale), zoom: from.zoom};
  }

  const pointers = new Map();
  let drag = null, pinch = null;
  const spread = () => {
    const [a, b] = Array.from(pointers.values());
    return Math.hypot(a.x - b.x, a.y - b.y);
  };
  handle.addEventListener("pointerdown", (event) => {
    if (!selected) return;
    handle.setPointerCapture(event.pointerId);
    pointers.set(event.pointerId, {x: event.clientX, y: event.clientY});
    if (pointers.size === 1) drag = {x: event.clientX, y: event.clientY, framing: shown()};
    else if (pointers.size === 2) { drag = null; pinch = {spread: spread(), zoom: shown().zoom}; }
  });
  handle.addEventListener("pointermove", (event) => {
    if (!pointers.has(event.pointerId)) return;
    pointers.set(event.pointerId, {x: event.clientX, y: event.clientY});
    if (pinch && pointers.size === 2) {
      setFraming({...shown(), zoom: pinch.zoom * spread() / Math.max(pinch.spread, 1)});
    } else if (drag) {
      setFraming(moved(event.clientX - drag.x, event.clientY - drag.y, drag.framing));
    }
  });
  const lift = (event) => {
    pointers.delete(event.pointerId);
    if (pointers.size < 2) pinch = null;
    if (pointers.size === 0) drag = null;
  };
  handle.addEventListener("pointerup", lift);
  handle.addEventListener("pointercancel", lift);
  handle.addEventListener("wheel", (event) => {
    if (!selected) return;
    event.preventDefault();
    const rate = event.ctrlKey ? TRACKPAD_PINCH_RATE : SCROLL_ZOOM_RATE;
    const f = shown();
    setFraming({...f, zoom: f.zoom * Math.exp(-event.deltaY * rate)});
  }, {passive: false});
  handle.addEventListener("dblclick", () => { if (selected) setFraming(CENTRE); });
  handle.addEventListener("keydown", (event) => {
    if (!selected) return;
    const f = shown();
    const by = event.shiftKey ? 10 : 1;
    const across = {ArrowLeft: -1, ArrowRight: 1}[event.key] || 0;
    const down = {ArrowUp: -1, ArrowDown: 1}[event.key] || 0;
    if (across || down) setFraming({x: f.x + across * by * NUDGE, y: f.y + down * by * NUDGE * selected.w / selected.h, zoom: f.zoom});
    else if (event.key === "+" || event.key === "=") setFraming({...f, zoom: f.zoom * ZOOM_STEP});
    else if (event.key === "-") setFraming({...f, zoom: f.zoom / ZOOM_STEP});
    else return;
    event.preventDefault();
  });
  $("zoom").min = Math.log(N.minZoom);
  $("zoom").max = Math.log(N.maxZoom);
  $("zoom").addEventListener("input", () => setFraming({...shown(), zoom: Math.exp(Number($("zoom").value))}));
  $("centre").addEventListener("click", () => setFraming(CENTRE));

  $("undo-framing").addEventListener("click", () => setFraming(shown(selected.original)));
  $("framing-everywhere").addEventListener("click", async () => {
    clearTimeout(saveTimer);
    try {
      for (const type of N.pageTypes) {
        await post("pages/photo/" + selected.id + "/framing/" + type, selected.framing);
        byId(selected.id).framings[type] = {...selected.framing};
      }
      selected.saved = {...selected.framing};
      framingStatus("This framing is now on every page.");
    } catch (e) { say(e.message); }
  });

  async function select(id) {
    if (selected && selected.id === id) return;
    await saveFraming();
    const photo = byId(id);
    selected = {id, framing: CENTRE, saved: CENTRE, original: CENTRE, img: null};
    framingStatus("");
    $("hint").hidden = false;
    drawStrip();
    status("Opening the photo…");
    const img = new Image();
    img.src = "pages/photo/" + id + ".jpg";
    await img.decode();
    if (!selected || selected.id !== id) return;
    const w = img.naturalWidth, h = img.naturalHeight;
    const framing = pageFraming(photo, w, h);
    Object.assign(selected, {img, w, h, framing, saved: framing, original: framing});
    status("");
    $("framing-tools").hidden = false;
    $("undo-framing").disabled = true;
    drawPhoto();
  }

  // ---- Panel view ----

  async function panel(on) {
    panelOn = on;
    $("panel-view").setAttribute("aria-pressed", on ? "true" : "false");
    $("panel").hidden = !on;
    frame.style.visibility = on ? "hidden" : "";
    placeHandle();
    placeGrip();
    if (!on) return;
    await saveSize();
    status("Drawing the page as the display will…");
    const f = selected && selected.framing;
    const query = selected ? "?photo=" + selected.id + "&x=" + f.x + "&y=" + f.y + "&zoom=" + f.zoom : "";
    try {
      const blob = await (await call("pages/panel/" + pageType() + ".png" + query)).blob();
      if (!panelOn) return;
      const img = $("panel");
      if (img.src.startsWith("blob:")) URL.revokeObjectURL(img.src);
      img.src = URL.createObjectURL(blob);
      status("Exact: this is what the display shows.");
    } catch (e) { status(e.message); }
  }
  $("panel-view").addEventListener("click", () => panel(!panelOn));

  // ---- The page's photo list ----

  function thumb(photo) {
    const img = document.createElement("img");
    const f = photo.framing;
    img.src = "photos/" + photo.id + "/thumb.png?f=" + [f.x, f.y, f.zoom].join(",");
    img.alt = "";
    return img;
  }

  function drawStrip() {
    const ids = settings[pageType()].photos;
    const strip = $("strip");
    strip.replaceChildren(...ids.filter(byId).map((id) => {
      const li = document.createElement("li");
      li.dataset.id = id;
      li.classList.toggle("selected", !!selected && selected.id === id);
      const open = document.createElement("button");
      open.type = "button";
      open.className = "open";
      open.append(thumb(byId(id)));
      open.title = byId(id).name;
      open.addEventListener("click", () => select(id));
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "remove";
      remove.textContent = "×";
      remove.setAttribute("aria-label", "Remove " + byId(id).name + " from this page");
      remove.addEventListener("click", () => setPhotos(ids.filter((i) => i !== id)));
      li.append(open, remove);
      dragToReorder(li, open);
      return li;
    }));
    $("strip").dataset.empty = ids.length ? "" : "true";
  }

  async function setPhotos(ids) {
    if (selected && !ids.includes(selected.id)) selected = null;
    await change({[pageType()]: {photos: ids}});
  }

  // Moves the other photos past the one being dragged, so it keeps its pointer.
  function dragToReorder(li, grip) {
    let startX = 0, moving = false;
    grip.addEventListener("pointerdown", (event) => {
      startX = event.clientX;
      moving = false;
      grip.setPointerCapture(event.pointerId);
    });
    grip.addEventListener("pointermove", (event) => {
      if (!grip.hasPointerCapture(event.pointerId)) return;
      let dx = event.clientX - startX;
      if (!moving && Math.abs(dx) < 6) return;
      moving = true;
      li.classList.add("dragging");
      const before = li.previousElementSibling, after = li.nextElementSibling;
      if (after && dx > after.offsetWidth / 2) { li.before(after); startX += after.offsetWidth; dx -= after.offsetWidth; }
      else if (before && dx < -before.offsetWidth / 2) { li.after(before); startX -= before.offsetWidth; dx += before.offsetWidth; }
      li.style.transform = "translateX(" + dx + "px)";
    });
    grip.addEventListener("pointerup", (event) => {
      li.classList.remove("dragging");
      li.style.transform = "";
      if (!moving) return;
      event.stopPropagation();
      moving = false;
      const ids = Array.from($("strip").children).map((r) => r.dataset.id);
      setPhotos(ids);
    }, true);
  }

  $("add").addEventListener("click", () => {
    const on = settings[pageType()].photos;
    const choices = library.filter((p) => !on.includes(p.id));
    $("choices").replaceChildren(...choices.map((p) => {
      const li = document.createElement("li");
      const label = document.createElement("label");
      const box = document.createElement("input");
      box.type = "checkbox";
      box.value = p.id;
      label.append(box, thumb(p), " " + p.name);
      li.append(label);
      return li;
    }));
    if (!choices.length) $("choices").innerHTML = "<li>Every photo is on this page. Upload more below.</li>";
    $("picker").showModal();
  });
  $("picker-cancel").addEventListener("click", () => $("picker").close());
  $("picker-add").addEventListener("click", () => {
    const added = Array.from($("choices").querySelectorAll("input:checked")).map((b) => b.value);
    $("picker").close();
    if (added.length) setPhotos([...settings[pageType()].photos, ...added]);
  });

  // ---- The library ----

  function drawLibrary() {
    $("empty").hidden = library.length > 0;
    $("photos").replaceChildren(...library.map((p) => {
      const li = document.createElement("li");
      const name = document.createElement("span");
      name.className = "name";
      name.textContent = p.name;
      const used = N.pageTypes.filter((t) => settings[t].photos.includes(p.id)).map((t) => NAMES[t] || t);
      const where = document.createElement("span");
      where.className = "where";
      where.textContent = used.length ? "On " + used.join(", ") : "Not on a page";
      const del = document.createElement("button");
      del.type = "button";
      del.className = "danger";
      del.textContent = "Delete";
      del.addEventListener("click", async () => {
        if (!confirm("Delete " + p.name + "? It leaves every page, and this cannot be undone.")) return;
        try {
          await post("pages/photo/" + p.id + "/delete");
          if (selected && selected.id === p.id) selected = null;
          await refresh();
        } catch (e) { say(e.message); }
      });
      li.append(thumb(p), name, where, del);
      return li;
    }));
  }

  async function refresh() {
    await loadAll();
    drawLibrary();
    await showPage();
  }

  function sendOne(file, bar, words) {
    return new Promise((resolve) => {
      const form = new FormData();
      form.append("photo", file, file.name);
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "photos/upload");
      xhr.upload.addEventListener("progress", (e) => { if (e.lengthComputable) bar.value = e.loaded / e.total; });
      xhr.addEventListener("load", () => {
        let body = {};
        try { body = JSON.parse(xhr.responseText); } catch (e) { /* not JSON */ }
        if (xhr.status === 201) resolve(null);
        else if (xhr.status === 401) resolve("Signed out. Reload the page to sign in again.");
        else resolve(body.problem || "The server refused this (" + xhr.status + ").");
      });
      xhr.addEventListener("error", () => resolve("Cannot reach the server. Check that it is running."));
      xhr.send(form);
    }).then((problem) => {
      bar.value = 1;
      words.textContent = problem || "Added.";
      words.classList.toggle("problem", !!problem);
      return !problem;
    });
  }

  async function upload(files) {
    for (const file of files) {
      const item = document.createElement("li");
      const name = document.createElement("span");
      name.textContent = file.name;
      const bar = document.createElement("progress");
      bar.max = 1;
      bar.value = 0;
      const words = document.createElement("span");
      words.className = "result";
      item.append(name, bar, words);
      $("uploads").append(item);
      if (await sendOne(file, bar, words)) setTimeout(() => item.remove(), 3000);
    }
    library = (await (await call("photos/list")).json()).photos;
    drawLibrary();
  }
  $("files").addEventListener("change", () => {
    const files = Array.from($("files").files);
    $("files").value = "";
    if (files.length) upload(files);
  });
  const carriesFiles = (event) => Array.from(event.dataTransfer.types).includes("Files");
  document.addEventListener("dragover", (event) => {
    if (!carriesFiles(event)) return;
    event.preventDefault();
    $("drop").hidden = false;
  });
  document.addEventListener("dragleave", (event) => { if (event.relatedTarget === null) $("drop").hidden = true; });
  document.addEventListener("drop", (event) => {
    if (!carriesFiles(event)) return;
    event.preventDefault();
    $("drop").hidden = true;
    upload(Array.from(event.dataTransfer.files));
  });

  refresh().catch((e) => say(e.message));
})();

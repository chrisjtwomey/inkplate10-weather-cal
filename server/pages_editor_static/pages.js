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
  let panelOn = false;
  let saveTimer = 0;

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
    const theme = $("theme");
    theme.replaceChildren(...Object.entries(N.themes).filter(([, t]) => t.pages.includes(type)).map(([name, t]) => {
      const o = new Option(t.label, name);
      o.selected = name === s.theme;
      return o;
    }));
    $("map").replaceChildren(...N.maps.map((name) => {
      const o = new Option(name === "classic" ? "Classic" : name, name);
      o.selected = name === s.map;
      return o;
    }));
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

  // The page's scale on screen: 1:1, or as large as fits the column and the window below the bar.
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
    fit();
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
    if (!parts || !selected || !selected.img) return;
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
    const p = placement(selected.framing, selected.w, selected.h, areaBox({...parts, square: canvas}));
    pencil(canvas, p);
    placeHandle();
  }

  // The server's effect, in the same order: place on white, blur the negative,
  // dodge, stretch the middle 98% of greys to full range, dither to four greys.
  function pencil(canvas, p) {
    const w = selected.w * p.scale, h = selected.h * p.scale;
    const base = document.createElement("canvas");
    base.width = base.height = SIZE;
    const bc = base.getContext("2d");
    bc.fillStyle = "#fff";
    bc.fillRect(0, 0, SIZE, SIZE);
    bc.drawImage(selected.img, SIZE / 2 - p.x * w, SIZE / 2 - p.y * h, w, h);
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

  function setFraming(f) {
    selected.framing = {x: clamp(f.x, 0, 1), y: clamp(f.y, 0, 1), zoom: clamp(f.zoom, N.minZoom, N.maxZoom)};
    $("zoom").value = Math.log(selected.framing.zoom);
    $("undo-framing").disabled = same(selected.framing, selected.original);
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
    if (pointers.size === 1) drag = {x: event.clientX, y: event.clientY, framing: {...selected.framing}};
    else if (pointers.size === 2) { drag = null; pinch = {spread: spread(), zoom: selected.framing.zoom}; }
  });
  handle.addEventListener("pointermove", (event) => {
    if (!pointers.has(event.pointerId)) return;
    pointers.set(event.pointerId, {x: event.clientX, y: event.clientY});
    if (pinch && pointers.size === 2) {
      setFraming({...selected.framing, zoom: pinch.zoom * spread() / Math.max(pinch.spread, 1)});
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
    setFraming({...selected.framing, zoom: selected.framing.zoom * Math.exp(-event.deltaY * rate)});
  }, {passive: false});
  handle.addEventListener("dblclick", () => { if (selected) setFraming(CENTRE); });
  handle.addEventListener("keydown", (event) => {
    if (!selected) return;
    const f = selected.framing;
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
  $("zoom").addEventListener("input", () => setFraming({...selected.framing, zoom: Math.exp(Number($("zoom").value))}));
  $("centre").addEventListener("click", () => setFraming(CENTRE));

  $("undo-framing").addEventListener("click", () => setFraming(selected.original));
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
    const framing = {...CENTRE, ...(photo.framings[pageType()] || {})};
    selected = {id, framing, saved: {...framing}, original: {...framing}, img: null};
    framingStatus("");
    drawStrip();
    status("Opening the photo…");
    const img = new Image();
    img.src = "pages/photo/" + id + ".jpg";
    await img.decode();
    if (!selected || selected.id !== id) return;
    Object.assign(selected, {img, w: img.naturalWidth, h: img.naturalHeight});
    status("");
    $("framing-tools").hidden = false;
    setFraming(framing);
  }

  // ---- Panel view ----

  async function panel(on) {
    panelOn = on;
    $("panel-view").setAttribute("aria-pressed", on ? "true" : "false");
    $("panel").hidden = !on;
    frame.style.visibility = on ? "hidden" : "";
    placeHandle();
    if (!on) return;
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

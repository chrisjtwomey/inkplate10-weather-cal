// The Photos page: the list of photos, and the framing editor. The editor
// places the photo exactly as photos/picture.py framed() does, so what it
// shows in each window is what the server draws.
(function () {
  "use strict";
  const N = JSON.parse(document.getElementById("numbers").textContent);
  const $ = (id) => document.getElementById(id);
  const message = $("message");
  const editor = $("editor");
  const zoomInput = $("zoom");
  const windows = Array.from(document.querySelectorAll(".window"));
  const PREVIEW_DELAY_MS = 800;

  let photos = [];
  let editing = null;            // {photo, framing, saved}
  let previewTimer = null;
  let previewRound = 0;

  function say(words, kind) {
    message.textContent = words || "";
    message.className = "banner " + (kind || "problem");
    message.hidden = !words;
  }

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

  function post(path, body) {
    return call(path, {method: "POST", headers: {"Content-Type": "application/json"},
                       body: body === undefined ? undefined : JSON.stringify(body)});
  }

  async function load() {
    photos = (await (await call("photos/list")).json()).photos;
    drawList();
  }

  // ---- The list ----

  function button(words, onClick, disabled) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = words;
    b.disabled = !!disabled;
    b.addEventListener("click", onClick);
    return b;
  }

  function drawList() {
    const list = $("photos");
    list.replaceChildren();
    $("empty").hidden = photos.length > 0;
    photos.forEach((photo, i) => {
      const li = document.createElement("li");
      const thumb = document.createElement("img");
      const f = photo.framing;
      thumb.src = "photos/" + photo.id + "/thumb.png?f=" + [f.x, f.y, f.zoom].join(",");
      thumb.alt = "";
      thumb.loading = "lazy";
      const name = document.createElement("span");
      name.className = "name";
      name.textContent = photo.name;
      const inSet = document.createElement("label");
      const box = document.createElement("input");
      box.type = "checkbox";
      box.checked = photo.in_set;
      box.addEventListener("change", () => act(() => post("photos/" + photo.id + "/set", {in_set: box.checked})));
      inSet.append(box, " Include");
      const ids = photos.map((p) => p.id);
      const move = (to) => {
        ids.splice(i, 1);
        ids.splice(to, 0, photo.id);
        act(() => post("photos/order", {ids: ids}));
      };
      li.append(thumb, name, inSet,
        button("Up", () => move(i - 1), i === 0),
        button("Down", () => move(i + 1), i === photos.length - 1),
        button("Frame", () => openEditor(photo)),
        button("Delete", () => {
          if (!confirm("Delete " + photo.name + "? This cannot be undone.")) return;
          if (editing && editing.photo.id === photo.id) closeEditor();
          act(() => post("photos/" + photo.id + "/delete"));
        }));
      list.append(li);
    });
  }

  async function act(change) {
    try {
      await change();
      say("");
    } catch (e) {
      say(e.message);
    }
    await load().catch((e) => say(e.message));
  }

  $("upload").addEventListener("submit", async (event) => {
    event.preventDefault();
    const files = Array.from($("files").files);
    if (!files.length) {
      say("Choose a photo first.");
      return;
    }
    const problems = [];
    for (const file of files) {
      const form = new FormData();
      form.append("photo", file, file.name);
      try {
        await call("photos/upload", {method: "POST", body: form});
      } catch (e) {
        problems.push(file.name + ": " + e.message);
      }
    }
    $("files").value = "";
    say(problems.join(" "), "problem");
    if (!problems.length) say(files.length === 1 ? "Photo added." : files.length + " photos added.", "notice");
    await load().catch((e) => say(e.message));
  });

  // ---- The framing editor ----

  const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);
  const same = (a, b) => a.x === b.x && a.y === b.y && a.zoom === b.zoom;

  function openEditor(photo) {
    editing = {photo: photo, framing: Object.assign({}, photo.framing), saved: Object.assign({}, photo.framing)};
    $("editor-title").textContent = "Frame " + photo.name;
    zoomInput.min = Math.log(N.minZoom);
    zoomInput.max = Math.log(N.maxZoom);
    windows.forEach((w) => {
      const img = w.querySelector("img");
      img.onload = layout;
      img.src = "photos/" + photo.id + "/original";
    });
    editor.hidden = false;
    editor.scrollIntoView({behavior: "smooth"});
    changed();
  }

  function closeEditor() {
    editing = null;
    editor.hidden = true;
    previewRound++;
  }

  // The photo's natural size, upright: browsers apply EXIF orientation as the server does.
  function photoSize() {
    const img = windows[0].querySelector("img");
    return {w: img.naturalWidth, h: img.naturalHeight};
  }

  function layout() {
    if (!editing) return;
    const {w, h} = photoSize();
    if (!w || !h) return;
    const f = editing.framing;
    const scale = f.zoom * Math.max(N.size / w, N.size / h);
    const left = N.size / 2 - f.x * w * scale;
    const top = N.size / 2 - f.y * h * scale;
    windows.forEach((win) => {
      const [l, t, r, b] = N.windows[win.dataset.shape];
      win.style.aspectRatio = (r - l) + " / " + (b - t);
      const k = win.clientWidth / (r - l);
      const img = win.querySelector("img");
      img.style.left = (left - l) * k + "px";
      img.style.top = (top - t) * k + "px";
      img.style.width = w * scale * k + "px";
    });
    zoomInput.value = Math.log(f.zoom);
    $("save").disabled = same(f, editing.saved);
    $("undo").disabled = same(f, editing.saved);
  }

  function changed() {
    layout();
    clearTimeout(previewTimer);
    previewTimer = setTimeout(drawPreviews, PREVIEW_DELAY_MS);
  }

  function setFraming(f) {
    editing.framing = {x: clamp(f.x, 0, 1), y: clamp(f.y, 0, 1), zoom: clamp(f.zoom, N.minZoom, N.maxZoom)};
    changed();
  }

  windows.forEach((win) => {
    let from = null;
    win.addEventListener("pointerdown", (event) => {
      if (!editing) return;
      from = {x: event.clientX, y: event.clientY, framing: Object.assign({}, editing.framing)};
      win.setPointerCapture(event.pointerId);
    });
    win.addEventListener("pointermove", (event) => {
      if (!from) return;
      const [l, , r] = N.windows[win.dataset.shape];
      const k = win.clientWidth / (r - l);
      const {w, h} = photoSize();
      const scale = from.framing.zoom * Math.max(N.size / w, N.size / h);
      setFraming({
        x: from.framing.x - (event.clientX - from.x) / k / (w * scale),
        y: from.framing.y - (event.clientY - from.y) / k / (h * scale),
        zoom: from.framing.zoom,
      });
    });
    const stop = () => { from = null; };
    win.addEventListener("pointerup", stop);
    win.addEventListener("pointercancel", stop);
    win.addEventListener("wheel", (event) => {
      if (!editing) return;
      event.preventDefault();
      const f = editing.framing;
      setFraming({x: f.x, y: f.y, zoom: f.zoom * Math.exp(-event.deltaY * 0.0015)});
    }, {passive: false});
  });

  zoomInput.addEventListener("input", () => {
    const f = editing.framing;
    setFraming({x: f.x, y: f.y, zoom: Math.exp(Number(zoomInput.value))});
  });
  $("centre").addEventListener("click", () => setFraming({x: 0.5, y: 0.5, zoom: 1}));
  $("undo").addEventListener("click", () => setFraming(editing.saved));
  $("close").addEventListener("click", () => {
    if (!same(editing.framing, editing.saved) && !confirm("Close without saving the framing?")) return;
    closeEditor();
  });
  $("save").addEventListener("click", async () => {
    const f = Object.assign({}, editing.framing);
    try {
      await post("photos/" + editing.photo.id + "/framing", f);
      editing.saved = f;
      editing.photo.framing = f;
      layout();
      say("Framing saved.", "notice");
    } catch (e) {
      say(e.message);
    }
  });

  async function drawPreviews() {
    if (!editing) return;
    const round = ++previewRound;
    const f = editing.framing;
    const status = $("preview-status");
    status.textContent = "Drawing the previews…";
    try {
      for (const shape of ["wide", "tall"]) {
        const query = "?x=" + f.x + "&y=" + f.y + "&zoom=" + f.zoom;
        const blob = await (await call("photos/" + editing.photo.id + "/preview/" + shape + ".png" + query)).blob();
        if (round !== previewRound) return;
        const img = $("preview-" + shape);
        if (img.src.startsWith("blob:")) URL.revokeObjectURL(img.src);
        img.src = URL.createObjectURL(blob);
      }
      status.textContent = "";
    } catch (e) {
      if (round === previewRound) status.textContent = e.message;
    }
  }

  window.addEventListener("resize", layout);
  load().catch((e) => say(e.message));
})();

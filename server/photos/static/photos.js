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

  let marks = {today: null, tomorrow: null};

  async function load() {
    const listing = await (await call("photos/list")).json();
    photos = listing.photos;
    marks = {today: listing.today, tomorrow: listing.tomorrow};
    drawList();
  }

  // ---- The list ----

  function drawList() {
    const list = $("photos");
    const focused = document.activeElement && document.activeElement.closest("li");
    list.replaceChildren(...photos.map(row));
    $("empty").hidden = photos.length > 0;
    if (focused && focused.dataset.id) {
      const again = list.querySelector('li[data-id="' + focused.dataset.id + '"] .grip');
      if (again) again.focus();
    }
  }

  function row(photo) {
    const li = document.createElement("li");
    li.dataset.id = photo.id;
    li.classList.toggle("editing", !!editing && editing.photo.id === photo.id);
    li.classList.toggle("left-out", !photo.in_set);

    const grip = document.createElement("button");
    grip.type = "button";
    grip.className = "grip";
    grip.textContent = "⠿";
    grip.setAttribute("aria-label", "Move " + photo.name + " with the up and down arrows");
    grip.addEventListener("keydown", (event) => {
      const step = {ArrowUp: -1, ArrowDown: 1}[event.key];
      if (!step) return;
      event.preventDefault();
      const ids = photos.map((p) => p.id);
      const from = ids.indexOf(photo.id);
      const to = from + step;
      if (to < 0 || to >= ids.length) return;
      ids.splice(to, 0, ids.splice(from, 1)[0]);
      act(() => post("photos/order", {ids: ids}));
    });
    dragByGrip(li, grip);

    const open = document.createElement("button");
    open.type = "button";
    open.className = "open";
    const thumb = document.createElement("img");
    const f = photo.framing;
    thumb.src = "photos/" + photo.id + "/thumb.png?f=" + [f.x, f.y, f.zoom].join(",");
    thumb.alt = "";
    const name = document.createElement("span");
    name.className = "name";
    name.textContent = photo.name;
    for (const [id, words] of [[marks.today, "Today"], [marks.tomorrow, "Tomorrow"]]) {
      if (id !== photo.id) continue;
      const mark = document.createElement("span");
      mark.className = "mark";
      mark.textContent = words;
      name.append(" ", mark);
    }
    open.append(thumb, name);
    open.addEventListener("click", () => openEditor(photo));

    const include = document.createElement("label");
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = photo.in_set;
    box.addEventListener("change", () => act(() => post("photos/" + photo.id + "/set", {in_set: box.checked})));
    include.append(box, " Include");

    li.append(grip, open, include);
    return li;
  }

  // Moves the other rows past the one being dragged, so the dragged row keeps its pointer capture.
  function dragByGrip(li, grip) {
    let startY = 0;
    grip.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      grip.setPointerCapture(event.pointerId);
      startY = event.clientY;
      li.classList.add("dragging");
    });
    grip.addEventListener("pointermove", (event) => {
      if (!li.classList.contains("dragging")) return;
      let dy = event.clientY - startY;
      const before = li.previousElementSibling;
      const after = li.nextElementSibling;
      if (after && dy > after.offsetHeight / 2) {
        li.before(after);
        startY += after.offsetHeight;
        dy -= after.offsetHeight;
      } else if (before && dy < -before.offsetHeight / 2) {
        li.after(before);
        startY -= before.offsetHeight;
        dy += before.offsetHeight;
      }
      li.style.transform = "translateY(" + dy + "px)";
    });
    const drop = () => {
      if (!li.classList.contains("dragging")) return;
      li.classList.remove("dragging");
      li.style.transform = "";
      const ids = Array.from($("photos").children).map((r) => r.dataset.id);
      if (ids.join() !== photos.map((p) => p.id).join()) act(() => post("photos/order", {ids: ids}));
    };
    grip.addEventListener("pointerup", drop);
    grip.addEventListener("pointercancel", drop);
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

  // ---- Adding photos ----

  function sendOne(file, bar, words) {
    return new Promise((resolve) => {
      const form = new FormData();
      form.append("photo", file, file.name);
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "photos/upload");
      xhr.upload.addEventListener("progress", (event) => {
        if (event.lengthComputable) bar.value = event.loaded / event.total;
      });
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

  async function add(files) {
    const list = $("uploads");
    say("");
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
      list.append(item);
      if (await sendOne(file, bar, words)) setTimeout(() => item.remove(), 3000);
    }
    await load().catch((e) => say(e.message));
  }

  $("files").addEventListener("change", () => {
    const files = Array.from($("files").files);
    $("files").value = "";
    if (files.length) add(files);
  });

  const dropZone = $("drop");
  const carriesFiles = (event) => Array.from(event.dataTransfer.types).includes("Files");
  document.addEventListener("dragover", (event) => {
    if (!carriesFiles(event)) return;
    event.preventDefault();
    dropZone.hidden = false;
  });
  document.addEventListener("dragleave", (event) => {
    if (event.relatedTarget === null) dropZone.hidden = true;
  });
  document.addEventListener("drop", (event) => {
    if (!carriesFiles(event)) return;
    event.preventDefault();
    dropZone.hidden = true;
    add(Array.from(event.dataTransfer.files));
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
    drawList();
    changed();
  }

  function closeEditor() {
    editing = null;
    editor.hidden = true;
    previewRound++;
    drawList();
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
  $("delete").addEventListener("click", () => {
    const photo = editing.photo;
    if (!confirm("Delete " + photo.name + "? This cannot be undone.")) return;
    closeEditor();
    act(() => post("photos/" + photo.id + "/delete"));
  });
  $("save").addEventListener("click", async () => {
    const f = Object.assign({}, editing.framing);
    try {
      await post("photos/" + editing.photo.id + "/framing", f);
      editing.saved = f;
      editing.photo.framing = f;
      layout();
      say("Framing saved.", "notice");
      await load();
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

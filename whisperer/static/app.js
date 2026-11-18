// Example complaints fill the form.
document.querySelectorAll("[data-example]").forEach((chip) => {
  chip.addEventListener("click", () => {
    const box = document.querySelector("textarea[name=report]");
    box.value = chip.dataset.example;
    box.focus();
  });
});

// The evidence drop: files add up across picks and drops (up to 8), each listed with a button to
// take it out again, so what will be sent is always in view. The browser's own file list is
// rebuilt from that list, so the form sends exactly the files shown.
const MAX_FILES = 8, MAX_BYTES = 5 * 1024 * 1024;
const READABLE = /\.(png|jpe?g|webp|gif|pdf|xlsx|csv|tsv|docx|txt|md|json|xml|html?|log)$/i;
document.querySelectorAll(".evidence-drop").forEach((drop) => {
  const input = drop.querySelector("input[type=file]");
  const form = drop.closest("form");
  const title = drop.querySelector("[data-drop-title]"), hint = drop.querySelector("[data-drop-list]");
  const list = form.querySelector("[data-drop-files]"), note = form.querySelector("[data-drop-note]");
  const empty = [title.textContent, hint.textContent];
  let chosen = [];
  const size = (n) => (n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1048576).toFixed(1)} MB`);
  const say = (text) => { note.textContent = text; note.hidden = !text; };

  const render = () => {
    const box = new DataTransfer();
    chosen.forEach((f) => box.items.add(f));
    input.files = box.files;
    const n = chosen.length;
    drop.classList.toggle("has-files", n > 0);
    title.textContent = n ? `✓ ${n} file${n > 1 ? "s" : ""} ready to send` : empty[0];
    hint.textContent = n ? (n < MAX_FILES ? `Drop or pick more to add them · up to ${MAX_FILES} files` : `That's the most: ${MAX_FILES} files`) : empty[1];
    list.hidden = !n;
    list.replaceChildren(...chosen.map((f, i) => {
      const li = document.createElement("li");
      const name = document.createElement("span");
      name.className = "drop-file-name"; name.textContent = f.name;
      const meta = document.createElement("small");
      meta.textContent = size(f.size);
      const remove = document.createElement("button");
      remove.type = "button"; remove.className = "drop-remove"; remove.textContent = "×";
      remove.setAttribute("aria-label", `Remove ${f.name}`);
      remove.addEventListener("click", () => { chosen.splice(i, 1); say(""); render(); });
      li.append(name, meta, remove);
      return li;
    }));
  };

  input.addEventListener("change", () => {
    const skipped = [];
    for (const f of input.files) {
      if (chosen.some((c) => c.name === f.name && c.size === f.size && c.lastModified === f.lastModified)) continue;
      if (!READABLE.test(f.name)) skipped.push(`${f.name} (Bug Whisperer can't read this kind of file)`);
      else if (f.size > MAX_BYTES) skipped.push(`${f.name} (over 5 MB)`);
      else if (chosen.length >= MAX_FILES) skipped.push(`${f.name} (${MAX_FILES} files is the most)`);
      else chosen.push(f);
    }
    say(skipped.length ? `Not added: ${skipped.join(", ")}.` : "");
    render();
  });
  input.addEventListener("dragenter", () => drop.classList.add("dragging"));
  ["dragleave", "drop"].forEach((e) => input.addEventListener(e, () => drop.classList.remove("dragging")));
  // back to this page: start clean, so the list and what the form sends always match
  window.addEventListener("pageshow", () => { chosen = []; say(""); render(); });
});

// Home page: sections below the fold rise once as they scroll into view.
// Nothing is hidden until this runs, so the page still reads fine without JavaScript.
const revealable = document.querySelectorAll("[data-reveal], .how");
if (revealable.length && "IntersectionObserver" in window) {
  const watcher = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("seen");
      watcher.unobserve(entry.target);
    });
  }, { rootMargin: "0px 0px -60px 0px" });
  revealable.forEach((node) => watcher.observe(node));
  document.documentElement.classList.add("reveal-ready");
}

// The live tracker's clock counts up every second, between page refreshes too. The server sends
// how long Kane has been at work; each refreshed tracker restarts from that, so clocks never drift.
setInterval(() => {
  document.querySelectorAll("[data-elapsed]").forEach((el) => {
    if (!el.dataset.t0) el.dataset.t0 = Date.now() - Number(el.dataset.elapsed) * 1000;
    const s = Math.max(0, Math.floor((Date.now() - Number(el.dataset.t0)) / 1000));
    el.textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  });
}, 1000);

// Copy buttons (event delegation, because the live part is replaced while polling).
document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy]");
  if (!button) return;
  const text = document.getElementById(button.dataset.copy)?.innerText || "";
  try {
    await navigator.clipboard.writeText(text);
    const label = button.textContent;
    button.textContent = "Copied ✓";
    setTimeout(() => (button.textContent = label), 1500);
  } catch {
    /* clipboard not allowed: the text is on the page to copy by hand */
  }
});

// The live 3D game's lightweight controls. The WebGL stage is kept across polling, while these
// buttons are replaced with the fresh HUD, so the selected camera is read back from the stage.
function syncKaneControls(root = document) {
  root.querySelectorAll("[data-kane-game]").forEach((game) => {
    const stage = game.querySelector("[data-kane3d]");
    const label = game.querySelector("[data-game-camera] b");
    if (label && stage?.dataset.camera) label.textContent = stage.dataset.camera;
    const fullscreen = game.querySelector("[data-game-fullscreen]");
    if (fullscreen) {
      const on = document.fullscreenElement === game;
      fullscreen.setAttribute("aria-label", on ? "Exit fullscreen" : "Enter fullscreen");
      fullscreen.querySelector("span").textContent = on ? "⛶" : "⛶";
    }
  });
}

document.addEventListener("click", async (event) => {
  const camera = event.target.closest("[data-game-camera]");
  if (camera) {
    const stage = camera.closest("[data-kane-game]")?.querySelector("[data-kane3d]");
    const label = stage?.kaneCameraNext?.();
    if (label) camera.querySelector("b").textContent = label;
    return;
  }
  const view = event.target.closest("[data-game-view]");
  if (view) {  // 3D office or simple view: the person's choice, kept for next time
    window.kaneSetView?.(view.dataset.gameView);
    return;
  }
  const fullscreen = event.target.closest("[data-game-fullscreen]");
  if (!fullscreen) return;
  const game = fullscreen.closest("[data-kane-game]");
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await game.requestFullscreen();
  } catch {
    /* Fullscreen can be blocked by an embedded browser; the game still works in place. */
  }
});
document.addEventListener("fullscreenchange", () => syncKaneControls());

// Before/after compare slider: dragging moves a clip-path wipe (no layout, GPU only).
document.addEventListener("input", (event) => {
  const range = event.target.closest(".compare-range");
  if (!range) return;
  range.closest("[data-compare]").style.setProperty("--pos", `${range.value}%`);
});

// "Watch Kane solve this case": a flipbook of Kane's real screenshots, each with Kane's line.
// Screens crossfade (two stacked images, opacity + a little blur so it reads as one change),
// the progress bar moves with transform only, and the stamp lands once at the end.
const FRAME_MS = 1200;

function initReplay(el) {
  if (el.dataset.ready) return;
  el.dataset.ready = "1";
  const data = JSON.parse(el.querySelector(".replay-data").textContent);
  const frames = data.chapters.flatMap((c) => c.frames.map((f) => ({ ...f, chapter: c.title })));
  const [imgA, imgB] = el.querySelectorAll(".replay-img");
  const chapter = el.querySelector(".replay-chapter");
  const line = el.querySelector(".replay-line .text");
  const lineBox = el.querySelector(".replay-line");
  const bar = el.querySelector(".replay-progress span");
  const end = el.querySelector(".replay-end");
  const play = el.querySelector(".replay-play");
  let i = 0, timer = null, front = imgA;

  const show = (n) => {
    i = Math.max(0, Math.min(frames.length - 1, n));
    const f = frames[i];
    const back = front === imgA ? imgB : imgA;
    back.onload = () => { back.classList.add("on"); front.classList.remove("on"); front = back; };
    back.src = f.src;
    if (frames[i + 1]) new Image().src = frames[i + 1].src;  // preload the next screen
    chapter.textContent = f.chapter;
    line.textContent = f.line;
    lineBox.classList.toggle("failed", !!f.failed);
    lineBox.classList.remove("fresh"); void lineBox.offsetWidth; lineBox.classList.add("fresh");
    bar.style.transform = `scaleX(${(i + 1) / frames.length})`;
    end.hidden = true;
    el.classList.remove("ended");
  };
  const finish = () => {
    stop();
    end.querySelector(".replay-stamp").textContent = data.end.stamp;
    end.querySelector(".replay-stamp").className = `stamp replay-stamp tone-${data.end.tone}`;
    end.querySelector(".replay-end-line").textContent = `🕵️ Kane: “${data.end.line}”`;
    end.hidden = false;
    el.classList.add("ended");
    play.hidden = false;
    play.innerHTML = "<span>↺</span> Watch again";
  };
  const stop = () => { clearInterval(timer); timer = null; el.classList.remove("playing"); };
  const start = () => {
    if (i >= frames.length - 1) show(0);
    play.hidden = true;
    el.classList.add("playing");
    timer = setInterval(() => (i >= frames.length - 1 ? finish() : show(i + 1)), FRAME_MS);
  };

  play.addEventListener("click", start);
  el.querySelector(".replay-stage").addEventListener("click", (e) => {
    if (e.target.closest(".replay-play")) return;
    if (timer) { stop(); play.hidden = false; play.innerHTML = "<span>▶</span> Continue"; } else start();
  });
  el.querySelector(".replay-prev").addEventListener("click", () => { stop(); play.hidden = false; show(i - 1); });
  el.querySelector(".replay-next").addEventListener("click", () => {
    stop(); play.hidden = false; i >= frames.length - 1 ? finish() : show(i + 1);
  });
  el.tabIndex = 0;
  el.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight") el.querySelector(".replay-next").click();
    if (e.key === "ArrowLeft") el.querySelector(".replay-prev").click();
  });
  show(0);
}
document.querySelectorAll("[data-replay]").forEach(initReplay);

// Red string on the boards: a gently sagging line from pin to pin, for each pair in data-links
// (cases from the same scene, or the steps of one investigation). It draws in once, after the
// pins have landed; on resize it is simply redrawn.
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function drawStrings(board, animate) {
  const svg = board.querySelector(".strings");
  if (!svg || getComputedStyle(svg).display === "none") return;
  const wall = svg.parentElement;
  const origin = wall.getBoundingClientRect();
  const centre = (id) => {
    const pin = wall.querySelector(`[data-pin="${CSS.escape(id)}"] .pin`);
    if (!pin) return null;
    const r = pin.getBoundingClientRect();
    return [r.left + r.width / 2 - origin.left - wall.clientLeft, r.top + r.height / 2 - origin.top - wall.clientTop];
  };
  svg.replaceChildren();
  svg.classList.remove("drawing");
  JSON.parse(board.dataset.links || "[]").forEach(([from, to], i) => {
    const a = centre(from), b = centre(to);
    if (!a || !b) return;
    const sag = Math.min(70, Math.hypot(b[0] - a[0], b[1] - a[1]) * 0.15);
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", `M${a[0]},${a[1]} Q${(a[0] + b[0]) / 2},${(a[1] + b[1]) / 2 + sag} ${b[0]},${b[1]}`);
    svg.append(path);
    if (animate) {
      const length = path.getTotalLength();
      path.style.strokeDasharray = length;
      path.style.strokeDashoffset = length;
      path.style.transitionDelay = `${i * 110}ms`;
    }
  });
  if (animate) {
    svg.getBoundingClientRect();  // start from the hidden state, then let the strings draw in
    svg.classList.add("drawing");
    svg.querySelectorAll("path").forEach((p) => (p.style.strokeDashoffset = "0"));
  }
}

function initBoard(board) {
  const pins = board.querySelectorAll(".pinned").length;
  const landed = reduceMotion ? 0 : pins * 70 + 380;  // matches the pin-drop stagger in style.css
  let ready = false, frame = 0;
  setTimeout(() => { drawStrings(board, !reduceMotion); ready = true; }, landed);
  new ResizeObserver(() => {
    if (!ready) return;  // the first drawing happens once the pins have landed
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => drawStrings(board, false));
  }).observe(board);
}

document.querySelectorAll("[data-board]").forEach(initBoard);

// Kane's dialogue box types its line out, RPG style. A line is typed once: when the page refreshes
// with the same line, it just stays. Reduced motion shows the whole line at once.
const typed = new Set();
function typeLine(el) {
  const text = el.textContent;
  el.textContent = "";
  let i = 0;
  const step = () => {
    if (!el.isConnected) return;  // the page refreshed with a newer line
    el.textContent = text.slice(0, ++i);
    if (i < text.length) setTimeout(step, text[i - 1] === "." ? 120 : 18);
  };
  step();
}
// A box further down the page starts typing when it scrolls into view, not before.
const onScreen = "IntersectionObserver" in window && new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (!entry.isIntersecting) return;
    onScreen.unobserve(entry.target);
    typeLine(entry.target);
  });
}, { threshold: 0.6 });
function typeOut(root) {
  root.querySelectorAll("[data-type]").forEach((el) => {
    const key = el.dataset.type;
    if (typed.has(key) || reduceMotion) return;
    typed.add(key);
    if (onScreen) onScreen.observe(el);
    else typeLine(el);
  });
}
typeOut(document);

// The scene map: Kane's token walks the rooms in the order he really visited them, each room
// lighting up as he reaches it; the clue room (or the fixed room) gives a small pop. It walks
// once, when the map scrolls into view. Reduced motion shows the finished walk.
function initTrail(trail) {
  const rooms = [...trail.querySelectorAll("[data-room]")];
  const token = trail.querySelector(".trail-token");
  if (!rooms.length || !token) return;
  let at = rooms.length - 1;
  const place = (room) => {
    const t = trail.getBoundingClientRect(), r = room.getBoundingClientRect();
    token.style.transform = `translate(${r.right - t.left - 24}px, ${r.top - t.top - 13}px)`;
  };
  const finish = () => {
    trail.classList.remove("walking");
    trail.classList.add("walked");
    rooms.forEach((r) => r.classList.add("visited"));
    place(rooms[at]);
  };
  const walk = () => {
    if (reduceMotion) return finish();
    trail.classList.add("walking");
    token.style.transition = "none";
    place(rooms[0]);
    token.getBoundingClientRect();
    token.style.transition = "";
    let i = 0;
    const next = () => {
      at = i;
      place(rooms[i]);
      rooms[i].classList.add("visited");
      if (rooms[i].matches(".clue, .solved")) rooms[i].classList.add("found");
      i += 1;
      setTimeout(i < rooms.length ? next : finish, i < rooms.length ? 650 : 450);
    };
    next();
  };
  if ("IntersectionObserver" in window) {
    const seen = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      seen.disconnect();
      walk();
    }, { threshold: 0.35 });
    seen.observe(trail);
  } else walk();
  new ResizeObserver(() => place(rooms[at])).observe(trail);
}
document.querySelectorAll("[data-trail]").forEach(initTrail);

// The chapter card: a new case opens. Shown once per case (remembered in this browser), skipped
// with reduced motion, and a click dismisses it.
const chapter = document.querySelector("[data-chapter]");
if (chapter) {
  const key = `chapter-${chapter.dataset.chapter}`;
  let seen = false;
  try {
    seen = localStorage.getItem(key) === "1";
    localStorage.setItem(key, "1");
  } catch {
    /* no storage: show it this once */
  }
  if (seen || reduceMotion) chapter.remove();
  else {
    chapter.hidden = false;
    const close = () => {
      chapter.classList.add("out");
      setTimeout(() => chapter.remove(), 280);
    };
    const timer = setTimeout(close, 1900);
    chapter.addEventListener("click", () => { clearTimeout(timer); close(); });
  }
}

// Juice on a real verdict (CONFIRMED or CASE CLOSED): the world freezes for a beat as the stamp
// lands (hit-stop), one flash in the verdict's colour, and the verdict panel jolts from a
// decaying trauma value (summed sines, visual only). Nothing happens with reduced motion.
function impact(panel) {
  if (reduceMotion || !panel) return;
  const moving = document.querySelectorAll(".kane-body, .kane-lens");
  moving.forEach((n) => (n.style.animationPlayState = "paused"));
  setTimeout(() => moving.forEach((n) => (n.style.animationPlayState = "")), 120);
  panel.classList.remove("impact");
  void panel.offsetWidth;
  panel.classList.add("impact");
  let trauma = 0.7, last = 0, t = 0;
  const frame = (now) => {
    const dt = last ? (now - last) / 1000 : 0;
    last = now;
    trauma = Math.max(0, trauma - 1.8 * dt);
    t += dt * 30;
    const s = trauma * trauma;
    panel.style.transform = trauma
      ? `translate(${(8 * s * Math.sin(t * 1.7)).toFixed(2)}px, ${(5 * s * Math.sin(t * 2.3)).toFixed(2)}px) rotate(${(0.6 * s * Math.sin(t * 1.1)).toFixed(2)}deg)`
      : "";
    if (trauma > 0) requestAnimationFrame(frame);
  };
  setTimeout(() => requestAnimationFrame(frame), 120);
}

// Kane's browser, live: reload the camera's latest frame about once a second. The new frame is
// loaded off-screen first and swapped in only when ready, so the picture never flashes blank.
setInterval(() => {
  document.querySelectorAll(".live-shot[data-live-src]").forEach((img) => {
    if (img.dataset.loading) return;
    img.dataset.loading = "1";
    const next = new Image();
    next.onload = () => { img.src = next.src; delete img.dataset.loading; };
    next.onerror = () => { delete img.dataset.loading; };
    next.src = `${img.dataset.liveSrc}?t=${Date.now()}`;
  });
}, 900);

// Put a freshly rendered page (inside `freshRoot`) into `root` without ever taking `keep` out
// of the page: `keep` takes the fresh contents of its twin `freshKeep`, and at each level up to
// `root` its siblings are swapped for the fresh ones and its parent takes the fresh attributes.
function keepInPlace(root, keep, freshRoot, freshKeep) {
  const copyAttributes = (to, from) => {
    [...to.attributes].forEach((a) => { if (!from.hasAttribute(a.name)) to.removeAttribute(a.name); });
    [...from.attributes].forEach((a) => to.setAttribute(a.name, a.value));
  };
  copyAttributes(keep, freshKeep);
  keep.replaceChildren(...freshKeep.childNodes);
  let o = keep, f = freshKeep;
  while (o !== root && f !== freshRoot) {
    const before = [], after = [];
    let past = false;
    [...f.parentNode.childNodes].forEach((c) => { if (c === f) past = true; else (past ? after : before).push(c); });
    [...o.parentNode.childNodes].forEach((c) => { if (c !== o) c.remove(); });
    o.before(...before); o.after(...after);
    o = o.parentNode; f = f.parentNode;
    if (o !== root) copyAttributes(o, f);
  }
}

// While Kane or Claude is working, refresh the live part of a case page.
// Only what is NEW animates: steps that weren't there before, and a stamp whose words changed.
// Without this, everything would re-animate every 2 seconds.
const live = document.getElementById("live");
if (live) {
  const isActive = () => live.querySelector(".live-root")?.dataset.active === "true";
  const stampText = () => live.querySelector(".verdict .stamp")?.textContent.trim() || "";
  const tick = async () => {
    if (!isActive()) return;
    try {
      const response = await fetch(live.dataset.url, { cache: "no-store" });
      if (response.ok) {
        const stepsBefore = live.querySelectorAll(".steps.live li").length;
        const stampBefore = stampText();
        // Keep what the viewer is looking at: the live picture stays the same element (so it
        // never blanks out and reloads), and open sections stay open.
        const kept = {};
        live.querySelectorAll("[data-keep]").forEach((n) => (kept[n.dataset.keep] = n));
        const open = new Set([...live.querySelectorAll("details[data-key]")]
          .filter((d) => d.open).map((d) => d.dataset.key));
        const fresh = document.createElement("div");
        fresh.innerHTML = await response.text();
        // The 3D game in full screen: its frame must never leave the page (that ends full
        // screen), so the fresh page is built around it instead of replacing it.
        const shell = document.fullscreenElement?.matches("[data-keep-shell]") && live.contains(document.fullscreenElement)
          ? document.fullscreenElement : null;
        const freshShell = shell && fresh.querySelector(`[data-keep="${shell.dataset.keep}"]`);
        if (freshShell) keepInPlace(live, shell, fresh, freshShell);
        else live.replaceChildren(...fresh.childNodes);
        // a kept "shell" (the 3D game's frame) takes the fresh contents; anything kept inside
        // it (the 3D stage) is put back after
        live.querySelectorAll("[data-keep]").forEach((n) => {
          const old = kept[n.dataset.keep];
          if (!old || old === n) return;
          Object.assign(old.dataset, n.dataset);
          if ("keepShell" in n.dataset) old.replaceChildren(...n.childNodes);
          n.replaceWith(old);
        });
        live.querySelectorAll("details[data-key]").forEach((d) => {
          if (open.has(d.dataset.key)) d.open = true;
        });
        const root = live.querySelector(".live-root");
        if (root && stampText() === stampBefore) root.classList.add("polled");
        live.querySelectorAll(".steps.live li").forEach((li, i) => {
          if (i >= stepsBefore) li.classList.add("new");
        });
        live.querySelectorAll("[data-replay]").forEach(initReplay);  // appears when the case ends
        live.querySelectorAll("[data-board]").forEach(initBoard);
        live.querySelectorAll("[data-trail]").forEach(initTrail);
        if (window.initRecon) live.querySelectorAll("[data-recon]").forEach(window.initRecon);
        if (window.initLineup3d) live.querySelectorAll("[data-lineup3d]").forEach(window.initLineup3d);
        if (window.initKane3d) window.initKane3d(live);
        syncKaneControls(live);
        document.dispatchEvent(new Event("kane:update"));  // Kane in 3D acts out any new steps
        typeOut(live);
        const stampNow = stampText();
        if (stampNow && stampNow !== stampBefore && /confirmed|case closed/i.test(stampNow)) {
          setTimeout(() => impact(live.querySelector(".verdict")), 260);  // as the stamp lands
        }
      }
    } catch {
      /* try again next tick */
    }
    setTimeout(tick, 2000);
  };
  setTimeout(tick, 2000);
}

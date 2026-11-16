// Example complaints fill the form.
document.querySelectorAll("[data-example]").forEach((chip) => {
  chip.addEventListener("click", () => {
    const box = document.querySelector("textarea[name=report]");
    box.value = chip.dataset.example;
    box.focus();
  });
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
        live.innerHTML = await response.text();
        live.querySelectorAll("[data-keep]").forEach((n) => {
          if (kept[n.dataset.keep]) n.replaceWith(kept[n.dataset.keep]);
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
      }
    } catch {
      /* try again next tick */
    }
    setTimeout(tick, 2000);
  };
  setTimeout(tick, 2000);
}

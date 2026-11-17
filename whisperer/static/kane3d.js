// Detective Kane in 3D, acting out each of his real steps while a case runs.
//
// The live tracker on the page lists Kane's steps as they really happen (from Kane CLI's own
// events), each marked with its kind: go, type, click, pick, check, look… Every new step becomes
// an action in Kane's office: he walks through the door to the page he really went to, types at
// the computer (the screen shows the real value), jabs the real button, and nods or shakes his
// head at each check; a failed check turns the screen red and the room glows red. Nothing here is
// invented: no step, no action.
//
// Kane is the CC0 "RobotExpressive" model by Tomás Laulhé (see static/models/CREDITS.md),
// recoloured with a fedora, a red scarf and a magnifying glass: an AI detective. The furniture is
// CC0 models from Poly Haven; the room and everything that shows the case is built in code.
// three.js loads only on a live case in the 3D view; the simple view (or no WebGL) keeps the 2D detective.

(function () {
  const GLTF_LOADER = "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js";
  const ROOM_ENV = "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/environments/RoomEnvironment.js";
  const MODEL = "/static/models/RobotExpressive.glb";
  const PATH_RE = /https?:\/\/[^\s]+/;

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = src; s.onload = resolve; s.onerror = () => reject(new Error(`couldn't load ${src}`));
      document.head.append(s);
    });
  }
  // ── 3D or simple: the person chooses with the view button (the choice is read in base.html).
  // The simple view is the 2D detective and never starts WebGL, for slower computers.
  const kaneView = () => document.documentElement.dataset.kaneView || "3d";
  // the button: the page reloads into the other view (the case itself lives on the server)
  window.kaneSetView = (view) => {
    try { localStorage.setItem("kaneView", view); } catch { /* storage blocked: this page only */ }
    location.reload();
  };

  async function loadEngine() {
    await loadThree();  // from recon.js
    if (!window.THREE.GLTFLoader) await loadScript(GLTF_LOADER);
    if (!window.THREE.RoomEnvironment) await loadScript(ROOM_ENV).catch(() => {});  // reflections are a nicety
  }

  // ── reading the real steps from the live tracker ──────────────────────────────────────────
  function trackerSteps() {
    const list = document.querySelector("#live .track-list");
    if (!list) return { total: 0, steps: [], thinking: false };
    const items = [...list.querySelectorAll("li")].map((li) => ({
      kind: li.dataset.kind || "do",
      status: li.classList.contains("failed") ? "failed" : li.classList.contains("running") ? "running" : "done",
      text: (li.querySelector(".txt")?.textContent || "").trim(),
    }));
    const done = items.filter((s) => s.status !== "running");
    return { total: Number(list.dataset.total || done.length), steps: done, thinking: items.some((s) => s.status === "running") };
  }

  function parseStep(step) {
    const t = step.text.replace(/\s+/g, " ");
    let m;
    if (step.kind === "go") {
      const url = (t.match(PATH_RE) || [])[0];
      let path = url ? url.replace(/[.,]$/, "") : t.replace(/^I went to /, "").replace(/\.$/, "");
      try { if (url) path = new URL(path).pathname; } catch (e) { /* keep the words */ }
      return { action: "go", label: path };
    }
    if (step.kind === "type" && (m = t.match(/^I typed (.+?) into (.+?)\.?$/))) return { action: "type", value: m[1], field: m[2] };
    if (step.kind === "type") return { action: "type", value: t.replace(/^I /, ""), field: "" };
    if (step.kind === "pick" && (m = t.match(/^I picked (.+?) in (.+?)\.?$/))) return { action: "click", label: m[1], field: m[2] };
    if (step.kind === "click" || step.kind === "pick") return { action: "click", label: t.replace(/^I (clicked|picked) /, "").replace(/\.$/, "") };
    if (step.kind === "check" || step.kind === "look") {
      return { action: "check", label: t.replace(/^I (checked|looked closely): /, ""), failed: step.status === "failed" };
    }
    if (step.kind === "key") return { action: "type", value: t.replace(/^I pressed /, "").replace(/\.$/, ""), field: "keyboard" };
    return { action: "wait", label: t };
  }

  // ── canvas textures ────────────────────────────────────────────────────────────────────────
  function canvasTex(T, w, h, paint) {
    const c = document.createElement("canvas"); c.width = w; c.height = h;
    paint(c.getContext("2d"), w, h);
    const tex = new T.CanvasTexture(c); tex.encoding = T.sRGBEncoding; tex.anisotropy = 4;
    return tex;
  }

  function wrapText(g, text, x, y, width, lh, max) {
    const words = String(text || "").split(" ");
    let line = "", n = 0;
    for (const w of words) {
      const next = line ? line + " " + w : w;
      if (g.measureText(next).width > width && line) {
        g.fillText(line, x, y + n * lh); line = w;
        if (++n >= max - 1) { line += "…"; break; }
      } else line = next;
    }
    g.fillText(line, x, y + n * lh);
  }

  function fitTextEnd(g, text, width) {
    const value = String(text || "");
    if (g.measureText(value).width <= width) return value;
    let tail = value;
    while (tail.length > 1 && g.measureText("…" + tail).width > width) tail = tail.slice(1);
    return "…" + tail;
  }

  function makeScreen(T) {
    const c = document.createElement("canvas"); c.width = 640; c.height = 400;
    const tex = new T.CanvasTexture(c); tex.encoding = T.sRGBEncoding;
    const g = c.getContext("2d");
    const state = { path: "about:blank", body: null, live: null };
    function draw() {
      if (state.live) {
        // Kane's real browser, from the live camera (1440x900, the screen's own 16:10 shape)
        g.drawImage(state.live, 0, 0, 640, 400);
        const b = state.body;
        if (b && b.kind === "check" && b.result) {  // the verdict, as a badge on the real page
          g.fillStyle = b.result === "fail" ? "rgba(179,38,30,.92)" : "rgba(15,122,82,.92)";
          g.fillRect(300, 300, 320, 80);
          g.fillStyle = "#fff"; g.font = "800 28px Inter, sans-serif";
          g.fillText(b.result === "fail" ? "✗ Not as expected" : "✓ As expected", 316, 350);
        }
        tex.needsUpdate = true;
        return;
      }
      g.fillStyle = "#f6f7fb"; g.fillRect(0, 0, 640, 400);
      g.fillStyle = "#dfe3ec"; g.fillRect(0, 0, 640, 46);
      g.fillStyle = "#ffffff"; g.fillRect(70, 10, 540, 26);
      g.fillStyle = "#4b5263"; g.font = "600 18px 'JetBrains Mono', monospace"; g.fillText(state.path.slice(0, 48), 82, 30);
      ["#ff6b6b", "#ffd166", "#4fd39b"].forEach((col, i) => { g.fillStyle = col; g.beginPath(); g.arc(20 + i * 16, 23, 5, 0, 7); g.fill(); });
      const b = state.body;
      if (!b) { g.fillStyle = "#8a90a0"; g.font = "600 26px Inter, sans-serif"; g.fillText("Kane's browser", 220, 220); }
      else if (b.kind === "type") {
        g.fillStyle = "#4b5263"; g.font = "700 26px Inter, sans-serif"; g.fillText(b.field || "Input", 60, 140);
        g.strokeStyle = "#7a5af8"; g.lineWidth = 4; g.strokeRect(60, 158, 520, 64);
        g.fillStyle = "#17181d"; g.font = "600 32px 'JetBrains Mono', monospace";
        const typed = fitTextEnd(g, b.shown + (b.caret ? "▌" : ""), 486);
        g.save(); g.beginPath(); g.rect(68, 162, 504, 54); g.clip();
        g.fillText(typed, 76, 202); g.restore();
      } else if (b.kind === "click") {
        if (b.field) { g.fillStyle = "#4b5263"; g.font = "700 24px Inter, sans-serif"; g.fillText(b.field, 60, 130); }
        g.fillStyle = b.pressed ? "#0b5e44" : "#0f7a52"; g.fillRect(140, 160, 360, 78);
        g.fillStyle = "#ffffff"; g.font = "700 28px Inter, sans-serif"; g.textAlign = "center";
        g.fillText(String(b.label).slice(0, 24), 320, 210); g.textAlign = "left";
      } else if (b.kind === "check") {
        g.fillStyle = b.result === "fail" ? "#fbe9e7" : b.result === "pass" ? "#e3f3ea" : "#ffffff"; g.fillRect(24, 64, 592, 320);
        g.fillStyle = "#23201b"; g.font = "600 23px Inter, sans-serif"; wrapText(g, b.label, 50, 108, 540, 31, 4);
        if (b.result) {
          g.fillStyle = b.result === "fail" ? "#b3261e" : "#0f7a52"; g.font = "800 96px Inter, sans-serif";
          g.fillText(b.result === "fail" ? "✗" : "✓", 50, 362);
          g.font = "800 32px Inter, sans-serif"; g.fillText(b.result === "fail" ? "Not as expected" : "As expected", 140, 336);
        }
      } else if (b.kind === "loading") {
        g.fillStyle = "#8a90a0"; g.font = "600 28px Inter, sans-serif"; g.fillText("Loading…", 250, 220);
      } else if (b.kind === "note") {
        g.fillStyle = "#4b5263"; g.font = "600 26px Inter, sans-serif"; wrapText(g, b.label, 60, 170, 520, 34, 4);
      }
      tex.needsUpdate = true;
    }
    draw();
    return { tex, state, draw, canvas: c };
  }

  function makeSign(T) {
    const c = document.createElement("canvas"); c.width = 512; c.height = 96;
    const tex = new T.CanvasTexture(c); tex.encoding = T.sRGBEncoding;
    const g = c.getContext("2d");
    return {
      tex,
      set(text) {
        g.fillStyle = "#15182a"; g.fillRect(0, 0, 512, 96);
        g.strokeStyle = "#ffd166"; g.lineWidth = 6; g.strokeRect(4, 4, 504, 88);
        g.fillStyle = "#ffd166"; g.font = "700 34px 'JetBrains Mono', monospace"; g.textAlign = "center";
        g.fillText(String(text).slice(0, 24), 256, 60);
        tex.needsUpdate = true;
      },
    };
  }

  function bubbleSprite(T) {
    const tex = canvasTex(T, 128, 96, (g) => {
      g.fillStyle = "#ffffff"; g.beginPath(); g.ellipse(64, 40, 56, 34, 0, 0, 7); g.fill();
      g.beginPath(); g.arc(30, 82, 9, 0, 7); g.fill();
      g.fillStyle = "#15182a"; g.font = "800 44px Inter, sans-serif"; g.textAlign = "center"; g.fillText("…", 64, 52);
    });
    const s = new T.Sprite(new T.SpriteMaterial({ map: tex, transparent: true, depthWrite: false }));
    s.scale.set(0.55, 0.41, 1);
    return s;
  }

  function radialTex(T, inner, outer) {
    return canvasTex(T, 128, 128, (g) => {
      const r = g.createRadialGradient(64, 64, 0, 64, 64, 64);
      r.addColorStop(0, inner); r.addColorStop(1, outer);
      g.fillStyle = r; g.fillRect(0, 0, 128, 128);
    });
  }

  // The view from the window: the sky follows the time on the viewer's own computer (dawn, day,
  // dusk, night) and the weather is picked at random each visit (clear, cloudy, rain, storm, fog).
  const SKIES = {
    dawn: ["#3b4a7a", "#f5a37a"], day: ["#5f9fd8", "#cfe6f7"], dusk: ["#2b2a5a", "#f08a5a"], night: ["#0b1022", "#24304f"],
  };
  function makeWindow(T) {
    const c = document.createElement("canvas"); c.width = 512; c.height = 640;
    const city = new T.CanvasTexture(c); city.encoding = T.sRGBEncoding;
    const g = c.getContext("2d");
    const rainCanvas = document.createElement("canvas"); rainCanvas.width = 256; rainCanvas.height = 320;
    const rain = new T.CanvasTexture(rainCanvas); rain.encoding = T.sRGBEncoding;
    const drops = Array.from({ length: 90 }, () => [Math.random() * 256, Math.random() * 320, 6 + Math.random() * 10]);
    const rg = rainCanvas.getContext("2d");
    let raining = false, heavy = false;
    return {
      city, rain,
      paint(phase, weather) {
        const w = 512, h = 640, [top, bottom] = SKIES[phase];
        const sky = g.createLinearGradient(0, 0, 0, h); sky.addColorStop(0, top); sky.addColorStop(1, bottom);
        g.fillStyle = sky; g.fillRect(0, 0, w, h);
        const overcast = weather !== "clear";
        if (!overcast || weather === "cloudy") {  // the sun or the moon, where the sky is clear enough
          const low = phase === "dawn" || phase === "dusk";
          g.fillStyle = phase === "night" ? "rgba(255,255,255,.8)" : low ? "rgba(255,200,120,.95)" : "rgba(255,248,220,.95)";
          g.beginPath(); g.arc(phase === "dusk" ? 110 : 400, low ? 230 : 70, phase === "night" ? 26 : 34, 0, 7); g.fill();
        }
        if (overcast) {  // clouds: light on a calm day, heavy and dark in a storm
          const shade = weather === "storm" ? "rgba(40,44,56,.85)" : phase === "night" ? "rgba(70,78,98,.6)" : "rgba(230,232,238,.75)";
          g.fillStyle = shade;
          for (let i = 0; i < 9; i++) { g.beginPath(); g.ellipse((i * 83) % 560, 40 + (i * 37) % 90, 90, 30, 0, 0, 7); g.fill(); }
          if (weather === "rain" || weather === "storm") { g.fillStyle = "rgba(20,24,34,.35)"; g.fillRect(0, 0, w, h); }
        }
        const lit = phase === "night" || phase === "dusk" || weather === "storm";
        for (let x = 0; x < w; x += 46) {  // the city across the street
          const bh = 190 + ((x * 37) % 260);
          g.fillStyle = phase === "day" ? "#5a6a80" : phase === "night" ? "#0e1428" : "#2a2f48"; g.fillRect(x, h - bh, 42, bh);
          for (let y = h - bh + 10; y < h - 8; y += 16) for (let wx = x + 6; wx < x + 38; wx += 10) {
            if (lit && ((wx * 13 + y * 7) % 11) < 4) { g.fillStyle = "rgba(255,210,120,.85)"; g.fillRect(wx, y, 5, 7); }
            else if (!lit && ((wx * 7 + y * 3) % 9) < 2) { g.fillStyle = "rgba(200,225,255,.5)"; g.fillRect(wx, y, 5, 7); }
          }
        }
        // the clock tower, its face lit at night
        g.fillStyle = phase === "day" ? "#5e6f88" : phase === "night" ? "#16203d" : "#2f3550";
        g.fillRect(232, 200, 60, h - 200); g.beginPath(); g.moveTo(222, 200); g.lineTo(262, 120); g.lineTo(302, 200); g.fill();
        g.fillStyle = lit ? "#ffd98a" : "#f4f1e6"; g.beginPath(); g.arc(262, 245, 22, 0, 7); g.fill();
        g.strokeStyle = "#3a2a1a"; g.lineWidth = 3; g.beginPath(); g.moveTo(262, 245); g.lineTo(262, 230); g.moveTo(262, 245); g.lineTo(274, 250); g.stroke();
        if (weather === "fog") { g.fillStyle = "rgba(205,210,220,.62)"; g.fillRect(0, 0, w, h); }
        city.needsUpdate = true;
        raining = weather === "rain" || weather === "storm"; heavy = weather === "storm";
        if (!raining) { rg.clearRect(0, 0, 256, 320); rain.needsUpdate = true; }
      },
      update(dt) {
        if (!raining) return;
        rg.clearRect(0, 0, 256, 320); rg.strokeStyle = "rgba(190,210,255,.55)"; rg.lineWidth = heavy ? 1.4 : 1;
        for (const d of drops.slice(0, heavy ? 90 : 60)) {
          d[1] += d[2] * dt * (heavy ? 60 : 40); d[0] -= dt * (heavy ? 60 : 30);
          if (d[1] > 320) { d[1] = -10; d[0] = Math.random() * 280; }
          rg.beginPath(); rg.moveTo(d[0], d[1]); rg.lineTo(d[0] - 2, d[1] + d[2]); rg.stroke();
        }
        rain.needsUpdate = true;
      },
    };
  }

  function phaseOf(date) {
    const h = date.getHours() + date.getMinutes() / 60;
    return h >= 5 && h < 7 ? "dawn" : h >= 7 && h < 17 ? "day" : h >= 17 && h < 19 ? "dusk" : "night";
  }
  // the room's mood for a time of day and a weather: window light, fill, desk lamp, blind stripes
  const MOODS = {
    night: { bg: 0x0a0d15, fogFar: 13, exposure: 0.95, hemi: [0x51618c, 0x1a120c, 0.34], sun: [0x8fb0ff, 0.45], rim: 0.6, lamp: 3.8, stripes: [0x96b4ff, 0.22] },
    dawn: { bg: 0x2a1f22, fogFar: 16, exposure: 1.0, hemi: [0xffc9a8, 0x2a1a14, 0.6], sun: [0xffc090, 1.1], rim: 0.35, lamp: 2.8, stripes: [0xffc090, 0.35] },
    day: { bg: 0x3a3632, fogFar: 22, exposure: 1.1, hemi: [0xfff4e0, 0x3a2a1c, 0.95], sun: [0xfff1d0, 1.8], rim: 0.25, lamp: 1.6, stripes: [0xfff0c0, 0.45] },
    dusk: { bg: 0x241822, fogFar: 15, exposure: 1.0, hemi: [0xffb07a, 0x2a1a10, 0.6], sun: [0xff9a5a, 1.2], rim: 0.4, lamp: 3.0, stripes: [0xffa060, 0.4] },
  };
  const WEATHER_LIGHT = { clear: 1, cloudy: 0.65, rain: 0.5, storm: 0.35, fog: 0.55 };

  function applyMood(rig, phase, weather) {
    const m = MOODS[phase], k = WEATHER_LIGHT[weather];
    rig.scene.background.setHex(m.bg); rig.scene.fog.color.setHex(m.bg); rig.scene.fog.far = m.fogFar;
    rig.renderer.toneMappingExposure = m.exposure;
    rig.hemi.color.setHex(m.hemi[0]); rig.hemi.groundColor.setHex(m.hemi[1]); rig.hemi.intensity = m.hemi[2] * (0.75 + 0.25 * k);
    rig.sun.color.setHex(m.sun[0]); rig.sunBase = m.sun[1] * k; rig.sun.intensity = rig.sunBase;
    rig.rim.intensity = m.rim; rig.lampLight.intensity = m.lamp;
    const dim = m.lamp / MOODS.night.lamp;  // the lamps matter most at night
    rig.pictureLight.intensity = 3.0 * dim; rig.doorLamp.intensity = 1.2 * dim;
    rig.halos.forEach((h) => { h.material.opacity = 0.25 + 0.5 * dim; });
    rig.blinds.material.color.setHex(m.stripes[0]); rig.blinds.material.opacity = m.stripes[1] * k * 0.85;
    rig.shaft.material.color.setHex(m.stripes[0]); rig.shaft.material.opacity = 0.18 * k;
    rig.win.paint(phase, weather);
  }

  // ── the office ────────────────────────────────────────────────────────────────────────────
  // A detective's office: teal wallpaper over dark panelling, a herringbone floor and a Persian
  // rug, a tall window on the city, the corkboard under a picture light, and the door to the app.
  // The furniture is real CC0 models from Poly Haven (credits in static/models/CREDITS.md); the
  // room, the screen, the board and the door are drawn in code because they show the real case.
  const PH = "/static/models/ph", TEX = "/static/textures";
  function buildOffice(T, canvas) {
    const renderer = new T.WebGLRenderer({ canvas, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.outputEncoding = T.sRGBEncoding;
    renderer.toneMapping = T.ACESFilmicToneMapping; renderer.toneMappingExposure = 0.95;
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = T.PCFSoftShadowMap;
    renderer.shadowMap.autoUpdate = false;  // redrawn only when something moves (see frame)
    // asking the driver for each shader's error log makes it compile them one by one (seconds on
    // some laptops); without it they compile side by side
    renderer.debug.checkShaderErrors = false;
    const scene = new T.Scene();
    scene.background = new T.Color(0x0a0d15);
    scene.fog = new T.Fog(0x0a0d15, 7, 14);
    if (T.RoomEnvironment) {  // soft image-based lighting: varnish, brass and glass catch a little light
      const pmrem = new T.PMREMGenerator(renderer);
      scene.environment = pmrem.fromScene(new T.RoomEnvironment(), 0.04).texture;
      pmrem.dispose();
    }
    const camera = new T.PerspectiveCamera(38, 16 / 7, 0.1, 40);
    camera.position.set(2.15, 2.25, 4.35);
    const focus = new T.Vector3(-0.25, 1.3, -1.45);

    // building blocks
    const loads = [];
    const std = (color, rough = 0.8, extra = {}) => new T.MeshStandardMaterial({ color, roughness: rough, metalness: 0, ...extra });
    const put = (geo, mat, x, y, z, parent = scene, rot = [0, 0, 0], shadows = true) => {
      const m = new T.Mesh(geo, mat); m.position.set(x, y, z); m.rotation.set(...rot);
      m.castShadow = m.receiveShadow = shadows; parent.add(m); return m;
    };
    const box = (w, h, d, mat, x, y, z, parent, rot) => put(new T.BoxGeometry(w, h, d), mat, x, y, z, parent, rot);
    const cyl = (rt, rb, h, mat, x, y, z, parent, rot, seg = 24) => put(new T.CylinderGeometry(rt, rb, h, seg), mat, x, y, z, parent, rot);
    const plane = (w, h, mat, x, y, z, parent, rot) => { const m = put(new T.PlaneGeometry(w, h), mat, x, y, z, parent, rot); m.castShadow = false; return m; };
    const flat = (w, h, mat, x, y, z, parent, rot) => { const m = plane(w, h, mat, x, y, z, parent, rot); m.receiveShadow = false; return m; };
    const halo = (color, size, x, y, z, opacity = 0.6, parent = scene) => {
      const s = new T.Sprite(new T.SpriteMaterial({ map: radialTex(T, "rgba(255,255,255,1)", "rgba(255,255,255,0)"), color, transparent: true, opacity, blending: T.AdditiveBlending, depthWrite: false }));
      s.scale.set(size, size, 1); s.position.set(x, y, z); parent.add(s); return s;
    };
    const gltf = new T.GLTFLoader();
    const model = (id, x, y, z, ry = 0, scale = 1, parent = scene) => loads.push(new Promise((done) => gltf.load(`${PH}/${id}/${id}_1k.gltf`, (g) => {
      const m = g.scene; m.position.set(x, y, z); m.rotation.y = ry; m.scale.setScalar(scale);
      m.traverse((o) => { if (o.isMesh) o.castShadow = o.receiveShadow = true; });
      parent.add(m); done(m);
    }, undefined, () => done(null))));  // a missing model leaves a gap, never a broken office
    const texLoader = new T.TextureLoader();
    const pbr = (name, repeat, tint = 0xffffff) => {
      const t = (kind, srgb) => {
        let done; loads.push(new Promise((ok) => { done = ok; }));
        const x = texLoader.load(`${TEX}/${name}_${kind}.jpg`, done, undefined, done);
        x.wrapS = x.wrapT = T.RepeatWrapping; x.repeat.set(...repeat); x.anisotropy = 8;
        if (srgb) x.encoding = T.sRGBEncoding;
        return x;
      };
      return new T.MeshStandardMaterial({ map: t("diff", true), normalMap: t("nor"), roughnessMap: t("rough"), color: tint });
    };
    const BRASS = std(0xc9a24e, 0.32, { metalness: 0.9 }), WALNUT = std(0x5a341f, 0.55), DARKWOOD = std(0x3a2214, 0.6);
    const WX = -1.45, WY = 2.15, BOARD = new T.Vector3(0.62, 1.85, -2.97), DX = 2.6;

    // light: the room's mood (time of day, weather) sets these; see MOODS
    const hemi = new T.HemisphereLight(0x51618c, 0x1a120c, 0.34); scene.add(hemi);
    const lampLight = new T.SpotLight(0xffcf8f, 3.8, 7, 0.9, 0.6, 1.3);
    lampLight.position.set(-1.35, 1.75, -1.25); lampLight.target.position.set(-1.1, 0.7, -0.4);
    lampLight.castShadow = true; lampLight.shadow.mapSize.set(1024, 1024); lampLight.shadow.bias = -0.0006;
    lampLight.shadow.normalBias = 0.02; lampLight.shadow.camera.near = 0.2; lampLight.shadow.camera.far = 8;
    scene.add(lampLight, lampLight.target);
    const sun = new T.DirectionalLight(0x8fb0ff, 0.45); sun.position.set(-2.2, 4, -7); sun.target.position.set(0.5, 0, 1);
    scene.add(sun, sun.target);
    const rim = new T.PointLight(0x7f9cff, 0.6, 6); rim.position.set(1.2, 2.4, -1.8); scene.add(rim);
    const glow = new T.PointLight(0xa9d0ff, 0.5, 3); glow.position.set(-1.85, 1.3, -0.55); scene.add(glow);
    const alarm = new T.PointLight(0xff3b30, 0, 7); alarm.position.set(-0.4, 2.3, -0.3); scene.add(alarm);
    const pictureLight = new T.SpotLight(0xffd9a0, 3.0, 4, 0.75, 0.6, 1.5);
    pictureLight.position.set(BOARD.x, 3.0, -2.6); pictureLight.target.position.set(BOARD.x, 1.8, -3); scene.add(pictureLight, pictureLight.target);
    const doorLamp = new T.PointLight(0xffc98a, 1.2, 3.5, 1.6); doorLamp.position.set(DX - 0.1, 2.6, -2.6); scene.add(doorLamp);

    // walls: teal paper above dark panelling with raised panels and a rail
    const wallpaper = canvasTex(T, 256, 256, (g, w, h) => {
      g.fillStyle = "#1d3a3d"; g.fillRect(0, 0, w, h);
      g.strokeStyle = "rgba(160,200,190,.07)"; g.lineWidth = 3;
      for (let x = 0; x < w; x += 64) for (let y = 0; y < h; y += 64) {
        g.beginPath(); g.moveTo(x + 32, y + 6); g.lineTo(x + 58, y + 32); g.lineTo(x + 32, y + 58); g.lineTo(x + 6, y + 32); g.closePath(); g.stroke();
      }
      g.fillStyle = "rgba(0,0,0,.12)"; for (let x = 0; x < w; x += 64) g.fillRect(x, 0, 2, h);
    });
    wallpaper.wrapS = wallpaper.wrapT = T.RepeatWrapping; wallpaper.repeat.set(6, 2);
    const wallMat = std(0xffffff, 0.9, { map: wallpaper });
    plane(10, 4.2, wallMat, 0, 2.1, -3.0);
    plane(9, 4.2, wallMat, -3.55, 2.1, 0.5, scene, [0, Math.PI / 2, 0]);
    const panelMat = pbr("dark_paneled_wood", [6, 1], 0x8a6a55), raised = pbr("dark_paneled_wood", [0.4, 0.4], 0x9a7a62);
    const rail = std(0x6b4128, 0.4);
    for (const [x0, x1] of [[-5, DX - 0.66], [DX + 0.66, 5]]) {  // the back wall's panelling, broken by the door
      const w = x1 - x0, x = (x0 + x1) / 2;
      box(w, 1.05, 0.04, panelMat, x, 0.53, -2.99); box(w, 0.07, 0.08, rail, x, 1.07, -2.95); box(w, 0.14, 0.06, DARKWOOD, x, 0.07, -2.97);
    }
    for (let x = -4.2; x < 4.4; x += 0.85) if (Math.abs(x - DX) > 0.95) box(0.66, 0.66, 0.03, raised, x, 0.52, -2.965);
    box(0.04, 1.05, 9, panelMat, -3.53, 0.53, 0.5); box(0.08, 0.07, 9, rail, -3.49, 1.07, 0.5); box(0.06, 0.14, 9, DARKWOOD, -3.51, 0.07, 0.5);
    for (let z = -2.6; z < 3; z += 0.85) box(0.03, 0.66, 0.66, raised, -3.505, 0.52, z);

    // floor: herringbone parquet; a Persian rug with a real woven surface under the desk
    plane(10, 9, pbr("herringbone_parquet", [5, 4.5], 0xb88a66), 0, 0, 0.5, scene, [-Math.PI / 2, 0, 0]);
    const rugTex = canvasTex(T, 1024, 640, (g, w, h) => {
      g.fillStyle = "#6c1d22"; g.fillRect(0, 0, w, h);
      [["#c99a4a", 22, 10], ["#1f2a44", 44, 16], ["#c99a4a", 70, 6]].forEach(([c, o, lw]) => { g.strokeStyle = c; g.lineWidth = lw; g.strokeRect(o, o, w - 2 * o, h - 2 * o); });
      g.fillStyle = "#8a2a2c"; for (let x = 70; x < w - 70; x += 36) for (let y = 70; y < h - 70; y += 36) { g.beginPath(); g.arc(x, y, 6, 0, 7); g.fill(); }
      g.fillStyle = "#c99a4a"; for (let x = 30; x < w - 20; x += 40) { g.beginPath(); g.arc(x, 33, 5, 0, 7); g.arc(x, h - 33, 5, 0, 7); g.fill(); }
      g.save(); g.translate(w / 2, h / 2); g.fillStyle = "#1f2a44";
      for (let a = 0; a < 12; a++) { g.rotate(Math.PI / 6); g.beginPath(); g.ellipse(190, 0, 60, 22, 0, 0, 7); g.fill(); }
      g.beginPath(); g.ellipse(0, 0, 230, 150, 0, 0, 7); g.fill();
      g.fillStyle = "#c99a4a"; g.beginPath(); g.ellipse(0, 0, 170, 105, 0, 0, 7); g.fill();
      g.fillStyle = "#6c1d22"; g.beginPath(); g.ellipse(0, 0, 120, 72, 0, 0, 7); g.fill();
      g.restore();
    });
    const weave = pbr("floral_jacquard", [6, 4]);  // only its normal and roughness: the feel of the weave
    plane(3.6, 2.4, new T.MeshStandardMaterial({ map: rugTex, normalMap: weave.normalMap, roughnessMap: weave.roughnessMap, normalScale: new T.Vector2(1.4, 1.4) }), -0.35, 0.012, 0.05, scene, [-Math.PI / 2, 0, 0.18]);
    plane(3.75, 2.55, std(0x2a1a2a, 0.95), -0.35, 0.006, 0.05, scene, [-Math.PI / 2, 0, 0.18]);

    // the tall window: the city (sky and weather from the mood), rain, blinds, light on the floor
    const win = makeWindow(T);
    flat(1.7, 2.1, new T.MeshBasicMaterial({ map: win.city, toneMapped: false }), WX, WY, -2.995);
    flat(1.7, 2.1, new T.MeshBasicMaterial({ map: win.rain, transparent: true, toneMapped: false }), WX, WY, -2.99);
    const flash = flat(1.7, 2.1, new T.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, toneMapped: false }), WX, WY, -2.985);
    const frameMat = std(0x2c1a10, 0.5);
    [[0, 1.08, 1.86, 0.1], [0, -1.08, 1.86, 0.12], [-0.9, 0, 0.1, 2.26], [0.9, 0, 0.1, 2.26], [0, 0, 0.06, 2.1], [0, 0.25, 1.7, 0.05]]
      .forEach(([x, y, w, h]) => box(w, h, 0.1, frameMat, WX + x, WY + y, -2.94));
    box(1.95, 0.06, 0.25, frameMat, WX, WY - 1.12, -2.86);
    for (let i = 0; i < 12; i++) box(1.72, 0.035, 0.03, std(0xd9c8a0, 0.6), WX, WY + 1.0 - i * 0.065, -2.9, scene, [0.5, 0, 0]);
    const stripes = canvasTex(T, 256, 256, (g, w, h) => {
      for (let y = 10; y < h; y += 30) {
        const b = g.createLinearGradient(0, 0, w, 0);
        b.addColorStop(0, "rgba(255,255,255,0)"); b.addColorStop(0.5, "rgba(255,255,255,.95)"); b.addColorStop(1, "rgba(255,255,255,0)");
        g.fillStyle = b; g.fillRect(10, y, w - 20, 13);
      }
    });
    const blinds = flat(2.6, 3.0, new T.MeshBasicMaterial({ map: stripes, transparent: true, opacity: 0.22, blending: T.AdditiveBlending, depthWrite: false }), -0.9, 0.014, -1.0, scene, [-Math.PI / 2, 0, 0.45]);
    const shaft = flat(1.6, 3.4, new T.MeshBasicMaterial({ map: radialTex(T, "rgba(255,255,255,.5)", "rgba(255,255,255,0)"), transparent: true, opacity: 0.18, depthWrite: false, blending: T.AdditiveBlending }), WX - 0.2, 1.4, -2.1, scene, [-0.55, 0.3, 0]);

    // a hanging plant beside the window
    const leaf = std(0x3f7a3a, 0.7), leafDark = std(0x2e5c2c, 0.7);
    const bush = (x, y, z, n, spread) => {
      for (let i = 0; i < n; i++) {
        const m = put(new T.SphereGeometry(0.07 + (i % 3) * 0.025, 8, 6), i % 2 ? leaf : leafDark,
          x + Math.sin(i * 2.3) * spread, y + Math.cos(i * 1.7) * spread * 0.6, z + Math.cos(i * 3.1) * spread * 0.5);
        m.scale.set(1.4, 0.55, 1); m.rotation.z = i;
      }
    };
    cyl(0.11, 0.08, 0.14, std(0x8a5a3a, 0.7), WX - 1.15, 3.2, -2.8); bush(WX - 1.15, 3.3, -2.8, 8, 0.14);
    cyl(0.006, 0.006, 0.95, std(0x2a2a2a, 0.5), WX - 1.15, 3.75, -2.8);  // its cord to the ceiling
    for (const [x, n] of [[WX - 1.2, 5], [WX - 1.08, 4]]) for (let i = 0; i < n; i++) bush(x + Math.sin(i) * 0.06, 3.2 - i * 0.12, -2.75, 2, 0.05);

    // the corkboard under its picture light: Kane pins the case's real evidence on the left; the
    // right-hand column is the board's own furniture (a header, a street map, three status lights)
    box(2.25, 1.5, 0.06, std(0x5a361f, 0.45), BOARD.x, BOARD.y, BOARD.z);
    const cork = canvasTex(T, 512, 340, (g, w, h) => {
      g.fillStyle = "#a9784a"; g.fillRect(0, 0, w, h);
      for (let i = 0; i < 5000; i++) { g.fillStyle = i % 2 ? "rgba(70,40,15,.25)" : "rgba(255,235,205,.13)"; g.fillRect((i * 97) % w, (i * 61) % h, 2, 2); }
    });
    plane(2.1, 1.36, std(0xffffff, 0.95, { map: cork }), BOARD.x, BOARD.y, BOARD.z + 0.035);
    const decor = (w, h, paint, x, y, rz, tint) => {
      const t = canvasTex(T, Math.round(w * 600), Math.round(h * 600), (g, cw, ch) => { g.fillStyle = tint; g.fillRect(0, 0, cw, ch); paint(g, cw, ch); });
      plane(w, h, std(0xffffff, 0.85, { map: t }), BOARD.x + x, BOARD.y + y, BOARD.z + 0.045, scene, [0, 0, rz]);
      put(new T.SphereGeometry(0.018, 10, 8), std(0xc62828, 0.4), BOARD.x + x, BOARD.y + y + h / 2 - 0.03, BOARD.z + 0.06);
    };
    decor(0.42, 0.15, (g) => { g.fillStyle = "#23201b"; g.font = "800 38px 'Courier New', monospace"; g.fillText("CASE FILE", 16, 60); }, 0.78, 0.5, 0.04, "#f3e6c4");
    decor(0.4, 0.32, (g, w, h) => {
      g.strokeStyle = "#9a8f74"; g.lineWidth = 6;
      for (let i = 0; i < 8; i++) { g.beginPath(); g.moveTo(0, i * 30 + 10); g.lineTo(w, i * 30 + 40); g.stroke(); g.beginPath(); g.moveTo(i * 40, 0); g.lineTo(i * 40 + 30, h); g.stroke(); }
      g.strokeStyle = "#c62828"; g.lineWidth = 9; g.beginPath(); g.arc(150, 110, 24, 0, 7); g.stroke();
    }, 0.8, 0.05, -0.04, "#e9e1c8");
    [0x2fb67c, 0xf0b23a, 0x8a8f9c].forEach((c, i) => put(new T.SphereGeometry(0.035, 12, 10), std(c, 0.4, { emissive: c, emissiveIntensity: i < 2 ? 0.6 : 0 }), BOARD.x + 0.7 + i * 0.09, BOARD.y - 0.5, BOARD.z + 0.06));
    box(0.06, 0.06, 0.25, BRASS, BOARD.x, BOARD.y + 0.85, -2.86);
    cyl(0.07, 0.07, 0.55, BRASS, BOARD.x, BOARD.y + 0.83, -2.74, scene, [0, 0, Math.PI / 2]);
    const boardHalo = halo(0xffd9a0, 0.9, BOARD.x, BOARD.y + 0.78, -2.72, 0.5);
    const pinned = new T.Group(); scene.add(pinned);
    const SLOTS = [[-0.72, 0.3], [-0.22, 0.32], [0.28, 0.29], [-0.72, -0.22], [-0.22, -0.2], [0.28, -0.23]];
    const board = {
      cards: [],
      add(tex) {
        const slot = this.cards.length % 6, [x, y] = SLOTS[slot];
        if (this.cards.length >= 6) pinned.remove(this.cards[slot].group);  // a full board: the oldest card makes room
        const group = new T.Group();
        group.position.set(BOARD.x + x, BOARD.y + y, BOARD.z + 0.05 + this.cards.length * 0.0005);
        group.rotation.z = [0.05, -0.04, 0.03, -0.06, 0.04, -0.03][slot];
        const card = new T.Mesh(new T.PlaneGeometry(0.42, 0.31), new T.MeshStandardMaterial({ map: tex, roughness: 0.9 }));
        const pin = new T.Mesh(new T.SphereGeometry(0.022, 10, 8), std(0xc62828, 0.4)); pin.position.set(0, 0.13, 0.015);
        group.add(card, pin); pinned.add(group);
        this.cards[slot] = { group, pin };
        // red string from the last card to this one
        const prev = this.last, here = new T.Vector3(); pin.getWorldPosition(here);
        if (prev) {
          const mid = prev.clone().add(here).multiplyScalar(0.5); mid.y -= 0.06; mid.z += 0.01;
          const curve = new T.QuadraticBezierCurve3(prev, mid, here);
          pinned.add(new T.Line(new T.BufferGeometry().setFromPoints(curve.getPoints(16)), new T.LineBasicMaterial({ color: 0xd32f2f })));
        }
        this.last = here;
      },
    };

    // the wall clock: it keeps this computer's time
    const clockFace = canvasTex(T, 256, 256, (g) => {
      g.fillStyle = "#f3eee5"; g.beginPath(); g.arc(128, 128, 122, 0, 7); g.fill();
      g.fillStyle = "#23201b";
      for (let i = 0; i < 60; i++) { const a = i * Math.PI / 30; g.beginPath(); g.arc(128 + Math.sin(a) * 112, 128 - Math.cos(a) * 112, i % 5 ? 2 : 3.5, 0, 7); g.fill(); }
      g.font = "700 30px Georgia, serif"; g.textAlign = "center"; g.textBaseline = "middle";
      for (let n = 1; n <= 12; n++) { const a = n * Math.PI / 6; g.fillText(String(n), 128 + Math.sin(a) * 88, 130 - Math.cos(a) * 88); }
    });
    const CLOCK = new T.Vector3(1.75, 3.15, -2.97);
    // every layer at its own depth: two faces at the same depth flicker (z-fighting)
    cyl(0.3, 0.3, 0.05, std(0x3a2214, 0.4), CLOCK.x, CLOCK.y, CLOCK.z - 0.005, scene, [Math.PI / 2, 0, 0], 40);
    put(new T.TorusGeometry(0.285, 0.022, 10, 48), BRASS, CLOCK.x, CLOCK.y, CLOCK.z + 0.025, scene, [0, 0, 0], false);
    put(new T.CircleGeometry(0.26, 40), new T.MeshBasicMaterial({ map: clockFace }), CLOCK.x, CLOCK.y, CLOCK.z + 0.035, scene, [0, 0, 0], false);
    const hands = new T.Group(); hands.position.set(CLOCK.x, CLOCK.y, CLOCK.z + 0.045); scene.add(hands);
    const hourHand = new T.Mesh(new T.BoxGeometry(0.025, 0.13, 0.01), std(0x23201b)); hourHand.position.y = 0.06;
    const minHand = new T.Mesh(new T.BoxGeometry(0.016, 0.2, 0.01), std(0x23201b)); minHand.position.y = 0.09;
    const hourPivot = new T.Group(); hourPivot.add(hourHand); const minPivot = new T.Group(); minPivot.add(minHand);
    hands.add(hourPivot, minPivot);

    // the door to the app's next page: it opens on a lit corridor; the sign shows the real page
    box(0.1, 2.3, 0.12, DARKWOOD, DX - 0.6, 1.15, -2.95); box(0.1, 2.3, 0.12, DARKWOOD, DX + 0.6, 1.15, -2.95);
    box(1.3, 0.12, 0.12, DARKWOOD, DX, 2.32, -2.95);
    flat(1.1, 2.26, new T.MeshBasicMaterial({ color: 0xfff0c8, toneMapped: false }), DX, 1.13, -2.992);
    const doorLight = new T.PointLight(0xffd9a0, 0, 5, 1.6); doorLight.position.set(DX, 1.3, -2.55); scene.add(doorLight);
    const hinge = new T.Group(); hinge.position.set(DX - 0.535, 0, -2.93); scene.add(hinge);
    const doorWood = std(0x6b3f22, 0.45);
    box(1.06, 2.24, 0.06, doorWood, 0.535, 1.12, 0, hinge);
    box(0.6, 0.9, 0.02, std(0xd8c7a0, 0.25, { transparent: true, opacity: 0.88, emissive: 0x4a3a1c }), 0.535, 1.55, 0.035, hinge);
    box(0.7, 0.55, 0.02, std(0x5e361d, 0.45), 0.535, 0.55, 0.035, hinge);
    box(0.04, 0.2, 0.04, BRASS, 0.935, 1.05, 0.05, hinge); put(new T.SphereGeometry(0.04, 12, 10), BRASS, 0.935, 1.0, 0.07, hinge);
    const sign = makeSign(T); sign.set("the scene");
    flat(1.15, 0.22, new T.MeshBasicMaterial({ map: sign.tex, toneMapped: false }), DX, 2.55, -2.9, scene, [0, 0, 0.03]);
    cyl(0.05, 0.08, 0.14, BRASS, DX + 0.85, 2.15, -2.92); halo(0xffc98a, 0.6, DX + 0.85, 2.15, -2.86, 0.6);

    // the glass cabinet on the left wall, a picture above it
    model("vintage_cabinet_01", -3.2, 0, 0.9, Math.PI / 2);
    model("hanging_picture_frame_01", -3.5, 3.0, 0.9, Math.PI / 2);

    // the desk: a steel office desk, turned to the camera, with the computer (the window into the
    // user's app), a brass banker's lamp, books, a notebook, a mug and a pot of pens
    const station = new T.Group(); station.position.set(-1.55, 0, -0.85); station.rotation.y = Math.PI / 4; scene.add(station);
    model("metal_office_desk", 0, 0, 0, 0, 1, station);
    model("stationery_supplies", 0.86, 0.86, -0.12, 0.4, 1.2, station);
    const TOP = 0.79;  // the desk's top
    const screen = makeScreen(T);
    const mon = new T.Group(); mon.position.set(-0.45, 0, 0); mon.rotation.y = 0.35; station.add(mon);
    const plastic = std(0x1c1f27, 0.35, { metalness: 0.3 });
    box(1.2, 0.76, 0.06, plastic, 0.05, TOP + 0.48, -0.3, mon);
    flat(1.1, 0.68, new T.MeshBasicMaterial({ map: screen.tex, toneMapped: false }), 0.05, TOP + 0.48, -0.265, mon);
    box(0.08, 0.36, 0.08, plastic, 0.05, TOP + 0.16, -0.33, mon); box(0.4, 0.02, 0.22, plastic, 0.05, TOP + 0.01, -0.33, mon);
    box(0.72, 0.03, 0.26, std(0x2c2f3a, 0.5), 0.05, TOP + 0.02, 0.14, mon);
    cyl(0.11, 0.13, 0.04, BRASS, 0.62, TOP + 0.02, -0.3, station); cyl(0.015, 0.015, 0.6, BRASS, 0.62, TOP + 0.33, -0.3, station);
    cyl(0.015, 0.015, 0.36, BRASS, 0.5, TOP + 0.64, -0.3, station, [0, 0, 1.1]);
    put(new T.SphereGeometry(0.16, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2.2), std(0xc9a24e, 0.3, { metalness: 0.9, side: T.DoubleSide }), 0.34, TOP + 0.74, -0.28, station, [0.2, 0, 0.5]);
    put(new T.SphereGeometry(0.045, 12, 10), new T.MeshBasicMaterial({ color: 0xfff1c8, toneMapped: false }), 0.32, TOP + 0.68, -0.27, station);
    const lampHalo = halo(0xffcf8f, 1.3, 0.32, TOP + 0.68, -0.27, 0.75, station);
    [[0x6e1f22, 0.06], [0x1f3a5f, 0.05], [0x7a6a2a, 0.045]].forEach(([c, h], i) => box(0.36, h, 0.26, std(c, 0.6), 0.6, TOP + 0.03 + i * 0.055, 0.2, station, [0, 0.1 * i, 0]));
    const note = canvasTex(T, 300, 220, (g) => {
      g.fillStyle = "#f4ecd8"; g.fillRect(0, 0, 300, 220); g.strokeStyle = "#b3261e"; g.lineWidth = 3;
      for (let i = 0; i < 5; i++) { g.strokeRect(20, 22 + i * 38, 18, 18); g.fillStyle = "#7a7363"; g.fillRect(50, 28 + i * 38, 180 - i * 18, 6); }
    });
    plane(0.42, 0.3, std(0xffffff, 0.8, { map: note }), -0.25, TOP + 0.011, 0.3, station, [-Math.PI / 2, 0, 0.3]);
    cyl(0.006, 0.006, 0.18, std(0x1a1a1a, 0.3, { metalness: 0.6 }), -0.05, TOP + 0.015, 0.36, station, [Math.PI / 2, 0, 1.2]);
    const mugTex = canvasTex(T, 256, 128, (g) => {
      g.fillStyle = "#f3eee5"; g.fillRect(0, 0, 256, 128); g.fillStyle = "#4a2f20"; g.fillRect(96, 30, 64, 12);
      g.beginPath(); g.ellipse(128, 32, 50, 9, 0, 0, 7); g.fill(); g.fillStyle = "#15171d"; g.beginPath(); g.arc(110, 62, 11, 0, 7); g.arc(146, 62, 11, 0, 7); g.fill();
    });
    cyl(0.055, 0.05, 0.13, std(0xffffff, 0.4, { map: mugTex }), 0.78, TOP + 0.065, 0.28, station);
    put(new T.TorusGeometry(0.035, 0.01, 8, 16), std(0xf3eee5, 0.4), 0.84, TOP + 0.065, 0.28, station);
    for (let i = 0; i < 4; i++) halo(0xffffff, 0.12 + i * 0.05, 0.78 + Math.sin(i * 2) * 0.02, TOP + 0.19 + i * 0.07, 0.28, 0.12, station);

    // the leather armchair in front of the computer: Kane pulls it out, sits, slides in
    const CHAIR = new T.Vector3(-1.09, 0, -0.46), SEAT_YAW = Math.PI / 4 + Math.PI;  // facing the computer
    const chair = new T.Group(); chair.position.copy(CHAIR); chair.rotation.y = SEAT_YAW; scene.add(chair);
    model("modern_arm_chair_01", 0, 0, 0, 0, 1, chair);

    // a side table in front with the evidence tray, and a big plant by the door
    const side = new T.Group(); side.position.set(-1.25, 0, 2.0); side.rotation.y = 0.35; scene.add(side);
    box(1.0, 0.06, 0.6, WALNUT, 0, 0.62, 0, side); box(0.9, 0.6, 0.5, DARKWOOD, 0, 0.3, 0, side);
    box(0.6, 0.16, 0.36, std(0x6a3d22, 0.5), 0.05, 0.73, 0, side);
    const tag = canvasTex(T, 256, 64, (g) => { g.fillStyle = "#c9a24e"; g.fillRect(0, 0, 256, 64); g.fillStyle = "#2a1a0e"; g.font = "800 36px Georgia, serif"; g.textAlign = "center"; g.fillText("EVIDENCE", 128, 46); });
    plane(0.32, 0.08, std(0xffffff, 0.4, { metalness: 0.6, map: tag }), 0.05, 0.73, 0.185, side);
    for (let i = 0; i < 5; i++) box(0.5, 0.005, 0.3, std([0xf3eee5, 0xe9dfc8, 0xd6e3ff, 0xf3eee5, 0xc9b88a][i], 0.8), 0.05, 0.82 + i * 0.012, -0.02 + i * 0.008, side, [0.3 - i * 0.05, 0, 0]);
    model("potted_plant_02", 2.7, 0, 1.3, 0.6, 1.35);

    // soft contact shadows under the furniture, and one that follows Kane
    const blobTex = radialTex(T, "rgba(0,0,0,.55)", "rgba(0,0,0,0)");
    const blob = (w, d, x, z, ry = 0, parent = scene) => {
      const m = new T.Mesh(new T.PlaneGeometry(w, d), new T.MeshBasicMaterial({ map: blobTex, transparent: true, depthWrite: false }));
      m.rotation.x = -Math.PI / 2; m.rotation.z = ry; m.position.set(x, 0.016, z); parent.add(m); return m;
    };
    blob(2.5, 1.4, -1.55, -0.85, Math.PI / 4);
    blob(1.0, 1.1, 0, 0, 0, chair).position.y = 0.016;
    blob(0.9, 2.3, -3.2, 0.9);
    blob(1.0, 1.0, 2.7, 1.3);
    blob(1.2, 0.8, -1.25, 2.0, -0.35);
    const kaneShadow = blob(0.9, 0.9, 0, 0);

    // Kane's spots. He starts to the right of the desk, three-quarters to you.
    const DESK = new T.Vector3(-0.38, 0, -0.12), YOU = -0.55;
    const DOOR = new T.Vector3(DX, 0, -2.25), INSIDE = new T.Vector3(DX, 0, -2.85);  // inside the room, in the doorway
    const PIN_SPOT = new T.Vector3(BOARD.x - 0.2, 0, -2.3);
    // seated, the robot's hips sit 0.29 up and 0.24 behind its feet: lift and shift it onto the cushion
    const SEAT = new T.Vector3(CHAIR.x + 0.24 * Math.sin(SEAT_YAW), 0.3, CHAIR.z + 0.24 * Math.cos(SEAT_YAW));
    const AWAY = new T.Vector3(-Math.sin(SEAT_YAW), 0, -Math.cos(SEAT_YAW));      // away from the desk
    const ALONG = new T.Vector3(AWAY.z, 0, -AWAY.x);                               // along the desk, room side
    const PULL = 0.9;                                                              // the armchair is deep
    const OUT = CHAIR.clone().addScaledVector(AWAY, PULL);                         // the chair pulled out
    const SIDE = OUT.clone().addScaledVector(ALONG, 0.8);                          // beside it
    const STAND = OUT.clone().addScaledVector(AWAY, -0.8);                         // between the desk and the pulled-out chair
    const STEP_IN = STAND.clone().addScaledVector(ALONG, 0.8);                     // the same gap, from the side
    const SEAT_OUT = SEAT.clone().addScaledVector(AWAY, PULL);                     // seated, before sliding in
    return {
      renderer, scene, camera, focus, screen, sign, hinge, doorLight, alarm, win, board, kaneShadow, loads,
      hemi, sun, rim, lampLight, pictureLight, doorLamp, halos: [boardHalo, lampHalo], blinds, shaft, flash,
      clock: { hourPivot, minPivot }, DESK, DOOR, INSIDE, CHAIR, SEAT, SEAT_YAW, chair, OUT, SIDE, STAND, STEP_IN, SEAT_OUT, PIN_SPOT, YOU, yaw: YOU,
    };
  }

  // ── Detective Kane: the CC0 robot, recoloured, with a fedora and a magnifying glass ───────
  async function loadKane(T, rig) {
    const gltf = await new Promise((resolve, reject) => new T.GLTFLoader().load(MODEL, resolve, undefined, reject));
    const model = gltf.scene;
    const box = new T.Box3().setFromObject(model);
    model.scale.setScalar(1.72 / (box.max.y - box.min.y));
    const colours = { Main: 0xcdb48a, Grey: 0x384055, Black: 0x15171d };
    model.traverse((o) => {
      if (!o.isMesh) return;
      o.castShadow = true; o.receiveShadow = true;
      const m = o.material;
      if (m && colours[m.name] !== undefined) { m.color.setHex(colours[m.name]); m.roughness = 0.55; m.metalness = 0.15; }
    });
    model.position.copy(rig.DESK); model.rotation.y = rig.YOU;
    rig.scene.add(model);

    const mixer = new T.AnimationMixer(model);
    const clips = {};
    gltf.animations.forEach((c) => { clips[c.name] = mixer.clipAction(c); });
    ["No", "Yes", "Punch", "ThumbsUp", "Wave"].forEach((n) => { if (clips[n]) { clips[n].setLoop(T.LoopOnce, 1); clips[n].clampWhenFinished = true; } });
    clips.Idle.play();
    mixer.update(0);
    model.updateMatrixWorld(true);

    const find = (re) => { let hit = null; model.traverse((o) => { if (!hit && o.isBone && re.test(o.name)) hit = o; }); return hit; };
    // the loader renames duplicate node names (the model has a 'Head' bone and a 'Head' mesh group)
    const headBone = find(/^Head(?!_?end)/i), headEnd = headBone, palm = find(/^Palm2\.?R/) || find(/LowerArm\.?R/);
    // the head is several meshes (all carrying the face expressions); measure and animate them together
    const headMeshes = [];
    model.traverse((o) => { if (o.isMesh && o.morphTargetDictionary && "Surprised" in o.morphTargetDictionary) headMeshes.push(o); });

    // the fedora, sized in world units, then fixed to the head so it moves with it
    const hat = new T.Group();
    const felt = new T.MeshStandardMaterial({ color: 0x6b4630, roughness: 0.75 });
    const brim = new T.Mesh(new T.CylinderGeometry(0.36, 0.36, 0.025, 36), felt);
    const crown = new T.Mesh(new T.CylinderGeometry(0.2, 0.235, 0.22, 32), felt); crown.position.y = 0.12;
    const band = new T.Mesh(new T.CylinderGeometry(0.237, 0.237, 0.055, 32), new T.MeshStandardMaterial({ color: 0x1a120c, roughness: 0.6 })); band.position.y = 0.04;
    const dent = new T.Mesh(new T.BoxGeometry(0.2, 0.03, 0.2), felt); dent.position.y = 0.23;
    [brim, crown, band, dent].forEach((m) => { m.castShadow = true; hat.add(m); });
    if (headMeshes.length && (headBone || headEnd)) {
      // sized and placed from the whole head's real bounds (this robot has a big round head)
      const hb = new T.Box3(), size = new T.Vector3(), mid = new T.Vector3();
      headMeshes.forEach((m) => hb.expandByObject(m));
      hb.getSize(size); hb.getCenter(mid);
      const k = Math.max(size.x, size.z) / 0.8;  // the hat was drawn for a 0.8-wide head
      hat.scale.setScalar(k);
      hat.position.set(mid.x, hb.max.y - 0.14 * k, mid.z); hat.rotation.set(-0.1, model.rotation.y, 0.06);
      rig.scene.add(hat); (headBone || headEnd).attach(hat);
      // the red scarf: a wrap round the neck and two tails, tied to the torso so they move with him
      const torso = find(/^Torso/);
      if (torso) {
        const wool = new T.MeshStandardMaterial({ color: 0x7a1a22, roughness: 0.85 }), wool2 = new T.MeshStandardMaterial({ color: 0x8a2028, roughness: 0.85 });
        const neck = new T.Vector3(mid.x, hb.min.y + 0.02, mid.z), yaw = model.rotation.y;
        const wrap = new T.Mesh(new T.TorusGeometry(0.21 * k * 0.9, 0.06, 10, 28), wool); wrap.position.copy(neck); wrap.rotation.x = Math.PI / 2;
        const tail = new T.Mesh(new T.BoxGeometry(0.13, 0.42, 0.04), wool); tail.position.set(neck.x, neck.y - 0.22, neck.z);
        tail.rotation.y = yaw; tail.translateZ(-0.19); tail.translateX(0.08); tail.rotation.z = 0.15;
        const tail2 = new T.Mesh(new T.BoxGeometry(0.12, 0.3, 0.04), wool2); tail2.position.set(neck.x, neck.y - 0.16, neck.z);
        tail2.rotation.y = yaw; tail2.translateZ(-0.2); tail2.translateX(-0.07); tail2.rotation.z = -0.1;
        [wrap, tail, tail2].forEach((m) => { m.castShadow = true; rig.scene.add(m); torso.attach(m); });
      }
    }
    // the magnifying glass in his right hand
    const lens = new T.Group();
    const ring = new T.Mesh(new T.TorusGeometry(0.07, 0.014, 10, 26), new T.MeshStandardMaterial({ color: 0xd9b45a, roughness: 0.3, metalness: 0.8 }));
    const glass = new T.Mesh(new T.CircleGeometry(0.065, 24), new T.MeshStandardMaterial({ color: 0xbfe3ff, transparent: true, opacity: 0.45, roughness: 0.05 }));
    const handle = new T.Mesh(new T.CylinderGeometry(0.014, 0.017, 0.13), new T.MeshStandardMaterial({ color: 0x2b1b12, roughness: 0.6 })); handle.position.y = -0.135;
    lens.add(ring, glass, handle);
    if (palm) {
      const at = new T.Vector3(); palm.getWorldPosition(at);
      lens.scale.setScalar(1.9); lens.position.copy(at).add(new T.Vector3(0, 0.22, 0)); lens.rotation.y = model.rotation.y;
      rig.scene.add(lens); palm.attach(lens);
    }
    const bubble = bubbleSprite(T); bubble.position.set(0.32, 2.2, 0); rig.scene.add(bubble); bubble.visible = false;

    let base = clips.Idle, oneShot = null;
    mixer.addEventListener("finished", (e) => {
      if (e.action !== oneShot) return;
      base.reset().fadeIn(0.3).play(); oneShot.fadeOut(0.3); oneShot = null;
    });
    return {
      model, mixer, bubble,
      loop(name) {
        const next = clips[name];
        if (!next || next === base) return;
        next.reset().fadeIn(0.25).play();
        if (!oneShot) base.fadeOut(0.25);
        base = next;
      },
      play(name) {
        const a = clips[name];
        if (!a) return;
        if (oneShot) oneShot.fadeOut(0.1);
        a.reset().fadeIn(0.15).play(); base.fadeOut(0.15); oneShot = a;
      },
      // a one-off move whose last pose is kept (sitting down, standing up)
      hold(name) {
        const a = clips[name];
        if (!a || a === base) return;
        a.reset(); a.setLoop(T.LoopOnce, 1); a.clampWhenFinished = true;
        a.fadeIn(0.15).play();
        if (oneShot) { oneShot.fadeOut(0.1); oneShot = null; }
        base.fadeOut(0.15); base = a;
      },
      face(name, amount) {
        headMeshes.forEach((m) => {
          const i = m.morphTargetDictionary[name];
          if (i !== undefined) m.morphTargetInfluences[i] = amount;
        });
      },
    };
  }

  // ── evidence cards for the corkboard: always the case's real text ─────────────────────────
  function cardTex(T, { title, body, mark, hand }) {
    return canvasTex(T, 336, 248, (g, w, h) => {
      g.fillStyle = "#fffcf2"; g.fillRect(0, 0, w, h);
      g.fillStyle = "#6f6a62"; g.font = "700 15px 'JetBrains Mono', monospace"; g.fillText(String(title).toUpperCase(), 16, 28);
      if (mark) {
        g.fillStyle = mark === "fail" ? "#b3261e" : "#0f7a52"; g.font = "800 46px Inter, sans-serif";
        g.fillText(mark === "fail" ? "✗" : "✓", w - 52, 46);
      }
      g.fillStyle = hand ? "#1f3a8a" : "#23201b";
      g.font = hand ? "600 25px Caveat, cursive" : "600 17px Inter, sans-serif";
      wrapText(g, body, 16, hand ? 62 : 60, w - 32, hand ? 28 : 23, hand ? 6 : 7);
    });
  }

  // ── actions: each real step becomes a short script of moves ──────────────────────────────
  // A move: { dur (seconds), enter(), run(k) with k from 0 to 1 }.
  const move = (dur, run = () => {}, enter = () => {}) => ({ dur, run, enter });

  // ── finding the way: A* on a coarse floor grid around the furniture ───────────────────────
  // Following the game-ai skill: one route per walk (never every frame), octile heuristic with
  // √2 diagonals, no cutting across obstacle corners, a cap on the search, then line-of-sight
  // smoothing so the route is a few straight legs. Furniture is grown by Kane's radius; the chair
  // is read where it actually is, tucked in or pulled out.
  const NAV = { x0: -3.2, x1: 3.4, z0: -2.95, z1: 3.0, step: 0.1, radius: 0.3, chair: 0.42 };
  function makeNav(rig) {
    const R = NAV.radius;
    const boxes = [  // footprints: centre, half sizes, turn (as set in buildOffice)
      { cx: -1.55, cz: -0.85, hx: 1.0, hz: 0.48, a: Math.PI / 4 },   // desk
      { cx: -3.2, cz: 0.9, hx: 1.01, hz: 0.34, a: Math.PI / 2 },     // glass cabinet
      { cx: -1.25, cz: 2.0, hx: 0.5, hz: 0.3, a: 0.35 },             // side table
    ];
    const plants = [{ cx: 2.7, cz: 1.3, r: 0.42 }];
    const door = rig.DOOR.x;
    const blocked = (x, z) => {
      if (z < -2.7 && Math.abs(x - door) > 0.35) return true;       // the back wall, except the doorway
      if (x < NAV.x0 || x > NAV.x1 || z < NAV.z0 || z > NAV.z1) return true;
      for (const b of boxes) {
        const dx = x - b.cx, dz = z - b.cz, c = Math.cos(b.a), sn = Math.sin(b.a);
        if (Math.abs(dx * c - dz * sn) < b.hx + R && Math.abs(dx * sn + dz * c) < b.hz + R) return true;
      }
      for (const c of plants) if ((x - c.cx) ** 2 + (z - c.cz) ** 2 < (c.r + R) ** 2) return true;
      const ch = rig.chair.position;
      return (x - ch.x) ** 2 + (z - ch.z) ** 2 < (NAV.chair + R) ** 2;
    };
    const cols = Math.round((NAV.x1 - NAV.x0) / NAV.step) + 1, rows = Math.round((NAV.z1 - NAV.z0) / NAV.step) + 1;
    const cellX = (i) => NAV.x0 + (i % cols) * NAV.step, cellZ = (i) => NAV.z0 + Math.floor(i / cols) * NAV.step;
    const cellOf = (x, z) => Math.min(rows - 1, Math.max(0, Math.round((z - NAV.z0) / NAV.step))) * cols
                           + Math.min(cols - 1, Math.max(0, Math.round((x - NAV.x0) / NAV.step)));
    const free = (i) => !blocked(cellX(i), cellZ(i));
    const nearestFree = (i) => {  // a start or goal inside a grown footprint: the closest free cell
      if (free(i)) return i;
      const c0 = i % cols, r0 = Math.floor(i / cols);
      for (let d = 1; d < 15; d++)
        for (let dr = -d; dr <= d; dr++) for (let dc = -d; dc <= d; dc++) {
          if (Math.max(Math.abs(dr), Math.abs(dc)) !== d) continue;
          const r = r0 + dr, c = c0 + dc;
          if (r >= 0 && r < rows && c >= 0 && c < cols && free(r * cols + c)) return r * cols + c;
        }
      return i;
    };
    function search(s, g, useHeuristic = true) {
      const gx = g % cols, gz = Math.floor(g / cols);
      const h = (i) => {
        if (!useHeuristic) return 0;
        const dx = Math.abs(i % cols - gx), dz = Math.abs(Math.floor(i / cols) - gz);
        return (dx + dz + (Math.SQRT2 - 2) * Math.min(dx, dz)) * NAV.step;  // octile
      };
      const cost = new Map([[s, 0]]), came = new Map(), heap = [[h(s), s]], closed = new Set();
      const push = (item) => { heap.push(item); let i = heap.length - 1; while (i && heap[(i - 1) >> 1][0] > heap[i][0]) { [heap[i], heap[(i - 1) >> 1]] = [heap[(i - 1) >> 1], heap[i]]; i = (i - 1) >> 1; } };
      const pop = () => { const top = heap[0], last = heap.pop(); if (heap.length) { heap[0] = last; let i = 0;
        for (;;) { const l = 2 * i + 1, r = l + 1; let m = i; if (l < heap.length && heap[l][0] < heap[m][0]) m = l; if (r < heap.length && heap[r][0] < heap[m][0]) m = r; if (m === i) break; [heap[i], heap[m]] = [heap[m], heap[i]]; i = m; } } return top; };
      let expanded = 0;
      while (heap.length && expanded < 25000) {
        const [, i] = pop();
        if (closed.has(i)) continue;
        if (i === g) break;
        closed.add(i); expanded++;
        const c = i % cols, r = Math.floor(i / cols);
        for (let dr = -1; dr <= 1; dr++) for (let dc = -1; dc <= 1; dc++) {
          if (!dr && !dc) continue;
          const nr = r + dr, nc = c + dc;
          if (nr < 0 || nr >= rows || nc < 0 || nc >= cols) continue;
          const n = nr * cols + nc;
          if (!free(n)) continue;
          if (dr && dc && (!free(r * cols + nc) || !free(nr * cols + c))) continue;  // no corner cutting
          const next = cost.get(i) + (dr && dc ? Math.SQRT2 : 1) * NAV.step;
          if (next < (cost.has(n) ? cost.get(n) : Infinity)) { cost.set(n, next); came.set(n, i); push([next + h(n), n]); }
        }
      }
      if (!cost.has(g)) return null;
      const cells = [g];
      while (cells[0] !== s) cells.unshift(came.get(cells[0]));
      return { cells, cost: cost.get(g) };
    }
    const clear = (a, b) => {  // a straight leg with nothing in the way
      const n = Math.ceil(a.distanceTo(b) / 0.05);
      for (let k = 1; k < n; k++) if (blocked(a.x + (b.x - a.x) * k / n, a.z + (b.z - a.z) * k / n)) return false;
      return true;
    };
    return {
      blocked, search,
      cellOf, nearestFree, cols, rows,
      route(from, to) {
        const T = window.THREE;
        const s = nearestFree(cellOf(from.x, from.z)), g = nearestFree(cellOf(to.x, to.z));
        const found = search(s, g);
        if (!found) return [from.clone(), to.clone()];  // nowhere to go round: walk straight
        const pts = found.cells.map((i) => new T.Vector3(cellX(i), 0, cellZ(i)));
        const smooth = [pts[0]];
        for (let i = 0; i < pts.length - 1;) {  // keep the farthest point still in plain sight
          let j = pts.length - 1;
          while (j > i + 1 && !clear(pts[i], pts[j])) j--;
          smooth.push(pts[j]); i = j;
        }
        return [from.clone(), ...smooth, to.clone()].filter((p, k, all) => !k || p.distanceTo(all[k - 1]) > 0.02);
      },
    };
  }

  // walk to a spot along the route the navigator finds (direct: a short step in a tight spot)
  function walkTo(rig, kane, target, direct = false) {
    let pts = [], lengths = [0], total = 0;
    return {
      get dur() { return total ? Math.max(0.35, total / 1.3) : 0.35; },
      enter() {
        const from = kane.model.position.clone(); from.y = 0;
        pts = direct ? [from, target.clone()] : rig.nav.route(from, target);
        lengths = [0];
        for (let i = 1; i < pts.length; i++) lengths.push(lengths[i - 1] + pts[i].distanceTo(pts[i - 1]));
        total = lengths[lengths.length - 1];
        kane.loop("Walking"); rig.seated = false;
      },
      run(k) {
        if (!total) return;
        const d = k * total;
        let i = 0;
        while (i < pts.length - 2 && lengths[i + 1] < d) i++;
        const leg = lengths[i + 1] - lengths[i] || 1, t = Math.min(1, (d - lengths[i]) / leg);
        kane.model.position.lerpVectors(pts[i], pts[i + 1], t);
        rig.yaw = Math.atan2(pts[i + 1].x - pts[i].x, pts[i + 1].z - pts[i].z);  // he turns smoothly into each leg
      },
    };
  }
  const faceChair = (rig) => { rig.yaw = Math.atan2(rig.OUT.x - rig.SIDE.x, rig.OUT.z - rig.SIDE.z); };
  const slideChair = (rig, kane, from, to, withKane) => move(0.6, (k) => {
    rig.chair.position.lerpVectors(from, to, k);
    if (withKane) kane.model.position.lerpVectors(withKane[0], withKane[1], k);
  }, () => { if (!withKane) { kane.loop("Idle"); faceChair(rig); } });
  const sitAtDesk = (rig, kane) => [
    walkTo(rig, kane, rig.SIDE),
    slideChair(rig, kane, rig.CHAIR, rig.OUT),                                 // pull the chair out
    walkTo(rig, kane, rig.STEP_IN, true),                                      // in between chair and desk
    walkTo(rig, kane, rig.STAND, true),
    move(0.5, (k) => kane.model.position.lerpVectors(rig.STAND, rig.SEAT_OUT, k),
      () => { rig.yaw = rig.SEAT_YAW; kane.model.rotation.y = rig.SEAT_YAW; kane.hold("Sitting"); rig.seated = true; }),
    slideChair(rig, kane, rig.OUT, rig.CHAIR, [rig.SEAT_OUT, rig.SEAT]),        // slide in to the desk
  ];
  const getUp = (rig, kane) => [
    slideChair(rig, kane, rig.CHAIR, rig.OUT, [rig.SEAT, rig.SEAT_OUT]),        // slide back from the desk
    move(0.45, (k) => kane.model.position.lerpVectors(rig.SEAT_OUT, rig.STAND, k),
      () => { kane.hold("Standing"); rig.seated = false; }),
    walkTo(rig, kane, rig.STEP_IN, true),
    walkTo(rig, kane, rig.SIDE, true),
    slideChair(rig, kane, rig.OUT, rig.CHAIR),                                 // push the chair back in
  ];
  const pinCard = (rig, kane, tex) => {
    let pinned = false;
    return move(1.0, (k) => { if (!pinned && k > 0.45) { pinned = true; rig.board.add(tex); } },
      () => { rig.yaw = Math.PI; kane.model.rotation.y = Math.PI; kane.loop("Idle"); kane.play("Punch"); });  // he presses the pin in
  };
  const toBoardAndBack = (rig, kane, tex) => [
    walkTo(rig, kane, rig.PIN_SPOT), pinCard(rig, kane, tex), ...sitAtDesk(rig, kane),
  ];

  function plan(rig, kane, step) {
    const a = parseStep(step), S = rig.screen, T = window.THREE;
    if (a.action === "go") {
      // at the computer: the address bar types the page, it loads, the door's sign shows where he is
      return [move(1.5, (k) => {
        const typed = a.label.slice(0, Math.ceil(a.label.length * Math.min(1, k / 0.55)));
        if (S.state.path !== typed || (k > 0.95 && S.state.body)) {
          S.state.path = typed; S.state.body = k < 0.95 ? { kind: "loading" } : null; S.draw();
        }
        if (k > 0.95 && !a.signed) { a.signed = true; rig.sign.set(a.label); }
      })];
    }
    if (a.action === "type") {
      return [move(2.0, (k) => {
        const shown = a.value.slice(0, Math.ceil(a.value.length * Math.min(1, k / 0.8)));
        const b = S.state.body;
        if (b && (b.shown !== shown || b.caret !== k < 1)) { b.shown = shown; b.caret = k < 1; S.draw(); }
      }, () => { S.state.body = { kind: "type", field: a.field, shown: "", caret: true }; S.draw(); })];
    }
    if (a.action === "click") {
      return [move(1.1, (k) => {
        const b = S.state.body, pressed = k > 0.3 && k < 0.65;
        if (b && b.pressed !== pressed) { b.pressed = pressed; S.draw(); }
      }, () => { S.state.body = { kind: "click", label: a.label, field: a.field, pressed: false }; S.draw(); })];
    }
    if (a.action === "check") {
      // the result on screen; he stands, turns to you to nod or shake his head, then pins it up
      const tex = cardTex(T, { title: a.failed ? "Clue: not as expected" : "Checked", body: a.label, mark: a.failed ? "fail" : "pass" });
      return [
        move(1.1, (k) => {
          const b = S.state.body;
          if (b && !b.result && k > 0.5) { b.result = a.failed ? "fail" : "pass"; S.draw(); if (a.failed) rig.alarmUntil = performance.now() + 2200; }
        }, () => { S.state.body = { kind: "check", label: a.label, result: null }; S.draw(); }),
        ...(rig.seated ? getUp(rig, kane) : []),
        move(1.8, (k) => { if (k >= 1) kane.face("Surprised", 0); },
          () => { rig.yaw = rig.YOU; kane.play(a.failed ? "No" : "Yes"); if (a.failed) kane.face("Surprised", 1); }),
        ...toBoardAndBack(rig, kane, tex),
      ];
    }
    return [move(0.6)];
  }

  // ── while he waits on Claude (or the case is closed): a small errand away from the desk ─────
  // Never while his real browser is working; the frame loop drops the errand the moment a real
  // step arrives, and he walks back and sits down first.
  const ERRANDS = [
    { at: [-1.45, -2.45], look: [-1.45, -3] },               // watches the rain at the window
    { at: [0.42, -2.3], look: [0.42, -3], then: "Yes" },     // studies the corkboard, nods
    { at: [-0.4, 1.7], look: [-1.25, 2.0] },                 // looks over the evidence tray
    { at: [1.6, -2.2], look: [1.75, -3], then: "No" },       // checks the clock, shakes his head
  ];
  function errand(rig, kane, e) {
    const T = window.THREE, spot = new T.Vector3(e.at[0], 0, e.at[1]);
    let gestured = false;
    const away = [
      walkTo(rig, kane, spot),
      move(3.2, (k) => { if (e.then && !gestured && k > 0.45) { gestured = true; kane.play(e.then); } },
        () => { rig.yaw = Math.atan2(e.look[0] - e.at[0], e.look[1] - e.at[1]); kane.loop("Idle"); }),
    ];
    away.forEach((m) => (m.errand = true));
    return [...getUp(rig, kane), ...away, ...sitAtDesk(rig, kane)];
  }

  // the case opens: Kane comes in through the door, pins the witness statement, sits at the computer
  function entrance(rig, kane, statement) {
    const T = window.THREE;
    const tex = cardTex(T, { title: "Witness statement", body: statement || "(the user's report)", hand: true });
    const door = (k) => { rig.hinge.rotation.y = k * 1.35; rig.doorLight.intensity = k * 1.8; };
    return [
      move(0.6, door, () => { kane.model.position.copy(rig.INSIDE); kane.model.visible = true; rig.yaw = 0; kane.model.rotation.y = 0; rig.seated = false; }),
      walkTo(rig, kane, rig.DOOR),
      move(1.7, (k) => door(1 - Math.min(1, k * 3)), () => { rig.yaw = rig.YOU; kane.loop("Idle"); kane.play("Wave"); }),
      walkTo(rig, kane, rig.PIN_SPOT), pinCard(rig, kane, tex), ...sitAtDesk(rig, kane),
    ];
  }

  // ── wiring it to the page ─────────────────────────────────────────────────────────────────
  async function init(stage) {
    if (stage.dataset.ready || typeof loadThree !== "function") return;
    if (kaneView() === "simple") { stage.dataset.ready = "simple"; return; }
    stage.dataset.ready = "loading";
    const canvas = stage.querySelector(".kane3d-canvas");
    let rig, kane;
    try {
      await loadEngine();
      if (document.fonts) await Promise.all(["600 25px Caveat", "600 17px Inter"].map((f) => document.fonts.load(f).catch(() => {})));
      rig = buildOffice(window.THREE, canvas);
      kane = await loadKane(window.THREE, rig);
      await Promise.race([Promise.all(rig.loads), new Promise((ok) => setTimeout(ok, 15000))]);
      // compile every shader now, hidden things included (Kane before his entrance), so the
      // scene never stops for a compile once it is on screen
      const hidden = [];
      rig.scene.traverse((o) => { if (!o.visible) { hidden.push(o); o.visible = true; } });
      rig.renderer.compile(rig.scene, rig.camera);
      hidden.forEach((o) => (o.visible = false));
    } catch (e) {
      stage.dataset.ready = "";  // no WebGL or no model: keep the 2D detective
      return;
    }
    stage.classList.add("ready");
    stage.dataset.ready = "1";
    rig.nav = makeNav(rig);
    stage.kaneNav = rig.nav;  // for checking the routes from the page (see tests)
    const T = window.THREE;
    const cameraViews = [
      { label: "Office", position: new T.Vector3(2.15, 2.25, 4.35), focus: new T.Vector3(-0.25, 1.3, -1.45) },
      { label: "Desk", position: new T.Vector3(0.55, 1.75, 1.9), focus: new T.Vector3(-1.55, 1.05, -0.85) },
      { label: "Evidence", position: new T.Vector3(1.35, 1.9, 1.3), focus: new T.Vector3(0.55, 1.8, -2.97) },
    ];
    let cameraAt = Math.max(0, cameraViews.findIndex((view) => view.label === stage.dataset.camera));
    stage.dataset.camera = cameraViews[cameraAt].label;
    stage.kaneCameraNext = () => {
      cameraAt = (cameraAt + 1) % cameraViews.length;
      stage.dataset.camera = cameraViews[cameraAt].label;
      return stage.dataset.camera;
    };
    rig.scene.traverse((o) => {
      for (const m of [].concat(o.material || [])) if (m.isMeshStandardMaterial) m.envMapIntensity = m.metalness > 0.5 ? 0.5 : 0.08;
    });

    // "Kane's screen": the same picture as the 3D monitor, readable even with Kane sitting in front of it
    const hud = document.createElement("div");
    hud.className = "kane3d-screen";
    hud.innerHTML = "<span>Kane's screen</span>";
    hud.append(rig.screen.canvas);
    stage.append(hud);

    const fit = () => {
      const w = canvas.clientWidth, h = canvas.clientHeight;
      if (!w || !h) return;
      rig.renderer.setSize(w, h, false); rig.camera.aspect = w / h; rig.camera.updateProjectionMatrix();
    };
    fit();

    // the time of day follows this computer's clock; the weather is a surprise each visit
    const weather = ["clear", "clear", "cloudy", "rain", "rain", "storm", "fog"][Math.floor(Math.random() * 7)];
    const label = document.createElement("div"); label.className = "kane3d-time"; stage.append(label);
    const WEATHER_ICON = { clear: "☀", cloudy: "☁", rain: "🌧", storm: "⛈", fog: "🌫" };
    let phase = null;
    const tickMood = () => {
      const d = new Date(), now = phaseOf(d);
      if (now !== phase) { phase = now; applyMood(rig, phase, weather); }
      const icon = weather === "clear" && phase === "night" ? "☾" : WEATHER_ICON[weather];
      label.textContent = `${d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} · ${phase} · ${icon} ${weather}`;
    };
    tickMood();
    setInterval(() => { if (canvas.isConnected) tickMood(); }, 20000);
    let nextFlash = performance.now() + 4000;
    new ResizeObserver(fit).observe(canvas);

    // the case so far: a fresh case gets Kane's entrance; one already under way shows him at work,
    // with the statement and the checks he has already made pinned up
    const statement = (document.querySelector("#live .complaint")?.textContent || "").trim();
    const sofar = trackerSteps();
    const script = [];
    if (sofar.total === 0) {
      kane.model.visible = false;
      script.push(...entrance(rig, kane, statement));
    } else {
      rig.board.add(cardTex(T, { title: "Witness statement", body: statement, hand: true }));
      sofar.steps.filter((st) => st.kind === "check" || st.kind === "look").forEach((st) => {
        const a = parseStep(st);
        rig.board.add(cardTex(T, { title: a.failed ? "Clue: not as expected" : "Checked", body: a.label, mark: a.failed ? "fail" : "pass" }));
      });
      const go = sofar.steps.filter((st) => st.kind === "go").pop();
      if (go) { const a = parseStep(go); rig.sign.set(a.label); rig.screen.state.path = a.label; rig.screen.draw(); }
      kane.model.position.copy(rig.SEAT); rig.yaw = rig.SEAT_YAW; kane.model.rotation.y = rig.SEAT_YAW;
      kane.hold("Sitting"); rig.seated = true;
    }

    let seen = sofar.total, current = null, last = performance.now(), lastDraw = 0, rainAt = 0, shadowTick = 0;
    let idleFor = 0, restFor = 4, lastErrand = -1;  // the first errand soon: Claude often plans quickly
    // real work comes first: drop what is left of an errand (he still walks back and sits down)
    const cutErrand = () => {
      for (let i = script.length - 1; i >= 0; i--) if (script[i].errand) script.splice(i, 1);
      if (current?.errand) current = null;
    };
    const update = () => {
      const now = trackerSteps();
      if (now.total > seen) {
        cutErrand();
        now.steps.slice(-(now.total - seen)).forEach((st) => script.push({ step: st })); seen = now.total;
      }
    };
    document.addEventListener("kane:update", update);
    // what he is doing, for checking from the page (see tests)
    stage.kaneNow = () => ({ seated: !!rig.seated, errand: !!current?.errand || script.some((x) => x.errand),
      x: +kane.model.position.x.toFixed(2), z: +kane.model.position.z.toFixed(2),
      screen: rig.screen.state.body?.label || rig.screen.state.body?.kind || "" });

    // Kane's real browser on the 3D screen, whenever the live camera is filming it
    let misses = 0;
    const pollLive = () => {
      if (!canvas.isConnected) return;
      const liveSrc = stage.dataset.liveSrc;
      if (!liveSrc) { setTimeout(pollLive, 1500); return; }
      const img = new Image();
      img.onload = () => { misses = 0; rig.screen.state.live = img; rig.screen.draw(); setTimeout(pollLive, 1000); };
      img.onerror = () => {
        misses += 1;
        if (rig.screen.state.live) { rig.screen.state.live = null; rig.screen.draw(); }
        setTimeout(pollLive, misses > 3 ? 5000 : 1500);  // no camera: check now and then, quietly
      };
      img.src = `${liveSrc}?t=${Date.now()}`;
    };
    pollLive();

    // the next move: queued steps are expanded into their moves as they come up
    const nextMove = () => {
      while (script.length) {
        const item = script.shift();
        if (item.step) { script.unshift(...plan(rig, kane, item.step)); continue; }
        item.enter(); item.t = 0;
        return item;
      }
      return null;
    };

    const frame = (now) => {
      if (!canvas.isConnected) { document.removeEventListener("kane:update", update); rig.renderer.dispose(); return; }
      requestAnimationFrame(frame);
      // full speed (up to 60 a second) while Kane or the camera moves, 30 while he sits and
      // works, none when the tab is hidden
      const settling = rig.camera.position.distanceToSquared(cameraViews[cameraAt].position) > 1e-4;
      if (document.hidden || now - lastDraw < (current || settling ? 15 : 30)) return;
      const dt = Math.min(0.1, (now - last) / 1000); last = now; lastDraw = now;
      const backlog = script.filter((x) => x.step).length;
      const speed = backlog > 2 ? 2.2 : backlog ? 1.4 : 1;  // catch up when Kane is quick
      const mode = document.querySelector("#live .scene-live")?.dataset.mode || "idle";
      if (mode === "walking" && (current?.errand || script.some((x) => x.errand))) cutErrand();
      if (current || script.length) idleFor = 0;
      else if ((idleFor += dt) > restFor && rig.seated && kane.model.visible && mode !== "walking") {
        let pick; do pick = Math.floor(Math.random() * ERRANDS.length); while (pick === lastErrand);
        lastErrand = pick; idleFor = 0; restFor = 8 + Math.random() * 7;
        script.push(...errand(rig, kane, ERRANDS[pick]));
      }
      if (!current) current = nextMove();
      kane.mixer.update(dt * (current ? speed : 1));
      if (current) {
        current.t += dt * speed;
        const k = Math.min(1, current.t / current.dur);
        current.run(k);
        if (k >= 1) current = null;
      }
      if (!rig.seated || !current) {  // turn smoothly toward where he means to face
        const turn = Math.atan2(Math.sin(rig.yaw - kane.model.rotation.y), Math.cos(rig.yaw - kane.model.rotation.y));
        kane.model.rotation.y += turn * Math.min(1, dt * 7);
      }
      kane.bubble.visible = !current && (trackerSteps().thinking || mode === "reading");
      const head = kane.model.position;
      kane.bubble.position.set(head.x + 0.3, (rig.seated ? 1.85 : 2.2) + Math.sin(now / 300) * 0.03, head.z);
      // between real steps the screen says what is really going on: which part Claude is doing, or
      // that Kane's real browser is starting (a step's own result stays up until the next step)
      const chapter = document.querySelector("#live .game-chapter")?.textContent || "";
      const note = mode === "reading"
        ? (/repair/i.test(chapter) ? "Claude is repairing the code…" : /evidence|verdict/i.test(chapter)
          ? "Claude is checking my evidence…" : "Claude is writing my orders…")
        : mode === "walking" && trackerSteps().total === 0 ? "Opening a real Chrome browser…" : null;
      const shown = rig.screen.state.body;
      if (!current && note && shown?.label !== note && (mode === "reading" || !shown || shown.kind === "note")) {
        rig.screen.state.body = { kind: "note", label: note }; rig.screen.draw();
      }
      if (now - rainAt > 100) { rig.win.update(Math.min(0.2, (now - rainAt) / 1000)); rainAt = now; }
      if (weather === "storm" && now > nextFlash) { rig.flashAt = now; nextFlash = now + 6000 + Math.random() * 9000; }
      const f = rig.flashAt ? Math.max(0, 1 - (now - rig.flashAt) / 260) * (Math.sin((now - rig.flashAt) / 40) > -0.3 ? 1 : 0.3) : 0;
      rig.flash.material.opacity = f * 0.85; rig.sun.intensity = rig.sunBase + f * 4;
      rig.kaneShadow.visible = kane.model.visible;
      rig.kaneShadow.position.set(kane.model.position.x, 0.009, kane.model.position.z);
      const d = new Date();
      rig.clock.minPivot.rotation.z = -d.getMinutes() / 60 * Math.PI * 2;
      rig.clock.hourPivot.rotation.z = -((d.getHours() % 12) + d.getMinutes() / 60) / 12 * Math.PI * 2;
      rig.alarm.intensity = rig.alarmUntil && now < rig.alarmUntil ? 2.2 + Math.sin(now / 70) * 1.2 : 0;
      const view = cameraViews[cameraAt], ease = Math.min(1, dt * 3.2);
      rig.camera.position.x += (view.position.x - rig.camera.position.x) * ease;
      rig.camera.position.y += (view.position.y - rig.camera.position.y) * ease;
      rig.camera.position.z += (view.position.z - rig.camera.position.z) * ease;
      rig.focus.lerp(view.focus, ease);
      rig.camera.lookAt(rig.focus);
      if (current || ++shadowTick % 10 === 0) rig.renderer.shadowMap.needsUpdate = true;
      rig.renderer.render(rig.scene, rig.camera);
    };
    requestAnimationFrame(frame);
  }

  // the same Detective Kane for the 3D reconstruction of finished cases (recon.js)
  window.kaneRobot = { loadEngine, loadKane };
  window.initKane3d = (root) => (root || document).querySelectorAll("[data-kane3d]").forEach(init);
  window.initKane3d();
})();

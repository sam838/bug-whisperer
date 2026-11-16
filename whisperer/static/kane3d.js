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
// recoloured with a fedora and a magnifying glass: an AI detective. The office is built in code.
// three.js loads only on a live case; reduced motion or no WebGL keeps the 2D detective.

(function () {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const GLTF_LOADER = "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js";
  const MODEL = "/static/models/RobotExpressive.glb";
  const PATH_RE = /https?:\/\/[^\s]+/;

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = src; s.onload = resolve; s.onerror = () => reject(new Error(`couldn't load ${src}`));
      document.head.append(s);
    });
  }
  async function loadEngine() {
    await loadThree();  // from recon.js
    if (!window.THREE.GLTFLoader) await loadScript(GLTF_LOADER);
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

  function makeScreen(T) {
    const c = document.createElement("canvas"); c.width = 640; c.height = 400;
    const tex = new T.CanvasTexture(c); tex.encoding = T.sRGBEncoding;
    const g = c.getContext("2d");
    const state = { path: "about:blank", body: null };
    function draw() {
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
        g.fillStyle = "#17181d"; g.font = "600 32px 'JetBrains Mono', monospace"; g.fillText(b.shown + (b.caret ? "▌" : ""), 76, 202);
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
    return { tex, state, draw };
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

  // the night outside the window: a city skyline with lit windows, and rain drawn every frame
  function makeWindow(T) {
    const city = canvasTex(T, 512, 384, (g, w, h) => {
      const sky = g.createLinearGradient(0, 0, 0, h); sky.addColorStop(0, "#0b1022"); sky.addColorStop(1, "#24304f");
      g.fillStyle = sky; g.fillRect(0, 0, w, h);
      g.fillStyle = "rgba(255,255,255,.75)"; g.beginPath(); g.arc(400, 70, 26, 0, 7); g.fill();
      for (let x = 0; x < w; x += 46) {
        const bh = 110 + ((x * 37) % 170);
        g.fillStyle = "#0e1428"; g.fillRect(x, h - bh, 42, bh);
        for (let y = h - bh + 10; y < h - 8; y += 16) for (let wx = x + 6; wx < x + 38; wx += 10) {
          if (((wx * 13 + y * 7) % 11) < 4) { g.fillStyle = "rgba(255,210,120,.85)"; g.fillRect(wx, y, 5, 7); }
        }
      }
    });
    const rainCanvas = document.createElement("canvas"); rainCanvas.width = 256; rainCanvas.height = 192;
    const rain = new T.CanvasTexture(rainCanvas);
    const drops = Array.from({ length: 70 }, () => [Math.random() * 256, Math.random() * 192, 6 + Math.random() * 10]);
    const rg = rainCanvas.getContext("2d");
    return {
      city, rain,
      update(dt) {
        rg.clearRect(0, 0, 256, 192); rg.strokeStyle = "rgba(190,210,255,.55)"; rg.lineWidth = 1;
        for (const d of drops) {
          d[1] += d[2] * dt * 40; d[0] -= dt * 30;
          if (d[1] > 192) { d[1] = -10; d[0] = Math.random() * 280; }
          rg.beginPath(); rg.moveTo(d[0], d[1]); rg.lineTo(d[0] - 2, d[1] + d[2]); rg.stroke();
        }
        rain.needsUpdate = true;
      },
    };
  }

  // ── the office ────────────────────────────────────────────────────────────────────────────
  function buildOffice(T, canvas) {
    const renderer = new T.WebGLRenderer({ canvas, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.outputEncoding = T.sRGBEncoding;
    renderer.toneMapping = T.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.05;
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = T.PCFSoftShadowMap;
    const scene = new T.Scene();
    scene.background = new T.Color(0x0d1018);
    scene.fog = new T.Fog(0x0d1018, 7, 14);
    const camera = new T.PerspectiveCamera(36, 16 / 7, 0.1, 40);
    camera.position.set(0.9, 1.95, 3.7);
    const focus = new T.Vector3(-0.65, 1.12, -0.95);

    const std = (color, rough = 0.8, extra = {}) => new T.MeshStandardMaterial({ color, roughness: rough, metalness: 0, ...extra });
    const add = (mesh, x, y, z, { cast = true, receive = true, ry = 0 } = {}) => {
      mesh.position.set(x, y, z); mesh.rotation.y = ry; mesh.castShadow = cast; mesh.receiveShadow = receive; scene.add(mesh); return mesh;
    };

    // light: a dim blue night, a warm desk lamp with shadows, moonlight through the window
    scene.add(new T.HemisphereLight(0x5a6c99, 0x1a120c, 0.55));
    const lampLight = new T.SpotLight(0xffc98a, 3.2, 9, 0.95, 0.65, 1.4);
    lampLight.position.set(-1.25, 2.0, -0.35); lampLight.target.position.set(-0.6, 0.6, -0.4);
    lampLight.castShadow = true; lampLight.shadow.mapSize.set(1024, 1024); lampLight.shadow.bias = -0.0008;
    scene.add(lampLight, lampLight.target);
    const moon = new T.DirectionalLight(0x8fb0ff, 0.45); moon.position.set(-1.8, 3, -6); scene.add(moon);
    const rim = new T.PointLight(0x7f9cff, 0.6, 6); rim.position.set(1.2, 2.4, -1.8); scene.add(rim);
    const glow = new T.PointLight(0xa9d0ff, 0.5, 3); glow.position.set(-1.25, 1.5, -0.55); scene.add(glow);
    const alarm = new T.PointLight(0xff3b30, 0, 7); alarm.position.set(-0.4, 2.3, -0.3); scene.add(alarm);

    // floor (planks), walls, skirting
    const planks = canvasTex(T, 512, 512, (g, w) => {
      for (let i = 0; i < 8; i++) {
        g.fillStyle = ["#4a3324", "#523928", "#47301f", "#4e3626"][i % 4]; g.fillRect(0, i * 64, w, 64);
        g.fillStyle = "rgba(0,0,0,.35)"; g.fillRect(0, i * 64, w, 2); g.fillRect(((i * 173) % w), i * 64, 2, 64);
      }
    });
    planks.wrapS = planks.wrapT = T.RepeatWrapping; planks.repeat.set(3, 3);
    const floor = add(new T.Mesh(new T.PlaneGeometry(10, 9), std(0xffffff, 0.85, { map: planks })), 0, 0, 0.5, { cast: false });
    floor.rotation.x = -Math.PI / 2;
    const wallMat = std(0x1d2436, 0.95);
    add(new T.Mesh(new T.BoxGeometry(10, 4, 0.1), wallMat), 0, 2, -3.05, { cast: false });
    add(new T.Mesh(new T.BoxGeometry(0.1, 4, 9), wallMat), -3.55, 2, 0.5, { cast: false });
    add(new T.Mesh(new T.BoxGeometry(10, 0.14, 0.04), std(0x2b2116)), 0, 0.07, -2.99, { cast: false });
    add(new T.Mesh(new T.BoxGeometry(0.04, 0.14, 9), std(0x2b2116)), -3.49, 0.07, 0.5, { cast: false });

    // a rug under the desk
    const rugTex = canvasTex(T, 512, 320, (g, w, h) => {
      g.fillStyle = "#6b1f24"; g.fillRect(0, 0, w, h);
      g.strokeStyle = "#c79b4a"; g.lineWidth = 10; g.strokeRect(18, 18, w - 36, h - 36);
      g.strokeStyle = "#3d1215"; g.lineWidth = 4; g.strokeRect(40, 40, w - 80, h - 80);
      g.fillStyle = "#c79b4a"; for (let i = 0; i < 6; i++) { g.beginPath(); g.arc(90 + i * 66, h / 2, 14, 0, 7); g.fill(); }
    });
    const rug = add(new T.Mesh(new T.PlaneGeometry(3.2, 2.0), std(0xffffff, 1, { map: rugTex })), -0.8, 0.006, -0.3, { cast: false });
    rug.rotation.x = -Math.PI / 2; rug.rotation.z = 0.12;

    // the window with blinds, the city and the rain
    const win = makeWindow(T);
    add(new T.Mesh(new T.PlaneGeometry(1.5, 1.15), new T.MeshBasicMaterial({ map: win.city })), -2.1, 2.05, -2.99, { cast: false, receive: false });
    add(new T.Mesh(new T.PlaneGeometry(1.5, 1.15), new T.MeshBasicMaterial({ map: win.rain, transparent: true })), -2.1, 2.05, -2.985, { cast: false, receive: false });
    const frameMat = std(0x3b2a1b, 0.7);
    [[0, 0.62, 1.62, 0.08], [0, -0.62, 1.62, 0.08], [-0.79, 0, 0.08, 1.3], [0.79, 0, 0.08, 1.3], [0, 0, 0.05, 1.2]].forEach(([x, y, w, h]) =>
      add(new T.Mesh(new T.BoxGeometry(w, h, 0.08), frameMat), -2.1 + x, 2.05 + y, -2.96));
    for (let i = 0; i < 5; i++) add(new T.Mesh(new T.BoxGeometry(1.52, 0.035, 0.03), std(0xb9a37f, 0.6)), -2.1, 2.5 - i * 0.1, -2.93);

    // the bookshelf on the left wall
    const shelf = new T.Group(); shelf.position.set(-3.3, 0, 1.1); shelf.rotation.y = Math.PI / 2; scene.add(shelf);
    const wood = std(0x4f3322, 0.75);
    const back = new T.Mesh(new T.BoxGeometry(1.4, 2.0, 0.04), wood); back.position.set(0, 1.0, -0.2); back.receiveShadow = true; shelf.add(back);
    [-0.68, 0.68].forEach((x) => { const s = new T.Mesh(new T.BoxGeometry(0.04, 2.0, 0.4), wood); s.position.set(x, 1.0, 0); s.castShadow = s.receiveShadow = true; shelf.add(s); });
    const spines = [0x8c2f2f, 0x2f5d8c, 0x7a6a2a, 0x2f6b4f, 0x5b3a6e, 0x9a5a28, 0x1f3a5f];
    for (let row = 0; row < 4; row++) {
      const plank = new T.Mesh(new T.BoxGeometry(1.36, 0.04, 0.38), wood); plank.position.set(0, 0.1 + row * 0.48, 0); plank.receiveShadow = true; shelf.add(plank);
      let x = -0.62, n = 0;
      while (x < 0.55) {
        const bw = 0.05 + ((n * 7 + row * 3) % 3) * 0.02, bh = 0.28 + ((n * 5 + row) % 4) * 0.035;
        const book = new T.Mesh(new T.BoxGeometry(bw, bh, 0.26), std(spines[(n + row * 2) % spines.length], 0.7));
        book.position.set(x + bw / 2, 0.12 + row * 0.48 + bh / 2, 0.02); book.castShadow = true; shelf.add(book);
        x += bw + 0.008; n += 1;
      }
    }

    // a filing cabinet and a wall clock
    add(new T.Mesh(new T.BoxGeometry(0.6, 1.3, 0.6), std(0x56606e, 0.5, { metalness: 0.4 })), 2.75, 0.65, -2.6);
    for (let i = 0; i < 3; i++) add(new T.Mesh(new T.BoxGeometry(0.2, 0.03, 0.03), std(0xc9c9c9, 0.3, { metalness: 0.8 })), 2.75, 1.1 - i * 0.38, -2.29);
    const clockFace = canvasTex(T, 256, 256, (g) => {
      g.fillStyle = "#f3eee5"; g.beginPath(); g.arc(128, 128, 120, 0, 7); g.fill();
      g.strokeStyle = "#23201b"; g.lineWidth = 10; g.stroke();
      for (let i = 0; i < 12; i++) { const a = i * Math.PI / 6; g.fillStyle = "#23201b"; g.fillRect(128 + Math.sin(a) * 95 - 3, 128 - Math.cos(a) * 95 - 8, 6, 16); }
    });
    add(new T.Mesh(new T.CylinderGeometry(0.28, 0.28, 0.05, 32), std(0x3b2a1b, 0.6)), 0.25, 2.75, -2.97, { cast: false }).rotation.x = Math.PI / 2;
    add(new T.Mesh(new T.CircleGeometry(0.25, 32), new T.MeshBasicMaterial({ map: clockFace })), 0.25, 2.75, -2.94, { cast: false, receive: false });
    const hands = new T.Group(); hands.position.set(0.25, 2.75, -2.93); scene.add(hands);
    const hourHand = new T.Mesh(new T.BoxGeometry(0.025, 0.13, 0.01), std(0x23201b)); hourHand.position.y = 0.06;
    const minHand = new T.Mesh(new T.BoxGeometry(0.018, 0.2, 0.01), std(0x23201b)); minHand.position.y = 0.09;
    const hourPivot = new T.Group(); hourPivot.add(hourHand); const minPivot = new T.Group(); minPivot.add(minHand);
    hands.add(hourPivot, minPivot);

    // desk, chair, lamp and the computer (the window into the user's app), turned to the camera
    const station = new T.Group(); station.position.set(-1.55, 0, -0.85); station.rotation.y = Math.PI / 4; scene.add(station);
    const part = (geo, mat, x, y, z) => { const m = new T.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = m.receiveShadow = true; station.add(m); return m; };
    const deskWood = std(0x6b4630, 0.6);
    part(new T.BoxGeometry(1.9, 0.07, 1.0), deskWood, 0, 0.9, 0);
    part(new T.BoxGeometry(0.5, 0.82, 0.95), deskWood, -0.68, 0.45, 0);  // drawers
    part(new T.BoxGeometry(0.06, 0.86, 0.06), deskWood, 0.88, 0.43, 0.44);
    part(new T.BoxGeometry(0.06, 0.86, 0.06), deskWood, 0.88, 0.43, -0.44);
    for (let i = 0; i < 3; i++) part(new T.BoxGeometry(0.12, 0.02, 0.02), std(0xd9b45a, 0.3, { metalness: 0.7 }), -0.68, 0.72 - i * 0.26, 0.49);
    const screen = makeScreen(T);
    part(new T.BoxGeometry(1.24, 0.8, 0.06), std(0x1c1f27, 0.4), 0.05, 1.42, -0.3);
    const display = new T.Mesh(new T.PlaneGeometry(1.14, 0.71), new T.MeshBasicMaterial({ map: screen.tex, toneMapped: false }));
    display.position.set(0.05, 1.42, -0.265); station.add(display);
    part(new T.BoxGeometry(0.08, 0.36, 0.08), std(0x1c1f27, 0.4), 0.05, 1.1, -0.32);
    part(new T.BoxGeometry(0.4, 0.02, 0.22), std(0x1c1f27, 0.4), 0.05, 0.94, -0.32);
    part(new T.BoxGeometry(0.72, 0.03, 0.26), std(0x2c2f3a, 0.5), 0.05, 0.95, 0.15);
    part(new T.CylinderGeometry(0.05, 0.045, 0.12, 16), std(0xf3eee5, 0.5), 0.75, 0.99, 0.25);  // coffee mug
    part(new T.BoxGeometry(0.34, 0.03, 0.44), std(0xe9dfc8, 0.9), -0.55, 0.95, 0.12);           // case folder
    part(new T.CylinderGeometry(0.12, 0.14, 0.04, 20), std(0x2f6b4f, 0.4, { metalness: 0.5 }), -0.72, 0.95, -0.25);  // lamp base
    part(new T.CylinderGeometry(0.018, 0.018, 0.7), std(0x8a8a8a, 0.3, { metalness: 0.8 }), -0.72, 1.3, -0.25);
    const shade = part(new T.ConeGeometry(0.2, 0.22, 24, 1, true), std(0x2f6b4f, 0.4, { metalness: 0.4, side: T.DoubleSide }), -0.62, 1.66, -0.18);
    shade.rotation.z = -0.5;
    const chairMat = std(0x3a2418, 0.6);
    const chair = new T.Group(); chair.position.set(-2.35, 0, 0.0); chair.rotation.y = Math.PI / 4 + 1.2; scene.add(chair);
    [[0, 0.5, 0, 0.55, 0.07, 0.55], [0, 0.85, -0.25, 0.55, 0.65, 0.06]].forEach(([x, y, z, w, h, d]) => { const m = new T.Mesh(new T.BoxGeometry(w, h, d), chairMat); m.position.set(x, y, z); m.castShadow = true; chair.add(m); });
    [[-0.24, -0.24], [0.24, -0.24], [-0.24, 0.24], [0.24, 0.24]].forEach(([x, z]) => { const m = new T.Mesh(new T.BoxGeometry(0.05, 0.5, 0.05), chairMat); m.position.set(x, 0.25, z); m.castShadow = true; chair.add(m); });

    // the door to the app's next page, with its sign
    add(new T.Mesh(new T.BoxGeometry(1.2, 2.2, 0.1), std(0x2b1d12, 0.7)), 1.45, 1.1, -2.98);
    const hinge = new T.Group(); hinge.position.set(0.9, 0, -2.9); scene.add(hinge);
    const door = new T.Mesh(new T.BoxGeometry(1.05, 2.08, 0.06), std(0x6e4a2c, 0.65)); door.position.set(0.53, 1.04, 0); door.castShadow = true; hinge.add(door);
    const pane = new T.Mesh(new T.PlaneGeometry(0.62, 0.5), std(0xd9cfa8, 0.2, { transparent: true, opacity: 0.85, emissive: 0x3a3320 }));
    pane.position.set(0.53, 1.55, 0.035); hinge.add(pane);
    const knob = new T.Mesh(new T.SphereGeometry(0.045, 12, 10), std(0xd9b45a, 0.25, { metalness: 0.9 })); knob.position.set(0.92, 1.0, 0.06); hinge.add(knob);
    const sign = makeSign(T); sign.set("the scene");
    add(new T.Mesh(new T.PlaneGeometry(1.3, 0.24), new T.MeshBasicMaterial({ map: sign.tex, toneMapped: false })), 1.45, 2.42, -2.95, { cast: false, receive: false });

    // Kane stands to the right of the desk: turned three-quarters to you, he turns to the screen to act
    const DESK = new T.Vector3(-0.38, 0, -0.12), DOOR = new T.Vector3(1.45, 0, -2.25);
    const FACE = Math.atan2(-1.73 - DESK.x, -1.03 - DESK.z);  // toward the screen
    const YOU = -0.55;                                          // three-quarters toward the camera
    return { renderer, scene, camera, focus, screen, sign, hinge, alarm, win, clock: { hourPivot, minPivot }, DESK, DOOR, FACE, YOU, yaw: YOU };
  }

  // ── Detective Kane: the CC0 robot, recoloured, with a fedora and a magnifying glass ───────
  async function loadKane(T, rig) {
    const gltf = await new Promise((resolve, reject) => new T.GLTFLoader().load(MODEL, resolve, undefined, reject));
    const model = gltf.scene;
    const box = new T.Box3().setFromObject(model);
    model.scale.setScalar(1.72 / (box.max.y - box.min.y));
    const colours = { Main: 0xc8a26a, Grey: 0x384055, Black: 0x15171d };
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
    const felt = new T.MeshStandardMaterial({ color: 0x4a2f20, roughness: 0.8 });
    const brim = new T.Mesh(new T.CylinderGeometry(0.34, 0.34, 0.025, 32), felt);
    const crown = new T.Mesh(new T.CylinderGeometry(0.19, 0.22, 0.2, 28), felt); crown.position.y = 0.11;
    const band = new T.Mesh(new T.CylinderGeometry(0.222, 0.222, 0.05, 28), new T.MeshStandardMaterial({ color: 0x1a120c, roughness: 0.6 })); band.position.y = 0.04;
    [brim, crown, band].forEach((m) => { m.castShadow = true; hat.add(m); });
    if (headMeshes.length && (headBone || headEnd)) {
      // sized and placed from the whole head's real bounds (this robot has a big round head)
      const hb = new T.Box3(), size = new T.Vector3(), mid = new T.Vector3();
      headMeshes.forEach((m) => hb.expandByObject(m));
      hb.getSize(size); hb.getCenter(mid);
      const k = Math.max(size.x, size.z) / 0.8;  // the hat was drawn for a 0.8-wide head
      hat.scale.setScalar(k);
      hat.position.set(mid.x, hb.max.y - 0.14 * k, mid.z); hat.rotation.set(-0.1, model.rotation.y, 0.06);
      rig.scene.add(hat); (headBone || headEnd).attach(hat);
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
      face(name, amount) {
        headMeshes.forEach((m) => {
          const i = m.morphTargetDictionary[name];
          if (i !== undefined) m.morphTargetInfluences[i] = amount;
        });
      },
    };
  }

  // ── actions: each a short timeline driven by one real step ────────────────────────────────
  const DUR = { go: 3.6, type: 2.0, click: 1.4, check: 2.4, wait: 1.0 };

  function start(rig, kane, step) {
    const a = parseStep(step);
    a.t = 0; a.dur = DUR[a.action] || 1;
    const s = rig.screen;
    if (a.action !== "go" && a.action !== "wait") rig.yaw = rig.FACE;  // turn to the screen
    if (a.action === "type") s.state.body = { kind: "type", field: a.field, shown: "", caret: true };
    if (a.action === "click") { s.state.body = { kind: "click", label: a.label, field: a.field, pressed: false }; kane.play("Punch"); }
    if (a.action === "check") s.state.body = { kind: "check", label: a.label, result: null };
    s.draw();
    return a;
  }

  function tick(rig, kane, a, dt, speed) {
    a.t += dt * speed;
    const p = Math.min(1, a.t / a.dur);
    const body = kane.model;
    if (a.action === "go") {
      // walk to the door (0-.38), it opens and the sign changes (.38-.62), walk back (.62-1)
      const there = rig.DOOR, home = rig.DESK;
      if (p < 0.38) {
        kane.loop("Walking"); body.position.lerpVectors(home, there, p / 0.38);
        body.rotation.y = rig.yaw = Math.atan2(there.x - home.x, there.z - home.z);
        if (rig.screen.state.body?.kind !== "loading") { rig.screen.state.body = { kind: "loading" }; rig.screen.draw(); }
      } else if (p < 0.62) {
        kane.loop("Idle"); body.rotation.y = rig.yaw = Math.PI;
        const k = (p - 0.38) / 0.24; rig.hinge.rotation.y = -Math.sin(k * Math.PI) * 1.25;
        if (!a.signed && k > 0.4) { a.signed = true; rig.sign.set(a.label); rig.screen.state.path = a.label; rig.screen.state.body = null; rig.screen.draw(); }
      } else {
        rig.hinge.rotation.y = 0; kane.loop("Walking");
        body.position.lerpVectors(there, home, (p - 0.62) / 0.38);
        body.rotation.y = rig.yaw = Math.atan2(home.x - there.x, home.z - there.z);
        if (p >= 1) { body.position.copy(home); rig.yaw = rig.YOU; kane.loop("Idle"); }
      }
    } else if (a.action === "type") {
      kane.loop("Idle");
      const shown = a.value.slice(0, Math.ceil(a.value.length * Math.min(1, p / 0.8)));
      const b = rig.screen.state.body;
      if (b && (b.shown !== shown || b.caret !== p < 1)) { b.shown = shown; b.caret = p < 1; rig.screen.draw(); }
    } else if (a.action === "click") {
      const b = rig.screen.state.body, pressed = p > 0.3 && p < 0.65;
      if (b && b.pressed !== pressed) { b.pressed = pressed; rig.screen.draw(); }
    } else if (a.action === "check") {
      const b = rig.screen.state.body;
      if (b && !b.result && p > 0.35) {
        b.result = a.failed ? "fail" : "pass"; rig.screen.draw(); rig.yaw = rig.YOU;  // turn to you with the verdict
        if (a.failed) { kane.play("No"); kane.face("Surprised", 1); rig.alarmUntil = performance.now() + 2200; }
        else kane.play("Yes");
      }
      if (p >= 1) kane.face("Surprised", 0);
    }
    if (p >= 1 && a.action !== "go") rig.yaw = rig.YOU;  // done: back to you
    return p >= 1;
  }

  // ── wiring it to the page ─────────────────────────────────────────────────────────────────
  async function init(stage) {
    if (stage.dataset.ready || reduce || typeof loadThree !== "function") return;
    stage.dataset.ready = "loading";
    const canvas = stage.querySelector(".kane3d-canvas");
    let rig, kane;
    try {
      await loadEngine();
      rig = buildOffice(window.THREE, canvas);
      kane = await loadKane(window.THREE, rig);
    } catch (e) {
      stage.dataset.ready = "";  // no WebGL or no model: keep the 2D detective
      return;
    }
    stage.classList.add("ready");
    stage.dataset.ready = "1";
    const queue = [];
    let seen = trackerSteps().total, current = null, last = performance.now(), lastDraw = 0, rainAt = 0;
    const fit = () => {
      const w = canvas.clientWidth, h = canvas.clientHeight;
      if (!w || !h) return;
      rig.renderer.setSize(w, h, false); rig.camera.aspect = w / h; rig.camera.updateProjectionMatrix();
    };
    fit();
    new ResizeObserver(fit).observe(canvas);

    // where Kane already is when the page opens: the latest page he went to
    const already = trackerSteps().steps.filter((s) => s.kind === "go").pop();
    if (already) { const a = parseStep(already); rig.sign.set(a.label); rig.screen.state.path = a.label; rig.screen.draw(); }
    kane.play("Wave");  // he greets you when you join him at the scene

    const update = () => {
      const now = trackerSteps();
      if (now.total > seen) { now.steps.slice(-(now.total - seen)).forEach((s) => queue.push(s)); seen = now.total; }
    };
    document.addEventListener("kane:update", update);

    const frame = (now) => {
      if (!canvas.isConnected) { document.removeEventListener("kane:update", update); rig.renderer.dispose(); return; }
      requestAnimationFrame(frame);
      if (document.hidden || now - lastDraw < 30) return;  // about 30 frames a second, none when hidden
      const dt = Math.min(0.1, (now - last) / 1000); last = now; lastDraw = now;
      const mode = document.querySelector("#live .scene-live")?.dataset.mode || "idle";
      if (!current && queue.length) current = start(rig, kane, queue.shift());
      const speed = queue.length > 2 ? 2.2 : queue.length ? 1.4 : 1;  // catch up when Kane is quick
      kane.mixer.update(dt * (current ? speed : 1));
      const turn = Math.atan2(Math.sin(rig.yaw - kane.model.rotation.y), Math.cos(rig.yaw - kane.model.rotation.y));
      kane.model.rotation.y += turn * Math.min(1, dt * 7);
      if (current) {
        kane.bubble.visible = false;
        if (tick(rig, kane, current, dt, speed)) current = null;
      } else {
        kane.bubble.visible = trackerSteps().thinking || mode === "reading";
        kane.bubble.position.set(kane.model.position.x + 0.32, 2.2 + Math.sin(now / 300) * 0.03, kane.model.position.z);
        if (mode === "reading" && rig.screen.state.body?.kind !== "note") {
          rig.screen.state.body = { kind: "note", label: "Claude is writing my orders…" }; rig.screen.draw();
        }
      }
      if (now - rainAt > 60) { rig.win.update(Math.min(0.2, (now - rainAt) / 1000)); rainAt = now; }
      const d = new Date();
      rig.clock.minPivot.rotation.z = -d.getMinutes() / 60 * Math.PI * 2;
      rig.clock.hourPivot.rotation.z = -((d.getHours() % 12) + d.getMinutes() / 60) / 12 * Math.PI * 2;
      rig.alarm.intensity = rig.alarmUntil && now < rig.alarmUntil ? 2.2 + Math.sin(now / 70) * 1.2 : 0;
      rig.camera.position.x = 0.9 + Math.sin(now / 6000) * 0.12;  // a slow drift, so the shot feels alive
      rig.camera.lookAt(rig.focus);
      rig.renderer.render(rig.scene, rig.camera);
    };
    requestAnimationFrame(frame);
  }

  window.initKane3d = (root) => (root || document).querySelectorAll("[data-kane3d]").forEach(init);
  window.initKane3d();
})();

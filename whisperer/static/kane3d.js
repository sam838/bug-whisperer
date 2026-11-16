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
    const c = document.createElement("canvas"); c.width = 512; c.height = 384;
    const city = new T.CanvasTexture(c); city.encoding = T.sRGBEncoding;
    const g = c.getContext("2d");
    const rainCanvas = document.createElement("canvas"); rainCanvas.width = 256; rainCanvas.height = 192;
    const rain = new T.CanvasTexture(rainCanvas); rain.encoding = T.sRGBEncoding;
    const drops = Array.from({ length: 90 }, () => [Math.random() * 256, Math.random() * 192, 6 + Math.random() * 10]);
    const rg = rainCanvas.getContext("2d");
    let raining = false, heavy = false;
    return {
      city, rain,
      paint(phase, weather) {
        const w = 512, h = 384, [top, bottom] = SKIES[phase];
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
          const bh = 110 + ((x * 37) % 170);
          g.fillStyle = phase === "day" ? "#5a6a80" : phase === "night" ? "#0e1428" : "#2a2f48"; g.fillRect(x, h - bh, 42, bh);
          for (let y = h - bh + 10; y < h - 8; y += 16) for (let wx = x + 6; wx < x + 38; wx += 10) {
            if (lit && ((wx * 13 + y * 7) % 11) < 4) { g.fillStyle = "rgba(255,210,120,.85)"; g.fillRect(wx, y, 5, 7); }
            else if (!lit && ((wx * 7 + y * 3) % 9) < 2) { g.fillStyle = "rgba(200,225,255,.5)"; g.fillRect(wx, y, 5, 7); }
          }
        }
        if (weather === "fog") { g.fillStyle = "rgba(205,210,220,.62)"; g.fillRect(0, 0, w, h); }
        city.needsUpdate = true;
        raining = weather === "rain" || weather === "storm"; heavy = weather === "storm";
        if (!raining) { rg.clearRect(0, 0, 256, 192); rain.needsUpdate = true; }
      },
      update(dt) {
        if (!raining) return;
        rg.clearRect(0, 0, 256, 192); rg.strokeStyle = "rgba(190,210,255,.55)"; rg.lineWidth = heavy ? 1.4 : 1;
        for (const d of drops.slice(0, heavy ? 90 : 60)) {
          d[1] += d[2] * dt * (heavy ? 60 : 40); d[0] -= dt * (heavy ? 60 : 30);
          if (d[1] > 192) { d[1] = -10; d[0] = Math.random() * 280; }
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
    rig.blinds.material.color.setHex(m.stripes[0]); rig.blinds.material.opacity = m.stripes[1] * k;
    rig.shaft.material.color.setHex(m.stripes[0]); rig.shaft.material.opacity = 0.18 * k;
    rig.win.paint(phase, weather);
  }

  // ── the office ────────────────────────────────────────────────────────────────────────────
  function buildOffice(T, canvas) {
    const renderer = new T.WebGLRenderer({ canvas, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.outputEncoding = T.sRGBEncoding;
    renderer.toneMapping = T.ACESFilmicToneMapping; renderer.toneMappingExposure = 0.95;
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = T.PCFSoftShadowMap;
    const scene = new T.Scene();
    scene.background = new T.Color(0x0a0d15);
    scene.fog = new T.Fog(0x0a0d15, 6.5, 13);
    if (T.RoomEnvironment) {  // soft image-based lighting: varnish, brass and glass catch a little light
      const pmrem = new T.PMREMGenerator(renderer);
      scene.environment = pmrem.fromScene(new T.RoomEnvironment(), 0.04).texture;
      pmrem.dispose();
    }
    const camera = new T.PerspectiveCamera(36, 16 / 7, 0.1, 40);
    camera.position.set(0.9, 1.95, 3.7);
    const focus = new T.Vector3(-0.65, 1.12, -0.95);

    const std = (color, rough = 0.8, extra = {}) => new T.MeshStandardMaterial({ color, roughness: rough, metalness: 0, ...extra });
    const add = (mesh, x, y, z, { cast = true, receive = true, ry = 0 } = {}) => {
      mesh.position.set(x, y, z); mesh.rotation.y = ry; mesh.castShadow = cast; mesh.receiveShadow = receive; scene.add(mesh); return mesh;
    };

    // light: a dim blue night, a warm desk lamp with shadows, moonlight through the window
    const hemi = new T.HemisphereLight(0x51618c, 0x1a120c, 0.34); scene.add(hemi);
    const lampLight = new T.SpotLight(0xffc98a, 3.8, 9, 0.95, 0.7, 1.3);
    lampLight.position.set(-1.25, 2.0, -0.35); lampLight.target.position.set(-0.6, 0.6, -0.4);
    lampLight.castShadow = true; lampLight.shadow.mapSize.set(1024, 1024); lampLight.shadow.bias = -0.0006;
    lampLight.shadow.normalBias = 0.02; lampLight.shadow.camera.near = 0.2; lampLight.shadow.camera.far = 9;
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
    const paper = canvasTex(T, 256, 256, (g, w, h) => {
      g.fillStyle = "#1f2840"; g.fillRect(0, 0, w, h);
      for (let x = 0; x < w; x += 32) { g.fillStyle = "rgba(255,255,255,.035)"; g.fillRect(x, 0, 12, h); g.fillStyle = "rgba(0,0,0,.12)"; g.fillRect(x + 12, 0, 2, h); }
    });
    paper.wrapS = paper.wrapT = T.RepeatWrapping; paper.repeat.set(5, 2);
    const wallMat = std(0xffffff, 0.92, { map: paper });
    add(new T.Mesh(new T.BoxGeometry(10, 4, 0.1), wallMat), 0, 2, -3.05, { cast: false });
    add(new T.Mesh(new T.BoxGeometry(0.1, 4, 9), wallMat), -3.55, 2, 0.5, { cast: false });
    add(new T.Mesh(new T.BoxGeometry(10, 0.14, 0.04), std(0x2b2116)), 0, 0.07, -2.99, { cast: false });
    const panel = std(0x2e2119, 0.55), rail = std(0x4a3424, 0.45);
    add(new T.Mesh(new T.BoxGeometry(10, 0.95, 0.03), panel), 0, 0.5, -2.985, { cast: false });
    add(new T.Mesh(new T.BoxGeometry(10, 0.05, 0.06), rail), 0, 0.99, -2.97, { cast: false });
    add(new T.Mesh(new T.BoxGeometry(0.03, 0.95, 9), panel), -3.485, 0.5, 0.5, { cast: false });
    add(new T.Mesh(new T.BoxGeometry(0.06, 0.05, 9), rail), -3.47, 0.99, 0.5, { cast: false });
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
    const flash = add(new T.Mesh(new T.PlaneGeometry(1.5, 1.15), new T.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, toneMapped: false })), -2.1, 2.05, -2.982, { cast: false, receive: false });
    const frameMat = std(0x3b2a1b, 0.7);
    [[0, 0.62, 1.62, 0.08], [0, -0.62, 1.62, 0.08], [-0.79, 0, 0.08, 1.3], [0.79, 0, 0.08, 1.3], [0, 0, 0.05, 1.2]].forEach(([x, y, w, h]) =>
      add(new T.Mesh(new T.BoxGeometry(w, h, 0.08), frameMat), -2.1 + x, 2.05 + y, -2.96));
    for (let i = 0; i < 5; i++) add(new T.Mesh(new T.BoxGeometry(1.52, 0.035, 0.03), std(0xb9a37f, 0.6)), -2.1, 2.5 - i * 0.1, -2.93);
    const stripes = canvasTex(T, 256, 256, (g, w, h) => {
      g.clearRect(0, 0, w, h);
      for (let y = 18; y < h - 18; y += 34) {
        const band = g.createLinearGradient(0, 0, w, 0);
        band.addColorStop(0, "rgba(255,255,255,0)"); band.addColorStop(0.5, "rgba(255,255,255,.9)"); band.addColorStop(1, "rgba(255,255,255,0)");
        g.fillStyle = band; g.fillRect(16, y, w - 32, 16);
      }
    });
    const blinds = new T.Mesh(new T.PlaneGeometry(2.2, 2.4), new T.MeshBasicMaterial({ map: stripes, transparent: true, opacity: 0.22, depthWrite: false, blending: T.AdditiveBlending }));
    blinds.rotation.x = -Math.PI / 2; blinds.rotation.z = 0.35; blinds.position.set(-1.25, 0.009, -1.25); scene.add(blinds);
    const shaft = new T.Mesh(new T.PlaneGeometry(1.4, 3.2), new T.MeshBasicMaterial({ map: radialTex(T, "rgba(255,255,255,.5)", "rgba(255,255,255,0)"), transparent: true, opacity: 0.18, depthWrite: false, blending: T.AdditiveBlending }));
    shaft.position.set(-1.75, 1.35, -2.0); shaft.rotation.set(-0.55, 0.3, 0); scene.add(shaft);

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
      g.fillStyle = "#23201b";
      for (let i = 0; i < 60; i++) { const a = i * Math.PI / 30, r = i % 5 ? 2 : 3.5; g.beginPath(); g.arc(128 + Math.sin(a) * 108, 128 - Math.cos(a) * 108, r, 0, 7); g.fill(); }
      g.font = "700 30px Georgia, serif"; g.textAlign = "center"; g.textBaseline = "middle";
      for (let n = 1; n <= 12; n++) { const a = n * Math.PI / 6; g.fillText(String(n), 128 + Math.sin(a) * 84, 130 - Math.cos(a) * 84); }
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
    const bulb = new T.Mesh(new T.SphereGeometry(0.05, 12, 10), new T.MeshBasicMaterial({ color: 0xfff1c8, toneMapped: false }));
    bulb.position.set(-0.6, 1.6, -0.17); station.add(bulb);
    const halo = new T.Sprite(new T.SpriteMaterial({ map: radialTex(T, "rgba(255,214,150,.55)", "rgba(255,214,150,0)"), transparent: true, depthWrite: false, blending: T.AdditiveBlending }));
    halo.scale.set(0.9, 0.9, 1); halo.position.copy(bulb.position); station.add(halo);
    // an office chair in front of the computer: Kane sits here while he works
    const leather = std(0x2a2422, 0.45), steel = std(0x9aa0a8, 0.3, { metalness: 0.75 });
    const chair = new T.Group(); chair.position.set(-1.09, 0, -0.46); chair.rotation.y = Math.PI / 4 + Math.PI; scene.add(chair);
    const cp = (geo, mat, x, y, z, rx = 0, ry = 0) => { const m = new T.Mesh(geo, mat); m.position.set(x, y, z); m.rotation.set(rx, ry, 0); m.castShadow = m.receiveShadow = true; chair.add(m); return m; };
    for (let i = 0; i < 5; i++) {
      const a = i * Math.PI * 2 / 5;
      cp(new T.BoxGeometry(0.05, 0.035, 0.3), steel, Math.sin(a) * 0.15, 0.07, Math.cos(a) * 0.15, 0, a);
      cp(new T.SphereGeometry(0.032, 10, 8), std(0x1a1a1a, 0.5), Math.sin(a) * 0.29, 0.032, Math.cos(a) * 0.29);
    }
    cp(new T.CylinderGeometry(0.03, 0.035, 0.36, 12), steel, 0, 0.26, 0);
    cp(new T.BoxGeometry(0.5, 0.06, 0.48), leather, 0, 0.47, 0);
    cp(new T.BoxGeometry(0.46, 0.06, 0.44), std(0x3a302c, 0.6), 0, 0.52, 0.01);
    cp(new T.BoxGeometry(0.06, 0.32, 0.05), steel, 0, 0.62, -0.24, -0.1);
    cp(new T.BoxGeometry(0.48, 0.5, 0.07), leather, 0, 0.92, -0.27, -0.12);
    cp(new T.BoxGeometry(0.42, 0.44, 0.04), std(0x3a302c, 0.6), 0, 0.92, -0.225, -0.12);
    [-0.27, 0.27].forEach((x) => { cp(new T.BoxGeometry(0.05, 0.04, 0.3), leather, x, 0.68, -0.02); cp(new T.BoxGeometry(0.03, 0.17, 0.03), steel, x, 0.6, -0.02); });

    const blobTex = radialTex(T, "rgba(0,0,0,.55)", "rgba(0,0,0,0)");
    const blob = (w, d, x, z, ry = 0) => {
      const m = new T.Mesh(new T.PlaneGeometry(w, d), new T.MeshBasicMaterial({ map: blobTex, transparent: true, depthWrite: false }));
      m.rotation.x = -Math.PI / 2; m.rotation.z = ry; m.position.set(x, 0.008, z); scene.add(m); return m;
    };
    blob(2.4, 1.4, -1.55, -0.85, Math.PI / 4);   // desk
    blob(0.9, 0.9, -1.09, -0.46);                  // chair
    blob(0.9, 0.9, 2.75, -2.6);                    // filing cabinet
    blob(0.8, 1.8, -3.25, 1.1);                    // bookshelf
    const kaneShadow = blob(0.9, 0.9, 0, 0);

    // dust drifting in the lamplight
    const dustGeo = new T.BufferGeometry(), dustPos = new Float32Array(90 * 3);
    for (let i = 0; i < 90; i++) { dustPos[i * 3] = -1.6 + Math.random() * 1.6; dustPos[i * 3 + 1] = 0.6 + Math.random() * 1.4; dustPos[i * 3 + 2] = -1.2 + Math.random() * 1.2; }
    dustGeo.setAttribute("position", new T.BufferAttribute(dustPos, 3));
    const dust = new T.Points(dustGeo, new T.PointsMaterial({ size: 0.018, color: 0xffd9a0, transparent: true, opacity: 0.55, depthWrite: false, blending: T.AdditiveBlending }));
    scene.add(dust);
    dust.update = (dt) => {
      for (let i = 0; i < 90; i++) {
        dustPos[i * 3 + 1] += dt * 0.03 * (1 + (i % 3)); dustPos[i * 3] += Math.sin((dustPos[i * 3 + 1] + i) * 3) * dt * 0.02;
        if (dustPos[i * 3 + 1] > 2.0) dustPos[i * 3 + 1] = 0.6;
      }
      dustGeo.attributes.position.needsUpdate = true;
    };

    // the corkboard on the back wall, where Kane pins the case's evidence as he finds it
    const corkTex = canvasTex(T, 512, 320, (g, w, h) => {
      g.fillStyle = "#b8875a"; g.fillRect(0, 0, w, h);
      for (let i = 0; i < 2400; i++) { g.fillStyle = i % 2 ? "rgba(70,40,15,.22)" : "rgba(255,240,215,.14)"; g.fillRect((i * 97) % w, (i * 57) % h, 2, 2); }
    });
    const BOARD = new T.Vector3(-0.25, 1.72, -2.965);
    add(new T.Mesh(new T.BoxGeometry(1.72, 1.12, 0.05), std(0x6e4a2c, 0.7)), BOARD.x, BOARD.y, -2.985, { cast: false });
    add(new T.Mesh(new T.PlaneGeometry(1.6, 1.0), std(0xffffff, 0.95, { map: corkTex })), BOARD.x, BOARD.y, BOARD.z - 0.004, { cast: false });
    const pinned = new T.Group(); scene.add(pinned);
    const board = {
      cards: [],
      add(tex) {
        const slot = this.cards.length % 6, col = slot % 3, row = Math.floor(slot / 3);
        if (this.cards.length >= 6) pinned.remove(this.cards[slot].group);  // a full board: the oldest card makes room
        const group = new T.Group();
        group.position.set(BOARD.x + (col - 1) * 0.5, BOARD.y + (row ? -0.23 : 0.22), BOARD.z + 0.01 + this.cards.length * 0.0005);
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

    // the door to the app's next page, with its sign
    const frameWood = std(0x2b1d12, 0.7);
    add(new T.Mesh(new T.BoxGeometry(1.24, 0.1, 0.12), frameWood), 1.45, 2.13, -2.95);
    [0.86, 2.04].forEach((x) => add(new T.Mesh(new T.BoxGeometry(0.1, 2.18, 0.12), frameWood), x, 1.09, -2.95));
    add(new T.Mesh(new T.PlaneGeometry(1.08, 2.08), new T.MeshBasicMaterial({ color: 0xfff0c8, toneMapped: false })), 1.45, 1.04, -2.995, { cast: false, receive: false });
    const doorLight = new T.PointLight(0xffd9a0, 0, 5, 1.6); doorLight.position.set(1.45, 1.3, -2.55); scene.add(doorLight);
    const hinge = new T.Group(); hinge.position.set(0.91, 0, -2.93); scene.add(hinge);
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
    const INSIDE = new T.Vector3(1.45, 0, -2.85);  // in the doorway
    const CHAIR = new T.Vector3(-1.09, 0, -0.46);   // standing by the chair
    const SEAT_YAW = Math.PI / 4 + Math.PI;           // facing the computer
    // seated, the robot's hips sit 0.29 up and 0.24 behind its feet: lift and shift it onto the cushion
    const SEAT = new T.Vector3(CHAIR.x - 0.24 * Math.sin(SEAT_YAW) * -1, 0.26, CHAIR.z - 0.24 * Math.cos(SEAT_YAW) * -1);
    const AISLE = new T.Vector3(-0.4, 0, -0.2), PIN_SPOT = new T.Vector3(BOARD.x, 0, -2.3);
    const AWAY = new T.Vector3(-Math.sin(SEAT_YAW), 0, -Math.cos(SEAT_YAW));     // away from the desk
    const OUT = CHAIR.clone().addScaledVector(AWAY, 0.5);                         // the chair pulled out
    const SIDE = OUT.clone().addScaledVector(new T.Vector3(AWAY.z, 0, -AWAY.x), 0.55);  // beside it, room side
    const STAND = OUT.clone().addScaledVector(AWAY, -0.3);                        // in front of the pulled-out chair
    const SEAT_OUT = SEAT.clone().addScaledVector(AWAY, 0.5);                    // seated, before sliding in
    return { renderer, scene, camera, focus, screen, sign, hinge, doorLight, alarm, win, board, dust, kaneShadow, hemi, sun: moon, rim, lampLight, blinds, shaft, flash, clock: { hourPivot, minPivot }, DESK, DOOR, INSIDE, CHAIR, SEAT, SEAT_YAW, chair, OUT, SIDE, STAND, SEAT_OUT, AISLE, PIN_SPOT, FACE, YOU, yaw: YOU };
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

  function walkTo(rig, kane, target) {
    let from;
    return {
      get dur() { return from ? Math.max(0.35, from.distanceTo(target) / 1.3) : 1; },
      enter() { from = kane.model.position.clone(); from.y = 0; kane.loop("Walking"); rig.seated = false; },
      run(k) {
        kane.model.position.lerpVectors(from, target, k);
        rig.yaw = Math.atan2(target.x - from.x, target.z - from.z); kane.model.rotation.y = rig.yaw;
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
    walkTo(rig, kane, rig.STAND),
    move(0.5, (k) => kane.model.position.lerpVectors(rig.STAND, rig.SEAT_OUT, k),
      () => { rig.yaw = rig.SEAT_YAW; kane.model.rotation.y = rig.SEAT_YAW; kane.hold("Sitting"); rig.seated = true; }),
    slideChair(rig, kane, rig.OUT, rig.CHAIR, [rig.SEAT_OUT, rig.SEAT]),        // slide in to the desk
  ];
  const getUp = (rig, kane) => [
    slideChair(rig, kane, rig.CHAIR, rig.OUT, [rig.SEAT, rig.SEAT_OUT]),        // slide back from the desk
    move(0.45, (k) => kane.model.position.lerpVectors(rig.SEAT_OUT, rig.STAND, k),
      () => { kane.hold("Standing"); rig.seated = false; }),
    walkTo(rig, kane, rig.SIDE),
    slideChair(rig, kane, rig.OUT, rig.CHAIR),                                 // push the chair back in
  ];
  const pinCard = (rig, kane, tex) => {
    let pinned = false;
    return move(1.0, (k) => { if (!pinned && k > 0.45) { pinned = true; rig.board.add(tex); } },
      () => { rig.yaw = Math.PI; kane.model.rotation.y = Math.PI; kane.loop("Idle"); kane.play("Punch"); });  // he presses the pin in
  };
  const toBoardAndBack = (rig, kane, tex) => [
    walkTo(rig, kane, rig.AISLE), walkTo(rig, kane, rig.PIN_SPOT), pinCard(rig, kane, tex),
    walkTo(rig, kane, rig.AISLE), ...sitAtDesk(rig, kane),
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

  // the case opens: Kane comes in through the door, pins the witness statement, sits at the computer
  function entrance(rig, kane, statement) {
    const T = window.THREE;
    const tex = cardTex(T, { title: "Witness statement", body: statement || "(the user's report)", hand: true });
    const door = (k) => { rig.hinge.rotation.y = k * 1.35; rig.doorLight.intensity = k * 1.8; };
    return [
      move(0.6, door, () => { kane.model.position.copy(rig.INSIDE); kane.model.visible = true; rig.yaw = 0; kane.model.rotation.y = 0; rig.seated = false; }),
      walkTo(rig, kane, rig.DOOR),
      move(1.7, (k) => door(1 - Math.min(1, k * 3)), () => { rig.yaw = rig.YOU; kane.loop("Idle"); kane.play("Wave"); }),
      walkTo(rig, kane, rig.PIN_SPOT), pinCard(rig, kane, tex),
      walkTo(rig, kane, rig.AISLE), ...sitAtDesk(rig, kane),
    ];
  }

  // ── wiring it to the page ─────────────────────────────────────────────────────────────────
  async function init(stage) {
    if (stage.dataset.ready || reduce || typeof loadThree !== "function") return;
    stage.dataset.ready = "loading";
    const canvas = stage.querySelector(".kane3d-canvas");
    let rig, kane;
    try {
      await loadEngine();
      if (document.fonts) await Promise.all(["600 25px Caveat", "600 17px Inter"].map((f) => document.fonts.load(f).catch(() => {})));
      rig = buildOffice(window.THREE, canvas);
      kane = await loadKane(window.THREE, rig);
    } catch (e) {
      stage.dataset.ready = "";  // no WebGL or no model: keep the 2D detective
      return;
    }
    stage.classList.add("ready");
    stage.dataset.ready = "1";
    const T = window.THREE;
    rig.scene.traverse((o) => {
      for (const m of [].concat(o.material || [])) if (m.isMeshStandardMaterial) m.envMapIntensity = m.metalness > 0.5 ? 0.6 : 0.1;
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

    let seen = sofar.total, current = null, last = performance.now(), lastDraw = 0, rainAt = 0;
    const update = () => {
      const now = trackerSteps();
      if (now.total > seen) { now.steps.slice(-(now.total - seen)).forEach((st) => script.push({ step: st })); seen = now.total; }
    };
    document.addEventListener("kane:update", update);

    // Kane's real browser on the 3D screen, whenever the live camera is filming it
    const liveSrc = stage.dataset.liveSrc;
    let misses = 0;
    const pollLive = () => {
      if (!canvas.isConnected || !liveSrc) return;
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
      if (document.hidden || now - lastDraw < 30) return;  // about 30 frames a second, none when hidden
      const dt = Math.min(0.1, (now - last) / 1000); last = now; lastDraw = now;
      const backlog = script.filter((x) => x.step).length;
      const speed = backlog > 2 ? 2.2 : backlog ? 1.4 : 1;  // catch up when Kane is quick
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
      const mode = document.querySelector("#live .scene-live")?.dataset.mode || "idle";
      kane.bubble.visible = !current && (trackerSteps().thinking || mode === "reading");
      const head = kane.model.position;
      kane.bubble.position.set(head.x + 0.3, (rig.seated ? 1.85 : 2.2) + Math.sin(now / 300) * 0.03, head.z);
      if (!current && mode === "reading" && rig.screen.state.body?.kind !== "note") {
        rig.screen.state.body = { kind: "note", label: "Claude is writing my orders…" }; rig.screen.draw();
      }
      if (now - rainAt > 60) { rig.win.update(Math.min(0.2, (now - rainAt) / 1000)); rainAt = now; }
      rig.dust.update(dt);
      if (weather === "storm" && now > nextFlash) { rig.flashAt = now; nextFlash = now + 6000 + Math.random() * 9000; }
      const f = rig.flashAt ? Math.max(0, 1 - (now - rig.flashAt) / 260) * (Math.sin((now - rig.flashAt) / 40) > -0.3 ? 1 : 0.3) : 0;
      rig.flash.material.opacity = f * 0.85; rig.sun.intensity = rig.sunBase + f * 4;
      rig.kaneShadow.visible = kane.model.visible;
      rig.kaneShadow.position.set(kane.model.position.x, 0.009, kane.model.position.z);
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

  // the same Detective Kane for the 3D reconstruction of finished cases (recon.js)
  window.kaneRobot = { loadEngine, loadKane };
  window.initKane3d = (root) => (root || document).querySelectorAll("[data-kane3d]").forEach(init);
  window.initKane3d();
})();

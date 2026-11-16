// Detective Kane in 3D, acting out each of his real steps while a case runs.
//
// The live tracker on the page lists Kane's steps as they really happen (from Kane CLI's own
// events), each marked with its kind: go, type, click, pick, check, look… Every new step becomes
// an action here: he walks through the door to a new page, types at the computer (the screen
// shows the real value), presses the real button, raises his magnifying glass to check, and a
// failed check turns the screen red. Between steps he works out his next move. Nothing here is
// invented: no step, no action. three.js loads only on a live case; reduced motion or no WebGL
// keeps the 2D detective.

(function () {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const PATH_RE = /https?:\/\/[^\s]+/;

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
    if (step.kind === "wait") return { action: "wait", label: t };
    return { action: "wait", label: t };
  }

  // ── canvas textures: the computer screen and the door sign ────────────────────────────────
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
    const c = document.createElement("canvas");
    c.width = 640; c.height = 400;
    const tex = new T.CanvasTexture(c);
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
        g.fillStyle = "#4b5263"; g.font = "700 24px Inter, sans-serif"; g.fillText(b.field || "Input", 60, 140);
        g.strokeStyle = "#7a5af8"; g.lineWidth = 4; g.strokeRect(60, 156, 520, 62);
        g.fillStyle = "#17181d"; g.font = "600 30px 'JetBrains Mono', monospace"; g.fillText(b.shown + (b.caret ? "▌" : ""), 76, 198);
      } else if (b.kind === "click") {
        if (b.field) { g.fillStyle = "#4b5263"; g.font = "700 22px Inter, sans-serif"; g.fillText(b.field, 60, 130); }
        g.fillStyle = b.pressed ? "#0b5e44" : "#0f7a52"; g.fillRect(150, 160, 340, 74);
        g.fillStyle = "#ffffff"; g.font = "700 26px Inter, sans-serif"; g.textAlign = "center";
        g.fillText(String(b.label).slice(0, 26), 320, 208); g.textAlign = "left";
      } else if (b.kind === "check") {
        g.fillStyle = b.result === "fail" ? "#fbe9e7" : b.result === "pass" ? "#e3f3ea" : "#ffffff";
        g.fillRect(30, 70, 580, 310);
        g.fillStyle = "#23201b"; g.font = "600 22px Inter, sans-serif"; wrapText(g, b.label, 50, 112, 540, 30, 4);
        if (b.result) {  // bottom-left, where Kane's raised arm doesn't cover it
          g.fillStyle = b.result === "fail" ? "#b3261e" : "#0f7a52"; g.font = "800 96px Inter, sans-serif";
          g.fillText(b.result === "fail" ? "✗" : "✓", 50, 360);
          g.font = "800 30px Inter, sans-serif"; g.fillText(b.result === "fail" ? "Not as expected" : "As expected", 140, 335);
        }
      } else if (b.kind === "loading") {
        g.fillStyle = "#8a90a0"; g.font = "600 28px Inter, sans-serif"; g.fillText("Loading " + state.path.slice(0, 26) + "…", 70, 220);
      } else if (b.kind === "paper") {
        g.fillStyle = "#8a90a0"; g.font = "600 24px Inter, sans-serif"; wrapText(g, b.label, 60, 180, 520, 32, 4);
      }
      tex.needsUpdate = true;
    }
    draw();
    return { tex, state, draw };
  }

  function makeSign(T) {
    const c = document.createElement("canvas");
    c.width = 512; c.height = 96;
    const tex = new T.CanvasTexture(c);
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
    const c = document.createElement("canvas");
    c.width = 128; c.height = 96;
    const g = c.getContext("2d");
    g.fillStyle = "#ffffff"; g.beginPath(); g.ellipse(64, 40, 56, 34, 0, 0, 7); g.fill();
    g.beginPath(); g.arc(30, 82, 9, 0, 7); g.fill();
    g.fillStyle = "#15182a"; g.font = "800 44px Inter, sans-serif"; g.textAlign = "center"; g.fillText("…", 64, 52);
    const s = new T.Sprite(new T.SpriteMaterial({ map: new T.CanvasTexture(c), transparent: true }));
    s.scale.set(0.7, 0.52, 1);
    return s;
  }

  // ── the office and the detective ──────────────────────────────────────────────────────────
  function build(T, canvas) {
    const renderer = new T.WebGLRenderer({ canvas, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    const scene = new T.Scene();
    scene.background = new T.Color(0x12141c);
    const camera = new T.PerspectiveCamera(38, 16 / 7, 0.1, 50);
    camera.position.set(0.6, 2.05, 4.0);
    const focus = new T.Vector3(-0.6, 1.25, -1.0);
    camera.lookAt(focus);

    scene.add(new T.HemisphereLight(0xfff2dd, 0x2a2f42, 0.95));
    scene.add(new T.AmbientLight(0xffffff, 0.18));
    const key = new T.DirectionalLight(0xffffff, 0.55); key.position.set(4, 6, 5); scene.add(key);
    const glow = new T.PointLight(0x9fc7ff, 0.7, 4); glow.position.set(-1.3, 1.6, -0.3); scene.add(glow);
    const alarm = new T.PointLight(0xff3b30, 0, 6); alarm.position.set(-0.6, 2.2, -0.4); scene.add(alarm);

    const mat = (color) => new T.MeshLambertMaterial({ color });
    const floor = new T.Mesh(new T.PlaneGeometry(12, 10), mat(0x3a2a1f)); floor.rotation.x = -Math.PI / 2; scene.add(floor);
    const back = new T.Mesh(new T.PlaneGeometry(12, 5), mat(0x1f2433)); back.position.set(0, 2.5, -3); scene.add(back);
    const side = new T.Mesh(new T.PlaneGeometry(10, 5), mat(0x1a1e2b)); side.position.set(-3.2, 2.5, 0); side.rotation.y = Math.PI / 2; scene.add(side);

    // desk + computer (the window into the user's app), turned toward the camera so the screen reads
    const station = new T.Group(); station.position.set(-1.6, 0, -0.7); station.rotation.y = Math.PI / 4; scene.add(station);
    const desk = new T.Mesh(new T.BoxGeometry(1.8, 0.08, 1.0), mat(0x5b3a29)); desk.position.set(0, 0.9, 0); station.add(desk);
    const legGeo = new T.BoxGeometry(0.07, 0.9, 0.07);
    [[-0.82, -0.42], [0.82, -0.42], [-0.82, 0.42], [0.82, 0.42]].forEach(([x, z]) => { const l = new T.Mesh(legGeo, mat(0x4a2f20)); l.position.set(x, 0.45, z); station.add(l); });
    const screen = makeScreen(T);
    const monitor = new T.Mesh(new T.BoxGeometry(1.22, 0.78, 0.06), mat(0x23262f)); monitor.position.set(0, 1.42, -0.3); station.add(monitor);
    const display = new T.Mesh(new T.PlaneGeometry(1.12, 0.7), new T.MeshBasicMaterial({ map: screen.tex }));
    display.position.set(0, 1.42, -0.265); station.add(display);
    const stand = new T.Mesh(new T.BoxGeometry(0.08, 0.36, 0.08), mat(0x23262f)); stand.position.set(0, 1.1, -0.32); station.add(stand);
    const keyboard = new T.Mesh(new T.BoxGeometry(0.7, 0.03, 0.28), mat(0x2c2f3a)); keyboard.position.set(0, 0.955, 0.15); station.add(keyboard);

    // the door to the app's next page, with its sign
    const doorFrame = new T.Mesh(new T.BoxGeometry(1.14, 2.14, 0.08), mat(0x3b2a1b)); doorFrame.position.set(1.4, 1.07, -2.98); scene.add(doorFrame);
    const hinge = new T.Group(); hinge.position.set(0.88, 0, -2.92); scene.add(hinge);
    const door = new T.Mesh(new T.BoxGeometry(1.0, 2.0, 0.06), mat(0x6e4a2c)); door.position.set(0.5, 1.0, 0); hinge.add(door);
    const knob = new T.Mesh(new T.SphereGeometry(0.04, 10, 8), mat(0xd9b45a)); knob.position.set(0.88, 1.0, 0.05); hinge.add(knob);
    const sign = makeSign(T); sign.set("the scene");
    const plate = new T.Mesh(new T.PlaneGeometry(1.3, 0.24), new T.MeshBasicMaterial({ map: sign.tex })); plate.position.set(1.4, 2.42, -2.95); scene.add(plate);

    // Detective Kane: jointed so he can walk, type and point
    const kane = new T.Group();
    const coatMat = mat(0xc8a26a), darkMat = mat(0x2b2d36), skin = mat(0xf2c9a0);
    const hipL = new T.Group(), hipR = new T.Group();
    hipL.position.set(-0.13, 0.72, 0); hipR.position.set(0.13, 0.72, 0);
    [hipL, hipR].forEach((hip) => { const leg = new T.Mesh(new T.CylinderGeometry(0.075, 0.075, 0.72), darkMat); leg.position.y = -0.36; hip.add(leg); kane.add(hip); });
    const body = new T.Group(); kane.add(body);
    const coat = new T.Mesh(new T.CylinderGeometry(0.3, 0.44, 0.95, 18), coatMat); coat.position.y = 1.18; body.add(coat);
    const belt = new T.Mesh(new T.CylinderGeometry(0.4, 0.41, 0.07, 18), mat(0x7a5a34)); belt.position.y = 1.0; body.add(belt);
    const head = new T.Group(); head.position.y = 1.9; body.add(head);
    head.add(new T.Mesh(new T.SphereGeometry(0.25, 20, 16), skin));
    [-0.09, 0.09].forEach((x) => { const eye = new T.Mesh(new T.SphereGeometry(0.03, 8, 6), mat(0x23201b)); eye.position.set(x, 0.02, 0.23); head.add(eye); });
    const brim = new T.Mesh(new T.CylinderGeometry(0.44, 0.44, 0.04, 24), mat(0x4a2f20)); brim.position.y = 0.18; head.add(brim);
    const crown = new T.Mesh(new T.CylinderGeometry(0.23, 0.27, 0.26, 20), mat(0x5b3a29)); crown.position.y = 0.31; head.add(crown);
    const band = new T.Mesh(new T.CylinderGeometry(0.271, 0.271, 0.06, 20), mat(0x23170f)); band.position.y = 0.22; head.add(band);
    const shoulderL = new T.Group(), shoulderR = new T.Group();
    shoulderL.position.set(-0.36, 1.58, 0); shoulderR.position.set(0.36, 1.58, 0);
    [shoulderL, shoulderR].forEach((sh) => {
      const arm = new T.Mesh(new T.CylinderGeometry(0.075, 0.065, 0.66), coatMat); arm.position.y = -0.33; sh.add(arm);
      const hand = new T.Mesh(new T.SphereGeometry(0.07, 10, 8), skin); hand.position.y = -0.68; sh.add(hand);
      body.add(sh);
    });
    const lens = new T.Group(); lens.position.set(0, -0.78, 0.05); shoulderR.add(lens);
    const ring = new T.Mesh(new T.TorusGeometry(0.13, 0.03, 8, 22), mat(0x2b1b12)); lens.add(ring);
    const glass = new T.Mesh(new T.CircleGeometry(0.12, 22), new T.MeshBasicMaterial({ color: 0xaad7ff, transparent: true, opacity: 0.45 })); lens.add(glass);
    lens.visible = false;
    const paperSheet = new T.Mesh(new T.PlaneGeometry(0.34, 0.44), new T.MeshLambertMaterial({ color: 0xfffcf2, side: T.DoubleSide }));
    paperSheet.position.set(0, 1.45, 0.42); paperSheet.rotation.x = -0.5; body.add(paperSheet); paperSheet.visible = false;
    const bubble = bubbleSprite(T); bubble.position.set(0.45, 2.55, 0); kane.add(bubble); bubble.visible = false;
    scene.add(kane);

    // Kane's spot: beside the desk, turned toward the screen, so the camera sees both
    const DESK = new T.Vector3(-0.68, 0, -0.28), DOOR = new T.Vector3(1.4, 0, -2.3);
    const FACE = Math.atan2(-1.81 - DESK.x, -0.91 - DESK.z);  // toward the screen
    kane.position.copy(DESK); kane.rotation.y = FACE;
    return { renderer, scene, camera, focus, kane, body, head, hipL, hipR, shoulderL, shoulderR, lens, paperSheet, bubble,
      hinge, sign, screen, alarm, DESK, DOOR, FACE };
  }

  // ── actions: each a timeline over a few seconds, driven by one real step ───────────────────
  const DUR = { go: 3.2, type: 1.9, click: 1.1, check: 2.0, wait: 1.0 };

  function start(rig, step) {
    const a = parseStep(step);
    a.t = 0; a.dur = DUR[a.action] || 1;
    const s = rig.screen;
    if (a.action === "type") s.state.body = { kind: "type", field: a.field, shown: "", caret: true };
    if (a.action === "click") s.state.body = { kind: "click", label: a.label, field: a.field, pressed: false };
    if (a.action === "check") s.state.body = { kind: "check", label: a.label, result: null };
    s.draw();
    return a;
  }

  function tick(rig, a, dt, speed) {
    a.t += dt * speed;
    const p = Math.min(1, a.t / a.dur);
    const { kane, hipL, hipR, shoulderL, shoulderR, lens } = rig;
    const stride = (on) => { const sw = on ? Math.sin(a.t * 9) * 0.5 : 0; hipL.rotation.x = sw; hipR.rotation.x = -sw; shoulderL.rotation.x = -sw * 0.7; shoulderR.rotation.x = sw * 0.7; };
    if (a.action === "go") {
      // walk to the door (0-.35), door opens and the sign changes (.35-.6), walk back (.6-1)
      const there = rig.DOOR, home = rig.DESK;
      if (p < 0.35) {
        const k = p / 0.35; kane.position.lerpVectors(home, there, k);
        kane.rotation.y = Math.atan2(there.x - home.x, there.z - home.z); stride(true);
        if (rig.screen.state.body?.kind !== "loading") { rig.screen.state.body = { kind: "loading" }; rig.screen.draw(); }
      } else if (p < 0.6) {
        stride(false); kane.rotation.y = Math.PI;
        const k = (p - 0.35) / 0.25; rig.hinge.rotation.y = -Math.sin(k * Math.PI) * 1.2;
        if (!a.signed && k > 0.4) { a.signed = true; rig.sign.set(a.label); rig.screen.state.path = a.label; rig.screen.state.body = null; rig.screen.draw(); }
      } else {
        rig.hinge.rotation.y = 0;
        const k = (p - 0.6) / 0.4; kane.position.lerpVectors(there, home, k);
        kane.rotation.y = Math.atan2(home.x - there.x, home.z - there.z); stride(true);
        if (p >= 1) { kane.rotation.y = rig.FACE; stride(false); }
      }
    } else if (a.action === "type") {
      shoulderL.rotation.x = -1.0 + Math.sin(a.t * 26) * 0.12; shoulderR.rotation.x = -1.0 + Math.cos(a.t * 26) * 0.12;
      const shown = a.value.slice(0, Math.ceil(a.value.length * Math.min(1, p / 0.8)));
      const b = rig.screen.state.body;
      if (b && (b.shown !== shown || b.caret !== p < 1)) { b.shown = shown; b.caret = p < 1; rig.screen.draw(); }
    } else if (a.action === "click") {
      shoulderR.rotation.x = -1.3 * Math.sin(Math.min(1, p * 1.4) * Math.PI); shoulderL.rotation.x = 0;
      const b = rig.screen.state.body; const pressed = p > 0.35 && p < 0.7;
      if (b && b.pressed !== pressed) { b.pressed = pressed; rig.screen.draw(); }
    } else if (a.action === "check") {
      lens.visible = true; shoulderR.rotation.x = -1.45 * Math.min(1, p * 3); rig.head.rotation.x = -0.1;
      const b = rig.screen.state.body;
      if (b && !b.result && p > 0.55) {
        b.result = a.failed ? "fail" : "pass"; rig.screen.draw();
        if (a.failed) rig.alarmUntil = performance.now() + 1500;
      }
      if (p >= 1) { lens.visible = false; shoulderR.rotation.x = 0; rig.head.rotation.x = 0; }
    } else {
      rig.head.rotation.y = Math.sin(a.t * 3) * 0.3;
      if (p >= 1) rig.head.rotation.y = 0;
    }
    return p >= 1;
  }

  // between steps: thinking, reading Claude's orders, or simply breathing
  function idle(rig, now, mode, thinking) {
    const reading = mode === "reading";
    rig.paperSheet.visible = reading;
    rig.bubble.visible = !reading && thinking;
    rig.bubble.position.y = 2.55 + Math.sin(now / 300) * 0.04;
    rig.body.scale.y = 1 + Math.sin(now / 700) * 0.008;
    rig.hipL.rotation.x = rig.hipR.rotation.x = 0;
    if (reading) { rig.shoulderL.rotation.x = rig.shoulderR.rotation.x = -0.95; rig.head.rotation.x = 0.25; }
    else if (thinking) { rig.shoulderR.rotation.x = -2.2; rig.shoulderL.rotation.x = 0; rig.head.rotation.x = -0.15; rig.head.rotation.y = Math.sin(now / 900) * 0.25; }
    else { rig.shoulderL.rotation.x = rig.shoulderR.rotation.x = 0; rig.head.rotation.x = 0; rig.head.rotation.y = Math.sin(now / 1400) * 0.2; }
  }

  // ── wiring it to the page ───────────────────────────────────────────────────────────────────
  async function init(stage) {
    if (stage.dataset.ready || reduce || typeof loadThree !== "function") return;
    stage.dataset.ready = "loading";
    try { await loadThree(); } catch (e) { stage.dataset.ready = ""; return; }
    const T = window.THREE, canvas = stage.querySelector(".kane3d-canvas");
    let rig;
    try { rig = build(T, canvas); } catch (e) { stage.dataset.ready = ""; return; }  // no WebGL: keep the 2D detective
    stage.classList.add("ready");
    stage.dataset.ready = "1";
    const queue = [];
    let seen = trackerSteps().total, current = null, last = performance.now(), lastDraw = 0;
    const fit = () => {
      const w = canvas.clientWidth, h = canvas.clientHeight;
      if (!w || !h) return;
      rig.renderer.setSize(w, h, false); rig.camera.aspect = w / h; rig.camera.updateProjectionMatrix();
    };
    fit();
    new ResizeObserver(fit).observe(canvas);

    // the first steps already done when the page opened: start from the latest page Kane is on
    const already = trackerSteps().steps.filter((s) => s.kind === "go").pop();
    if (already) { const a = parseStep(already); rig.sign.set(a.label); rig.screen.state.path = a.label; rig.screen.draw(); }

    const update = () => {
      const now = trackerSteps();
      if (now.total > seen) {
        const fresh = now.steps.slice(-(now.total - seen));
        fresh.forEach((s) => queue.push(s));
        seen = now.total;
      }
    };
    document.addEventListener("kane:update", update);

    const frame = (now) => {
      if (!canvas.isConnected) { document.removeEventListener("kane:update", update); rig.renderer.dispose(); return; }
      requestAnimationFrame(frame);
      if (document.hidden || now - lastDraw < 30) return;  // about 30 frames a second, none when hidden
      const dt = Math.min(0.1, (now - last) / 1000); last = now; lastDraw = now;
      const mode = document.querySelector("#live .scene-live")?.dataset.mode || "idle";
      if (!current && queue.length) current = start(rig, queue.shift());
      if (current) {
        rig.paperSheet.visible = false; rig.bubble.visible = false;
        const speed = queue.length > 2 ? 2.2 : queue.length ? 1.4 : 1;  // catch up when Kane is quick
        if (tick(rig, current, dt, speed)) current = null;
      } else idle(rig, now, mode, trackerSteps().thinking);
      rig.alarm.intensity = rig.alarmUntil && now < rig.alarmUntil ? 1.4 + Math.sin(now / 60) * 0.8 : 0;
      rig.camera.position.x = 0.6 + Math.sin(now / 5000) * 0.12;  // a slow drift, so the shot feels alive
      rig.camera.lookAt(rig.focus);
      rig.renderer.render(rig.scene, rig.camera);
    };
    requestAnimationFrame(frame);
  }

  window.initKane3d = (root) => (root || document).querySelectorAll("[data-kane3d]").forEach(init);
  window.initKane3d();
})();

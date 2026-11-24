// The Lineup, played in 3D. Every commit Kane had to consider stands in a row in front of a height
// chart, holding a placard with its hash and message. Detective Kane walks to each version he really
// questioned, in the real order, and nods (the test passed: cleared) or shakes his head (the bug
// is there). The suspects that answer rules out step back into the dark, and the camera pulls back
// to the ones still in play, which shows the halving. At the end a red light falls on the culprit.
//
// Nothing is invented: the row, the order, the verdicts and Kane's words all come from the
// lineup's record (lineup.stage() on the server). three.js loads only when Play is pressed, and the
// scene renders only while it plays.

(function () {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const GAP = 0.82;         // metres between two suspects
  const KANE_Z = 1.05;      // Kane's lane, in front of the line
  const FORWARD = 0.7;      // "step forward": where a suspect stands to be questioned
  const FOV = 38;
  const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
  const wait = (ms) => new Promise((r) => setTimeout(r, reduce ? Math.min(ms, 900) : ms));
  // long enough to read what Kane says, as it types out
  const readTime = (text) => Math.max(1600, String(text).length * 24 + 700);

  function tween(ms, fn, linear = false) {
    if (reduce || ms <= 0) { fn(1); return Promise.resolve(); }
    return new Promise((resolve) => {
      const start = performance.now();
      const tick = (now) => {
        const k = Math.min(1, (now - start) / ms);
        fn(linear ? k : ease(k));
        if (k < 1) requestAnimationFrame(tick); else resolve();
      };
      requestAnimationFrame(tick);
    });
  }

  // ── drawn textures: the height chart and the placards ───────────────────────────────────────
  function heightChart(T) {
    const c = document.createElement("canvas"); c.width = 512; c.height = 512;
    const g = c.getContext("2d");
    g.fillStyle = "#262a36"; g.fillRect(0, 0, 512, 512);
    const px = 512 / 3;  // the wall is 3 m tall
    for (let cm = 10; cm < 300; cm += 10) {
      const y = 512 - (cm / 100) * px;
      const major = cm % 50 === 0;
      g.fillStyle = major ? "rgba(236,231,222,.55)" : "rgba(236,231,222,.16)";
      g.fillRect(0, y, 512, major ? 3 : 1);
      if (major) { g.font = "600 22px 'JetBrains Mono', monospace"; g.fillText(String(cm), 10, y - 8); }
    }
    const t = new T.CanvasTexture(c);
    t.wrapS = T.RepeatWrapping; t.encoding = T.sRGBEncoding;
    return t;
  }

  function wrapLines(g, text, width, max) {
    const words = String(text || "").split(/\s+/), lines = [];
    let line = "";
    for (const w of words) {
      const next = line ? `${line} ${w}` : w;
      if (g.measureText(next).width > width && line) {
        lines.push(line); line = w;
        if (lines.length === max) break;
      } else line = next;
    }
    if (lines.length < max && line) lines.push(line);
    if (lines.length === max && words.join(" ").length > lines.join(" ").length) lines[max - 1] = lines[max - 1].replace(/\s*\S*$/, "…");
    return lines;
  }

  const STAMPS = {
    passed: ["CLEARED", "#0f7a52"], failed: ["BUG THERE", "#b3261e"], error: ["CAN'T TELL", "#946200"],
    guilty: ["GUILTY", "#b3261e"],
  };

  function drawPlacard(p, s, stamp) {
    const g = p.canvas.getContext("2d"), w = p.canvas.width, h = p.canvas.height;
    g.fillStyle = "#f6f1e7"; g.fillRect(0, 0, w, h);
    g.fillStyle = "#17181d"; g.fillRect(0, 0, w, 10);
    const role = { good: "LAST GOOD", bad: "BROKEN" }[s.role];
    g.fillStyle = "#6f6a62"; g.font = "700 20px 'JetBrains Mono', monospace";
    g.fillText(role || s.date.slice(5), 18, 40);
    g.fillStyle = "#17181d"; g.font = "700 50px 'JetBrains Mono', monospace";
    g.fillText(s.short, 18, 96);
    g.font = "500 23px Inter, sans-serif"; g.fillStyle = "#3d3f47";
    wrapLines(g, s.subject, w - 36, 3).forEach((l, i) => g.fillText(l, 18, 134 + i * 29));
    if (stamp) {
      const [word, colour] = STAMPS[stamp];
      g.save(); g.translate(w / 2, h / 2 + 10); g.rotate(-0.16);
      g.globalAlpha = 0.92; g.strokeStyle = colour; g.lineWidth = 7;
      g.font = `800 ${stamp === "guilty" ? 60 : 46}px Inter, sans-serif`;
      const tw = g.measureText(word).width;
      g.strokeRect(-tw / 2 - 18, -42, tw + 36, 70);
      g.fillStyle = colour; g.textAlign = "center"; g.fillText(word, 0, 12);
      g.restore();
    }
    p.texture.needsUpdate = true;
  }

  // ── the room and the suspects ───────────────────────────────────────────────────────────────
  // The room and the suspects are our own Blockbench models (art/models.py): a 3 m stretch of wall
  // with its height chart and floor, laid as many times as the row needs, and three suspects in
  // turn down the row.
  const SUSPECTS = ["suspect_hoodie", "suspect_suit", "suspect_beanie"];
  const STRETCH = 3;  // metres of wall in one lineup_wall model
  async function loadModels(T) {
    if (!T.GLTFLoader) return { suspects: [], wall: null };
    const loader = new T.GLTFLoader();
    const one = (name) => new Promise((ok) => loader.load(`/static/models/bb/${name}.glb`, (g) => ok(g.scene), undefined, () => ok(null)));
    const [wall, ...suspects] = await Promise.all([one("lineup_wall"), ...SUSPECTS.map(one)]);
    return { wall, suspects: suspects.every(Boolean) ? suspects : [] };
  }

  function buildRoom(T, canvas, data, { suspects, wall: stretch }) {
    const renderer = new T.WebGLRenderer({ canvas, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.outputEncoding = T.sRGBEncoding;
    const scene = new T.Scene();
    scene.background = new T.Color(0x0e1016);
    const camera = new T.PerspectiveCamera(FOV, 16 / 9, 0.1, 120);

    scene.add(new T.HemisphereLight(0xdfe6ff, 0x101218, 0.55));
    const key = new T.DirectionalLight(0xfff0dd, 0.55); key.position.set(2, 7, 9); scene.add(key);

    const n = data.line.length, width = (n - 1) * GAP;
    const xOf = (i) => -width / 2 + i * GAP;
    const wallW = width + 8;
    if (stretch) {  // the wall, its floor and the yellow line, one 3 m stretch after another
      const count = Math.ceil(wallW / STRETCH);
      for (let i = 0; i < count; i++) {
        const piece = i ? stretch.clone(true) : stretch;
        piece.position.set(-count * STRETCH / 2 + i * STRETCH, 0, -0.75); scene.add(piece);
      }
    } else {  // a drawn room, if the model couldn't load
      const chart = heightChart(T); chart.repeat.set(wallW / 3, 1);
      const wall = new T.Mesh(new T.PlaneGeometry(wallW, 3), new T.MeshLambertMaterial({ map: chart }));
      wall.position.set(0, 1.5, -0.75); scene.add(wall);
      const floor = new T.Mesh(new T.PlaneGeometry(wallW, 14), new T.MeshLambertMaterial({ color: 0x1b1d24 }));
      floor.rotation.x = -Math.PI / 2; floor.position.z = 5; scene.add(floor);
      const strip = new T.Mesh(new T.PlaneGeometry(wallW, 0.06), new T.MeshBasicMaterial({ color: 0xffd166 }));
      strip.rotation.x = -Math.PI / 2; strip.position.set(0, 0.005, 0.6); scene.add(strip);  // the line on the floor
    }

    const figs = data.line.map((s, i) => {
      const group = new T.Group();
      group.position.set(xOf(i), 0, 0);
      let mats;
      if (suspects.length) {  // our Blockbench suspects in turn, each with its own materials to dim
        const body = suspects[i % suspects.length].clone(true);
        mats = [];
        body.traverse((o) => { if (o.isMesh) { o.material = o.material.clone(); mats.push(o.material); } });
        group.add(body);
      } else {  // a plain figure, if the models couldn't load
        const shade = 0x3a3f4d + ((i * 7919) % 5) * 0x030303;  // a little variety down the row
        const body = new T.MeshLambertMaterial({ color: shade });
        const skin = new T.MeshLambertMaterial({ color: 0x555b6b });
        const torso = new T.Mesh(new T.CylinderGeometry(0.2, 0.25, 0.95, 14), body); torso.position.y = 0.92; group.add(torso);
        [-0.09, 0.09].forEach((x) => {
          const leg = new T.Mesh(new T.CylinderGeometry(0.07, 0.07, 0.48, 10), body); leg.position.set(x, 0.24, 0); group.add(leg);
        });
        const head = new T.Mesh(new T.SphereGeometry(0.16, 18, 14), skin); head.position.y = 1.58; group.add(head);
        mats = [body, skin];
      }
      // the placard, held up at chest height
      const pc = document.createElement("canvas"); pc.width = 384; pc.height = 240;
      const texture = new T.CanvasTexture(pc); texture.encoding = T.sRGBEncoding;
      const plate = new T.MeshBasicMaterial({ map: texture });
      const placard = new T.Mesh(new T.PlaneGeometry(0.66, 0.41), plate);
      placard.position.set(0, 1.08, 0.27); group.add(placard);
      scene.add(group);
      const fig = { group, x: xOf(i), mats, base: mats.map((m) => m.color.clone()), plate,
                    placard: { canvas: pc, texture }, s, light: 1, z: 0 };
      drawPlacard(fig.placard, s, null);
      return fig;
    });

    // the interrogation lamp, moved over whoever Kane is questioning; red for the culprit
    const lamp = new T.SpotLight(0xffe2b0, 0, 9, 0.42, 0.55, 1.4);
    lamp.position.set(0, 4.2, 1.6); scene.add(lamp); scene.add(lamp.target);
    return { renderer, scene, camera, figs, lamp, xOf, n };
  }

  // a stand-in, if the robot model can't load
  function drawnKane(T) {
    const kane = new T.Group(), mat = (c) => new T.MeshLambertMaterial({ color: c });
    const coat = new T.Mesh(new T.CylinderGeometry(0.3, 0.45, 1.05, 18), mat(0xc8a26a)); coat.position.y = 0.95; kane.add(coat);
    const head = new T.Mesh(new T.SphereGeometry(0.26, 20, 16), mat(0xf2c9a0)); head.position.y = 1.7; kane.add(head);
    const brim = new T.Mesh(new T.CylinderGeometry(0.46, 0.46, 0.04, 26), mat(0x4a2f20)); brim.position.y = 1.88; kane.add(brim);
    const crown = new T.Mesh(new T.CylinderGeometry(0.24, 0.28, 0.27, 22), mat(0x5b3a29)); crown.position.y = 2.02; kane.add(crown);
    return { model: kane, mixer: null, loop() {}, play() {} };
  }

  function initLineup3d(section) {
    if (section.dataset.ready) return;
    section.dataset.ready = "1";
    const canvas = section.querySelector(".recon-canvas");
    const button = section.querySelector(".recon-play");
    const say = section.querySelector(".recon-say");
    const lineEl = section.querySelector(".recon-line");
    const data = JSON.parse(section.querySelector(".lineup3d-data").textContent || "{}");
    let world = null, kane = null, playing = false, typer = 0;
    const cam = { pos: null, look: null, goalPos: null, goalLook: null, follow: false };

    const speak = (text) => {
      clearTimeout(typer);
      if (reduce) { lineEl.textContent = text; return; }
      let i = 0;
      const step = () => { lineEl.textContent = text.slice(0, ++i); if (i < text.length) typer = setTimeout(step, 16); };
      step();
    };
    const fit = () => {
      const w = canvas.clientWidth, h = canvas.clientHeight;
      world.renderer.setSize(w, h, false);
      world.camera.aspect = w / h; world.camera.updateProjectionMatrix();
    };
    // a camera goal that shows suspects i..j, with room for Kane's dialogue box below
    const frameRange = (i, j) => {
      const T = window.THREE, x0 = world.xOf(i), x1 = world.xOf(j);
      const half = (x1 - x0) / 2 + 1.0;
      const hfov = 2 * Math.atan(Math.tan((FOV * Math.PI) / 360) * world.camera.aspect);
      const dist = Math.min(11, Math.max(4.4, half / Math.tan(hfov / 2)));
      const cx = (x0 + x1) / 2;
      // a little from above, so the suspects who stepped back into the dark show as a gap
      cam.goalPos = new T.Vector3(cx, 1.4 + dist * 0.2, dist);
      cam.goalLook = new T.Vector3(cx, 0.85, 0);
    };
    // after an answer: look back along the line at the boundary, the suspects still in play lit in
    // front of us and the ruled-out ones dark beyond it (Kane, who stands at the boundary, is in the
    // middle distance). A few left: a plain front shot.
    const frameHalving = (open) => {
      const T = window.THREE, left = open[1] - open[0] + 1;
      if (left <= 8) return frameRange(Math.max(0, open[0] - 3), open[1]);
      const xb = world.xOf(open[0]) - GAP / 2;
      cam.goalPos = new T.Vector3(xb + 5.2, 2.5, 4.4);
      cam.goalLook = new T.Vector3(xb - 0.6, 0.95, 0);
    };
    // the opening shot: down the line from its oldest end, so the near suspects are readable
    const wideShot = () => {
      const T = window.THREE, x0 = world.xOf(0);
      cam.goalPos = new T.Vector3(x0 - 2.6, 1.9, 5.4);
      cam.goalLook = new T.Vector3(x0 + 6.5, 1.0, 0);
    };
    // the suspect steps forward and Kane stands beside him, side-on: the camera sees both faces
    const closeUp = (x) => {
      const T = window.THREE;
      cam.goalPos = new T.Vector3(x + 0.4, 1.45, 3.55);
      cam.goalLook = new T.Vector3(x + 0.4, 1.12, 0.7);
    };

    function render(dt) {
      const T = window.THREE;
      if (kane.mixer) kane.mixer.update(dt);
      if (cam.follow) {
        const kx = kane.model.position.x;
        cam.goalPos = new T.Vector3(kx - 1.8, 2.15, 4.7);
        cam.goalLook = new T.Vector3(kx - 0.3, 1.15, 0);
      }
      const k = reduce ? 1 : 1 - Math.pow(0.0025, dt);  // smooth, frame-rate independent
      cam.pos.lerp(cam.goalPos, k); cam.look.lerp(cam.goalLook, k);
      world.camera.position.copy(cam.pos); world.camera.lookAt(cam.look);
      world.renderer.render(world.scene, world.camera);
    }

    // a suspect steps back into the dark (ruled out), stays (still a suspect), or dims red (bug there, but not first)
    function settle(fig, state, inPlay) {
      const target = state === "cleared" ? { z: -0.32, light: 0.32 } : inPlay ? { z: 0, light: 1 } : { z: -0.12, light: 0.55 };
      const fromZ = fig.z, fromL = fig.light;
      return tween(650, (k) => {
        fig.z = fromZ + (target.z - fromZ) * k; fig.light = fromL + (target.light - fromL) * k;
        fig.group.position.z = fig.z;
        fig.mats.forEach((m, n) => m.color.copy(fig.base[n]).multiplyScalar(fig.light));
        if (state === "present" && !inPlay) fig.mats.forEach((m) => { m.color.r += 0.08 * k; });
        fig.plate.color.setScalar(Math.max(0.42, fig.light));
      });
    }

    const SIDE = 0.8;  // Kane stands this far to the right of whoever he questions
    async function walkTo(fx) {
      const x = fx + SIDE, from = kane.model.position.x, dist = Math.abs(x - from);
      if (dist < 0.05) return;
      if (dist > 7 && !reduce) {  // a long way is a cut, not a 30 m slide: Kane is nearly there already
        kane.model.position.set(x - Math.sign(x - from) * 2.2, 0, KANE_Z);
        cam.follow = true; render(0); cam.pos.copy(cam.goalPos); cam.look.copy(cam.goalLook);
        return walkTo(fx);
      }
      const ms = Math.min(1900, Math.max(650, dist * 300));
      const speed = dist / (ms / 1000);
      kane.loop("Walking");
      if (kane.mixer) kane.mixer.timeScale = Math.min(2.4, Math.max(1, speed / 1.3));
      kane.model.rotation.y = x > from ? Math.PI / 2 : -Math.PI / 2;
      cam.follow = true;
      await tween(ms, (k) => { kane.model.position.x = from + (x - from) * k; }, true);
      cam.follow = false;
      if (kane.mixer) kane.mixer.timeScale = 1;
      kane.loop("Idle");
      kane.model.rotation.y = Math.atan2(-SIDE, 0.15);  // side-on to the suspect, a little towards us
    }
    const stepOut = (fig, out) => tween(450, (k) => { fig.group.position.z = fig.z + (out ? k : 1 - k) * FORWARD; });

    function who(i) {
      const s = data.line[i];
      if (s.role === "good") return "the last good version";
      if (s.role === "bad") return "the broken version";
      return `suspect ${i} of ${data.suspects}`;
    }

    async function story() {
      const T = window.THREE, line = data.line;
      wideShot();
      const intro = `${data.suspects} commits changed the code between a version that worked and one that's broken. One of them broke it. I'll question as few as I can.`;
      speak(intro);
      await wait(readTime(intro));
      let open = [1, line.length - 1], news = "";
      for (const step of data.steps) {
        const fig = world.figs[step.at], s = fig.s;
        const ask = `${news}#${step.asked_as}: ${who(step.at)}, ${s.short} “${s.subject}”.`;
        speak(ask);
        await walkTo(fig.x);
        closeUp(fig.x);
        world.lamp.color.set(0xffe2b0); world.lamp.position.set(fig.x, 4.2, 2.2); world.lamp.target.position.set(fig.x, 1, FORWARD);
        await Promise.all([stepOut(fig, true), tween(350, (k) => { world.lamp.intensity = 1.6 * k; })]);
        await wait(Math.max(500, readTime(ask) - 2200));
        drawPlacard(fig.placard, s, step.verdict);
        kane.play(step.verdict === "passed" ? "Yes" : "No");
        const said = step.said ? `“${step.said}”` : { passed: "Cleared.", failed: "The bug is there.", error: "I couldn't tell." }[step.verdict];
        speak(said);
        await wait(readTime(said));
        world.lamp.intensity = 0;
        await stepOut(fig, false);
        // what the answer rules out: those suspects step back, and the camera shows who is left
        const before = open[1] - open[0] + 1;
        open = step.open;
        const now = open[1] - open[0] + 1;
        news = now < before ? `${before - now} ruled out, ${now === 1 ? "one left" : `${now} left`}. ` : "";
        if (now < before) frameHalving(open);
        await Promise.all(world.figs.map((f, i) => settle(f, step.after[i], i >= open[0] && i <= open[1] && i > 0)));
        if (now < before) await wait(900);
      }
      const c = data.culprit;
      if (c !== null && c !== undefined) {
        const fig = world.figs[c], s = fig.s;
        await walkTo(fig.x);
        closeUp(fig.x);
        world.lamp.color.set(0xff4a3d); world.lamp.position.set(fig.x, 4.2, 2.2); world.lamp.target.position.set(fig.x, 1, FORWARD);
        await Promise.all([stepOut(fig, true), tween(500, (k) => { world.lamp.intensity = 2.4 * k; })]);
        drawPlacard(fig.placard, s, "guilty");
        kane.play("Punch");
        const end = `${news}It was ${s.short}: “${s.subject}”${s.author ? `, by ${s.author}` : ""}, ${s.date}. The version just before it passed the same test.`;
        speak(end);
        await wait(readTime(end));
        kane.model.rotation.y = -0.35; kane.play("ThumbsUp");
        cam.goalPos = new T.Vector3(fig.x - 0.2, 1.55, 4.6); cam.goalLook = new T.Vector3(fig.x - 0.2, 1.1, 0.4);
        speak(`${data.steps.length} questionings for ${data.suspects} suspects. Case closed.`);
        await wait(3200);
      } else {
        speak(data.words || "No one accused.");
        await wait(readTime(data.words || ""));
      }
    }

    async function play() {
      if (playing) return;
      button.disabled = true;
      button.innerHTML = "<span>…</span> Setting up the lineup";
      try {
        await loadThree();  // from recon.js
        if (window.kaneRobot) await window.kaneRobot.loadEngine().catch(() => {});
        if (document.fonts) await Promise.all(["700 50px 'JetBrains Mono'", "500 23px Inter", "800 46px Inter"].map((f) => document.fonts.load(f).catch(() => {})));
      } catch (err) {
        button.disabled = false;
        button.innerHTML = "<span>!</span> The 3D view couldn't load. Try again";
        return;
      }
      const T = window.THREE;
      if (world) {  // play again: everyone back in line
        world.figs.forEach((f) => { drawPlacard(f.placard, f.s, null); f.z = 0; f.light = 1; f.group.position.z = 0;
          f.mats.forEach((m, n) => m.color.copy(f.base[n])); f.plate.color.setScalar(1); });
        world.lamp.intensity = 0;
      }
      world ||= buildRoom(T, canvas, data, await loadModels(T));
      if (!kane) {
        const start = new T.Vector3(world.xOf(0) - 1.6, 0, KANE_Z);
        try {
          kane = await window.kaneRobot.loadKane(T, { scene: world.scene, DESK: start, YOU: Math.PI / 2 });
        } catch (e) {
          kane = drawnKane(T); kane.model.position.copy(start); world.scene.add(kane.model);
        }
      }
      kane.model.position.set(world.xOf(0) - 1.6, 0, KANE_Z); kane.model.rotation.y = Math.PI / 2;
      fit();
      frameRange(0, world.n - 1);
      cam.pos = cam.goalPos.clone(); cam.look = cam.goalLook.clone();
      playing = true;
      section.classList.remove("ended");
      section.classList.add("playing");
      button.hidden = true; say.hidden = false;
      let previous = performance.now();
      const frame = (now) => {
        const dt = Math.min(0.1, (now - previous) / 1000); previous = now;
        render(dt);
        if (playing) requestAnimationFrame(frame);
      };
      requestAnimationFrame(frame);
      try {
        await story();
      } finally {
        playing = false;
        section.classList.remove("playing");
        section.classList.add("ended");
        button.hidden = false; button.disabled = false;
        button.innerHTML = "<span>↻</span> Play again";
      }
    }

    button.addEventListener("click", play);
    new ResizeObserver(() => { if (world && cam.pos) { fit(); render(0); } }).observe(canvas);
  }

  window.initLineup3d = initLineup3d;
  document.querySelectorAll("[data-lineup3d]").forEach(initLineup3d);
})();

// The case, reconstructed in 3D: Kane's office, with the case's real evidence pinned to a
// corkboard and joined by red string in the order the investigation went. The camera tours the
// evidence by itself while Kane narrates in his dialogue box. three.js is loaded only when Play
// is pressed, and the scene only renders while the tour plays, so idle pages cost nothing.

const THREE_URL = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js";
const reconReduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
let threeLoading = null;

function loadThree() {
  if (window.THREE) return Promise.resolve();
  threeLoading ||= new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = THREE_URL;
    s.onload = resolve;
    s.onerror = () => reject(new Error("couldn't load the 3D library"));
    document.head.append(s);
  });
  return threeLoading;
}

// ── evidence as paper: notes, stamps and printouts drawn onto canvas textures ─────────────────
function wrap(g, text, x, y, width, lineHeight, maxLines) {
  const words = String(text || "").split(/\s+/);
  let line = "", lines = 0;
  for (const word of words) {
    const next = line ? `${line} ${word}` : word;
    if (g.measureText(next).width > width && line) {
      g.fillText(line, x, y + lines * lineHeight);
      line = word;
      if (++lines >= maxLines - 1) { line += "…"; break; }
    } else line = next;
  }
  g.fillText(line, x, y + lines * lineHeight);
}

function paper(pin) {
  const c = document.createElement("canvas");
  c.width = 640; c.height = 480;
  const g = c.getContext("2d");
  g.fillStyle = "#fffcf2"; g.fillRect(0, 0, 640, 480);
  g.fillStyle = "#6f6a62"; g.font = "700 22px 'JetBrains Mono', monospace";
  g.fillText(String(pin.title || "").toUpperCase(), 32, 50);
  if (pin.kind === "stamp") {
    const colour = { ok: "#0f7a52", bug: "#b3261e", warn: "#946200" }[pin.tone] || "#6f6a62";
    g.save(); g.translate(320, 170); g.rotate(-0.07);
    g.strokeStyle = colour; g.lineWidth = 8; g.strokeRect(-230, -52, 460, 104);
    g.fillStyle = colour; g.font = "800 58px Inter, sans-serif"; g.textAlign = "center";
    g.fillText(String(pin.stamp || "").toUpperCase(), 0, 20); g.restore();
    g.fillStyle = "#3d3f47"; g.font = "500 24px Inter, sans-serif";
    wrap(g, pin.body, 32, 290, 576, 32, 5);
  } else if (pin.kind === "diff") {
    g.font = "500 19px 'JetBrains Mono', monospace";
    (pin.lines || []).slice(0, 12).forEach((l, i) => {
      g.fillStyle = l.startsWith("+") ? "#0f7a52" : "#b3261e";
      g.fillText(l.slice(0, 52), 32, 96 + i * 30);
    });
  } else if (pin.kind === "hand") {
    g.fillStyle = "#1f3a8a"; g.font = "600 44px Caveat, cursive";
    wrap(g, `“${pin.body}”`, 32, 110, 576, 50, 7);
  } else {
    g.fillStyle = "#23201b"; g.font = "500 25px 'JetBrains Mono', monospace";
    wrap(g, pin.body, 32, 100, 576, 36, 10);
  }
  return c;
}

function corkTexture(T) {
  const c = document.createElement("canvas");
  c.width = 512; c.height = 512;
  const g = c.getContext("2d");
  g.fillStyle = "#b8875a"; g.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 2600; i++) {
    g.fillStyle = Math.random() < 0.55 ? "rgba(70,40,15,.22)" : "rgba(255,240,215,.14)";
    g.fillRect(Math.random() * 512, Math.random() * 512, 2, 2);
  }
  const t = new T.CanvasTexture(c);
  t.wrapS = t.wrapT = T.RepeatWrapping; t.repeat.set(3, 1.6);
  return t;
}

// What Kane says at each piece of evidence: always the case's real text.
function kaneLine(pin) {
  switch (pin.id) {
    case "statement": return `The witness says: “${pin.body}”`;
    case "reading": return `Claude's reading of it: ${pin.body}`;
    case "scene": return pin.body || "My photo from the scene.";
    case "claim": return `${pin.title}. ${pin.body}`;
    case "verdict": return `${pin.stamp}. ${pin.body}`;
    case "repair": return `Claude's repair: ${(pin.lines || []).length} changed lines. I don't take its word for it.`;
    case "recheck": return pin.body || "Back at the scene, same steps.";
    case "closed": return pin.stamp === "Case closed"
      ? `Case closed. I saw the fix with my own eyes. ${pin.body}` : `${pin.stamp}. ${pin.body}`;
    default: return pin.body || pin.title || "";
  }
}

// ── the scene ────────────────────────────────────────────────────────────────────────────────
function buildOffice(T, canvas, board) {
  const renderer = new T.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
  const scene = new T.Scene();
  scene.background = new T.Color(0x0f1118);
  scene.fog = new T.Fog(0x0f1118, 9, 18);
  const camera = new T.PerspectiveCamera(45, 16 / 9, 0.1, 60);

  scene.add(new T.HemisphereLight(0xfff2dd, 0x1a1d29, 0.55));
  const lamp = new T.PointLight(0xffd9a0, 1.1, 12, 1.6);
  lamp.position.set(-1.2, 3.2, 0.8); scene.add(lamp);
  const fill = new T.DirectionalLight(0xbfd4ff, 0.35); fill.position.set(4, 5, 6); scene.add(fill);

  const mat = (color) => new T.MeshLambertMaterial({ color });
  const floor = new T.Mesh(new T.PlaneGeometry(14, 12), mat(0x3a2a1f)); floor.rotation.x = -Math.PI / 2; scene.add(floor);
  const back = new T.Mesh(new T.PlaneGeometry(14, 6), mat(0x1f2433)); back.position.set(0, 3, -4); scene.add(back);
  const left = new T.Mesh(new T.PlaneGeometry(12, 6), mat(0x1a1e2b)); left.position.set(-7, 3, 2); left.rotation.y = Math.PI / 2; scene.add(left);
  const right = left.clone(); right.position.x = 7; right.rotation.y = -Math.PI / 2; scene.add(right);

  // the desk with its lamp, in the foreground
  const desk = new T.Mesh(new T.BoxGeometry(3.4, 0.12, 1.4), mat(0x5b3a29)); desk.position.set(-1.2, 0.95, 1.2); scene.add(desk);
  [[-2.7, 0.65], [0.3, 0.65], [-2.7, 1.75], [0.3, 1.75]].forEach(([x, z]) => {
    const leg = new T.Mesh(new T.BoxGeometry(0.1, 0.95, 0.1), mat(0x4a2f20)); leg.position.set(x, 0.47, z); scene.add(leg);
  });
  const shade = new T.Mesh(new T.ConeGeometry(0.28, 0.3, 20, 1, true), new T.MeshLambertMaterial({ color: 0x2f6b4f, side: T.DoubleSide }));
  shade.position.set(-1.2, 1.75, 0.9); scene.add(shade);
  const pole = new T.Mesh(new T.CylinderGeometry(0.03, 0.03, 0.7), mat(0x2b2b2b)); pole.position.set(-1.2, 1.35, 0.9); scene.add(pole);

  // the corkboard
  const W = 7.6, H = 3.9, BY = 2.35, BZ = -3.94;
  const frame = new T.Mesh(new T.BoxGeometry(W + 0.3, H + 0.3, 0.08), mat(0x6e4a2c)); frame.position.set(0, BY, BZ - 0.03); scene.add(frame);
  const cork = new T.Mesh(new T.PlaneGeometry(W, H), new T.MeshLambertMaterial({ map: corkTexture(T) })); cork.position.set(0, BY, BZ + 0.02); scene.add(cork);

  // Detective Kane, standing by the board
  const kane = new T.Group();
  const coat = new T.Mesh(new T.CylinderGeometry(0.3, 0.45, 1.05, 18), mat(0xc8a26a)); coat.position.y = 0.95; kane.add(coat);
  [-0.14, 0.14].forEach((x) => { const leg = new T.Mesh(new T.CylinderGeometry(0.08, 0.08, 0.45), mat(0x2b2d36)); leg.position.set(x, 0.22, 0); kane.add(leg); });
  const head = new T.Mesh(new T.SphereGeometry(0.26, 20, 16), mat(0xf2c9a0)); head.position.y = 1.7; kane.add(head);
  const brim = new T.Mesh(new T.CylinderGeometry(0.46, 0.46, 0.04, 26), mat(0x4a2f20)); brim.position.y = 1.88; kane.add(brim);
  const crown = new T.Mesh(new T.CylinderGeometry(0.24, 0.28, 0.27, 22), mat(0x5b3a29)); crown.position.y = 2.02; kane.add(crown);
  const lens = new T.Mesh(new T.TorusGeometry(0.14, 0.035, 8, 22), mat(0x2b1b12)); lens.position.set(-0.42, 1.25, 0.25); kane.add(lens);
  kane.position.set(4.6, 0, -2.6); kane.rotation.y = -0.9; scene.add(kane);

  // the evidence: pinned in a grid, in the order the investigation went
  const loader = new T.TextureLoader();
  const pins = board.pins;
  const cols = Math.min(4, Math.max(2, Math.ceil(pins.length / 2)));
  const rows = Math.ceil(pins.length / cols);
  const spots = {};
  pins.forEach((pin, i) => {
    const col = i % cols, row = Math.floor(i / cols);
    const x = -W / 2 + (col + 0.5) * (W / cols) + (Math.sin(i * 7.3) * 0.12);
    const y = BY + H / 2 - (row + 0.5) * (H / rows) + (Math.cos(i * 3.1) * 0.08);
    const tilt = Math.sin(i * 4.7) * 0.06;
    const group = new T.Group();
    group.position.set(x, y, BZ + 0.05); group.rotation.z = tilt;
    if (pin.kind === "photo") {
      const backing = new T.Mesh(new T.PlaneGeometry(1.62, 1.08), mat(0xffffff)); group.add(backing);
      const photo = new T.Mesh(new T.PlaneGeometry(1.5, 0.84), new T.MeshBasicMaterial({ color: 0xffffff }));
      photo.position.set(0, 0.06, 0.005); group.add(photo);
      loader.load(pin.img, (tex) => { photo.material.map = tex; photo.material.needsUpdate = true; });
    } else {
      const note = new T.Mesh(new T.PlaneGeometry(1.5, 1.125), new T.MeshLambertMaterial({ map: new T.CanvasTexture(paper(pin)) }));
      group.add(note);
    }
    const tack = new T.Mesh(new T.SphereGeometry(0.06, 14, 10), mat(0xc62828)); tack.position.set(0, 0.5, 0.05); group.add(tack);
    scene.add(group);
    spots[pin.id] = { pin, x, y, tack: new T.Vector3(x, y + 0.5, BZ + 0.1) };
  });

  // red string, sagging between the pins
  (board.links || []).forEach(([a, b]) => {
    if (!spots[a] || !spots[b]) return;
    const p1 = spots[a].tack, p2 = spots[b].tack;
    const mid = p1.clone().add(p2).multiplyScalar(0.5); mid.y -= 0.25; mid.z += 0.02;
    const curve = new T.QuadraticBezierCurve3(p1, mid, p2);
    const line = new T.Line(new T.BufferGeometry().setFromPoints(curve.getPoints(24)), new T.LineBasicMaterial({ color: 0xd32f2f }));
    scene.add(line);
  });

  return { renderer, scene, camera, kane, spots, pins, board: { W, H, BY, BZ } };
}

// ── the tour: wide shot, then each piece of evidence in turn, then wide again ────────────────
function shotsFor(world) {
  const { BY, BZ } = world.board;
  const wide = { pos: [0.7, 2.25, 5.2], look: [0.4, 1.7, BZ], line: "This is the case as it happened. Every piece on my board is real evidence." };
  const stops = world.pins.map((pin) => {
    const s = world.spots[pin.id];
    // aim a little low, so the evidence sits above Kane's dialogue box
    return { pos: [s.x * 0.8, s.y - 0.3, BZ + 1.75], look: [s.x, s.y - 0.28, BZ], line: kaneLine(pin), pin };
  });
  const last = world.pins[world.pins.length - 1];
  const end = { pos: [0.8, 2.2, 4.4], look: [0.5, 1.75, BZ],
    line: last && last.id === "closed" && last.stamp === "Case closed" ? "Case closed." : "That's the case so far." };
  return [wide, ...stops, end];
}

const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

function initRecon(section) {
  if (section.dataset.ready) return;
  section.dataset.ready = "1";
  const canvas = section.querySelector(".recon-canvas");
  const button = section.querySelector(".recon-play");
  const say = section.querySelector(".recon-say");
  const lineEl = section.querySelector(".recon-line");
  const board = JSON.parse(section.querySelector(".recon-data").textContent || "{}");
  let world = null, playing = false, typer = 0;

  const speakLine = (text) => {
    clearTimeout(typer);
    if (reconReduce) { lineEl.textContent = text; return; }
    let i = 0;
    const step = () => { lineEl.textContent = text.slice(0, ++i); if (i < text.length) typer = setTimeout(step, 16); };
    step();
  };
  const fit = () => {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    world.renderer.setSize(w, h, false);
    world.camera.aspect = w / h; world.camera.updateProjectionMatrix();
  };

  async function play() {
    if (playing) return;
    button.disabled = true;
    button.innerHTML = "<span>…</span> Setting up Kane's office";
    try {
      await loadThree();
      if (window.kaneRobot) await window.kaneRobot.loadEngine().catch(() => {});
      if (document.fonts) await Promise.all(["600 44px Caveat", "500 25px 'JetBrains Mono'", "800 58px Inter"].map((f) => document.fonts.load(f).catch(() => {})));
    } catch (err) {
      button.disabled = false;
      button.innerHTML = "<span>!</span> The 3D view couldn't load. Try again";
      return;
    }
    world ||= buildOffice(window.THREE, canvas, board);
    if (!world.robot && window.kaneRobot && window.THREE.GLTFLoader) {
      // the same Detective Kane as in his live office: swap the drawn stand-in for the robot
      try {
        const T = window.THREE;
        world.robot = await window.kaneRobot.loadKane(T, { scene: world.scene, DESK: new T.Vector3(2.7, 0, -0.9), YOU: -0.6 });
        world.scene.remove(world.kane);
        world.kane = world.robot.model;
      } catch (e) { /* keep the drawn detective */ }
    }
    if (world.robot) world.robot.play("Wave");  // he greets you as the tour starts
    fit();
    playing = true;
    section.classList.add("playing");
    button.hidden = true;
    say.hidden = false;
    const shots = shotsFor(world);
    const cam = world.camera, T = window.THREE;
    const from = new T.Vector3(), to = new T.Vector3(), lookFrom = new T.Vector3(), lookTo = new T.Vector3(), look = new T.Vector3();
    cam.position.set(...shots[0].pos); look.set(...shots[0].look); cam.lookAt(look);
    let index = 0, phaseStart = performance.now();
    const MOVE = reconReduce ? 0 : 1100;
    // each shot holds until Kane has finished his line, plus a moment to read it
    const hold = (i) => Math.max(2600, shots[i].line.length * 16 + 1500);
    speakLine(shots[0].line);
    let previous = performance.now(), cheered = false;
    const frame = (now) => {
      const dt = Math.min(0.1, (now - previous) / 1000); previous = now;
      if (world.robot) world.robot.mixer.update(dt);
      if (!playing) return;
      const elapsed = now - phaseStart;
      if (index < shots.length - 1 && elapsed > hold(index) + MOVE) {
        index += 1; phaseStart = now;
        from.copy(cam.position); to.set(...shots[index].pos);
        lookFrom.copy(look); lookTo.set(...shots[index].look);
        speakLine(shots[index].line);
        if (world.robot && !cheered && shots[index].line === "Case closed.") { cheered = true; world.robot.play("ThumbsUp"); }
      }
      if (index > 0 && MOVE) {
        const t = ease(Math.min(1, (now - phaseStart) / MOVE));
        cam.position.lerpVectors(from, to, t);
        look.lerpVectors(lookFrom, lookTo, t);
      } else if (index > 0) {
        cam.position.set(...shots[index].pos); look.set(...shots[index].look);
      }
      cam.lookAt(look);
      if (!reconReduce) world.kane.rotation.y = (world.robot ? -0.6 : -0.9) + Math.sin(now / 900) * 0.08;  // Kane looks around
      world.renderer.render(world.scene, cam);
      if (index === shots.length - 1 && now - phaseStart > MOVE + hold(index)) {
        playing = false;
        section.classList.remove("playing");
        button.hidden = false; button.disabled = false;
        button.innerHTML = "<span>↻</span> Play again";
        return;
      }
      requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
  }

  button.addEventListener("click", play);
  new ResizeObserver(() => { if (world) { fit(); world.renderer.render(world.scene, world.camera); } }).observe(canvas);
}

document.querySelectorAll("[data-recon]").forEach(initRecon);
window.initRecon = initRecon;

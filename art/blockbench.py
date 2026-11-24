"""A small Blockbench builder: models made of cubes, painted pixel by pixel.

Every model is written twice from the same description:
  - art/<name>.bbmodel: the Blockbench project (format 5.0, textures and animations inside). Open it
    in Blockbench to look at it, pose it or change it.
  - whisperer/static/models/bb/<name>.glb: what the website loads. It is laid out the way
    Blockbench's own glTF export lays it out: one node per group, placed at the group's pivot,
    16 units to a metre, animations under their own names.

Coordinates are Blockbench units (16 to a metre), Y up, with a model's front facing +Z (south).
Rotations are degrees, applied Z, then Y, then X (three.js order 'ZYX', Blockbench's default).
Faces are painted as seen from outside the cube, upright; the top face has north at the top.
A pixel left unpainted is see-through (a leaf's outline, say).
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import random
import struct
import uuid as uuidlib
import zlib
from dataclasses import dataclass, field

UNIT = 16           # Blockbench units in a metre
PX = 2              # texels per unit: every model shares one pixel size
PAD = 1             # texels of edge colour round each face in the atlas, so mipmaps don't bleed
FACES = ("north", "east", "south", "west", "up", "down")


# ── describing a model ──────────────────────────────────────────────────────────────────────────

@dataclass
class Cube:
    name: str
    at: tuple            # the corner with the smallest x, y and z
    size: tuple
    paint: object        # a painter, or {face or "sides"/"top"/"bottom"/"*": painter or None (no face)}
    rotate: tuple = (0, 0, 0)
    pivot: tuple | None = None   # what the cube turns around (default: its centre)
    glow: bool = False           # painted on the glow texture: it lights itself
    px: int | None = None        # texels a unit, where a face needs finer pixels (a poster's words)


@dataclass
class Group:
    name: str
    pivot: tuple
    children: list = field(default_factory=list)
    hidden: bool = False   # starts hidden (an alternative face, say); the page shows it when needed


@dataclass
class Animation:
    name: str
    length: float
    loop: str            # "loop", "once" or "hold"
    bones: dict          # {group name: {"rotation": [(t, x, y, z)], "position": [(t, x, y, z)]}}


@dataclass
class Model:
    name: str
    root: list
    animations: list = field(default_factory=list)


def cube(name, at, size, paint, **kw) -> Cube:
    return Cube(name, tuple(at), tuple(size), paint, **kw)


def group(name, pivot, *children, hidden=False) -> Group:
    return Group(name, tuple(pivot), list(children), hidden)


# ── painting ────────────────────────────────────────────────────────────────────────────────────

def rgb(col) -> tuple:
    if isinstance(col, str):
        col = col.lstrip("#")
        return tuple(int(col[i:i + 2], 16) for i in (0, 2, 4))
    return tuple(col)


def shade(col, k: float) -> tuple:
    return tuple(max(0, min(255, round(c * k))) for c in rgb(col))


# a 3x5 pixel font for signs and labels
FONT = {
    "A": "010101111101101", "B": "110101110101110", "C": "011100100100011", "D": "110101101101110",
    "E": "111100110100111", "F": "111100110100100", "G": "011100101101011", "H": "101101111101101",
    "I": "111010010010111", "J": "001001001101010", "K": "101101110101101", "L": "100100100100111",
    "M": "1000111011101011000110001", "N": "10011101101110011001", "O": "010101101101010", "P": "110101110100100",
    "Q": "010101101110011", "R": "110101110101101", "S": "011100010001110", "T": "111010010010010",
    "U": "101101101101111", "V": "101101101101010", "W": "1000110001101011010101010", "X": "101101010101101",
    "Y": "101101010010010", "Z": "111001010100111", "0": "111101101101111", "1": "010110010010111",
    "2": "110001010100111", "3": "110001010001110", "4": "101101111001001", "5": "111100110001110",
    "6": "011100111101111", "7": "111001010010010", "8": "111101111101111", "9": "111101111001110",
    " ": "000000000000000", "-": "000000111000000", ".": "000000000000010", "!": "010010010000010",
    "?": "110001010000010", "$": "011110010011110", "#": "101111101111101", ":": "000010000010000",
}


class Face:
    """One face of a cube, w x h texels, painted as seen from outside."""

    def __init__(self, name: str, w: int, h: int, rng: random.Random):
        self.name, self.w, self.h, self.rng = name, w, h, rng
        self.px = [[None] * w for _ in range(h)]

    @property
    def side(self) -> bool:
        return self.name not in ("up", "down")

    def set(self, x, y, col, jitter=0.0):
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h and col is not None:
            self.px[y][x] = shade(col, 1 + self.rng.uniform(-jitter, jitter)) if jitter else rgb(col)

    def get(self, x, y):
        return self.px[y][x]

    def rect(self, x, y, w, h, col, jitter=0.0):
        for j in range(int(h)):
            for i in range(int(w)):
                self.set(x + i, y + j, col, jitter)
        return self

    def fill(self, col, jitter=0.04):
        return self.rect(0, 0, self.w, self.h, col, jitter)

    def frame(self, col, t=1, jitter=0.0):
        self.rect(0, 0, self.w, t, col, jitter); self.rect(0, self.h - t, self.w, t, col, jitter)
        self.rect(0, 0, t, self.h, col, jitter); self.rect(self.w - t, 0, t, self.h, col, jitter)
        return self

    def box(self, x, y, w, h, col, t=1):
        """An outlined rectangle."""
        self.rect(x, y, w, t, col); self.rect(x, y + h - t, w, t, col)
        self.rect(x, y, t, h, col); self.rect(x + w - t, y, t, h, col)
        return self

    def hline(self, y, col, x0=0, x1=None, jitter=0.0):
        return self.rect(x0, y, (self.w if x1 is None else x1) - x0, 1, col, jitter)

    def vline(self, x, col, y0=0, y1=None, jitter=0.0):
        return self.rect(x, y0, 1, (self.h if y1 is None else y1) - y0, col, jitter)

    def speckle(self, col, amount, jitter=0.0):
        for y in range(self.h):
            for x in range(self.w):
                if self.rng.random() < amount:
                    self.set(x, y, col, jitter)
        return self

    def text(self, s, x, y, col, scale=1):
        for ch in s.upper():
            bits = FONT.get(ch, FONT["?"])
            w = len(bits) // 5
            for j in range(5):
                for i in range(w):
                    if bits[j * w + i] == "1":
                        self.rect(x + i * scale, y + j * scale, scale, scale, col)
            x += (w + 1) * scale
        return self

    @staticmethod
    def text_width(s, scale=1):
        return max(0, sum(len(FONT.get(ch, FONT["?"])) // 5 + 1 for ch in s.upper()) - 1) * scale


def painter_for(paint, face: str):
    """The face's painter, or None for a face that isn't there (a wall's back, say)."""
    if callable(paint):
        return paint
    alias = {"up": "top", "down": "bottom"}.get(face, "sides")
    for key in (face, alias, "*"):
        if key in paint:
            return paint[key]
    return lambda f: f.fill("#808080")


# ── geometry ────────────────────────────────────────────────────────────────────────────────────

def quat(deg) -> tuple:
    """Euler degrees (order ZYX, as three.js and Blockbench) to a quaternion (x, y, z, w)."""
    x, y, z = (math.radians(a) / 2 for a in deg)
    c1, c2, c3, s1, s2, s3 = math.cos(x), math.cos(y), math.cos(z), math.sin(x), math.sin(y), math.sin(z)
    return (s1 * c2 * c3 - c1 * s2 * s3, c1 * s2 * c3 + s1 * c2 * s3,
            c1 * c2 * s3 - s1 * s2 * c3, c1 * c2 * c3 + s1 * s2 * s3)


def turn(q, v) -> tuple:
    x, y, z, w = q
    vx, vy, vz = v
    ix, iy, iz, iw = w * vx + y * vz - z * vy, w * vy + z * vx - x * vz, w * vz + x * vy - y * vx, -x * vx - y * vy - z * vz
    return (ix * w + iw * -x + iy * -z - iz * -y, iy * w + iw * -y + iz * -x - ix * -z, iz * w + iw * -z + ix * -y - iy * -x)


def corners(c: Cube, face: str):
    """The face's corners: top-left, top-right, bottom-left, bottom-right, as seen from outside."""
    (x0, y0, z0), (w, h, d) = c.at, c.size
    x1, y1, z1 = x0 + w, y0 + h, z0 + d
    return {
        "south": [(x0, y1, z1), (x1, y1, z1), (x0, y0, z1), (x1, y0, z1)],
        "north": [(x1, y1, z0), (x0, y1, z0), (x1, y0, z0), (x0, y0, z0)],
        "east": [(x1, y1, z1), (x1, y1, z0), (x1, y0, z1), (x1, y0, z0)],
        "west": [(x0, y1, z0), (x0, y1, z1), (x0, y0, z0), (x0, y0, z1)],
        "up": [(x0, y1, z0), (x1, y1, z0), (x0, y1, z1), (x1, y1, z1)],
        "down": [(x0, y0, z1), (x1, y0, z1), (x0, y0, z0), (x1, y0, z0)],
    }[face]


NORMALS = {"south": (0, 0, 1), "north": (0, 0, -1), "east": (1, 0, 0), "west": (-1, 0, 0), "up": (0, 1, 0), "down": (0, -1, 0)}


def face_texels(c: Cube, face: str) -> tuple:
    w, h, d = c.size
    u, v = {"south": (w, h), "north": (w, h), "east": (d, h), "west": (d, h), "up": (w, d), "down": (w, d)}[face]
    k = c.px or PX
    return max(1, round(u * k)), max(1, round(v * k))


def has_area(c: Cube, face: str) -> bool:
    w, h, d = c.size
    u, v = {"south": (w, h), "north": (w, h), "east": (d, h), "west": (d, h), "up": (w, d), "down": (w, d)}[face]
    return u > 0 and v > 0


# ── textures ────────────────────────────────────────────────────────────────────────────────────

def png(pixels: list, size: int) -> bytes:
    raw = b"".join(b"\x00" + bytes(v for p in row for v in (p + (255,) if p else (0, 0, 0, 0))) for row in pixels)
    chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def pack(rects: list) -> int:
    """Shelf-pack rects (with .w, .h) into the smallest square power-of-two atlas; sets .x, .y."""
    size = 16
    while True:
        x = y = row = 0
        fits = True
        for r in sorted(rects, key=lambda r: (-r.h, -r.w)):
            w, h = r.w + 2 * PAD, r.h + 2 * PAD
            if w > size:
                fits = False; break
            if x + w > size:
                x, y, row = 0, y + row, 0
            r.x, r.y = x + PAD, y + PAD
            x += w; row = max(row, h)
        if fits and y + row <= size:
            return size
        size *= 2
        if size > 2048:
            raise ValueError("the atlas would be over 2048 px")


@dataclass
class Slot:
    cube: Cube
    face: str
    w: int
    h: int
    x: int = 0
    y: int = 0


def paint_atlas(model_name: str, slots: list) -> tuple:
    size = pack(slots)
    img = [[None] * size for _ in range(size)]
    for s in slots:
        seed = int(hashlib.sha256(f"{model_name}/{s.cube.name}/{s.face}".encode()).hexdigest()[:12], 16)
        f = Face(s.face, s.w, s.h, random.Random(seed))
        painter_for(s.cube.paint, s.face)(f)
        for j in range(-PAD, s.h + PAD):           # the face, its edge colour carried into the padding
            for i in range(-PAD, s.w + PAD):
                img[s.y + j][s.x + i] = f.px[min(s.h - 1, max(0, j))][min(s.w - 1, max(0, i))]
    return size, img


# ── building ────────────────────────────────────────────────────────────────────────────────────

def stable_uuid(*parts) -> str:
    return str(uuidlib.uuid5(uuidlib.NAMESPACE_URL, "bug-whisperer/" + "/".join(parts)))


def walk(nodes, parent=None, out=None):
    """Every group in order, with its parent group."""
    out = [] if out is None else out
    for n in nodes:
        if isinstance(n, Group):
            out.append((n, parent))
            walk(n.children, n, out)
    return out


def build(model: Model) -> tuple[dict, bytes]:
    """The model as a .bbmodel (a dict to save as JSON) and a .glb (bytes)."""
    groups = walk(model.root)
    names = [g.name for g, _ in groups]
    if len(set(names)) != len(names):
        raise ValueError(f"{model.name}: group names must be unique")
    for n in model.root:
        if not isinstance(n, Group):
            raise ValueError(f"{model.name}: put {n.name} in a group")
    cubes = [(c, g) for g, _ in groups for c in g.children if isinstance(c, Cube)]

    slots = {"main": [], "glow": []}
    for c, _ in cubes:
        for f in FACES:
            if has_area(c, f) and painter_for(c.paint, f) is not None:
                slots["glow" if c.glow else "main"].append(Slot(c, f, *face_texels(c, f)))
    textures = []   # (key, size, png bytes)
    where = {}      # (cube id, face) -> (texture index, slot, size)
    for key in ("main", "glow"):
        if not slots[key]:
            continue
        size, img = paint_atlas(f"{model.name}/{key}", slots[key])
        index = len(textures)
        textures.append((key, size, png(img, size)))
        for s in slots[key]:
            where[(id(s.cube), s.face)] = (index, s, size)
    return bbmodel(model, groups, cubes, textures, where), glb(model, groups, textures, where)


def bbmodel(model, groups, cubes, textures, where) -> dict:
    gid = {g.name: stable_uuid(model.name, "group", g.name) for g, _ in groups}
    elements = []
    for c, g in cubes:
        (x0, y0, z0), (w, h, d) = c.at, c.size
        centre = (x0 + w / 2, y0 + h / 2, z0 + d / 2)
        faces = {}
        for f in FACES:
            if (id(c), f) in where:
                tex, s, _ = where[(id(c), f)]
                faces[f] = {"uv": [s.x, s.y, s.x + s.w, s.y + s.h], "texture": tex}
            else:
                faces[f] = {"uv": [0, 0, 0, 0], "texture": None}
        el = {"name": c.name, "box_uv": False, "rescale": False, "locked": False, "light_emission": 0,
              "render_order": "default", "allow_mirror_modeling": True,
              "from": [x0, y0, z0], "to": [x0 + w, y0 + h, z0 + d], "autouv": 0, "color": 0,
              "origin": list(c.pivot or centre), "faces": faces, "type": "cube",
              "uuid": stable_uuid(model.name, "cube", g.name, c.name, str(c.at))}
        if any(c.rotate):
            el["rotation"] = list(c.rotate)
        elements.append(el)

    def outline(nodes):
        out = []
        for n in nodes:
            if isinstance(n, Group):
                out.append({"uuid": gid[n.name], "isOpen": True, "children": outline(n.children)})
            else:
                owner = next(g for c, g in cubes if c is n)
                out.append(stable_uuid(model.name, "cube", owner.name, n.name, str(n.at)))
        return out

    tex = []
    for i, (key, size, data) in enumerate(textures):
        tex.append({"path": "", "name": f"{model.name}{'' if key == 'main' else '_' + key}.png", "folder": "",
                    "namespace": "", "id": str(i), "group": "", "width": size, "height": size,
                    "uv_width": size, "uv_height": size, "particle": False, "use_as_default": False,
                    "layers_enabled": False, "sync_to_project": "",
                    "render_mode": "emissive" if key == "glow" else "default", "render_sides": "auto",
                    "pbr_channel": "color", "frame_time": 1, "frame_order_type": "loop", "frame_order": "",
                    "frame_interpolate": False, "visible": True, "internal": True, "saved": False,
                    "uuid": stable_uuid(model.name, "texture", key),
                    "source": "data:image/png;base64," + base64.b64encode(data).decode()})

    animations = []
    for a in model.animations:
        animators = {}
        for bone, channels in a.bones.items():
            keys = []
            for channel, frames in channels.items():
                for t, x, y, z in frames:
                    keys.append({"channel": channel, "data_points": [{"x": x, "y": y, "z": z}],
                                 "uuid": stable_uuid(model.name, a.name, bone, channel, str(t)),
                                 "time": t, "color": -1, "interpolation": "linear"})
            animators[gid[bone]] = {"name": bone, "type": "bone", "keyframes": keys}
        animations.append({"uuid": stable_uuid(model.name, "animation", a.name), "name": a.name, "loop": a.loop,
                           "override": False, "length": a.length, "snapping": 24, "selected": False,
                           "anim_time_update": "", "blend_weight": "", "start_delay": "", "loop_delay": "",
                           "animators": animators})

    main = textures[0][1] if textures else 16
    return {
        "meta": {"format_version": "5.0", "model_format": "free", "box_uv": False},
        "name": model.name, "model_identifier": "", "visible_box": [1, 1, 0],
        "variable_placeholders": "", "variable_placeholder_buttons": [], "timeline_setups": [],
        "unhandled_root_fields": {},
        "resolution": {"width": main, "height": main},
        "elements": elements,
        "groups": [{"name": g.name, "origin": list(g.pivot), "color": 0, "nbt": "{}", "uuid": gid[g.name],
                    "export": True, "mirror_uv": False, "isOpen": True, "locked": False,
                    "visibility": not g.hidden, "autouv": 0, "selected": False} for g, _ in groups],
        "outliner": outline(model.root),
        "textures": tex,
        "animations": animations,
    }


class Bin:
    """The .glb's binary chunk: accessors and buffer views, 4-byte aligned."""

    def __init__(self):
        self.data = bytearray()
        self.views, self.accessors = [], []

    def view(self, raw: bytes, target=None) -> int:
        while len(self.data) % 4:
            self.data.append(0)
        v = {"buffer": 0, "byteOffset": len(self.data), "byteLength": len(raw)}
        if target:
            v["target"] = target
        self.data += raw
        self.views.append(v)
        return len(self.views) - 1

    def floats(self, rows: list, kind: str, target=None, bounds=False) -> int:
        n = len(rows[0])
        acc = {"bufferView": self.view(struct.pack(f"<{len(rows) * n}f", *(v for r in rows for v in r)), target),
               "componentType": 5126, "count": len(rows), "type": kind}
        if bounds:
            acc["min"] = [min(r[i] for r in rows) for i in range(n)]
            acc["max"] = [max(r[i] for r in rows) for i in range(n)]
        self.accessors.append(acc)
        return len(self.accessors) - 1

    def indices(self, idx: list) -> int:
        fmt, comp = ("H", 5123) if max(idx) < 65536 else ("I", 5125)
        self.accessors.append({"bufferView": self.view(struct.pack(f"<{len(idx)}{fmt}", *idx), 34963),
                               "componentType": comp, "count": len(idx), "type": "SCALAR"})
        return len(self.accessors) - 1


def glb(model, groups, textures, where) -> bytes:
    b = Bin()
    index = {g.name: i for i, (g, _) in enumerate(groups)}
    nodes, meshes = [], []
    images, gltf_textures, materials = [], [], []
    for i, (key, size, data) in enumerate(textures):
        images.append({"bufferView": b.view(data), "mimeType": "image/png", "name": f"{model.name}_{key}"})
        gltf_textures.append({"sampler": 0, "source": i})
        mat = {"name": f"{model.name}_{key}", "pbrMetallicRoughness": {
            "baseColorTexture": {"index": i}, "metallicFactor": 0, "roughnessFactor": 1},
            "alphaMode": "MASK", "alphaCutoff": 0.5}
        if key == "glow":   # it shows its own colours, whatever the light
            mat["pbrMetallicRoughness"]["baseColorFactor"] = [0, 0, 0, 1]
            mat["emissiveTexture"] = {"index": i}
            mat["emissiveFactor"] = [1, 1, 1]
        materials.append(mat)

    for g, parent in groups:
        origin = parent.pivot if parent else (0, 0, 0)
        node = {"name": g.name, "translation": [(g.pivot[k] - origin[k]) / UNIT for k in range(3)]}
        kids = [index[c.name] for c in g.children if isinstance(c, Group)]
        if kids:
            node["children"] = kids
        if g.hidden:
            node["extras"] = {"hidden": True}
        prims = {}
        for c in (c for c in g.children if isinstance(c, Cube)):
            q = quat(c.rotate) if any(c.rotate) else None
            (x0, y0, z0), (w, h, d) = c.at, c.size
            pivot = c.pivot or (x0 + w / 2, y0 + h / 2, z0 + d / 2)
            for f in FACES:
                if (id(c), f) not in where:
                    continue
                tex, s, size = where[(id(c), f)]
                p = prims.setdefault(tex, {"pos": [], "nrm": [], "uv": [], "idx": []})
                base = len(p["pos"])
                n = NORMALS[f]
                if q:
                    n = turn(q, n)
                uvs = [(s.x, s.y), (s.x + s.w, s.y), (s.x, s.y + s.h), (s.x + s.w, s.y + s.h)]
                for corner, (u, v) in zip(corners(c, f), uvs):
                    if q:
                        rel = turn(q, tuple(corner[k] - pivot[k] for k in range(3)))
                        corner = tuple(rel[k] + pivot[k] for k in range(3))
                    p["pos"].append(tuple((corner[k] - g.pivot[k]) / UNIT for k in range(3)))
                    p["nrm"].append(n)
                    p["uv"].append((u / size, v / size))
                p["idx"] += [base, base + 2, base + 3, base, base + 3, base + 1]
        if prims:
            primitives = []
            for tex in sorted(prims):
                p = prims[tex]
                primitives.append({"attributes": {
                    "POSITION": b.floats(p["pos"], "VEC3", 34962, bounds=True),
                    "NORMAL": b.floats(p["nrm"], "VEC3", 34962),
                    "TEXCOORD_0": b.floats(p["uv"], "VEC2", 34962)},
                    "indices": b.indices(p["idx"]), "material": tex})
            node["mesh"] = len(meshes)
            meshes.append({"name": g.name, "primitives": primitives})
        nodes.append(node)

    animations = []
    for a in model.animations:
        channels, samplers = [], []
        for bone, chans in a.bones.items():
            g = groups[index[bone]][0]
            rest = nodes[index[bone]]["translation"]
            for channel, frames in chans.items():
                times = [(t,) for t, *_ in frames]
                if channel == "rotation":
                    values, prev = [], None
                    for _, x, y, z in frames:
                        q = quat((x, y, z))
                        if prev and sum(q[k] * prev[k] for k in range(4)) < 0:
                            q = tuple(-v for v in q)   # the short way round
                        values.append(q); prev = q
                    kind, path = "VEC4", "rotation"
                else:
                    values = [tuple(rest[k] + v / UNIT for k, v in enumerate((x, y, z))) for _, x, y, z in frames]
                    kind, path = "VEC3", "translation"
                samplers.append({"input": b.floats(times, "SCALAR", bounds=True), "output": b.floats(values, kind),
                                 "interpolation": "LINEAR"})
                channels.append({"sampler": len(samplers) - 1, "target": {"node": index[g.name], "path": path}})
        animations.append({"name": a.name, "channels": channels, "samplers": samplers})

    doc = {"asset": {"version": "2.0", "generator": "Bug Whisperer art/blockbench.py"},
           "scene": 0, "scenes": [{"name": model.name, "nodes": [index[g.name] for g in model.root]}],
           "nodes": nodes, "meshes": meshes, "materials": materials, "textures": gltf_textures,
           "images": images,
           # crisp pixels up close, smooth from far away
           "samplers": [{"magFilter": 9728, "minFilter": 9986, "wrapS": 33071, "wrapT": 33071}],
           "accessors": b.accessors, "bufferViews": b.views, "buffers": [{"byteLength": len(b.data)}]}
    if animations:
        doc["animations"] = animations
    js = json.dumps(doc, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    bin_ = bytes(b.data) + b"\x00" * (-len(b.data) % 4)
    total = 12 + 8 + len(js) + 8 + len(bin_)
    return (struct.pack("<4sII", b"glTF", 2, total) + struct.pack("<I4s", len(js), b"JSON") + js
            + struct.pack("<I4s", len(bin_), b"BIN\x00") + bin_)

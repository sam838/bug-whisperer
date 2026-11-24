"""Every 3D model in Bug Whisperer, as Blockbench cubes and hand-placed pixels.

    python art/models.py      writes art/<name>.bbmodel and whisperer/static/models/bb/<name>.glb

Units are Blockbench units: 16 to a metre, Y up, the front of each model facing +Z. The sizes
match the spots kane3d.js, lineup3d.js and recon.js give them (the desk's top is at 0.79 m, Kane
sits on the armchair's cushion, the office's back wall is at z = -3 m, and so on), so change a size
here and there together.

To change a model by hand instead, open art/<name>.bbmodel in Blockbench, edit it, and use
File > Export > Export glTF Model into whisperer/static/models/bb/<name>.glb. Keep the group and
animation names (the scenes look them up), and take that model out of all_models() below, or
the next run of this script will write over your work.
"""
from __future__ import annotations

import json
import math
import random
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blockbench import Animation, Cube, Model, build, cube, group, shade  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
GLB_DIR = ROOT / "whisperer" / "static" / "models" / "bb"


# ── painters ────────────────────────────────────────────────────────────────────────────────────

def plain(col, j=0.05):
    return lambda f: f.fill(col, j)


def layers(*painters):
    def paint(f):
        for p in painters:
            p(f)
    return paint


def edge(col, t=1):
    return lambda f: f.frame(col, t)


def grain(col, across=True, j=0.04, k=0.84):
    """Wood: streaks of darker and lighter grain, across the face or down it."""
    def paint(f):
        f.fill(col, j)
        dark, light = shade(col, k), shade(col, 1.1)
        lines = f.h if across else f.w
        length = f.w if across else f.h
        for n in range(lines):
            if f.rng.random() < 0.45:
                a = f.rng.randrange(length); b = min(length, a + f.rng.randint(3, 12))
                c = dark if f.rng.random() < 0.7 else light
                for m in range(a, b):
                    f.set(m, n, c) if across else f.set(n, m, c)
    return paint


def leather(col):
    return lambda f: f.fill(col, 0.04).speckle(shade(col, 1.12), 0.04).speckle(shade(col, 0.88), 0.03)


def metal(col):
    return lambda f: f.fill(col, 0.03).speckle(shade(col, 1.15), 0.05)


def knit(col):
    def paint(f):
        f.fill(col, 0.04)
        for y in range(0, f.h, 2):
            f.hline(y, shade(col, 0.85), jitter=0.04)
    return paint


def tufted(col, step=4):
    """Buttoned leather: a grid of buttons with creases."""
    def paint(f):
        leather(col)(f)
        for y in range(step // 2, f.h, step):
            for x in range(step // 2 + (y // step) % 2 * (step // 2), f.w, step):
                f.set(x, y, shade(col, 0.55)); f.set(x + 1, y, shade(col, 1.25))
    return paint


def studded(col, stud="#c9a24e"):
    """Leather with a row of brass studs round the edge."""
    def paint(f):
        leather(col)(f)
        for x in range(1, f.w - 1, 2):
            f.set(x, 1, stud); f.set(x, f.h - 2, stud)
        for y in range(1, f.h - 1, 2):
            f.set(1, y, stud); f.set(f.w - 2, y, stud)
    return paint


# ── Detective Kane ──────────────────────────────────────────────────────────────────────────────
# A robot detective: an old CRT monitor for a head (his eyes glow on its screen), a trench coat
# belted at the waist, a red scarf, a felt fedora, and a magnifying glass in his right hand.

COAT, COAT_DARK, COAT_LIGHT = "#b38955", "#8a6440", "#c9a06a"
BELT, BRASS = "#4a3020", "#d4a94a"
SCARF, SCARF_DARK = "#a8262f", "#781a22"
TROUSERS, SHOE = "#2c2f3a", "#2a1b13"
STEEL, STEEL_DARK = "#8b93a3", "#5b6373"
CASE, CASE_DARK = "#d9cfb6", "#b2a78c"
SCREEN, EYE = "#0d2a2d", "#7af5e6"
FELT, FELT_DARK, BAND = "#5a3b28", "#462d1e", "#1d1410"


def coat_front(f):
    f.fill(COAT, 0.04)
    mid = f.w // 2
    for y in range(7):                                  # the V of the open collar: his steel chest
        half = max(0, 4 - y * 0.7)
        f.rect(mid - half, y, half * 2, 1, STEEL_DARK)
        f.set(mid - half - 1, y, COAT_DARK); f.set(mid + half, y, COAT_DARK)
        f.set(mid - half - 2, y, COAT_LIGHT); f.set(mid + half + 1, y, COAT_LIGHT)
    f.vline(mid, COAT_DARK, 5, f.h - 4)
    for y in (7, 10):                                   # double-breasted buttons
        f.set(mid - 3, y, BELT); f.set(mid + 2, y, BELT)
    f.rect(0, f.h - 4, f.w, 2, BELT, 0.05)              # the belt and its buckle
    f.box(mid - 2, f.h - 5, 4, 4, BRASS)


def coat_back(f):
    f.fill(COAT, 0.04)
    f.rect(0, f.h - 4, f.w, 2, BELT, 0.05)
    f.hline(4, COAT_DARK)                               # the storm flap across the shoulders
    f.vline(f.w // 2, COAT_DARK, 8, f.h - 4)


def coat_side(f):
    f.fill(COAT, 0.04)
    f.rect(0, f.h - 4, f.w, 2, BELT, 0.05)


def coat_skirt(f):
    f.fill(COAT, 0.04)
    f.hline(f.h - 1, COAT_DARK)
    if f.name == "south":
        f.vline(f.w - 1 if f.w > 4 else 0, COAT_DARK)


def sleeve(f):
    f.fill(COAT, 0.04)
    if f.side:
        f.hline(f.h - 2, COAT_DARK)                     # the cuff strap


def monitor(f):
    f.fill(CASE, 0.03)
    if f.name in ("east", "west"):                      # vents
        for y in range(3, f.h - 3, 2):
            f.hline(y, CASE_DARK, 3, f.w - 3)
    elif f.name == "north":
        f.frame(CASE_DARK)
    elif f.name == "south":
        f.frame(CASE_DARK)
        f.set(f.w - 3, f.h - 2, "#3ad06a")              # the power light


def screen(f):
    f.fill(SCREEN, 0.06)
    for y in range(0, f.h, 2):                          # scan lines
        f.hline(y, shade(SCREEN, 1.25), jitter=0.05)


def eye(f):
    f.fill(EYE, 0.03)


def hat_crown(f):
    f.fill(FELT, 0.05)
    if f.side:
        f.rect(0, f.h - 3, f.w, 2, BAND)                # the hat band
    else:
        f.rect(f.w // 2 - 3, 1, 6, f.h - 2, FELT_DARK)  # the pinch on top


def lens(f):
    if f.name in ("east", "west"):
        f.fill("#bfe3ff", 0.04)
        f.frame(BRASS)
        f.set(2, 2, "#ffffff"); f.set(3, 2, "#ffffff"); f.set(2, 3, "#ffffff")
    else:
        f.fill(BRASS, 0.05)


def mirror(cubes_or_groups, swap=("left", "right")):
    """The same parts on the other side (x mirrored), with left and right swapped in the names."""
    out = []
    for n in cubes_or_groups:
        name = n.name.replace(swap[0], swap[1])
        if isinstance(n, Cube):
            (x, y, z), (w, h, d) = n.at, n.size
            out.append(replace(n, name=name, at=(-(x + w), y, z)))
        else:
            px, py, pz = n.pivot
            out.append(replace(n, name=name, pivot=(-px, py, pz), children=mirror(n.children, swap)))
    return out


def kane() -> Model:
    shoe = {"up": plain(SHOE), "*": layers(plain(SHOE), lambda f: f.hline(f.h - 1, "#140c08") if f.side else None)}
    leg_left = group("thigh_left", (2.25, 13, 0),
        cube("coat_left", (0.05, 8, -2.45), (4.4, 5, 4.9), coat_skirt),
        cube("trouser_left", (0.75, 7, -1.5), (3, 1.5, 3), plain(TROUSERS)),
        group("shin_left", (2.25, 7, 0),
            cube("shin_left", (0.75, 1.5, -1.5), (3, 5.5, 3), plain(TROUSERS)),
            cube("shoe_left", (0.5, 0, -2), (3.5, 1.5, 4.75), shoe)))
    arm_left = group("arm_left", (5.75, 20.5, 0),
        cube("sleeve_left", (4.5, 14.5, -1.5), (2.75, 6.5, 3), {"*": plain(COAT)}),
        group("forearm_left", (5.875, 14.5, 0),
            cube("cuff_left", (4.6, 9.5, -1.4), (2.55, 5, 2.8), sleeve),
            cube("hand_left", (4.75, 7.5, -1.25), (2.25, 2, 2.5), metal(STEEL)),
            cube("thumb_left", (4.25, 8.5, 0.5), (0.75, 1.5, 0.75), metal(STEEL))))
    legs_right = mirror([leg_left])
    arm_right = mirror([arm_left])[0]
    # the right hand holds the magnifying glass out in front
    arm_right.children[1].children[-1:] = [
        cube("lens_handle", (-6.25, 8.1, 1.0), (0.75, 0.75, 3.25), grain("#3a2416")),
        cube("lens", (-6.65, 6.6, 4.1), (0.8, 3.75, 3.75), lens)]
    head = group("head", (0, 21, 0),
        cube("neck", (-1, 21, -1), (2, 1.5, 2), metal(STEEL_DARK)),
        cube("monitor", (-4, 22, -3.5), (8, 6.5, 7), monitor),
        cube("tube", (-3, 23, -5), (6, 4.5, 1.5), layers(plain(CASE_DARK), edge(shade(CASE_DARK, 0.85)))),
        cube("screen", (-3.25, 22.75, 3.5), (6.5, 5, 0.25), screen, glow=True),
        group("eyes", (0, 25, 3.75),
            cube("eye_left", (0.5, 24.75, 3.75), (1.75, 1.25, 0.25), eye, glow=True),
            cube("eye_right", (-2.25, 24.75, 3.75), (1.75, 1.25, 0.25), eye, glow=True),
            cube("mouth", (-1, 23.5, 3.75), (2, 0.5, 0.25), eye, glow=True)),
        group("eyes_surprised", (0, 25, 3.75),
            cube("wide_left", (0.5, 24.25, 3.75), (2, 2, 0.25), eye, glow=True),
            cube("wide_right", (-2.5, 24.25, 3.75), (2, 2, 0.25), eye, glow=True),
            cube("gasp", (-0.5, 23.25, 3.75), (1, 0.75, 0.25), eye, glow=True), hidden=True),
        cube("brim", (-5.5, 28.5, -5.25), (11, 0.75, 10.5), {"up": plain(FELT), "down": plain(FELT_DARK),
                                                              "*": plain(FELT_DARK)}),
        cube("crown", (-3.5, 29.25, -3.25), (7, 2.75, 6.5), hat_crown))
    torso = group("torso", (0, 13, 0),
        cube("coat", (-4.5, 13, -2.5), (9, 8, 5), {"south": coat_front, "north": coat_back, "*": coat_side}),
        cube("scarf", (-3.75, 20, -2.75), (7.5, 1.75, 5.5), knit(SCARF)),
        cube("scarf_tail", (0.75, 15.25, 2.5), (2, 5, 0.5),
             layers(knit(SCARF), lambda f: f.hline(f.h - 1, SCARF_DARK))),
        head, arm_left, arm_right)
    body = group("body", (0, 13, 0), torso, leg_left, *legs_right)
    return Model("kane", [group("kane", (0, 0, 0), body)], kane_animations())


def keys(*frames):
    return [tuple(f) for f in frames]


def eased(frames, fps=24):
    """Keyframes eased in and out of each pose (a smooth step), sampled for a linear player."""
    out = []
    for (t0, *a), (t1, *b) in zip(frames, frames[1:]):
        if a == b:                                       # a held pose needs no samples
            out.append((t0, *a)); continue
        n = max(1, round((t1 - t0) * fps))
        for i in range(n):
            k = i / n
            s = k * k * (3 - 2 * k)
            out.append((round(t0 + (t1 - t0) * k, 4), *(round(p + (q - p) * s, 3) for p, q in zip(a, b))))
    out.append(tuple(frames[-1]))
    return out


def cycle(fn, length=1.0, n=24):
    """A looping move from a function of the phase (0 to 1), sampled n times."""
    return [(round(length * i / n, 4), *(round(v, 3) for v in fn(i / n))) for i in range(n + 1)]


def kane_animations() -> list:
    rest_r = -20   # the right forearm holds the glass a little forward
    tau, cos, sin = 2 * math.pi, math.cos, math.sin
    swing = lambda t, lag=0.0: cos(tau * t - lag)
    bend = lambda t: max(0.0, -sin(tau * t + 0.4)) ** 1.3        # the knee folds early in the swing

    # a walk cycle: left foot down at 0, right foot down at 0.5. The hips drop as each foot lands,
    # twist with the legs while the shoulders twist back, and the arms swing a beat behind.
    walk = {
        "body": {"position": cycle(lambda t: (0, -0.5 - 0.5 * cos(2 * tau * t), 0)),
                 "rotation": cycle(lambda t: (0, -4 * swing(t), -2 * sin(tau * t)))},
        "torso": {"rotation": cycle(lambda t: (3, 7 * swing(t), 2 * sin(tau * t)))},
        "head": {"rotation": cycle(lambda t: (-3 + 1.2 * cos(2 * tau * t), -3 * swing(t), 0))},
        "thigh_left": {"rotation": cycle(lambda t: (-26 * swing(t), 0, 0))},
        "thigh_right": {"rotation": cycle(lambda t: (26 * swing(t), 0, 0))},
        "shin_left": {"rotation": cycle(lambda t: (5 + 55 * bend(t), 0, 0))},
        "shin_right": {"rotation": cycle(lambda t: (5 + 55 * bend(t + 0.5), 0, 0))},
        "arm_left": {"rotation": cycle(lambda t: (20 * swing(t, 0.35), 0, 4))},
        "arm_right": {"rotation": cycle(lambda t: (-12 * swing(t, 0.35), 0, -4))},
        "forearm_left": {"rotation": cycle(lambda t: (-12 - 16 * max(0, -swing(t, 0.8)), 0, 0))},
        "forearm_right": {"rotation": cycle(lambda t: (rest_r - 8 * max(0, swing(t, 0.8)), 0, 0))},
    }
    # standing about: he breathes, looks round the room, and lifts his glass for a closer look
    idle = {
        "body": {"position": eased(keys((0, 0, 0, 0), (1, 0, -0.25, 0), (2, 0, 0, 0), (3, 0, -0.25, 0), (4, 0, 0, 0)))},
        "torso": {"rotation": eased(keys((0, 0, 0, 0), (1, 1.5, 0, 0), (2, 0, 0, 0), (3, 1.5, 0, 0), (4, 0, 0, 0)))},
        "head": {"rotation": eased(keys((0, 0, 0, 0), (0.8, 0, 0, 0), (1.4, 2, 14, 0), (2.2, 2, 14, 0),
                                        (2.8, 6, -4, 3), (3.4, 6, -4, 3), (4, 0, 0, 0)))},
        "arm_left": {"rotation": eased(keys((0, 0, 0, 3), (2, 0, 0, 5), (4, 0, 0, 3)))},
        "arm_right": {"rotation": eased(keys((0, 0, 0, -3), (2.2, 0, 0, -4), (2.6, -14, 0, -4), (3.4, -14, 0, -4),
                                             (4, 0, 0, -3)))},
        "forearm_right": {"rotation": eased(keys((0, rest_r, 0, 0), (2.2, rest_r, 0, 0), (2.6, rest_r - 25, 0, 0),
                                                 (3.4, rest_r - 25, 0, 0), (4, rest_r, 0, 0)))},
    }
    # seated: the hips drop onto the armchair's cushion (5 units up), hands on the keyboard
    sit_pose = {"body": ("position", (0, -5.6, 0)), "thigh_left": ("rotation", (-90, 0, 0)),
                "thigh_right": ("rotation", (-90, 0, 0)), "shin_left": ("rotation", (90, 0, 0)),
                "shin_right": ("rotation", (90, 0, 0)), "arm_left": ("rotation", (-70, 0, 0)),
                "arm_right": ("rotation", (-70, 0, 0)), "forearm_left": ("rotation", (-30, 0, 0)),
                "forearm_right": ("rotation", (-30, 0, 0)), "torso": ("rotation", (4, 0, 0))}
    stand_pose = {bone: (ch, (rest_r, 0, 0) if bone == "forearm_right" else (0, 0, 0))
                  for bone, (ch, _) in sit_pose.items()}

    def between(a, b, length):
        return {bone: {ch: eased(keys((0, *a[bone][1]), (length, *b[bone][1])))} for bone, (ch, _) in a.items()}

    once = lambda bone, ch, *frames: {bone: {ch: eased(keys(*frames))}}
    return [
        Animation("Idle", 4.0, "loop", idle),
        Animation("Walking", 1.0, "loop", walk),
        Animation("Sitting", 0.7, "hold", between(stand_pose, sit_pose, 0.7)),
        Animation("Standing", 0.6, "hold", between(sit_pose, stand_pose, 0.6)),
        Animation("Yes", 1.2, "once", {
            **once("head", "rotation", (0, 0, 0, 0), (0.2, 18, 0, 0), (0.4, -2, 0, 0), (0.6, 16, 0, 0), (0.85, 0, 0, 0),
                   (1.2, 0, 0, 0)),
            **once("torso", "rotation", (0, 0, 0, 0), (0.2, 3, 0, 0), (0.85, 0, 0, 0), (1.2, 0, 0, 0))}),
        Animation("No", 1.4, "once", {
            **once("head", "rotation", (0, 0, 0, 0), (0.2, 4, 25, 0), (0.45, 4, -25, 0), (0.7, 4, 22, 0),
                   (0.95, 4, -18, 0), (1.2, 0, 0, 0), (1.4, 0, 0, 0)),
            **once("torso", "rotation", (0, 0, 0, 0), (0.3, 0, 5, 0), (0.7, 0, -5, 0), (1.2, 0, 0, 0), (1.4, 0, 0, 0))}),
        # he jabs with his free (left) hand: pressing a pin in, or pointing out the culprit
        Animation("Punch", 0.8, "once", {
            **once("arm_left", "rotation", (0, 0, 0, 0), (0.15, -30, 0, 0), (0.3, -90, 0, 0), (0.5, -90, 0, 0), (0.8, 0, 0, 0)),
            **once("forearm_left", "rotation", (0, 0, 0, 0), (0.15, -70, 0, 0), (0.3, 0, 0, 0), (0.5, 0, 0, 0), (0.8, 0, 0, 0)),
            **once("torso", "rotation", (0, 0, 0, 0), (0.3, 4, -12, 0), (0.5, 4, -12, 0), (0.8, 0, 0, 0)),
            **once("forearm_right", "rotation", (0, rest_r, 0, 0), (0.8, rest_r, 0, 0))}),
        Animation("ThumbsUp", 1.6, "once", {
            **once("arm_left", "rotation", (0, 0, 0, 0), (0.3, -50, 0, 0), (1.3, -50, 0, 0), (1.6, 0, 0, 0)),
            **once("forearm_left", "rotation", (0, 0, 0, 0), (0.3, -90, 0, 0), (1.3, -90, 0, 0), (1.6, 0, 0, 0)),
            **once("head", "rotation", (0, 0, 0, 0), (0.3, 0, 0, 0), (0.5, -6, 0, 4), (1.3, -6, 0, 4), (1.6, 0, 0, 0)),
            **once("forearm_right", "rotation", (0, rest_r, 0, 0), (1.6, rest_r, 0, 0))}),
        Animation("Wave", 2.0, "once", {
            **once("arm_left", "rotation", (0, 0, 0, 0), (0.3, 0, 0, 150), (1.7, 0, 0, 150), (2.0, 0, 0, 0)),
            **once("forearm_left", "rotation", (0, 0, 0, 0), (0.3, 0, 0, 0), (0.55, 0, 0, 25), (0.8, 0, 0, -20),
                   (1.05, 0, 0, 25), (1.3, 0, 0, -20), (1.55, 0, 0, 0), (2.0, 0, 0, 0)),
            **once("head", "rotation", (0, 0, 0, 0), (0.3, 0, 0, -6), (1.7, 0, 0, -6), (2.0, 0, 0, 0)),
            **once("forearm_right", "rotation", (0, rest_r, 0, 0), (2.0, rest_r, 0, 0))}),
    ]


# ── the office furniture ────────────────────────────────────────────────────────────────────────

WALNUT, WALNUT_DARK, WALNUT_LIGHT = "#6a3f24", "#4a2a17", "#7f4f2e"
GREEN_LEATHER, GOLD = "#2f5a3c", "#c9a24e"


def drawers(rows, pull=BRASS):
    """A front of `rows` drawers, each with a brass pull and a keyhole."""
    def paint(f):
        grain(WALNUT)(f)
        f.frame(WALNUT_DARK)
        step = f.h / rows
        for r in range(rows):
            y0 = round(r * step)
            f.hline(y0, WALNUT_DARK) if r else None
            mid = round(y0 + step / 2)
            f.rect(f.w // 2 - 2, mid, 4, 1, pull)
            f.set(f.w // 2, mid - 2, "#1b120b")
    return paint


def panel(col=WALNUT):
    return layers(grain(col), lambda f: f.box(1, 1, f.w - 2, f.h - 2, shade(col, 0.75)))


def desk() -> Model:
    def top(f):
        grain(WALNUT)(f)
        if f.name == "up":   # a green leather writing surface with a gold tooled border
            f.rect(3, 3, f.w - 6, f.h - 6, GREEN_LEATHER, 0.05)
            f.box(4, 4, f.w - 8, f.h - 8, GOLD)
    parts = [cube("top", (-16, 11.65, -7.5), (32, 1, 15), top),
             cube("pencil_drawer", (-8, 10.15, -7), (16, 1.5, 14),
                  {"south": layers(grain(WALNUT), edge(WALNUT_DARK), lambda f: f.rect(f.w // 2 - 2, 1, 4, 1, BRASS)),
                   "*": plain(WALNUT_DARK)}),
             cube("modesty", (-8, 3, -7), (16, 7.15, 1), panel())]
    for side, x in (("left", 8), ("right", -15.5)):
        parts += [cube(f"pedestal_{side}", (x, 0.75, -7), (7.5, 10.9, 14), {"south": drawers(3), "*": panel()}),
                  cube(f"plinth_{side}", (x + 0.25, 0, -6.75), (7, 0.75, 13.5), plain(WALNUT_DARK))]
    return Model("desk", [group("desk", (0, 0, 0), *parts)])


OXBLOOD = "#6e2a22"


def armchair() -> Model:
    dark = shade(OXBLOOD, 0.75)
    feet = [cube(f"foot_{i}", (x, 0, z), (1, 1, 1), plain("#2a1a10"))
            for i, (x, z) in enumerate([(-6.75, -4.25), (5.75, -4.25), (-6.75, 3.25), (5.75, 3.25)])]
    parts = feet + [
        cube("base", (-7, 1, -4.5), (14, 3, 9), {"south": studded(OXBLOOD), "*": leather(OXBLOOD)}),
        cube("cushion", (-5, 4, -2.5), (10, 1, 7), {"up": tufted(shade(OXBLOOD, 1.1), 5), "*": leather(OXBLOOD)}),
        cube("arm_left", (5, 4, -4.5), (2, 5, 9), {"south": studded(dark), "up": leather(shade(OXBLOOD, 1.08)),
                                                    "*": leather(OXBLOOD)}),
        cube("arm_right", (-7, 4, -4.5), (2, 5, 9), {"south": studded(dark), "up": leather(shade(OXBLOOD, 1.08)),
                                                      "*": leather(OXBLOOD)}),
        cube("back", (-7, 4, -4.5), (14, 9.5, 2), {"south": tufted(OXBLOOD, 4), "*": leather(OXBLOOD)}),
        cube("back_roll", (-7.25, 13.25, -4.75), (14.5, 1.25, 2.5), leather(shade(OXBLOOD, 1.08)))]
    return Model("armchair", [group("armchair", (0, 0, 0), *parts)])


BOOK_COLOURS = ["#7a1f24", "#1f3a5f", "#7a6a2a", "#2e5c3a", "#5a2f5f", "#8a4a1f", "#2a2f38", "#a08a5a"]


def book(col, gilt=GOLD):
    def paint(f):
        if f.name == "south":                            # the spine
            f.fill(col, 0.05)
            f.hline(1, gilt); f.hline(f.h - 2, gilt)
            if f.h > 6:
                f.rect(0, f.h // 2 - 1, f.w, 2, shade(col, 0.7))
        elif f.name == "up" or f.name == "north":
            f.fill("#ece2c6", 0.03)                      # the page edges
            f.frame(col)
        else:
            f.fill(col, 0.05)
    return paint


def flat_book(col, gilt=GOLD):
    """A book lying on its back: the cover on top, the spine to the west, page edges elsewhere."""
    def paint(f):
        if not f.side:
            f.fill(col, 0.05)
            f.box(1, 1, f.w - 2, f.h - 2, gilt)
        elif f.name == "west":
            f.fill(col, 0.05)
        else:
            f.fill("#ece2c6", 0.03); f.hline(0, col); f.hline(f.h - 1, col)
    return paint


def shelf_of_books(rng, x0, x1, y, z, max_h):
    """Books standing side by side from x0 to x1, now and then one leaning on its neighbour."""
    out, x, n = [], x0, 0
    while x < x1 - 1:
        w = rng.choice([1, 1.25, 1.5, 1.5, 2])
        if x + w > x1:
            break
        h = rng.uniform(max_h * 0.7, max_h)
        h = round(h * 4) / 4
        out.append(cube(f"book_{y}_{n}", (x, y, z), (w, h, rng.choice([5.5, 6, 6.5])),
                        book(rng.choice(BOOK_COLOURS))))
        x += w + (0.5 if rng.random() < 0.15 else 0)
        n += 1
    return out


def label_drawer(text):
    def paint(f):
        grain(WALNUT)(f)
        f.frame(WALNUT_DARK)
        lw = f.text_width(text) + 4
        f.rect(f.w // 2 - lw // 2, 1, lw, 7, "#efe6cc")
        f.text(text, f.w // 2 - lw // 2 + 2, 2, "#2a2018")
        f.rect(f.w // 2 - 3, f.h - 4, 6, 2, BRASS)
    return paint


def cabinet() -> Model:
    rng = random.Random(7)
    parts = [
        cube("side_left", (14.75, 0, -5), (1.25, 34, 10), panel()),
        cube("side_right", (-16, 0, -5), (1.25, 34, 10), panel()),
        cube("crown", (-16.5, 33, -5.5), (33, 1.25, 11), grain(WALNUT_LIGHT)),
        cube("back", (-14.75, 1, -5), (29.5, 32, 0.75), grain(WALNUT_DARK, j=0.03)),
        cube("plinth", (-16, 0, -4.75), (32, 1.5, 9.75), plain(WALNUT_DARK)),
        cube("counter", (-15.25, 14, -5), (30.5, 1, 10.5), grain(WALNUT_LIGHT)),
        cube("shelf_1", (-14.75, 21, -4.25), (29.5, 0.75, 9), grain(WALNUT)),
        cube("shelf_2", (-14.75, 27.5, -4.25), (29.5, 0.75, 9), grain(WALNUT)),
    ]
    for i, (text, x, y) in enumerate([("A-F", -14.75, 7.75), ("G-L", 0, 7.75), ("M-R", -14.75, 1.5), ("S-Z", 0, 1.5)]):
        parts.append(cube(f"files_{i}", (x, y, -4.25), (14.75, 6.25, 9.25), {"south": label_drawer(text),
                                                                             "*": plain(WALNUT_DARK)}))

    def safe(f):
        f.fill("#3d434d", 0.03)
        f.frame("#2a2f36")
        if f.name == "south":
            cx, cy = f.w // 2, f.h // 2
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    if dx * dx + dy * dy <= 5:
                        f.set(cx + dx, cy + dy, "#c9ccd2")
            f.set(cx, cy - 2, "#b3261e"); f.rect(cx + 4, cy - 1, 1, 3, "#c9ccd2")

    def globe(f):
        f.fill("#2f6f9f", 0.05)
        for _ in range(5):
            f.rect(f.rng.randrange(f.w), f.rng.randrange(f.h), f.rng.randint(2, 4), f.rng.randint(1, 3), "#6a9a4a", 0.06)

    def case_box(f):
        f.fill("#5b6b3a", 0.04)
        if f.name == "south":
            f.rect(1, 2, f.w - 2, 6, "#efe6cc"); f.text("CASE", 2, 3, "#2a2018")

    parts += shelf_of_books(rng, -14.5, -1.5, 15, -3.5, 5.75)
    parts += [cube("box_files", (-0.5, 15, -3.25), (9, 4, 6.5), case_box),
              cube("box_files_2", (0, 19, -3.25), (8, 2, 6.5), case_box),
              cube("safe", (9, 15, -3.5), (5.5, 5.5, 6.5), safe)]
    parts += shelf_of_books(rng, -14.5, 5, 21.75, -3.5, 5.5)
    parts += [cube("globe_stand", (9.25, 21.75, -1.75), (3, 0.75, 3), plain(BRASS)),
              cube("globe_post", (10.5, 22.5, -0.5), (0.5, 1, 0.5), plain(BRASS)),
              cube("globe", (8.75, 23.5, -2.25), (4, 4, 4), globe)]
    parts += shelf_of_books(rng, -14.5, -4, 28.25, -3.5, 4.5)
    parts += shelf_of_books(rng, 3, 14, 28.25, -3.5, 4.25)
    parts += [cube("trophy_base", (-2, 28.25, -1.5), (3, 1, 3), plain("#2a1a10")),
              cube("trophy_cup", (-1.5, 29.25, -1), (2, 2.25, 2), metal("#d8b048"))]
    return Model("cabinet", [group("cabinet", (0, 0, 0), *parts)])


LEAF, LEAF_DARK, LEAF_LIGHT = "#3f7f3a", "#2d5f2b", "#64a356"


def leaf_paint(f):
    """A leaf's outline, pointed at both ends, with its midrib; see-through round it and on its edges."""
    if f.side:
        return
    top = f.name == "up"
    for y in range(f.h):
        half = f.w / 2 * math.sin(math.pi * (y + 0.5) / f.h) ** 0.7
        for x in range(f.w):
            d = abs(x + 0.5 - f.w / 2)
            if d <= half:
                f.set(x, y, LEAF_DARK if d > half - 1 else LEAF if top else shade(LEAF, 1.15), 0.06)
    f.vline(f.w // 2, LEAF_LIGHT if top else shade(LEAF, 1.3), 1, f.h - 1)


def plant() -> Model:
    terracotta = "#b5603a"
    rng = random.Random(3)
    parts = [cube("pot", (-3.5, 0, -3.5), (7, 6, 7), layers(plain(terracotta), lambda f: f.hline(f.h - 1, shade(terracotta, 0.8)) if f.side else None)),
             cube("rim", (-4, 5, -4), (8, 1.5, 8), plain(shade(terracotta, 1.08))),
             cube("soil", (-3.5, 6.5, -3.5), (7, 0.1, 7), plain("#3a2618"))]
    leaves = []
    for i in range(15):
        yaw = i * 137.5 % 360
        h = 7 + (i % 5) * 2.4 + rng.uniform(0, 1.5)
        r = rng.uniform(0, 1.2)
        sx, sz = r * math.sin(math.radians(yaw)), r * math.cos(math.radians(yaw))
        tilt = rng.uniform(-40, 5) + (15 if h > 12 else 0)
        length = rng.choice([6, 6.5, 7])
        parts.append(cube(f"stem_{i}", (sx - 0.25, 6, sz - 0.25), (0.5, h - 6, 0.5), plain("#4a6a2a")))
        leaves.append(cube(f"leaf_{i}", (sx - 2.25, h, sz), (4.5, 0.1, length), leaf_paint,
                           rotate=(tilt, yaw, 0), pivot=(sx, h, sz)))
    return Model("plant", [group("plant", (0, 0, 0), *parts, *leaves)])


def hanging_plant() -> Model:
    rng = random.Random(5)
    parts = [cube("pot", (-2, 0, -2), (4, 2.5, 4), layers(plain("#e8e2d4"), lambda f: f.hline(1, "#c96f4a") if f.side else None)),
             cube("cord", (-0.15, 2.5, -0.15), (0.3, 15, 0.3), plain("#2a2a2a"))]
    for i in range(7):                                   # a crown of leaves over the rim
        a = math.radians(i * 51)
        parts.append(cube(f"tuft_{i}", (math.sin(a) * 1.8 - 0.75, 2, math.cos(a) * 1.8 - 0.75), (1.5, 1.25, 1.5),
                          plain(LEAF if i % 2 else LEAF_DARK, 0.08)))
    for v in range(5):                                   # vines trailing down
        a = math.radians(v * 72 + 20)
        x, z = math.sin(a) * 2.1, math.cos(a) * 2.1
        x, z = x * 1.1, z * 1.1
        for k in range(rng.randint(7, 12)):
            x += rng.uniform(-0.45, 0.45) + x * 0.04; z += rng.uniform(-0.45, 0.45) + z * 0.04
            parts.append(cube(f"vine_{v}_{k}", (x - 0.5, 1 - k * 1.2, z - 0.5), (1, 1, 1),
                              plain(LEAF_LIGHT if k % 3 == 0 else LEAF, 0.08)))
    return Model("hanging_plant", [group("hanging_plant", (0, 0, 0), *parts)])


def desk_set() -> Model:
    """What stands on the desk, at its place on the desk (the desk's own frame; its top is 12.65 up)."""
    top = 12.65
    green = "#2f7a4a"

    def shade_paint(f):
        f.fill(green, 0.04)
        if f.side:
            f.hline(0, shade(green, 1.3)); f.hline(f.h - 1, BRASS)

    def mug(f):
        if f.name == "up":
            f.fill("#3b2416", 0.04); f.frame("#f3eee5")
        else:
            f.fill("#f3eee5", 0.03)
            if f.name == "south":
                f.set(1, 1, "#15171d"); f.set(2, 1, "#15171d")   # two little eyes: Kane's mug

    def phone(f):
        f.fill("#17181d", 0.04)
        if f.name == "up":                               # the dial
            f.box(1, 1, f.w - 2, f.h - 2, "#c9ccd2")
            f.set(f.w // 2, 1, "#b3261e")

    def checklist(f):
        f.fill("#f4ecd8", 0.02)
        if f.name == "up":                               # five boxes, two ticked
            for i in range(5):
                y = 3 + i * 4
                f.box(2, y, 3, 3, "#b3261e")
                f.hline(y + 1, "#7a7363", 7, f.w - 3 - i * 3)
                if i < 2:
                    f.set(3, y + 1, "#0f7a52")

    parts = [
        cube("lamp_base", (8.4, top, -6.3), (3, 0.75, 3), metal(BRASS)),
        cube("lamp_stem", (9.55, top + 0.75, -5.15), (0.75, 12.1, 0.75), metal(BRASS)),
        cube("lamp_arm", (5.1, 24.75, -5.15), (5.2, 0.75, 0.75), metal(BRASS)),
        cube("lamp_shade", (3.0, 23, -6.5), (4.25, 2.5, 4.25), shade_paint),
        cube("bulb", (4.4, 22.6, -5.1), (1.5, 0.5, 1.5), plain("#fff1c8", 0.02), glow=True),
        cube("book_1", (6.75, top, 1.1), (5.75, 0.9, 4.2), flat_book(BOOK_COLOURS[0])),
        cube("book_2", (6.6, top + 0.9, 1.2), (5.5, 0.8, 4), flat_book(BOOK_COLOURS[1]), rotate=(0, 6, 0)),
        cube("book_3", (6.9, top + 1.7, 1.3), (5.2, 0.75, 3.8), flat_book(BOOK_COLOURS[2]), rotate=(0, -4, 0)),
        cube("mug", (11.6, top, 3.6), (1.75, 2, 1.75), mug),
        cube("mug_handle", (13.35, top + 0.5, 4.2), (0.5, 1, 0.5), plain("#f3eee5")),
        cube("phone", (12.3, top, -2.3), (3.2, 1.25, 3), phone),
        cube("handset", (12.1, top + 1.5, -2.05), (3.6, 0.75, 1), plain("#17181d")),
        cube("earpiece", (12.1, top + 1.25, -2.2), (0.9, 0.6, 1.3), plain("#17181d")),
        cube("mouthpiece", (14.8, top + 1.25, -2.2), (0.9, 0.6, 1.3), plain("#17181d")),
        cube("checklist", (-7.36, top, 2.4), (6.72, 0.08, 4.8), checklist, px=5, rotate=(0, 17.2, 0)),
        cube("pen", (-2.24, top + 0.08, 5.66), (2.88, 0.2, 0.2), plain("#1a1a1a"), rotate=(0, 21, 0)),
    ]
    return Model("desk_set", [group("desk_set", (0, 0, 0), *parts)])


def wanted_poster() -> Model:
    """A WANTED poster for a bug, framed. 5 texels a unit on its face, so the words are readable."""
    def poster(f):
        f.fill("#e9dcb8", 0.04)
        f.frame(WALNUT_DARK, 2)
        ink = "#2a1d14"
        f.text("WANTED", (f.w - f.text_width("WANTED", 2)) // 2, 5, ink, 2)
        cx, cy = f.w // 2, f.h // 2 + 2                  # the bug: a beetle, seen from above
        body = "#3b2a1c"
        for dy in range(-7, 8):
            half = round(5 * math.sqrt(max(0, 1 - (dy / 7.5) ** 2)))
            f.rect(cx - half, cy + dy, half * 2, 1, body)
        f.vline(cx, "#e9dcb8", cy - 4, cy + 8)           # the line between its wings
        f.rect(cx - 2, cy - 10, 4, 3, body)              # head
        for dy in (-3, 1, 5):                            # legs
            f.rect(cx - 9, cy + dy, 4, 1, body); f.rect(cx + 5, cy + dy, 4, 1, body)
        f.set(cx - 3, cy - 12, body); f.set(cx - 4, cy - 13, body); f.set(cx + 2, cy - 12, body); f.set(cx + 3, cy - 13, body)
        f.text("REWARD", (f.w - f.text_width("REWARD")) // 2, f.h - 15, "#8a1c1c")
        f.text("$500", (f.w - f.text_width("$500")) // 2, f.h - 9, ink)

    face = cube("poster", (-6, -8, 0.75), (12, 16, 0.1), {"south": poster, "*": plain("#e9dcb8")}, px=5)
    frame = cube("frame", (-6.5, -8.5, 0), (13, 17, 0.75), panel(WALNUT_DARK))
    return Model("wanted_poster", [group("wanted_poster", (0, 0, 0), frame, face)])


# ── the office itself: walls, floor, rug, window, door, clock, corkboard, computer ─────────────
# Placed by kane3d.js at its own spots: the back wall is at z = -3 m, the left wall at x = -3.55 m,
# the window's centre at (-1.45, 2.15), the door's at x = 2.6, the board's at (0.62, 1.85).

TEAL, PANEL, PANEL_RAISED, RAIL, SKIRTING = "#1d3a3d", "#4a2c1c", "#5a3622", "#6b4128", "#3a2214"
NO = None   # a face nobody sees: left out of the model


def wallpaper(f):
    """Teal paper with a faint diamond trellis and a gold dot in each diamond."""
    f.fill(TEAL, 0.03)
    for y in range(f.h):
        for x in range(f.w):
            cx, cy = x % 14 - 7, y % 14 - 7
            if abs(cx) + abs(cy) == 6:
                f.set(x, y, shade(TEAL, 1.3), 0.04)
            elif cx == 0 and cy == 0:
                f.set(x, y, "#6f6a44")
            elif cx == -7:
                f.set(x, y, shade(TEAL, 0.88), 0.03)


def planks(f):
    """Oak floorboards four pixels wide, staggered, with grain flecks and dark seams."""
    tones = ["#8a5a36", "#7a4e2e", "#94643c", "#6e4428", "#85573a"]
    for row in range(0, f.h, 4):
        x = -f.rng.randrange(24)
        while x < f.w:
            n = f.rng.randint(16, 36)
            f.rect(x, row, n, 4, f.rng.choice(tones), 0.03)
            for _ in range(n // 3):
                f.set(x + f.rng.randrange(n), row + f.rng.randrange(3), "#5a3a22")
            f.vline(x, "#3a2414", row, row + 4)
            x += n
        f.hline(row + 3, "#3a2414")


def raised_panel(f):
    """A raised panel: lit along the top and left, shaded along the bottom and right."""
    grain(PANEL_RAISED, across=False)(f)
    f.rect(0, 0, f.w, 1, "#6e4630"); f.rect(0, 0, 1, f.h, "#6e4630")
    f.rect(0, f.h - 1, f.w, 1, "#33200f"); f.rect(f.w - 1, 0, 1, f.h, "#33200f")


RUG, RUG_LIGHT, NAVY, RUG_GOLD, CREAM = "#6c1d22", "#8a2a2c", "#1f2a44", "#c99a4a", "#efe6cc"


def rug(f):
    """A Persian rug: a navy border between gold lines, a field of dots, a medallion, corner pieces."""
    if f.side:
        f.fill(RUG)
        return
    w, h = f.w, f.h
    cx, cy = (w - 1) / 2, (h - 1) / 2
    f.fill(RUG, 0.05)
    for y in range(10, h - 10, 5):                     # the field
        for x in range(11 + (y // 5 % 2) * 2, w - 10, 5):
            f.set(x, y, RUG_LIGHT)
    for (ox, oy) in ((9, 9), (w - 10, 9), (9, h - 10), (w - 10, h - 10)):   # corner pieces
        for y in range(h):
            for x in range(w):
                if ((x - ox) / 16) ** 2 + ((y - oy) / 10) ** 2 < 1:
                    f.set(x, y, NAVY, 0.04)
    for y in range(h):                                 # the medallion
        for x in range(w):
            dx, dy = (x - cx) / 32, (y - cy) / 20
            if math.hypot(dx, dy) < 0.9 + 0.12 * math.cos(12 * math.atan2(dy, dx)):
                f.set(x, y, NAVY, 0.04)
            if ((x - cx) / 23) ** 2 + ((y - cy) / 14) ** 2 < 1:
                f.set(x, y, RUG_GOLD, 0.04)
            if ((x - cx) / 16) ** 2 + ((y - cy) / 9.5) ** 2 < 1:
                f.set(x, y, RUG, 0.04)
            if abs(x - cx) / 6 + abs(y - cy) / 4 < 1:
                f.set(x, y, NAVY)
    f.box(2, 2, w - 4, h - 4, RUG_GOLD)                # the border
    f.rect(4, 4, w - 8, 3, NAVY); f.rect(4, h - 7, w - 8, 3, NAVY)
    f.rect(4, 4, 3, h - 8, NAVY); f.rect(w - 7, 4, 3, h - 8, NAVY)
    for x in range(6, w - 6, 4):
        f.set(x, 5, RUG_GOLD); f.set(x, h - 6, RUG_GOLD)
    for y in range(6, h - 6, 4):
        f.set(5, y, RUG_GOLD); f.set(w - 6, y, RUG_GOLD)
    f.box(8, 8, w - 16, h - 16, RUG_GOLD)
    for y in range(0, h, 2):                           # the fringe at both ends
        f.set(0, y, CREAM); f.set(w - 1, y, CREAM)


def wainscot(axis, x0, x1, wall, skip=(), facing=1):
    """Dark panelling to rail height along one wall, with raised panels, a rail and a skirting.

    axis "x": along a back wall whose face is at z = wall; "z": along a side wall whose face is at
    x = wall, facing +X (facing=1) or -X (facing=-1). Units are Blockbench units; skip lists
    (from, to) stretches left bare (a doorway, a corkboard).
    """
    runs, a = [], x0
    for s0, s1 in sorted(skip):
        runs.append((a, s0))
        a = s1
    runs.append((a, x1))
    face = "south" if axis == "x" else ("east" if facing > 0 else "west")
    tag = axis if facing > 0 else "r"

    def box(name, a, b, y0, y1, d0, d1, paint):
        if axis == "x":
            return cube(name, (a, y0, wall + d0), (b - a, y1 - y0, d1 - d0), paint)
        if facing > 0:
            return cube(name, (wall + d0, y0, a), (d1 - d0, y1 - y0, b - a), paint)
        return cube(name, (wall - d1, y0, a), (d1 - d0, y1 - y0, b - a), paint)

    parts = []
    for i, (a, b) in enumerate(runs):
        parts += [box(f"panelling_{tag}{i}", a, b, 0, 16.8, 0, 0.5, {face: grain(PANEL, across=False), "*": plain(PANEL)}),
                  box(f"rail_{tag}{i}", a, b, 16.8, 17.9, 0, 1.4, grain(RAIL)),
                  box(f"skirting_{tag}{i}", a, b, 0, 2.2, 0, 1.0, plain(SKIRTING))]
        n, p = 0, a + 1.6
        while p + 10.5 <= b - 1.6:
            parts.append(box(f"raised_{tag}{i}_{n}", p, p + 10.5, 3.2, 13.7, 0.5, 1.0,
                             {face: raised_panel, "*": plain(PANEL)}))
            p += 13.6
            n += 1
    return parts


def office_room() -> Model:
    """The office's walls and floor, and the rug under the desk (world units: 16 to the metre)."""
    back, left = -48, -56.8                             # z = -3 m and x = -3.55 m
    door = (31.0, 52.2)                                 # the doorway, x = 2.6 m ± 0.66
    parts = [
        cube("back_wall", (left, 0, back - 1), (80 - left, 67.2, 1), {"south": wallpaper, "*": NO}),
        cube("left_wall", (left - 1, 0, back), (1, 67.2, 80 - back), {"east": wallpaper, "*": NO}),
        cube("floor", (left, -1, back), (80 - left, 1, 80 - back), {"up": planks, "*": NO}),
        cube("rug", (-34.4, 0, -18.4), (57.6, 0.16, 38.4), {"down": NO, "*": rug}, rotate=(0, 10.31, 0)),
    ]
    parts += wainscot("x", left + 1.4, 80, back, skip=[door])
    parts += wainscot("z", back, 80, left)
    return Model("office_room", [group("office_room", (0, 0, 0), *parts)])


FRAME_WOOD = "#2c1a10"


def window() -> Model:
    """The tall window's frame, sill and half-drawn blinds. The city behind it is drawn by the page."""
    wood = grain(FRAME_WOOD)
    slat = layers(plain("#d9c8a0", 0.03), lambda f: f.hline(f.h - 1, "#b8a57c") if f.side else None)
    parts = [
        cube("frame_top", (-14.9, 16.5, 0), (29.8, 1.6, 1.8), wood),
        cube("frame_bottom", (-14.9, -18.3, 0), (29.8, 1.9, 1.8), wood),
        cube("frame_left", (-15.2, -18.3, 0), (1.6, 36.4, 1.8), wood),
        cube("frame_right", (13.6, -18.3, 0), (1.6, 36.4, 1.8), wood),
        cube("mullion", (-0.5, -16.8, 0), (1.0, 33.6, 1.2), wood),
        cube("transom", (-13.6, 3.6, 0), (27.2, 0.8, 1.2), wood),
        cube("sill", (-15.6, -19.3, 0), (31.2, 1.0, 4.0), grain(shade(FRAME_WOOD, 1.25))),
        cube("headrail", (-14, 15.6, 0.5), (28, 0.9, 1.6), plain("#c9b88a")),
        cube("cord", (11.5, 4.5, 2.1), (0.25, 11.1, 0.25), plain("#efe6cc")),
        cube("cord_pull", (11.3, 3.6, 1.9), (0.65, 0.9, 0.65), plain("#c9a24e")),
    ]
    for i in range(12):
        y = 15.0 - i * 1.04
        parts.append(cube(f"slat_{i}", (-13.8, y - 0.28, 1.3), (27.6, 0.56, 0.5), slat, rotate=(28.6, 0, 0)))
    return Model("window", [group("window", (0, 0, 0), *parts)])


DOOR_WOOD = "#6b3f22"


def door_glass(f):
    """Frosted glass lit from the corridor, with Kane's name on it."""
    f.fill("#e6d3a4", 0.03)
    for _ in range(40):
        f.set(f.rng.randrange(f.w), f.rng.randrange(f.h), "#f2e3bd")
    ink = "#3a2414"
    f.text("KANE", (f.w - f.text_width("KANE", 2)) // 2, 10, ink, 2)
    f.text("DETECTIVE", (f.w - f.text_width("DETECTIVE")) // 2, 24, ink)
    f.hline(32, ink, 8, f.w - 8)
    f.frame(DOOR_WOOD, 2)


def door() -> Model:
    """The door to the app's next page: a frame, a lit corridor behind it, and the door on its hinge
    (the group "leaf", which the page swings open). A lamp beside it, and a board for the sign above."""
    jamb = grain(SKIRTING, across=False)
    leaf = group("leaf", (-8.56, 0, 1.12),
        cube("door", (-8.56, 0, 0.64), (16.96, 35.84, 0.96), {"south": panel(DOOR_WOOD), "north": panel(DOOR_WOOD),
                                                            "*": plain(shade(DOOR_WOOD, 0.8))}),
        cube("glass", (-4.8, 17.6, 1.6), (9.6, 14.4, 0.2), {"south": door_glass, "*": plain(DOOR_WOOD)}, glow=True, px=5),
        cube("lower_panel", (-5.6, 4.4, 1.6), (11.2, 8.8, 0.3), {"south": raised_panel, "*": plain(PANEL)}),
        cube("kick_plate", (-7.5, 0.6, 1.6), (15, 1.6, 0.15), metal(BRASS)),
        cube("knob_plate", (5.9, 14.8, 1.6), (0.9, 3.4, 0.25), metal(BRASS)),
        cube("knob", (5.85, 15.6, 1.85), (1.0, 1.0, 1.0), metal(BRASS)))
    parts = [
        cube("corridor", (-8.8, 0, 0), (17.6, 36.2, 0.13), {"south": plain("#fff0c8", 0.02), "*": NO}, glow=True),
        cube("jamb_left", (-10.4, 0, -0.16), (1.6, 36.8, 1.92), jamb),
        cube("jamb_right", (8.8, 0, -0.16), (1.6, 36.8, 1.92), jamb),
        cube("head", (-10.4, 36.2, -0.16), (20.8, 1.9, 1.92), grain(SKIRTING)),
        cube("cornice", (-11.2, 38.1, -0.16), (22.4, 0.7, 2.4), grain(RAIL)),
        cube("threshold", (-8.8, 0, -0.5), (17.6, 0.3, 2.6), metal("#8a6a3a")),
        cube("sign_board", (-9.9, 39.1, 0), (19.8, 4.4, 1.3), panel(SKIRTING)),
        # the lamp beside the door
        cube("lamp_plate", (12.9, 32.8, 0), (1.4, 2.4, 0.4), metal(BRASS)),
        cube("lamp_arm", (13.3, 34.0, 0.4), (0.6, 0.6, 1.4), metal(BRASS)),
        cube("lamp_shade", (12.2, 34.6, 0.6), (2.8, 1.6, 1.4), {"down": plain("#fff1c8", 0.02), "*": metal(BRASS)}),
        cube("lamp_bulb", (12.7, 33.9, 0.9), (1.8, 0.7, 0.8), plain("#fff1c8", 0.02), glow=True),
        leaf,
    ]
    return Model("door", [group("door", (0, 0, 0), *parts)])


def round_slabs(name, r, z0, depth, paint, step=0.8):
    """A disc facing +Z, built the Blockbench way: a stack of flat bars, widest in the middle."""
    out, n = [], round(2 * r / step)
    for i in range(n):
        y = -r + step * (i + 0.5)
        half = math.sqrt(max(0.0, r * r - y * y))
        half = max(step / 2, round(half / step * 2) * step / 2)
        out.append(cube(f"{name}_{i}", (-half, y - step / 2, z0), (2 * half, step, depth), paint))
    return out


def clock_face(f):
    """The dial: a brass ring, minute dots, the four quarter numbers. See-through outside the ring."""
    c, r = (f.w - 1) / 2, f.w / 2
    for y in range(f.h):
        for x in range(f.w):
            d = math.hypot(x - c, y - c)
            if d < r - 2:
                f.set(x, y, "#f3eee5", 0.02)
            elif d < r:
                f.set(x, y, BRASS, 0.05)
    ink = "#23201b"
    for m in range(60):
        a = m * math.tau / 60
        rr = r - 4.5
        f.set(round(c + math.sin(a) * rr), round(c - math.cos(a) * rr), ink)
        if m % 5 == 0:                                 # the hours: a longer mark
            f.set(round(c + math.sin(a) * (rr - 1)), round(c - math.cos(a) * (rr - 1)), ink)
    mid = round(c)
    f.text("12", mid - 3, 7, ink)
    f.text("6", mid - 1, f.h - 12, ink)
    f.text("3", f.w - 11, mid - 2, ink)
    f.text("9", 8, mid - 2, ink)


def wall_clock() -> Model:
    """The wall clock. Its hands are the groups "hour_hand" and "minute_hand", turned by the page."""
    parts = round_slabs("case", 4.8, 0, 0.9, grain(SKIRTING))
    parts += round_slabs("bezel", 4.6, 0.9, 0.2, metal(BRASS))
    parts += [cube("dial", (-4.6, -4.6, 1.1), (9.2, 9.2, 0.05), {"south": clock_face, "*": NO}, px=5),
              cube("cap", (-0.35, -0.35, 1.5), (0.7, 0.7, 0.2), metal(BRASS)),
              group("hour_hand", (0, 0, 1.2), cube("hour", (-0.25, -0.5, 1.2), (0.5, 2.9, 0.12), plain("#23201b"))),
              group("minute_hand", (0, 0, 1.32), cube("minute", (-0.15, -0.6, 1.32), (0.3, 4.1, 0.12), plain("#23201b")))]
    return Model("wall_clock", [group("wall_clock", (0, 0, 0), *parts)])


CORK = "#a9784a"


def cork(f):
    f.fill(CORK, 0.05)
    f.speckle("#7a5230", 0.12, 0.08).speckle("#c99a6a", 0.08, 0.05)


def corkboard() -> Model:
    """The corkboard, its picture light, and the board's own furniture in the right-hand column: a
    CASE FILE header, a street map and three status lights. The evidence cards are pinned by the page."""
    frame = grain("#5a361f")
    pin = plain("#c62828")

    def header(f):
        f.fill("#f3e6c4", 0.03)
        f.text("CASE FILE", (f.w - f.text_width("CASE FILE")) // 2, 2, "#23201b")

    def street_map(f):
        f.fill("#e9e1c8", 0.03)
        for x in range(2, f.w, 6):
            f.vline(x, "#b8ad90")
        for y in range(3, f.h, 5):
            f.hline(y, "#b8ad90")
        f.rect(0, 9, f.w, 2, "#9fb0c0")                 # the river
        for a in range(24):                             # the spot, ringed in red
            f.set(round(14 + 3 * math.cos(a * math.tau / 24)), round(7 + 3 * math.sin(a * math.tau / 24)), "#c62828")

    parts = [
        cube("backing", (-17, -11, 0), (34, 22, 0.8), {"south": plain("#4a2c1c"), "*": NO}),
        cube("cork", (-16.8, -10.9, 0.8), (33.6, 21.8, 0.1), {"south": cork, "*": NO}),
        cube("frame_top", (-18, 10.9, 0), (36, 1.1, 1.3), frame),
        cube("frame_bottom", (-18, -12, 0), (36, 1.1, 1.3), frame),
        cube("frame_left", (-18, -10.9, 0), (1.2, 21.8, 1.3), frame),
        cube("frame_right", (16.8, -10.9, 0), (1.2, 21.8, 1.3), frame),
        cube("header", (9.1, 6.8, 0.92), (6.7, 2.4, 0.06), {"south": header, "*": plain("#f3e6c4")}, px=6,
             rotate=(0, 0, 2.3)),
        cube("header_pin", (12.2, 8.6, 0.98), (0.5, 0.5, 0.4), pin),
        cube("map", (9.6, -1.8, 0.92), (6.4, 5.1, 0.06), {"south": street_map, "*": plain("#e9e1c8")}, px=4,
             rotate=(0, 0, -2.3)),
        cube("map_pin", (12.6, 2.6, 0.98), (0.5, 0.5, 0.4), pin),
        cube("light_green", (10.6, -8.6, 0.9), (1.1, 1.1, 0.7), plain("#2fb67c"), glow=True),
        cube("light_amber", (12.1, -8.6, 0.9), (1.1, 1.1, 0.7), plain("#f0b23a"), glow=True),
        cube("light_off", (13.6, -8.6, 0.9), (1.1, 1.1, 0.7), plain("#5a5f6c")),
        # the picture light over the board
        cube("lamp_arm", (-0.5, 13.2, 0), (1.0, 1.0, 4.0), metal(BRASS)),
        cube("lamp_hood", (-4.4, 12.4, 3.2), (8.8, 2.0, 2.2), {"down": plain("#3a2a14"), "*": metal(BRASS)}),
        cube("lamp_tube", (-4.0, 12.2, 3.6), (8.0, 0.3, 1.4), plain("#fff1c8", 0.02), glow=True),
    ]
    return Model("corkboard", [group("corkboard", (0, 0, 0), *parts)])


def computer() -> Model:
    """Kane's computer, in the monitor's own frame on the desk (the desk top is 12.65 up). The page
    draws the screen itself, just in front of the bezel, because it shows Kane's real browser."""
    beige, beige_dark = CASE, CASE_DARK

    def bezel(f):
        f.fill(beige, 0.03)
        if f.name == "south":
            f.box(1, 1, f.w - 2, f.h - 2, beige_dark)
            f.rect(f.w - 6, f.h - 3, 2, 1, "#3ad06a")    # the power light
            f.rect(3, f.h - 3, 6, 1, beige_dark)         # the badge
        elif f.name in ("east", "west"):
            for y in range(2, f.h - 2, 2):
                f.hline(y, beige_dark, 1, f.w - 1)

    def keyboard(f):
        f.fill("#2c2f3a", 0.03)
        if f.name == "up":
            for row in range(4):
                for k in range(15 - (row == 3) * 4):
                    f.rect(2 + k * 3 + (row % 2), 2 + row * 3, 2, 2, "#c9ccd2" if row < 3 else "#8b93a3", 0.03)
            f.rect(14, 14, 18, 2, "#c9ccd2")             # the space bar

    parts = [
        cube("bezel", (-8.8, 14.2, -5.3), (19.2, 12.2, 1.0), bezel),
        cube("housing", (-6.6, 15.6, -7.6), (14.8, 9.4, 2.3), layers(plain(beige_dark), edge(shade(beige_dark, 0.85)))),
        cube("neck", (0.2, 12.9, -6.8), (1.2, 2.6, 1.2), plain(beige_dark)),
        cube("foot", (-2.4, 12.65, -7.6), (6.4, 0.35, 3.6), plain(beige)),
        cube("keyboard", (-4.96, 12.65, 0.16), (11.52, 0.45, 4.16), keyboard, px=4),
        cube("mouse_pad", (7.4, 12.65, 0.2), (3.6, 0.08, 3.4), plain("#1f3a5f")),
        cube("mouse", (8.4, 12.73, 0.9), (1.3, 0.45, 1.9),
             layers(plain(beige), lambda f: f.hline(1, beige_dark) if f.name == "up" else None)),
        cube("cable", (0.5, 12.65, -3.9), (0.25, 0.2, 4.0), plain("#1a1a1a")),
    ]
    return Model("computer", [group("computer", (0, 0, 0), *parts)])


def side_table() -> Model:
    """The side table with the evidence tray, in the table's own frame."""
    def tag(f):
        f.fill(GOLD, 0.03)
        f.text("EVIDENCE", (f.w - f.text_width("EVIDENCE")) // 2, 2, "#2a1a0e")

    def two_drawers(f):
        grain(WALNUT_DARK)(f)
        f.frame(shade(WALNUT_DARK, 0.75))
        f.hline(f.h // 2, shade(WALNUT_DARK, 0.75))
        for y in (f.h // 4, 3 * f.h // 4):
            f.rect(f.w // 2 - 2, y, 4, 1, BRASS)

    def sheet(col):
        def paint(f):
            f.fill(col, 0.02)
            if f.name == "up":
                for y in range(2, f.h - 1, 2):
                    f.hline(y, shade(col, 0.72), 2, f.w - 2 - f.rng.randrange(6))
        return paint

    def photo(f):
        f.fill("#f3eee5")
        if f.name == "up":
            f.rect(1, 1, f.w - 2, f.h - 3, "#4a5a6a", 0.08)

    wall = grain("#6a3d22")
    parts = [
        cube("top", (-8, 9.4, -4.8), (16, 1.0, 9.6), layers(grain(WALNUT), edge(WALNUT_DARK))),
        cube("body", (-7.2, 0.6, -4), (14.4, 8.8, 8), {"south": two_drawers, "*": panel(WALNUT_DARK)}),
        cube("plinth", (-7.4, 0, -4.2), (14.8, 0.6, 8.4), plain(SKIRTING)),
        cube("tray_base", (-4, 10.4, -2.9), (9.6, 0.4, 5.8), plain("#5a341c")),
        cube("tray_front", (-4, 10.8, 2.5), (9.6, 2.1, 0.4), wall),
        cube("tray_back", (-4, 10.8, -2.9), (9.6, 2.1, 0.4), wall),
        cube("tray_left", (-4, 10.8, -2.5), (0.4, 2.1, 5.0), wall),
        cube("tray_right", (5.2, 10.8, -2.5), (0.4, 2.1, 5.0), wall),
        cube("tag", (-1.76, 11.1, 2.9), (5.12, 1.2, 0.08), {"south": tag, "*": plain(GOLD)}, px=7),
    ]
    for i, col in enumerate(["#f3eee5", "#e9dfc8", "#d6e3ff", "#f3eee5", "#c9b88a"]):
        y, z = 11.0 + 0.32 * i, -0.3 + 0.13 * i
        parts.append(cube(f"paper_{i}", (-3.2, y, z - 2.3), (8.0, 0.08, 4.6), sheet(col), rotate=(14 - 2.5 * i, 0, 0)))
    parts.append(cube("photo", (-2.2, 12.6, -1.2), (3.6, 0.06, 2.8), photo, rotate=(6, -12, 0)))
    return Model("side_table", [group("side_table", (0, 0, 0), *parts)])


# ── the Lineup's room and the reconstruction's office ───────────────────────────────────────────

def height_chart(f):
    """A height chart 3 m tall: a line every 10 cm, a bold line and its number every 50 cm."""
    f.fill("#262a36", 0.02)
    per_cm = f.h / 300
    for cm in range(10, 300, 10):
        y = round(f.h - cm * per_cm)
        if cm % 50 == 0:
            f.rect(0, y - 1, f.w, 2, "#a3a19c")
            f.text(str(cm), 4, y - 14, "#d9d5cc", 2)
        else:
            f.hline(y, "#454956")


def lineup_wall() -> Model:
    """One 3 m stretch of the Lineup's room: the height chart, the floor, the yellow line to stand
    behind. lineup3d.js lays as many side by side as the row of suspects needs."""
    def concrete(f):
        f.fill("#1b1d24", 0.06)
        for y in range(0, f.h, 8):
            f.hline(y, "#15171d")
        for x in range(0, f.w, 16):
            f.vline(x, "#15171d")

    parts = [
        cube("chart", (0, 0, -1), (48, 48, 1), {"south": height_chart, "*": NO}, px=5),
        cube("skirting", (0, 0, 0), (48, 1.6, 0.6), {"south": plain("#15171d"), "up": plain("#15171d"), "*": NO}),
        cube("floor", (0, -1, 0), (48, 1, 204), {"up": concrete, "*": NO}, px=1),
        cube("line", (0, 0, 21.1), (48, 0.05, 1.0), {"up": plain("#ffd166", 0.02), "*": NO}, glow=True),
    ]
    return Model("lineup_wall", [group("lineup_wall", (0, 0, 0), *parts)])


def recon_room() -> Model:
    """The reconstruction's office: the same teal paper, panelling and floorboards as Kane's live
    office, and the big corkboard on the back wall (its cork face at z = -3.92 m). recon.js pins the
    evidence on it."""
    back, side = -64, 112                               # z = -4 m; the side walls at x = ±7 m
    parts = [
        cube("back_wall", (-side, 0, back - 1), (2 * side, 96, 1), {"south": wallpaper, "*": NO}),
        cube("left_wall", (-side - 1, 0, back), (1, 96, 96 - back), {"east": wallpaper, "*": NO}),
        cube("right_wall", (side, 0, back), (1, 96, 96 - back), {"west": wallpaper, "*": NO}),
        cube("floor", (-side, -1, back), (2 * side, 1, 96 - back), {"up": planks, "*": NO}),
        cube("board_frame", (-63.2, 4, -64.16), (126.4, 67.2, 1.28), {"south": panel("#6e4a2c"), "*": plain("#5a361f")}),
        cube("board_cork", (-60.8, 6.4, -62.88), (121.6, 62.4, 0.16), {"south": cork, "*": NO}),
    ]
    parts += wainscot("x", -side, side, back, skip=[(-64, 64)])
    parts += wainscot("z", back, 96, -side)
    parts += wainscot("z", back, 96, side, facing=-1)
    return Model("recon_room", [group("recon_room", (0, 0, 0), *parts)])


# ── the Lineup's suspects ───────────────────────────────────────────────────────────────────────
# Three suspects in turn down the row, each holding up a placard (drawn by lineup3d.js) at chest
# height in front of them.

SUSPECTS = {
    "suspect_hoodie": {"top": "#4b5d4f", "legs": "#3a4a6b", "shoes": "#e8e6e0", "skin": "#c99b77",
                       "hair": "#2a1d14", "extra": "hood"},
    "suspect_suit": {"top": "#2f3340", "legs": "#2a2d38", "shoes": "#111111", "skin": "#8d5a3b",
                     "hair": "#141010", "extra": "shades"},
    "suspect_beanie": {"top": "#8e2f2f", "legs": "#9c8a62", "shoes": "#4a3020", "skin": "#e2b892",
                       "hair": "#6a3f24", "extra": "beanie"},
}


def suspect(name: str) -> Model:
    s = SUSPECTS[name]
    top, skin = s["top"], s["skin"]

    def shirt(f):
        f.fill(top, 0.04)
        if s["extra"] == "beanie" and f.side:            # a check flannel
            for y in range(0, f.h, 4):
                f.hline(y, "#1d1414")
            for x in range(0, f.w, 4):
                f.vline(x, "#1d1414")
        if s["extra"] == "shades" and f.name == "south":    # the suit: a white shirt and a red tie
            mid = f.w // 2
            for y in range(6):
                half = max(0, 3 - y // 2)
                f.rect(mid - half, y, half * 2, 1, "#f1efe8")
            f.rect(mid - 1, 1, 2, 9, "#a3262e")          # the tie

    def face(f):
        f.fill(skin, 0.03)
        if f.name != "south":
            if f.name == "up" or f.name == "north":
                f.fill(s["hair"], 0.06)
            else:
                f.rect(0, 0, f.w, 3, s["hair"], 0.06)
            return
        f.rect(0, 0, f.w, 2, s["hair"], 0.06)
        if s["extra"] == "shades":
            f.rect(2, 4, f.w - 4, 2, "#0b0b0d")
        else:
            f.set(3, 5, "#1a1414"); f.set(f.w - 4, 5, "#1a1414")
            f.hline(3, shade(s["hair"], 1.2), 2, 5); f.hline(3, shade(s["hair"], 1.2), f.w - 5, f.w - 2)
        f.hline(f.h - 3, "#6a3a2a", 4, f.w - 4)          # a tight-lipped mouth
        if s["extra"] == "beanie":
            f.rect(1, f.h - 2, f.w - 2, 2, s["hair"], 0.08)  # beard

    shoes = plain(s["shoes"])
    parts = [
        cube("leg_left", (0.25, 1.25, -1.5), (3.25, 10, 3), plain(s["legs"])),
        cube("leg_right", (-3.5, 1.25, -1.5), (3.25, 10, 3), plain(s["legs"])),
        cube("shoe_left", (0, 0, -1.75), (3.75, 1.25, 4.25), shoes),
        cube("shoe_right", (-3.75, 0, -1.75), (3.75, 1.25, 4.25), shoes),
        cube("torso", (-4.5, 11, -2.5), (9, 9, 5), shirt),
        cube("neck", (-1, 20, -1), (2, 0.75, 2), plain(skin)),
        cube("head", (-3, 20.5, -3), (6, 6, 6), face),
        # arms: upper arms hang, forearms come forward to hold the placard up
        cube("arm_left", (4.5, 15, -1.25), (2.5, 5, 2.5), plain(top)),
        cube("arm_right", (-7, 15, -1.25), (2.5, 5, 2.5), plain(top)),
        cube("forearm_left", (4.5, 13.5, -1.25), (2.5, 2, 5.5), plain(top)),
        cube("forearm_right", (-7, 13.5, -1.25), (2.5, 2, 5.5), plain(top)),
        cube("hand_left", (4.25, 13.5, 4.25), (2.5, 2.5, 1.5), plain(skin)),
        cube("hand_right", (-6.75, 13.5, 4.25), (2.5, 2.5, 1.5), plain(skin)),
    ]
    if s["extra"] == "hood":
        parts.append(cube("hood", (-3.75, 18.5, -4), (7.5, 5.5, 2), plain(shade(top, 0.9))))
    if s["extra"] == "beanie":
        parts += [cube("beanie", (-3.25, 25.5, -3.25), (6.5, 2.25, 6.5), knit("#c9622e")),
                  cube("pompom", (-0.75, 27.75, -0.75), (1.5, 1, 1.5), plain("#efe6cc"))]
    if s["extra"] == "shades":
        parts.append(cube("hair_top", (-3.25, 26.25, -3.25), (6.5, 0.75, 6.5), plain(s["hair"])))
    return Model(name, [group(name, (0, 0, 0), *parts)])


# ── writing them out ────────────────────────────────────────────────────────────────────────────

def all_models() -> list:
    return [kane(), desk(), armchair(), cabinet(), plant(), hanging_plant(), desk_set(), wanted_poster(),
            office_room(), window(), door(), wall_clock(), corkboard(), computer(), side_table(),
            lineup_wall(), recon_room(), *(suspect(n) for n in SUSPECTS)]


def main():
    GLB_DIR.mkdir(parents=True, exist_ok=True)
    for model in all_models():
        project, binary = build(model)
        (ROOT / "art" / f"{model.name}.bbmodel").write_text(json.dumps(project, indent=1), encoding="utf-8")
        (GLB_DIR / f"{model.name}.glb").write_bytes(binary)
        print(f"{model.name:16s} {len(binary) / 1024:6.1f} KB")


if __name__ == "__main__":
    main()

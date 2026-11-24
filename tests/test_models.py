"""The 3D models: each one the scenes load exists, Kane has every move they ask for, and the
Blockbench projects open. No browser, no Kane."""
import json
import re
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "whisperer" / "static"
sys.path.insert(0, str(ROOT / "art"))
import models  # noqa: E402
from blockbench import build  # noqa: E402

KANE_MOVES = {"Idle", "Walking", "Sitting", "Standing", "Yes", "No", "Punch", "ThumbsUp", "Wave"}


def gltf(path: Path) -> dict:
    data = path.read_bytes()
    magic, version, length = struct.unpack_from("<4sII", data)
    assert (magic, version, length) == (b"glTF", 2, len(data))
    size, kind = struct.unpack_from("<I4s", data, 12)
    assert kind == b"JSON"
    return json.loads(data[20:20 + size])


def models_the_scenes_load() -> set:
    names = set()
    office = (STATIC / "kane3d.js").read_text(encoding="utf-8")
    names |= set(re.findall(r'\bmodel\("([a-z_]+)"', office))
    lineup = (STATIC / "lineup3d.js").read_text(encoding="utf-8")
    names |= set(re.findall(r'"(suspect_[a-z]+)"', lineup))
    for scene in ("lineup3d.js", "recon.js"):
        names |= set(re.findall(r'one\("([a-z_]+)"\)', (STATIC / scene).read_text(encoding="utf-8")))
    return names | {"kane"}


def test_every_model_the_scenes_load_is_there():
    names = models_the_scenes_load()
    # the patterns still find them: the furniture, the rooms, the suspects
    assert {"desk", "armchair", "cabinet", "office_room", "door", "wall_clock", "lineup_wall", "recon_room",
            "suspect_suit"} <= names
    for name in names:
        doc = gltf(STATIC / "models" / "bb" / f"{name}.glb")
        assert doc["meshes"], name


def test_kane_has_every_move_and_both_faces():
    doc = gltf(STATIC / "models" / "bb" / "kane.glb")
    assert {a["name"] for a in doc["animations"]} == KANE_MOVES
    nodes = {n["name"]: n for n in doc["nodes"]}
    assert "eyes" in nodes and nodes["eyes_surprised"]["extras"] == {"hidden": True}
    office = (STATIC / "kane3d.js").read_text(encoding="utf-8")
    asked = set(re.findall(r'(?:play|loop|hold)\("([A-Za-z]+)"\)', office))
    asked |= {m for pair in re.findall(r'play\(a\.failed \? "(\w+)" : "(\w+)"\)', office) for m in pair}
    assert asked <= KANE_MOVES


def test_the_parts_the_office_moves_are_there():
    office = (STATIC / "kane3d.js").read_text(encoding="utf-8")
    for model, part in (("door", "leaf"), ("wall_clock", "hour_hand"), ("wall_clock", "minute_hand")):
        assert f'getObjectByName("{part}")' in office
        assert part in {n["name"] for n in gltf(STATIC / "models" / "bb" / f"{model}.glb")["nodes"]}


@pytest.mark.parametrize("path", sorted((ROOT / "art").glob("*.bbmodel")), ids=lambda p: p.stem)
def test_each_blockbench_project_opens(path):
    project = json.loads(path.read_text(encoding="utf-8"))
    assert project["meta"] == {"format_version": "5.0", "model_format": "free", "box_uv": False}
    groups = {g["uuid"] for g in project["groups"]}
    cubes = {e["uuid"] for e in project["elements"]}

    def walk(items):
        for item in items:
            if isinstance(item, str):
                assert item in cubes
            else:
                assert item["uuid"] in groups
                walk(item["children"])
    walk(project["outliner"])
    assert all(t["source"].startswith("data:image/png;base64,") for t in project["textures"])
    for anim in project.get("animations", []):
        assert set(anim["animators"]) <= groups


def test_the_builder_makes_the_same_files_every_time():
    first, second = build(models.desk()), build(models.desk())
    assert first[1] == second[1] and first[0] == second[0]

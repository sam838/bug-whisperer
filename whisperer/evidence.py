"""Pull Kane's step screenshots out of its sealed evidence pack, so the website can show them.

A Kane session folder has evidence/<id>.evidence, a zip with one folder per step:
steps/<ordinal>-<id>/step.json (what Kane did), screenshot.jpg, and sometimes annotated.png
(the same screenshot with the element Kane acted on marked). failure.yaml at the top level has
Kane's own title for a failure.
"""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

STEP_DIR = re.compile(r"/steps/(\d+)-[^/]+/$")


def find_pack(session_dir: str | None) -> Path | None:
    if not session_dir:
        return None
    packs = sorted(Path(session_dir).glob("evidence/*.evidence"), key=lambda p: p.stat().st_mtime)
    return packs[-1] if packs else None


def extract_shots(session_dir: str | None, dest: Path) -> dict:
    """Copy each step's screenshot into dest/. Returns {"shots": [...], "failure_title": ...}."""
    pack = find_pack(session_dir)
    if not pack:
        return {"shots": [], "failure_title": None}
    dest.mkdir(parents=True, exist_ok=True)
    shots = []
    with zipfile.ZipFile(pack) as zf:
        names = set(zf.namelist())
        step_dirs = sorted({n.rsplit("/", 1)[0] + "/" for n in names if "/steps/" in n},
                           key=lambda d: int(STEP_DIR.search(d).group(1)) if STEP_DIR.search(d) else 0)
        for step_dir in step_dirs:
            match = STEP_DIR.search(step_dir)
            if not match:
                continue
            ordinal = int(match.group(1))
            info = json.loads(zf.read(step_dir + "step.json")) if step_dir + "step.json" in names else {}
            image = next((step_dir + f for f in ("annotated.png", "screenshot.jpg") if step_dir + f in names), None)
            if not image:
                continue
            target = dest / f"{ordinal:03d}{Path(image).suffix}"
            target.write_bytes(zf.read(image))
            shots.append({
                "ordinal": ordinal, "file": target.name, "summary": info.get("summary", ""),
                "status": info.get("status", ""), "url": info.get("url", ""),
            })
        failure_title = None
        if "failure.yaml" in names:
            found = re.search(r"^\s+title: (.+)$", zf.read("failure.yaml").decode("utf-8", "replace"), re.M)
            failure_title = found.group(1).strip() if found else None
    return {"shots": shots, "failure_title": failure_title}

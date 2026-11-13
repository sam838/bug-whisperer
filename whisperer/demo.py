"""The hosted live demo (Render): recorded cases, a passcode for live runs, a daily limit, and a
clinic app that starts every case as the AI builder first wrote it.

Settings (environment variables):
  WHISPERER_HOSTED=1    turn hosted mode on
  DEMO_PASSCODE         passcode judges type before sending Kane or pressing Repair
  DEMO_DAILY_LIMIT      live jobs per day (default 20) so credits can't run away

Why the passcode: complaints and screenshots go to Claude, and the repair loop runs the code
Claude writes. On a public server that must not be open to anyone.

Why the clinic resets to the AI builder's original version: the bugs in our evidence are fixed
in the repo, so a judge would find nothing. demo/clinic_original_app.py is clinic/app.py exactly
as the separate Claude session first wrote it (commit d6ab683). Before each live case, and after
each repair, the clinic goes back to that version.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path

from .detective import ROOT, RUNS

DEMO = ROOT / "demo"
CASES = DEMO / "cases"
ORIGINAL_APP = DEMO / "clinic_original_app.py"
USAGE = RUNS / "demo-usage.json"
SECRETS = ("sunrise123", "harbor123")  # demo logins: public, but never needed in case files


def hosted() -> bool:
    return os.environ.get("WHISPERER_HOSTED") == "1"


def passcode_token() -> str | None:
    code = os.environ.get("DEMO_PASSCODE", "")
    return hashlib.sha256(("bug-whisperer:" + code).encode()).hexdigest() if code else None


def daily_limit() -> int:
    return int(os.environ.get("DEMO_DAILY_LIMIT", "20"))


def used_today() -> int:
    if not USAGE.exists():
        return 0
    data = json.loads(USAGE.read_text(encoding="utf-8"))
    return data.get(time.strftime("%Y-%m-%d"), 0)


def count_job() -> None:
    data = json.loads(USAGE.read_text(encoding="utf-8")) if USAGE.exists() else {}
    day = time.strftime("%Y-%m-%d")
    data[day] = data.get(day, 0) + 1
    USAGE.parent.mkdir(parents=True, exist_ok=True)
    USAGE.write_text(json.dumps(data), encoding="utf-8")


def reset_clinic() -> None:
    """Put the clinic back to the AI builder's original code (bugs included)."""
    if ORIGINAL_APP.exists():
        shutil.copyfile(ORIGINAL_APP, ROOT / "clinic" / "app.py")


def export_cases() -> list[str]:
    """Copy recorded cases from runs/ into demo/cases/ (committed), without Kane's raw logs."""
    exported = []
    for inv_file in sorted(RUNS.glob("*/investigation.json")):
        src = inv_file.parent
        if src.name.startswith("guard-"):
            continue
        dst = CASES / src.name
        shutil.rmtree(dst, ignore_errors=True)
        dst.mkdir(parents=True)
        text = inv_file.read_text(encoding="utf-8")
        for secret in SECRETS:
            text = text.replace(secret, "********")
        (dst / "investigation.json").write_text(text, encoding="utf-8")
        for item in src.iterdir():
            if item.is_dir() and item.name.startswith("shots-"):
                shutil.copytree(item, dst / item.name)
            elif item.name.startswith("user-screenshot"):
                shutil.copyfile(item, dst / item.name)
        exported.append(src.name)
    return exported


def seed_runs() -> int:
    """On a fresh server, put the recorded cases where the website reads them."""
    RUNS.mkdir(parents=True, exist_ok=True)
    seeded = 0
    for case in sorted(CASES.glob("*/investigation.json")):
        dst = RUNS / case.parent.name
        if not dst.exists():
            shutil.copytree(case.parent, dst)
            seeded += 1
    return seeded

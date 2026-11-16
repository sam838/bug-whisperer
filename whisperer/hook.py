"""Claude Code Stop hook: before Claude may finish, Kane revisits every closed case it could affect.

Wired in .claude/settings.json. Claude Code runs it whenever Claude tries to stop. It:
  1. skips Bug Whisperer's own Claude sessions (the planner and the fixer), which set
     WHISPERER_INTERNAL, so the hook never runs inside itself;
  2. skips apps whose code hasn't changed since the last time every case held;
  3. otherwise replays the closed cases with Kane (about 15 s each, no credits);
  4. if a case reopened, blocks Claude from stopping and hands it Kane's evidence, so Claude
     re-prompts itself and fixes it. After 3 blocks in a row it lets Claude stop and says a
     person is needed, instead of looping forever.

Output follows the Stop hook contract: a JSON object on stdout, exit code 0.
{"decision": "block", "reason": ...} makes Claude keep working; anything else lets it stop.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from . import guard
from .detective import ROOT, RUNS, App

STATE = RUNS / "hook-state.json"
MAX_BLOCKS = 3


def main() -> int:
    payload = _read_stdin()
    if os.environ.get("WHISPERER_INTERNAL"):
        return _out({})
    apps = sorted({c["app_file"] for c in guard.closed_cases()})
    if not apps:
        return _out({})

    state = _load_state()
    changed = []
    for app_file in apps:
        app = App.load(ROOT / app_file)
        if app.code_dir and _fingerprint(app.code_dir) != state["clean"].get(app_file):
            changed.append(app_file)
    if not changed:
        return _out({})

    reopened, unknown, held = [], [], 0
    for app_file in changed:
        report = guard.revisit(app_file)
        reopened += report["reopened"]
        unknown += report["unknown"]
        held += sum(1 for r in report["results"] if r["verdict"] == "holds")
        if not report["reopened"] and not report["unknown"]:
            state["clean"][app_file] = _fingerprint(App.load(ROOT / app_file).code_dir)

    session = payload.get("session_id", "unknown")
    if reopened:
        blocks = state["blocks"].get(session, 0) + 1
        state["blocks"][session] = blocks
        _save_state(state)
        if blocks > MAX_BLOCKS:
            return _out({"systemMessage": (
                f"🕵️ Kane: {len(reopened)} closed case(s) are still open after {MAX_BLOCKS} "
                "repair attempts. Handing this to a person.")})
        return _out({"decision": "block", "reason": _reason(reopened, blocks)})

    state["blocks"].pop(session, None)
    _save_state(state)
    if unknown:
        return _out({"systemMessage": (
            f"🕵️ Kane revisited the closed cases: {held} still closed, {len(unknown)} couldn't be "
            "checked (Kane couldn't finish). Not blocking, but nothing is claimed for those.")})
    return _out({"systemMessage": f"🕵️ Kane revisited {held} closed case(s): all still closed. ✅"})


def _reason(reopened: list[dict], attempt: int) -> str:
    lines = [f"🕵️ Kane revisited the closed cases before letting you finish (check {attempt} of "
             f"{MAX_BLOCKS}). These bugs were fixed before and are BACK:"]
    for r in reopened:
        case = next((c for c in guard.closed_cases() if c["case_id"] == r["case_id"]), {})
        evidence = r.get("fresh") or r["replay"]
        lines += [
            "",
            f"Case {r['case_id']}: {r['title']}",
            f"  The user originally reported: {case.get('report', '')}",
            f"  Kane's steps: {case.get('objective', '')}",
            f"  Kane's check failed at: {evidence.get('failed_step') or evidence.get('reason')}",
            f"  Kane's account: {(evidence.get('summary') or '').strip()}",
        ]
    lines += [
        "",
        "Fix the app's code so these cases pass again, keeping the change you were making.",
        "Do not edit the saved Kane tests in .testmuai/tests/ or the case registry: they are the "
        "evidence. When you finish, Kane will revisit the cases again.",
    ]
    return "\n".join(lines)


def _fingerprint(code_dir: str) -> str:
    """The app's code as it is now: its folder in the last commit (not the whole commit, so work on
    other parts of the repo doesn't trigger a revisit), plus uncommitted changes in that folder."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace").stdout
    untracked = git("ls-files", "--others", "--exclude-standard", "--", code_dir).split()
    digest = hashlib.sha1()
    digest.update(git("rev-parse", f"HEAD:{Path(code_dir).as_posix()}").encode())
    digest.update(git("diff", "HEAD", "--", code_dir).encode())
    for name in sorted(untracked):
        path = ROOT / name
        digest.update(name.encode())
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _read_stdin() -> dict:
    try:
        text = sys.stdin.read() if not sys.stdin.isatty() else ""
        return json.loads(text) if text.strip() else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _load_state() -> dict:
    if STATE.exists():
        data = json.loads(STATE.read_text(encoding="utf-8"))
        data.setdefault("clean", {})
        data.setdefault("blocks", {})
        return data
    return {"clean": {}, "blocks": {}}


def _save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _out(data: dict) -> int:
    # ensure_ascii: emoji become \u escapes, so this works on any console encoding (Windows
    # cp1252 crashed on them when Claude Code read the hook through a pipe).
    print(json.dumps(data, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

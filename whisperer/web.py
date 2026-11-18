"""The Bug Whisperer website.

Run:  uvicorn whisperer.web:app --port 8000

One background worker runs jobs one at a time (Kane drives a real Chrome, and each run costs
credits), so reports wait in line. Pages poll a small HTML fragment while a job is running; live
Kane steps are read from the NDJSON log Kane is writing.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import queue
import re
import threading
import time
from dataclasses import asdict
from datetime import datetime
from urllib.parse import urlsplit
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import demo, intake, kane
from .detective import ROOT, RUNS, App, Investigation, investigate
from .voice import BOOKKEEPING, speak
from .fixer import fix, load_investigation

HERE = Path(__file__).resolve().parent
APPS = ROOT / "apps"
ID_RE = re.compile(r"^[0-9]{8}-[0-9]{6}(-[0-9a-f]{4})?$")
IMAGE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}
MAX_UPLOAD = 5 * 1024 * 1024
INTERNAL_REMARK = BOOKKEEPING

app = FastAPI(title="Bug Whisperer")
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")

EXAMPLES = [
    "hi. my receptionist booked mrs aisha for 3 march 2025 by accident (we meant 2027) and the "
    "system just saved it?? no warning nothing. it should not let us book in the past right. "
    "we are sunrise clinic",
    "we have 2 patients booked at 10:00 tomorrow with the same doctor?? how did the system allow that",
    "cant add a patient!!! i put the name and press add and it says something red. pls fix asap 😡",
]

# ---------------------------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------------------------

jobs: "queue.Queue[tuple[str, str]]" = queue.Queue()
waiting: list[str] = []


def worker() -> None:
    while True:
        kind, inv_id = jobs.get()
        try:
            inv = load_investigation(RUNS / inv_id)
            app_cfg = App.load(ROOT / inv.app_file)
            if kind == "investigate":
                if demo.hosted() and app_cfg.code_dir:
                    # Every live case starts from the clinic as the AI builder first wrote it.
                    from . import apprunner
                    demo.reset_clinic()
                    apprunner.restart(app_cfg)
                investigate(app_cfg, inv.report, inv.screenshot, inv=inv)
            elif kind == "fix":
                fix(app_cfg, inv)
        except Exception as exc:  # keep the worker alive; show the error on the page
            inv = load_investigation(RUNS / inv_id)
            target = inv.fix if kind == "fix" and inv.fix else None
            if target is not None:
                target.update(status="done", verdict="error", error=str(exc))
            else:
                inv.status, inv.verdict = "done", "inconclusive"
                inv.judgement = {"explanation": f"Bug Whisperer hit an error: {exc}"}
            inv.save()
        finally:
            if inv_id in waiting:
                waiting.remove(inv_id)
            jobs.task_done()


def boot_apps() -> None:
    """Start every connected app that has a start command and isn't running yet."""
    from . import apprunner
    for path in APPS.glob("*.json"):
        cfg = App.load(path)
        if cfg.start and not cfg.self_check and not apprunner.is_up(cfg):
            apprunner.start(cfg)


if demo.hosted():
    demo.seed_runs()      # recorded cases, so the site isn't empty on a fresh server
    demo.reset_clinic()   # the clinic as the AI builder first wrote it, bugs included

threading.Thread(target=worker, daemon=True).start()
if not __import__("os").environ.get("WHISPERER_NO_BOOT"):
    threading.Thread(target=boot_apps, daemon=True).start()


def enqueue(kind: str, inv_id: str) -> None:
    waiting.append(inv_id)
    jobs.put((kind, inv_id))


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------


def list_apps() -> list[dict]:
    out = []
    for path in sorted(APPS.glob("*.json")):
        cfg = App.load(path)
        if cfg.self_check:  # Bug Whisperer's own copy for Kane's self-checks: not a case to open
            continue
        out.append({"file": f"apps/{path.name}", "slug": path.stem, "name": cfg.name,
                    "url": cfg.base_url, "has_code": bool(cfg.code_dir), "about": cfg.about,
                    "accounts": list(cfg.accounts)})
    return out


def case_numbers() -> dict[str, int]:
    """Cases are numbered in the order they were opened: Case #1, #2, ..."""
    ids = sorted(p.parent.name for p in RUNS.glob("*/investigation.json"))
    return {inv_id: n for n, inv_id in enumerate(ids, start=1)}


def get_inv(inv_id: str) -> Investigation:
    if not ID_RE.match(inv_id) or not (RUNS / inv_id / "investigation.json").exists():
        raise HTTPException(404, "No such report")
    return load_investigation(RUNS / inv_id)


# The live tracker: what kind of action each Kane step was, and an icon for it.
STEP_KINDS = {"navigate": "go", "type": "type", "fill": "type", "click": "click", "select": "pick",
              "assert": "check", "analyze": "look", "press": "key", "key": "key", "scroll": "scroll",
              "wait": "wait"}
STEP_ICONS = {"go": "🧭", "type": "⌨️", "click": "👆", "pick": "☰", "check": "✔", "look": "🔎",
              "key": "⌨️", "scroll": "↕", "wait": "⏳", "think": "🕵️", "do": "•"}
templates.env.globals["step_icons"] = STEP_ICONS


def _step_kind(remark: str) -> str:
    prefix = remark.split(":", 1)[0].strip().lower() if ":" in remark else ""
    return STEP_KINDS.get(prefix, "do")


def _epoch(ts: str | None) -> float | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() if ts else None
    except ValueError:
        return None


def live_track(inv: Investigation) -> dict:
    """Kane at work, from its live NDJSON log: the steps so far (newest last), how many there
    have been, and how long Kane has been at it. Built only from Kane's own events, so it never
    touches Kane's browser."""
    logs = sorted(inv.folder.glob("*.ndjson"), key=lambda p: p.stat().st_mtime)
    if not logs:
        return {"steps": [], "total": 0, "hidden": 0, "elapsed": 0, "run": ""}
    started, busy = None, False
    steps: dict[int, dict] = {}
    for line in logs[-1].read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        started = started or _epoch(event.get("ts"))
        if event.get("type") in kane.COMPLETION_EVENTS:
            busy = False
        elif "step" in event and "type" not in event:
            # Kane announces a step as it starts ("Step 4", running) and describes it when done.
            busy = event.get("status") == "running"
        if "step" in event and "type" not in event and event.get("remark") and not INTERNAL_REMARK.match(event["remark"]):
            line = speak(event["remark"])
            if line is None and event.get("status") != "running":
                continue  # Kane's bookkeeping: not something the detective says out loud
            key = len(steps) if event.get("status") != "running" else -1
            steps[key] = {"status": event.get("status"), "remark": line or _plain(event["remark"]),
                          "kind": _step_kind(event["remark"])}
    ordered = _collapse(steps)
    total = len(ordered)
    if busy and not (ordered and ordered[-1]["status"] == "running"):
        ordered.append({"status": "running", "remark": "Working out the next move…", "kind": "think"})
    elapsed = int(time.time() - started) if started else 0
    return {"steps": ordered[-14:], "total": total, "hidden": max(0, len(ordered) - 14),
            "elapsed": max(0, elapsed), "run": logs[-1].stem}  # which Kane run: its steps count from 1


def live_steps(inv: Investigation) -> list[dict]:
    """Kane's steps so far (see live_track)."""
    return live_track(inv)["steps"]


def _collapse(steps: dict[int, dict]) -> list[dict]:
    """Steps in order, repeats folded, and the step Kane is on right now last."""
    running = steps.pop(-1, None)
    ordered = []
    for k in sorted(steps):  # 'I pressed Tab.' five times in a row → 'I pressed Tab. (×5)'
        step = steps[k]
        if ordered and ordered[-1]["remark"].split(" (×")[0] == step["remark"] and ordered[-1]["status"] == step["status"]:
            base, _, count = ordered[-1]["remark"].partition(" (×")
            ordered[-1]["remark"] = f"{base} (×{int(count.rstrip(')') or 1) + 1})"
        else:
            ordered.append(dict(step))
    if running and (not ordered or ordered[-1]["remark"] != running["remark"]):
        ordered.append(running)
    return ordered


MAX_FRAMES = 12
FRAME_SECONDS = 1.2


def _full_check(line: str, objective: str) -> str:
    """Kane shortens long step names in its logs ('…is al'). The full sentence is in the
    objective's 'Verify that …', so use it when the logged check is the start of it."""
    match = re.search(r"Verify that (.+?)\.?\s*$", objective or "", re.S)
    if not match or not line.startswith("I checked: "):
        return line
    full = match.group(1).strip()
    logged = line[len("I checked: "):].rstrip(".").strip()
    if len(logged) >= 15 and full.lower().startswith(logged.lower()[:60]):
        return f"I checked: {full[0].upper()}{full[1:]}."
    return line


def replay(inv: Investigation) -> dict | None:
    """'Watch Kane solve this case': Kane's real screenshots, each with Kane's own line."""
    chapters = []
    objective = (inv.plan or {}).get("objective", "")

    def frames(kane: dict | None) -> list[dict]:
        out = []
        for shot in (kane or {}).get("shots", []):
            line = speak(shot.get("summary"))
            if not line:
                continue
            line = _full_check(line, objective)
            failed = shot.get("status") == "failed"
            if failed and line.startswith("I checked:"):
                line = line[:-1] + ". It wasn't true."
            if out and out[-1]["line"] == line:
                continue
            out.append({"src": f"/files/{inv.id}/{kane['shots_dir']}/{shot['file']}",
                        "line": line, "failed": failed})
        # Long runs: keep how Kane got in, and the part where the case was decided.
        return out if len(out) <= MAX_FRAMES else out[:4] + out[-(MAX_FRAMES - 4):]

    scene = frames(inv.kane)
    if scene:
        chapters.append({"title": "At the scene", "frames": scene})
    attempts = (inv.fix or {}).get("attempts") or []
    if attempts:
        after = frames(attempts[-1].get("kane"))
        if after:
            chapters.append({"title": "Back at the scene, after the repair", "frames": after})
    if not chapters:
        return None

    fixv = (inv.fix or {}).get("verdict")
    if fixv == "fixed":
        end = {"stamp": "Case closed", "tone": "ok", "line": "I saw the fix with my own eyes."}
    elif inv.verdict == "reproduced":
        end = {"stamp": "Confirmed", "tone": "bug", "line": "The bug is real. Here's my evidence."}
    elif inv.verdict == "not_reproduced":
        end = {"stamp": "Open", "tone": "neutral", "line": "I couldn't make it happen. I need more from the user."}
    else:
        end = {"stamp": "Unsolved", "tone": "warn", "line": "I couldn't finish, so I claim nothing."}
    count = sum(len(c["frames"]) for c in chapters)
    return {"chapters": chapters, "end": end, "count": count, "seconds": round(count * FRAME_SECONDS)}


def _plain(remark: str) -> str:
    """Kane remarks look like 'click: Clicking Log in'. Keep the readable part."""
    remark = re.sub(r"^(PRIMARY|SECONDARY):\s*", "", remark)
    remark = re.sub(r"\{\{(global|secrets\.user)\.", "{{", remark)
    return remark.split(": ", 1)[1] if re.match(r"^[a-z_]+: ", remark) else remark


def view(inv: Investigation) -> dict:
    """Everything the templates need, worked out once."""
    app_cfg = App.load(ROOT / inv.app_file) if inv.app_file and (ROOT / inv.app_file).exists() else None
    fixing = bool(inv.fix) and inv.fix.get("status") != "done"
    investigating = inv.status not in ("done",)
    last_try = inv.fix["attempts"][-1]["kane"] if inv.fix.get("attempts") else None
    track = live_track(inv) if (investigating or fixing) else {"steps": [], "total": 0, "hidden": 0, "elapsed": 0}
    return {
        "inv": inv,
        "case_no": case_numbers().get(inv.id),
        "app_cfg": app_cfg,
        "active": investigating or fixing,
        "queued": inv.id in waiting and (inv.status == "queued" or inv.fix.get("status") == "queued"),
        "track": track,
        "scene": kane_scene(inv, track, inv.id in waiting and (inv.status == "queued" or inv.fix.get("status") == "queued"))
                 if (investigating or fixing) else None,
        "steps": track["steps"],
        "can_fix": inv.verdict == "reproduced" and app_cfg is not None and bool(app_cfg.code_dir)
                   and (not inv.fix or (inv.fix.get("status") == "done"
                                        and inv.fix.get("verdict") in ("needs_human", "inconclusive", "error"))),
        "retry": bool(inv.fix) and inv.fix.get("verdict") in ("needs_human", "inconclusive", "error"),
        "before": _key_shot(inv.kane),
        "after": _key_shot(last_try) if last_try else None,
        "trail": scene_trail(inv.kane, (inv.plan or {}).get("objective", "")) if not (investigating or fixing) else [],
        "trail_after": scene_trail(last_try, (inv.plan or {}).get("objective", "")) if last_try and not (investigating or fixing) else [],
        "board": evidence_board(inv, _key_shot(inv.kane), _key_shot(last_try) if last_try else None),
        "user_shot": Path(inv.screenshot).name if inv.screenshot else None,
        "reply": reply_for_user(inv),
        "ticket_md": ticket_markdown(inv),
        "replay": replay(inv) if not (investigating or fixing) else None,
        "live_shot": _live_shot(inv) if (investigating or fixing) else None,
        "speak": speak,
    }


def _live_shot(inv: Investigation) -> str | None:
    """Kane's browser right now: the camera's latest frame, if it's fresh."""
    frame = inv.folder / "live.jpg"
    try:
        if time.time() - frame.stat().st_mtime < 15:
            return f"/files/{inv.id}/live.jpg?t={int(frame.stat().st_mtime * 1000)}"
    except OSError:
        pass
    return None


RANKS = [(0, "Rookie"), (1, "Gumshoe"), (3, "Sleuth"), (6, "Inspector"), (10, "Chief Inspector")]


def detective_rank(closed: int) -> dict:
    """Detective Kane's rank, earned only by cases really closed (Kane saw the fix itself)."""
    name, start, nxt = RANKS[0][1], 0, None
    for i, (needed, title) in enumerate(RANKS):
        if closed >= needed:
            name, start = title, needed
            nxt = RANKS[i + 1] if i + 1 < len(RANKS) else None
    progress = 100 if not nxt else int(100 * (closed - start) / (nxt[0] - start))
    return {"name": name, "closed": closed, "next": nxt[1] if nxt else None,
            "to_next": (nxt[0] - closed) if nxt else 0, "progress": progress}


def kane_scene(inv: Investigation, track: dict, queued: bool) -> dict | None:
    """What Detective Kane is doing and saying right now, for the RPG scene. Every line is a real
    state of the case or one of Kane's real steps. None when the case is finished."""
    fixs = (inv.fix or {}).get("status", "")
    latest = next((s["remark"] for s in reversed(track["steps"]) if s["status"] != "running"), None)
    if queued:
        return {"mode": "idle", "line": "Another case on my desk. I work one at a time, and this one is next."}
    if inv.status in ("planning", "queued"):
        return {"mode": "reading", "line": "Claude is reading the witness statement and writing my orders…"}
    if inv.status == "re-planning":
        return {"mode": "reading", "line": "I lost the trail last time. Claude is rewriting my orders from my own notes…"}
    if inv.status == "reproducing":
        return {"mode": "walking", "line": latest or "Heading to the scene. A real browser, the user's own steps."}
    if inv.status == "judging":
        return {"mode": "reading", "line": "I found something. Claude is checking it matches the witness statement…"}
    if inv.status == "double-checking":
        return {"mode": "walking", "line": "Before I call it, I'm checking the witness's claim with my own eyes."}
    if fixs.startswith("fixing") or fixs == "queued":
        return {"mode": "reading", "line": "Claude is repairing the code, using only my evidence. I'll check it myself after."}
    if fixs.startswith("waiting"):
        return {"mode": "idle", "line": "The app is restarting with the repair…"}
    if fixs.startswith("Kane"):
        return {"mode": "walking", "line": latest or "Back to the scene. Same steps, no taking Claude's word for it."}
    return None


def _room_name(url: str) -> tuple[str, str]:
    """A page as a room on the scene map: a readable name and its path."""
    parts = urlsplit(url)
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    words = [p for p in parts.path.split("/") if p]
    name = " · ".join(f"#{w}" if w.isdigit() else w.replace("-", " ").replace("_", " ").capitalize()
                      for w in words) or "Home"
    return name, path


def scene_trail(kane: dict | None, objective: str) -> list[dict]:
    """The scene map: the app as the dungeon. Each room is a page Kane really visited (from the
    page address on each of his screenshots), in the order he went, with what he did there. The
    room where his check failed is the clue room."""
    rooms: list[dict] = []
    for shot in (kane or {}).get("shots") or []:
        url = shot.get("url") or ""
        if not url:
            continue
        if not rooms or rooms[-1]["url"] != url:
            name, path = _room_name(url)
            rooms.append({"url": url, "name": name, "path": path, "actions": [], "clue": False})
        room = rooms[-1]
        remark = shot.get("summary") or ""
        line = speak(remark)
        if line:
            line = _full_check(line, objective)
            # 'I went to http://host/appointments/new.' -> 'I went to /appointments/new.' (short, fits a room)
            line = re.sub(r"https?://[^/\s]+(/[^\s]*)?", lambda m: m.group(1) or "/", line)
            if not room["actions"] or room["actions"][-1]["text"] != line:
                room["actions"].append({"kind": _step_kind(remark), "text": line, "status": shot.get("status")})
        if shot.get("status") == "failed":
            room["clue"] = True
    return rooms


def case_stamp(inv: Investigation) -> tuple[str, str]:
    """The stamp on a case, as pinned on the boards: its words and its tone."""
    fix_verdict = inv.fix.get("verdict") if inv.fix else None
    if fix_verdict == "fixed":
        return "Case closed", "ok"
    if inv.fix and inv.fix.get("status") != "done":
        return "Repairing", "work"
    if inv.status != "done":
        return "Investigating", "work"
    if fix_verdict == "needs_human":
        return "Handed to a person", "warn"
    if fix_verdict in ("inconclusive", "error") or inv.verdict == "inconclusive":
        return "Unsolved", "warn"
    if inv.verdict == "reproduced":
        return "Confirmed", "bug"
    return "Open", "neutral"


def tilt(key: str) -> float:
    """A small tilt for a pinned note, so a board looks pinned by hand. Same on every visit."""
    return round((int(hashlib.sha1(key.encode()).hexdigest()[:4], 16) % 9 - 4) * 0.7, 1)


templates.env.globals["tilt"] = tilt


def _diff_lines(patch: str, limit: int = 6) -> list[str]:
    lines = [l for l in (patch or "").splitlines()
             if l[:1] in "+-" and not l.startswith(("+++", "---"))]
    return lines[:limit]


def _caption(remark: str, inv: Investigation) -> str:
    """A photo's caption in Kane's own voice, with Kane's shortened check written out in full."""
    return _full_check(speak(remark) or remark, (inv.plan or {}).get("objective", ""))


def evidence_board(inv: Investigation, before: dict | None, after: dict | None) -> dict | None:
    """The case laid out as a detective's evidence wall: real pieces of evidence, joined by red
    string in the order the investigation actually went. None until there's a verdict."""
    if inv.status != "done" or not inv.verdict:
        return None
    pins = [{"id": "statement", "kind": "hand", "title": "Witness statement",
             "body": inv.report[:220] + ("…" if len(inv.report) > 220 else "")}]
    links = []
    if (inv.plan or {}).get("understanding"):
        pins.append({"id": "reading", "kind": "typed", "title": "Claude's reading",
                     "body": inv.plan["understanding"]})
        links.append(("statement", "reading"))
    if before:
        pins.append({"id": "scene", "kind": "photo", "title": "Kane at the scene",
                     "img": f"/files/{inv.id}/{before['dir']}/{before['file']}",
                     "body": _caption(before.get("summary", ""), inv)})
        links.append((pins[-2]["id"], "scene"))
    if inv.claim:
        outcome = {"confirmed": "✓ true", "not_true": "✗ not true"}.get(inv.claim.get("outcome"), "? unknown")
        pins.append({"id": "claim", "kind": "typed", "title": f"Claim checked: {outcome}",
                     "body": inv.claim.get("objective", "")[:160]})
    stamp = {"reproduced": ("Confirmed", "bug"), "not_reproduced": ("Open", "neutral"),
             "needs_info": ("Open", "neutral")}.get(inv.verdict, ("Unsolved", "warn"))
    pins.append({"id": "verdict", "kind": "stamp", "stamp": stamp[0], "tone": stamp[1],
                 "body": (inv.judgement or {}).get("explanation", "")[:180]})
    links.append(("scene" if before else pins[0]["id"], "verdict"))
    if inv.claim:
        links.append(("claim", "verdict"))
    attempts = (inv.fix or {}).get("attempts") or []
    if attempts:
        last = attempts[-1]
        pins.append({"id": "repair", "kind": "diff", "title": f"Claude's repair · attempt {last.get('attempt', len(attempts))}",
                     "lines": _diff_lines(last.get("patch", ""))})
        links.append(("verdict", "repair"))
        if after:
            pins.append({"id": "recheck", "kind": "photo", "title": "Kane, back at the scene",
                         "img": f"/files/{inv.id}/{after['dir']}/{after['file']}",
                         "body": _caption(after.get("summary", ""), inv)})
            links.append(("repair", "recheck"))
    if inv.fix and inv.fix.get("status") == "done":
        words, tone = case_stamp(inv)
        test = inv.fix.get("regression_test")
        pins.append({"id": "closed", "kind": "stamp", "stamp": words, "tone": tone,
                     "body": f"Kept on file: {test}" if test else ""})
        links.append(("recheck" if after and attempts else "verdict", "closed"))
    return {"pins": pins, "links": links}


def _key_shot(kane: dict | None) -> dict | None:
    """The screenshot that matters: the step that failed, or else the last one."""
    if not kane or not kane.get("shots"):
        return None
    shots = kane["shots"]
    shot = next((s for s in reversed(shots) if s.get("status") == "failed"), shots[-1])
    return {**shot, "dir": kane.get("shots_dir")}


def reply_for_user(inv: Investigation) -> str | None:
    expected = (inv.plan or {}).get("expected", "")
    if inv.fix.get("verdict") == "fixed":
        return ("Thanks for telling us! We followed your exact steps and saw the same problem, and "
                f"it's fixed now. {expected} We checked the fix by doing the same steps again, and "
                "we'll re-check them after every future change, so it stays fixed.")
    if inv.verdict == "not_reproduced" and inv.claim.get("outcome") == "not_true":
        return ("Thanks for telling us! We followed your steps and checked carefully, and the app "
                "doesn't seem to work the way the report assumes. Could you send a screenshot or "
                "the exact page you were on, so we can look again?")
    if inv.verdict == "not_reproduced":
        return ("Thanks for telling us! We followed your steps and it worked for us. Could you tell "
                "us the exact day and time you tried, and what you saw on the screen?")
    if inv.verdict == "needs_info":
        return f"Thanks for telling us! One quick question so we can find it: {inv.plan.get('question')}"
    return None


def ticket_markdown(inv: Investigation) -> str | None:
    ticket = (inv.judgement or {}).get("ticket")
    if not ticket:
        return None
    steps = "\n".join(f"{i}. {s}" for i, s in enumerate(ticket.get("steps", []), start=1))
    return (f"## {ticket.get('title', 'Bug')}\n\n**Steps**\n{steps}\n\n"
            f"**Expected:** {ticket.get('expected', '')}\n\n**Actual:** {ticket.get('actual', '')}\n\n"
            f"Reproduced by Kane CLI (Bug Whisperer report {inv.id}).")


def _shot_caption(shot: dict | None, inv: Investigation) -> str:
    """A photo's caption with Kane's result for that step: ✗ when his check failed there."""
    if not shot:
        return ""
    mark = {"failed": "✗ not as expected", "passed": "✓ as expected"}.get(shot.get("status"), "")
    line = _caption(shot.get("summary", ""), inv)
    return f"{mark}. {line}" if mark and line.startswith("I checked") else line


def case_report(inv: Investigation) -> dict:
    """Everything a case proved, for the exported report. Only what was recorded: no new claims."""
    from .proof import _kane_runs
    stamp, tone = case_stamp(inv)
    record = json.loads(json.dumps(asdict(inv), default=str))
    runs = _kane_runs(record)
    last_try = inv.fix["attempts"][-1] if (inv.fix or {}).get("attempts") else None
    objective = (inv.plan or {}).get("objective", "")
    before = _key_shot(inv.kane)
    after = _key_shot(last_try["kane"]) if last_try else None
    steps = [_full_check(line, objective) for line in
             (speak(r) for r in (inv.kane or {}).get("steps") or []) if line]
    return {
        "inv": inv, "case_no": case_numbers().get(inv.id), "stamp": stamp, "tone": tone,
        "title": ((inv.judgement or {}).get("ticket") or {}).get("title") or inv.report[:80],
        "steps": steps, "before": before, "after": after, "last_try": last_try,
        "before_caption": _shot_caption(before, inv), "after_caption": _shot_caption(after, inv),
        # the verdict of the investigation itself (the header carries where the case ended up)
        "verdict_stamp": {"reproduced": "Confirmed", "not_reproduced": "Open", "needs_info": "Open"}.get(inv.verdict, "Unsolved"),
        "verdict_tone": {"reproduced": "bug", "not_reproduced": "neutral", "needs_info": "neutral"}.get(inv.verdict, "warn"),
        "kane_runs": len(runs), "credits": round(sum(r.get("credits") or 0 for r in runs), 1),
        "seconds": round(sum(r.get("duration") or 0 for r in runs)),
        "ticket_md": ticket_markdown(inv), "reply": reply_for_user(inv),
        "generated": time.strftime("%Y-%m-%d %H:%M"),
    }


def report_markdown(inv: Investigation) -> str:
    """The case report as Markdown, for GitHub, Jira or Notion."""
    r = case_report(inv)
    lines = [f"# Case #{r['case_no']}: {r['title']}", "",
             f"**{r['stamp'].upper()}** · {inv.app} · opened {inv.created} · report {inv.id}", "",
             "## The report", "", f"> {inv.report}", ""]
    if (inv.plan or {}).get("understanding"):
        lines += ["**What the user most likely did:** " + inv.plan["understanding"], ""]
    if (inv.plan or {}).get("expected"):
        lines += ["**What should happen:** " + inv.plan["expected"], ""]
    lines += ["## What Kane did, in a real browser", ""]
    lines += [f"{i}. {step}" for i, step in enumerate(r["steps"], start=1)] or ["(no steps recorded)"]
    lines += ["", "## Verdict", ""]
    explanation = (inv.judgement or {}).get("explanation") or (inv.kane or {}).get("summary") or ""
    lines += [f"**{r['verdict_stamp']}.** {explanation}".strip(), ""]
    if inv.claim:
        lines += [f"**Claim checked by Kane:** {inv.claim.get('outcome', 'unknown')}: {inv.claim.get('objective', '')}", ""]
    if r["last_try"]:
        t = r["last_try"]
        lines += ["## The repair", "", (t.get("fixer_said") or "").strip(), "", "```diff", (t.get("patch") or "").strip(), "```", "",
                  f"**Kane went back and repeated the same steps:** {t['kane'].get('verdict')}. {t['kane'].get('summary') or ''}".strip(), ""]
        if (inv.fix or {}).get("regression_test"):
            lines += [f"**Kept on file as a regression test:** `{inv.fix['regression_test']}`", ""]
    if r["ticket_md"]:
        lines += ["## Bug ticket", "", r["ticket_md"].replace("## ", "### ", 1), ""]
    lines += ["---", f"Proved by Kane CLI: {r['kane_runs']} run(s), about {r['seconds']} s, {r['credits']} credits. "
              f"Generated by Bug Whisperer on {r['generated']}."]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------------------------


PASS_COOKIE = "bw_pass"


def unlocked(request: Request) -> bool:
    """Live runs are open locally; on the hosted demo they need the judges' passcode."""
    if not demo.hosted():
        return True
    token = demo.passcode_token()
    return bool(token) and request.cookies.get(PASS_COOKIE) == token


def live_gate(request: Request):
    """None if a live job may start, else a page explaining why not."""
    if not unlocked(request):
        return RedirectResponse("/unlock", status_code=303)
    if demo.hosted() and demo.used_today() >= demo.daily_limit():
        return templates.TemplateResponse(request, "unlock.html", {
            "page": "report", "limit_reached": True, "limit": demo.daily_limit()}, status_code=429)
    return None


@app.exception_handler(StarletteHTTPException)
async def friendly_errors(request: Request, exc: StarletteHTTPException):
    """A browser that asks for a page that isn't there gets Kane's not-found page."""
    if exc.status_code == 404 and "text/html" in request.headers.get("accept", ""):
        return templates.TemplateResponse(request, "not_found.html", {"page": None, "what": exc.detail},
                                          status_code=404)
    return await http_exception_handler(request, exc)


@app.middleware("http")
async def demo_context(request: Request, call_next):
    request.state.hosted = demo.hosted()
    request.state.unlocked = unlocked(request)
    return await call_next(request)


@app.get("/unlock", response_class=HTMLResponse)
def unlock_page(request: Request, wrong: int = 0):
    return templates.TemplateResponse(request, "unlock.html", {"page": "report", "wrong": wrong})


@app.post("/unlock")
def unlock(passcode: str = Form("")):
    token = demo.passcode_token()
    tried = hashlib.sha256(("bug-whisperer:" + passcode).encode()).hexdigest()
    if not token or not hmac.compare_digest(tried, token):
        return RedirectResponse("/unlock?wrong=1", status_code=303)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(PASS_COOKIE, token, httponly=True, samesite="lax", max_age=7 * 24 * 3600)
    return response


def featured_case() -> dict | None:
    """The newest case Kane closed, with its before/after screens: proof on the front page."""
    for folder in sorted(RUNS.glob("*/investigation.json"), reverse=True):
        try:
            inv = load_investigation(folder.parent)
        except (json.JSONDecodeError, TypeError):
            continue
        v = view(inv)
        if inv.fix.get("verdict") == "fixed" and v["before"] and v["after"]:
            return v
    return None


def recent_cases(limit: int = 3) -> list[dict]:
    """Newest real case files for the compact front-page strip."""
    numbers = case_numbers()
    cards = []
    for folder in sorted(RUNS.glob("*/investigation.json"), reverse=True):
        try:
            inv = load_investigation(folder.parent)
        except (json.JSONDecodeError, TypeError):
            continue
        stamp, tone = case_stamp(inv)
        ticket = (inv.judgement.get("ticket") or {}) if inv.judgement else {}
        cards.append({"inv": inv, "case_no": numbers.get(inv.id), "stamp": stamp, "tone": tone,
                      "title": ticket.get("title") or inv.report[:72]})
        if len(cards) == limit:
            break
    return cards


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "report.html", {
        "apps": list_apps(), "examples": EXAMPLES, "page": "report", "featured": featured_case(),
        "recent": recent_cases()})


async def _read_uploads(files: list[UploadFile]) -> list[tuple[str, bytes]]:
    """The uploaded files that are allowed, as (safe name, bytes)."""
    out, seen = [], set()
    for f in [f for f in files if f and f.filename][: intake.MAX_FILES]:
        name = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(f.filename).name).strip("-.") or "file"
        if Path(name).suffix.lower() not in intake.ALLOWED:
            raise HTTPException(400, f"{f.filename}: Bug Whisperer reads spreadsheets (.xlsx, .csv), documents "
                                     "(.docx, .txt, .md, .pdf), test reports (.xml, .json, .html) and screenshots")
        data = await f.read()
        if len(data) > MAX_UPLOAD:
            raise HTTPException(400, f"{f.filename} is over 5 MB")
        while name in seen:
            name = "copy-" + name
        seen.add(name)
        out.append((name, data))
    return out


@app.post("/report")
async def submit(request: Request, app_file: str = Form(...), report: str = Form(""),
                 screenshot: UploadFile | None = File(None), files: list[UploadFile] = File(default=[])):
    gate = live_gate(request)
    if gate is not None:
        return gate
    valid = {a["file"] for a in list_apps()}
    uploads = await _read_uploads([*files, screenshot] if screenshot else files)
    if app_file not in valid or not (report.strip() or uploads):
        raise HTTPException(400, "Choose an app, and describe the problem or upload your test results")
    cfg = App.load(ROOT / app_file)
    # Test results (or several screenshots) are read by Claude and split into cases, one per problem.
    single_shot = len(uploads) == 1 and Path(uploads[0][0]).suffix.lower() in intake.IMAGE_SUFFIXES
    if uploads and not (single_shot and report.strip()):
        job = intake.Intake(app=cfg.name, app_file=app_file, note=report.strip()[:4000])
        for name, data in uploads:
            (job.folder / name).write_bytes(data)
            job.files.append(name)
        job.save()
        threading.Thread(target=intake.run, args=(job, enqueue), daemon=True).start()
        return RedirectResponse(f"/intake/{job.id}", status_code=303)
    screenshot = None
    if uploads:  # one screenshot with a typed report: an ordinary single case
        name, data = uploads[0]
        screenshot = (Path(name).suffix.lower(), data)
    return _single_case(cfg, app_file, report, screenshot)


def _single_case(cfg: App, app_file: str, report: str, shot: tuple[str, bytes] | None):
    inv = Investigation(report=report.strip()[:4000], app=cfg.name, app_file=app_file)
    inv.status = "queued"
    if shot:
        suffix, data = shot
        path = inv.folder / ("user-screenshot" + (".jpg" if suffix == ".jpeg" else suffix))
        path.write_bytes(data)
        inv.screenshot = str(path)
    inv.save()
    if demo.hosted():
        demo.count_job()
    enqueue("investigate", inv.id)
    return RedirectResponse(f"/r/{inv.id}", status_code=303)


def _intake_view(intake_id: str) -> dict:
    try:
        job = intake.Intake.load(intake_id)
    except (FileNotFoundError, json.JSONDecodeError):
        raise HTTPException(404)
    excerpt = ""
    for name in job.files:  # the real text the detective is reading, for the reading scene
        text = intake.file_text(job.folder / name)
        if text:
            excerpt = text[:900]
            break
    cases = []
    for inv_id in job.cases:
        try:
            cases.append(load_investigation(RUNS / inv_id))
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            continue
    cards = [{"inv": c, "stamp": case_stamp(c), "shot": _key_shot(c.kane),
              "title": (c.judgement.get("ticket") or {}).get("title") if c.judgement else None} for c in cases]
    return {"job": job, "excerpt": excerpt or job.note, "cards": cards, "case_no": case_numbers(),
            "active": job.status == "reading"}


@app.get("/intake/{intake_id}", response_class=HTMLResponse)
def intake_page(request: Request, intake_id: str):
    return templates.TemplateResponse(request, "intake.html", {**_intake_view(intake_id), "page": "report"})


@app.get("/intake/{intake_id}/live", response_class=HTMLResponse)
def intake_live(request: Request, intake_id: str):
    return templates.TemplateResponse(request, "_intake_live.html", _intake_view(intake_id))


@app.get("/r/{inv_id}", response_class=HTMLResponse)
def report_page(request: Request, inv_id: str):
    return templates.TemplateResponse(request, "investigation.html", {**view(get_inv(inv_id)), "page": "inbox"})


@app.get("/r/{inv_id}/report", response_class=HTMLResponse)
def report_export(request: Request, inv_id: str):
    """The case report, laid out for paper: print it or save it as a PDF."""
    return templates.TemplateResponse(request, "case_report.html", {**case_report(get_inv(inv_id)), "page": "inbox"})


@app.get("/r/{inv_id}/report.md")
def report_export_md(inv_id: str):
    inv = get_inv(inv_id)
    return Response(report_markdown(inv), media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="bug-whisperer-case-{inv.id}.md"'})


@app.get("/r/{inv_id}/live", response_class=HTMLResponse)
def report_live(request: Request, inv_id: str):
    return templates.TemplateResponse(request, "_live.html", view(get_inv(inv_id)))


@app.post("/r/{inv_id}/fix")
def start_fix(request: Request, inv_id: str):
    gate = live_gate(request)
    if gate is not None:
        return gate
    v = view(get_inv(inv_id))
    if not v["can_fix"]:
        raise HTTPException(400, "This report can't be fixed automatically")
    inv = v["inv"]
    if inv.fix.get("attempts"):
        inv.fix_history.append(inv.fix)  # keep the earlier try as evidence
    inv.fix = {"status": "queued", "attempts": [], "verdict": None}
    inv.save()
    if demo.hosted():
        demo.count_job()
    enqueue("fix", inv.id)
    return RedirectResponse(f"/r/{inv.id}", status_code=303)


@app.get("/apps", response_class=HTMLResponse)
def apps_page(request: Request, added: str | None = None):
    return templates.TemplateResponse(request, "apps.html", {
        "apps": list_apps(), "added": added, "page": "apps", "form": {}, "errors": []})


SLUG_RE = re.compile(r"[^a-z0-9]+")


@app.post("/apps", response_class=HTMLResponse)
async def connect_app(request: Request):
    if demo.hosted():
        # The public demo only tests our own sample apps: no strangers' sites through our Kane.
        raise HTTPException(403, "Connecting apps is turned off on the public demo. Run Bug Whisperer locally to connect your own.")
    form = dict(await request.form())
    errors = []
    name = form.get("name", "").strip()
    url = form.get("url", "").strip()
    if not name:
        errors.append("Give the app a name.")
    if not re.match(r"^https?://[^\s/]+", url):
        errors.append("The link must start with http:// or https://")
    if form.get("permission") != "yes":
        errors.append("Only connect apps you own or have permission to test.")
    slug = SLUG_RE.sub("-", name.lower()).strip("-")[:40] or "app"
    path = APPS / f"{slug}.json"
    if path.exists():
        errors.append(f"An app called {name!r} is already connected.")
    code_dir = form.get("code_dir", "").strip()
    if code_dir and not (ROOT / code_dir).is_dir():
        errors.append(f"The code folder {code_dir!r} doesn't exist on this computer.")
    if errors:
        return templates.TemplateResponse(request, "apps.html", {
            "apps": list_apps(), "page": "apps", "form": form, "errors": errors}, status_code=400)

    accounts, passwords = {}, {}
    for i in (1, 2):
        label = form.get(f"label{i}", "").strip()
        email = form.get(f"email{i}", "").strip()
        if label and email:
            accounts[label] = {"email": email, "password": ""}
            passwords[label] = form.get(f"password{i}", "")
    config = {
        "name": name, "base_url": url.rstrip("/"), "login_path": form.get("login_path", "").strip(),
        "accounts": accounts, "about": form.get("about", "").strip()[:500],
        "code_dir": code_dir or None,
        "start": form.get("start", "").split() or None,
        "reset": form.get("reset", "").split() or None,
    }
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    if passwords:
        (APPS / "secrets").mkdir(exist_ok=True)
        (APPS / "secrets" / path.name).write_text(json.dumps(passwords, indent=2), encoding="utf-8")
    return RedirectResponse(f"/apps?added={slug}", status_code=303)


templates.env.filters["verdict_words"] = lambda v: {
    "reproduced": "Confirmed", "not_reproduced": "Open: not reproduced",
    "needs_info": "Open: asked the user", "inconclusive": "Unsolved"}.get(v, v)


@app.get("/verified", response_class=HTMLResponse)
def verified(request: Request):
    """The proof a judge can check fast: read from docs/proof/results.json (python -m whisperer proof)."""
    path = ROOT / "docs" / "proof" / "results.json"
    if not path.exists():
        raise HTTPException(404, "No results yet")
    return templates.TemplateResponse(request, "verified.html", {
        "r": json.loads(path.read_text(encoding="utf-8")), "page": "verified"})


def lineup_view(data: dict) -> dict:
    """The Lineup page: the suspects in a row, and every questioning in the order Kane did it."""
    rows = data["suspects"]
    witnesses = [{**data["good"], "role": "Last good version"}, {**data["bad"], "role": "Broken version"}]
    asked = sorted([r for r in rows + witnesses if r.get("asked_as")], key=lambda r: r["asked_as"])
    seen, questionings = set(), []
    for r in asked:  # the broken version can also be the last suspect: list it once
        if r["asked_as"] not in seen:
            seen.add(r["asked_as"])
            questionings.append(r)
    from . import lineup
    stage = lineup.stage(data) if data["status"] == "done" and questionings else None
    return {"l": data, "rows": rows, "questionings": questionings, "stage": stage,
            "culprit": next((r for r in rows if r["status"] == "guilty"), None),
            "active": data["status"] != "done", "now": data.get("now"),
            "repo": "https://github.com/sam838/bug-whisperer"}


@app.get("/lineups", response_class=HTMLResponse)
def lineups_page(request: Request):
    from . import lineup
    return templates.TemplateResponse(request, "lineups.html", {"lineups": lineup.all_lineups(), "page": "verified"})


def _lineup(lineup_id: str) -> dict:
    from . import lineup
    try:
        return lineup_view(lineup.load(lineup_id))
    except FileNotFoundError:
        raise HTTPException(404, "No lineup with that name")


@app.get("/lineup/{lineup_id}", response_class=HTMLResponse)
def lineup_page(request: Request, lineup_id: str):
    return templates.TemplateResponse(request, "lineup.html", {**_lineup(lineup_id), "page": "verified"})


@app.get("/lineup/{lineup_id}/live", response_class=HTMLResponse)
def lineup_live(request: Request, lineup_id: str):
    return templates.TemplateResponse(request, "_lineup_live.html", _lineup(lineup_id))


@app.get("/inbox", response_class=HTMLResponse)
def inbox(request: Request):
    items = []
    for folder in sorted(RUNS.glob("*/investigation.json"), reverse=True):
        try:
            items.append(load_investigation(folder.parent))
        except (json.JSONDecodeError, TypeError):
            continue
    # Red string joins cases from the same app (the same scene), in the order they were opened.
    by_app: dict[str, list[str]] = {}
    for inv in sorted(items, key=lambda i: i.id):
        by_app.setdefault(inv.app, []).append(inv.id)
    links = [(a, b) for ids in by_app.values() for a, b in zip(ids, ids[1:])]
    cards = [{"inv": inv, "stamp": case_stamp(inv), "shot": _key_shot(inv.kane),
              "title": (inv.judgement.get("ticket") or {}).get("title") if inv.judgement else None}
             for inv in items]
    closed = sum(1 for inv in items if inv.fix and inv.fix.get("verdict") == "fixed")
    return templates.TemplateResponse(request, "inbox.html", {
        "items": items, "cards": cards, "links": links, "page": "inbox", "case_no": case_numbers(),
        "rank": detective_rank(closed), "opened": len(items)})


@app.get("/files/{inv_id}/{name:path}")
def files(inv_id: str, name: str):
    inv = get_inv(inv_id)
    path = (inv.folder / name).resolve()
    if inv.folder.resolve() not in path.parents or path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        raise HTTPException(404)
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path)

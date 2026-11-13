"""The Bug Whisperer website.

Run:  uvicorn whisperer.web:app --port 8000

One background worker runs jobs one at a time (Kane drives a real Chrome, and each run costs
credits), so reports wait in line. Pages poll a small HTML fragment while a job is running; live
Kane steps are read from the NDJSON log Kane is writing.
"""

from __future__ import annotations

import json
import queue
import re
import threading
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .detective import ROOT, RUNS, App, Investigation, investigate
from .fixer import fix, load_investigation

HERE = Path(__file__).resolve().parent
APPS = ROOT / "apps"
ID_RE = re.compile(r"^[0-9]{8}-[0-9]{6}(-[0-9a-f]{4})?$")
IMAGE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}
MAX_UPLOAD = 5 * 1024 * 1024
# Kane's own bookkeeping lines: true, but noise for someone watching.
INTERNAL_REMARK = re.compile(r"^(wait: queued plan|Step \d+$|analyze: ANALYZE\()")

app = FastAPI(title="Bug Whisperer")
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")

EXAMPLES = [
    "hi. my receptionist booked mrs aisha for 3 march 2025 by accident (we meant 2027) and the "
    "system just saved it?? no warning nothing. it should not let us book in the past right",
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
        if cfg.start and not apprunner.is_up(cfg):
            apprunner.start(cfg)


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
        out.append({"file": f"apps/{path.name}", "name": cfg.name, "url": cfg.base_url,
                    "has_code": bool(cfg.code_dir)})
    return out


def get_inv(inv_id: str) -> Investigation:
    if not ID_RE.match(inv_id) or not (RUNS / inv_id / "investigation.json").exists():
        raise HTTPException(404, "No such report")
    return load_investigation(RUNS / inv_id)


def live_steps(inv: Investigation) -> list[dict]:
    """Kane's steps so far, from the newest NDJSON log in the report's folder."""
    logs = sorted(inv.folder.glob("*.ndjson"), key=lambda p: p.stat().st_mtime)
    if not logs:
        return []
    steps: dict[int, dict] = {}
    for line in logs[-1].read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (isinstance(event, dict) and "step" in event and "type" not in event and event.get("remark")
                and not INTERNAL_REMARK.match(event["remark"])):
            key = len(steps) if event.get("status") != "running" else -1
            steps[key] = {"status": event.get("status"), "remark": _plain(event["remark"])}
    running = steps.pop(-1, None)
    ordered = [steps[k] for k in sorted(steps)]
    if running and (not ordered or ordered[-1]["remark"] != running["remark"]):
        ordered.append(running)
    return ordered[-14:]


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
    return {
        "inv": inv,
        "app_cfg": app_cfg,
        "active": investigating or fixing,
        "queued": inv.id in waiting and (inv.status == "queued" or inv.fix.get("status") == "queued"),
        "steps": live_steps(inv) if (investigating or fixing) else [],
        "can_fix": inv.verdict == "reproduced" and app_cfg is not None and bool(app_cfg.code_dir)
                   and (not inv.fix or (inv.fix.get("status") == "done"
                                        and inv.fix.get("verdict") in ("needs_human", "inconclusive", "error"))),
        "retry": bool(inv.fix) and inv.fix.get("verdict") in ("needs_human", "inconclusive", "error"),
        "before": _key_shot(inv.kane),
        "after": _key_shot(last_try) if last_try else None,
        "user_shot": Path(inv.screenshot).name if inv.screenshot else None,
        "reply": reply_for_user(inv),
        "ticket_md": ticket_markdown(inv),
    }


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
        return ("Thanks for telling us! We followed your steps and saw the same problem, and it's "
                f"fixed now. {expected} We checked the fix by doing the exact same steps again.")
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


# ---------------------------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "report.html", {
        "apps": list_apps(), "examples": EXAMPLES, "page": "report"})


@app.post("/report")
async def submit(request: Request, app_file: str = Form(...), report: str = Form(...),
                 screenshot: UploadFile | None = File(None)):
    valid = {a["file"] for a in list_apps()}
    if app_file not in valid or not report.strip():
        raise HTTPException(400, "Choose an app and describe the problem")
    cfg = App.load(ROOT / app_file)
    inv = Investigation(report=report.strip()[:4000], app=cfg.name, app_file=app_file)
    inv.status = "queued"
    if screenshot and screenshot.filename:
        if screenshot.content_type not in IMAGE_TYPES:
            raise HTTPException(400, "The screenshot must be a PNG, JPG, WEBP or GIF image")
        data = await screenshot.read()
        if len(data) > MAX_UPLOAD:
            raise HTTPException(400, "The screenshot must be under 5 MB")
        path = inv.folder / ("user-screenshot" + IMAGE_TYPES[screenshot.content_type])
        path.write_bytes(data)
        inv.screenshot = str(path)
    inv.save()
    enqueue("investigate", inv.id)
    return RedirectResponse(f"/r/{inv.id}", status_code=303)


@app.get("/r/{inv_id}", response_class=HTMLResponse)
def report_page(request: Request, inv_id: str):
    return templates.TemplateResponse(request, "investigation.html", {**view(get_inv(inv_id)), "page": "inbox"})


@app.get("/r/{inv_id}/live", response_class=HTMLResponse)
def report_live(request: Request, inv_id: str):
    return templates.TemplateResponse(request, "_live.html", view(get_inv(inv_id)))


@app.post("/r/{inv_id}/fix")
def start_fix(inv_id: str):
    v = view(get_inv(inv_id))
    if not v["can_fix"]:
        raise HTTPException(400, "This report can't be fixed automatically")
    inv = v["inv"]
    if inv.fix.get("attempts"):
        inv.fix_history.append(inv.fix)  # keep the earlier try as evidence
    inv.fix = {"status": "queued", "attempts": [], "verdict": None}
    inv.save()
    enqueue("fix", inv.id)
    return RedirectResponse(f"/r/{inv.id}", status_code=303)


@app.get("/inbox", response_class=HTMLResponse)
def inbox(request: Request):
    items = []
    for folder in sorted(RUNS.glob("*/investigation.json"), reverse=True):
        try:
            items.append(load_investigation(folder.parent))
        except (json.JSONDecodeError, TypeError):
            continue
    return templates.TemplateResponse(request, "inbox.html", {"items": items, "page": "inbox"})


@app.get("/files/{inv_id}/{name:path}")
def files(inv_id: str, name: str):
    inv = get_inv(inv_id)
    path = (inv.folder / name).resolve()
    if inv.folder.resolve() not in path.parents or path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        raise HTTPException(404)
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path)

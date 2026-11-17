"""Bug Whisperer in the terminal: the same cases as the website, followed live, step by step.

  bug-whisperer report "cant book!!! it just saved it"     one report, one case
  bug-whisperer report --file results.xlsx                  test results: one case per failure
  bug-whisperer repair <case>                                Claude repairs, Kane proves it
  bug-whisperer cases                                        what's on file

Every case is saved in runs/ like a website case, so `bug-whisperer up` shows it too, with the
3D replay and the PDF report.
"""

from __future__ import annotations

import json
import shutil
import socket
import sys
import threading
import time
from pathlib import Path

from . import voice
from .detective import RUNS, App, Investigation, investigate
from .paths import ROOT

SAYS = {  # what is happening, in Kane's words (the same states the website shows)
    "planning": "🧠 Claude is reading the report and writing Kane's orders…",
    "re-planning": "🧠 Kane lost the trail. Claude is rewriting his orders from his own notes…",
    "reproducing": "🕵️  Kane is at the scene, in a real Chrome browser:",
    "judging": "⚖️  Kane found something. Claude is checking it matches the report…",
    "double-checking": "🔎 Before calling it, Kane checks the user's claim with his own eyes:",
}


# ── which app ─────────────────────────────────────────────────────────────────────────────────

def apps() -> list[Path]:
    found = []
    for path in sorted((ROOT / "apps").glob("*.json")):
        try:
            if not json.loads(path.read_text(encoding="utf-8")).get("self_check"):
                found.append(path)
        except (OSError, ValueError):
            continue
    return found


def choose_app(wanted: str | None) -> Path:
    """The app to use: --app by file name or app name, or the only one connected."""
    known = apps()
    if not known:
        raise SystemExit("No apps connected in this folder. Start with: bug-whisperer init --sample")
    if wanted:
        for path in known:
            name = json.loads(path.read_text(encoding="utf-8")).get("name", "")
            if wanted.lower() in (path.stem.lower(), path.name.lower(), name.lower()):
                return path
        raise SystemExit(f"No app called {wanted!r}. Connected: {', '.join(p.stem for p in known)}")
    if len(known) == 1:
        return known[0]
    raise SystemExit("Which app? Add --app with one of: " + ", ".join(p.stem for p in known))


# ── following Kane live ───────────────────────────────────────────────────────────────────────

class Follow:
    """Prints Kane's steps as they happen, read from the newest NDJSON log in a case folder (the
    same log the website's live tracker reads)."""

    def __init__(self, folder: Path, out=print):
        self.folder, self.out = folder, out
        self.log, self.done = None, 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=5)
        self.poll()

    def _loop(self):
        while not self._stop.wait(0.5):
            self.poll()

    def poll(self) -> None:
        logs = sorted(self.folder.glob("*.ndjson"), key=lambda p: p.stat().st_mtime)
        if not logs:
            return
        if logs[-1] != self.log:
            self.log, self.done = logs[-1], 0
        try:
            text = self.log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        lines = text.split("\n")[:-1]  # only whole lines: the last one may still be being written
        for line in lines[self.done:]:
            self.say(line)
        self.done = len(lines)

    def say(self, line: str) -> None:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return
        if not isinstance(event, dict) or "type" in event or "step" not in event:
            return
        remark = event.get("remark") or ""
        if event.get("status") == "running" or not remark or voice.BOOKKEEPING.match(remark):
            return
        words = voice.speak(remark)
        if words:
            self.out(f"   {'✗' if event.get('status') == 'failed' else '·'} {words}")


# ── telling the result ────────────────────────────────────────────────────────────────────────

def website_link(inv_id: str, port: int = 8000) -> str:
    with socket.socket() as s:
        running = s.connect_ex(("127.0.0.1", port)) == 0
    url = f"http://127.0.0.1:{port}/r/{inv_id}"
    return f"On the website: {url}" if running else f"On the website (3D replay, PDF report): bug-whisperer up, then {url}"


def verdict(inv: Investigation) -> list[str]:
    plan, judged = inv.plan or {}, inv.judgement or {}
    if inv.verdict == "reproduced":
        lines = [f"🐛 CONFIRMED  {judged.get('explanation') or plan.get('understanding', '')}"]
        if (inv.claim or {}).get("outcome") == "confirmed":
            lines.append("   Kane also checked the user's claim and found it true.")
        ticket = judged.get("ticket") or {}
        if ticket.get("steps"):
            lines.append(f"   Ticket: {ticket.get('title', 'Bug')}")
            lines += [f"     {i}. {s}" for i, s in enumerate(ticket["steps"], start=1)]
            lines.append(f"     Expected: {ticket.get('expected', '')}")
            lines.append(f"     Actual:   {ticket.get('actual', '')}")
        return lines
    if inv.verdict == "not_reproduced":
        if (inv.claim or {}).get("outcome") == "not_true":
            return ["📂 OPEN  Kane checked the user's claim and it didn't hold up, so this isn't the bug the user thinks."]
        return ["📂 OPEN  Kane followed the steps and the app behaved correctly.",
                "   Ask the user for the exact day, time and what they saw on screen."]
    if inv.verdict == "needs_info":
        return ["❓ OPEN  Not enough to go on yet. Ask the user:", f"   {plan.get('question', '')}"]
    return ["⚠️  INCONCLUSIVE  Kane couldn't finish checking, so nothing is claimed.",
            f"   {judged.get('explanation', '')}".rstrip()]


def run_case(inv: Investigation, app: App, out=print) -> Investigation:
    out(f"\n━━ Case {inv.id} · {app.name}")
    out(f"   “{inv.report[:200]}{'…' if len(inv.report) > 200 else ''}”\n")
    try:
        with Follow(inv.folder, out):
            inv = investigate(app, inv.report, inv.screenshot, inv=inv,
                              on_update=lambda i: out(SAYS[i.status]) if i.status in SAYS else None)
    except Exception as exc:  # recorded like the website records it: nothing half-done is claimed
        inv.status, inv.verdict = "done", "inconclusive"
        inv.judgement = {"explanation": f"Bug Whisperer hit an error: {exc}"}
        inv.save()
    out("")
    for line in verdict(inv):
        out(line)
    out(f"   {website_link(inv.id)}")
    return inv


def repair(inv: Investigation, app: App, out=print) -> dict:
    from .fixer import fix
    out(f"\n━━ Repairing case {inv.id}: Claude works from Kane's evidence only, then Kane checks.\n")
    with Follow(inv.folder, out):
        record = fix(app, inv, on_update=lambda s: out(f"🛠️  {s}"))
    out("")
    if record["verdict"] == "fixed":
        changed = sorted({l[6:] for a in record.get("attempts", []) for l in (a.get("patch") or "").splitlines()
                          if l.startswith("+++ b/")})
        out("✅ CASE CLOSED  Kane repeated the same steps and saw the fix with his own eyes.")
        if changed:
            out(f"   Changed: {', '.join(changed)}")
        out("   The passing test is saved, and replayed whenever this app's code changes.")
    elif record["verdict"] == "needs_human":
        out("🙋 HANDED TO A PERSON  Three repairs didn't get past Kane.")
    else:
        out(f"⚠️  UNSOLVED  Kane couldn't finish checking the repair, so nothing is claimed. {record.get('error', '')}".rstrip())
    out(f"   {website_link(inv.id)}")
    return record


def offer_repair(inv: Investigation, app: App, choice: bool | None, out=print) -> None:
    """After a confirmed bug in an app whose code is connected: repair now, if wanted."""
    if inv.verdict != "reproduced" or not app.code_dir:
        return
    if choice is None:
        if not sys.stdin.isatty():
            out(f"\n   To repair it: bug-whisperer repair {inv.id}")
            return
        choice = input("\nRepair it now? Claude repairs from Kane's evidence, Kane checks. [y/N] ").strip().lower() in ("y", "yes")
    if choice:
        repair(inv, app, out)
    else:
        out(f"   Later: bug-whisperer repair {inv.id}")


def report(text: str, app_path: Path, files: list[str] = (), screenshot: str | None = None,
           repair_choice: bool | None = None, out=print) -> list[Investigation]:
    app_file = f"apps/{app_path.name}"
    app = App.load(app_path)
    if files:  # test results (and screenshots): Claude opens one case per real problem
        from . import intake
        job = intake.Intake(app=app.name, app_file=app_file, note=text.strip()[:4000])
        for f in files:
            src = Path(f)
            if not src.is_file():
                raise SystemExit(f"No such file: {f}")
            shutil.copyfile(src, job.folder / src.name)
            job.files.append(src.name)
        job.save()
        out(f"🧠 Claude is reading {', '.join(job.files)}…")
        opened: list[str] = []
        job = intake.run(job, lambda kind, inv_id: opened.append(inv_id))
        if job.error:
            raise SystemExit(f"Couldn't read the files: {job.error}")
        out(f"   {len(opened)} problem(s) worth investigating." + (f" Left out: {job.left_out}" if job.left_out else ""))
        from .fixer import load_investigation
        cases = [load_investigation(RUNS / i) for i in opened]
        out("   Kane takes them one at a time, in a real browser.")
    else:
        if not text.strip():
            raise SystemExit("Write the report, or add --file with test results")
        inv = Investigation(report=text.strip()[:4000], app=app.name, app_file=app_file)
        if screenshot:
            src = Path(screenshot)
            if not src.is_file():
                raise SystemExit(f"No such file: {screenshot}")
            target = inv.folder / ("user-screenshot" + src.suffix.lower())
            shutil.copyfile(src, target)
            inv.screenshot = str(target)
        cases = [inv]
    done = []
    for inv in cases:
        inv = run_case(inv, app, out)
        offer_repair(inv, app, repair_choice, out)
        done.append(inv)
    return done


def load_case(ref: str) -> Investigation:
    """A case by its id or its folder (runs/<id>)."""
    path = Path(ref)
    folder = path if (path / "investigation.json").is_file() else RUNS / path.name
    if not (folder / "investigation.json").is_file():
        raise SystemExit(f"No case {ref!r}. See them with: bug-whisperer cases")
    from .fixer import load_investigation
    return load_investigation(folder)


STAMPS = {"reproduced": "🐛 confirmed", "not_reproduced": "📂 open", "needs_info": "❓ asked",
          "inconclusive": "⚠️  inconclusive", None: "… running"}


def list_cases(limit: int = 15) -> list[str]:
    rows = []
    for path in sorted(RUNS.glob("*/investigation.json"), reverse=True)[:limit]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        fixed = (data.get("fix") or {}).get("verdict") == "fixed"
        stamp = "✅ closed, fix proven" if fixed else STAMPS.get(data.get("verdict"), data.get("verdict"))
        report = " ".join(str(data.get("report", "")).split())
        rows.append(f"{data.get('id', path.parent.name)}  {stamp:22} {data.get('app', '')}: {report[:60]}")
    return rows

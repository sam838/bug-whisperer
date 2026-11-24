"""Before the repair: Claude reads the code, changes nothing, and lays out how it would fix the bug.

The person sees the plan before pressing Repair:
- the cause, in plain words;
- one to three ways to repair it, each with the files it would change and its trade-off;
- Kane's sealed question: one more check, the same bug reached another way (another value,
  another form, another account). The fixer never sees it. Kane asks it only after his usual
  re-check passes, so a repair can't be written just to pass it.

Claude proposes; this code decides what counts. A way to repair it must name files that exist in
the code folder, and the sealed question must start at the app's address, end with one
"Verify that", and hold no password. After the repair, `kept_word` compares the files the plan
named with the files the repair really changed.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from . import claude, fields
from .detective import ROOT, App, Investigation

MAX_OPTIONS = 3
LETTERS = "ABC"

PROMPT = """You are planning a repair. Do NOT edit anything: only read the code in this folder.
A user reported a problem with this web app, and a browser agent (Kane CLI) reproduced it.

The user's report:
<report>
{report}
</report>

What the app should do: {expected}
{clock}

What Kane did and saw:
- Kane's steps: {objective}
- Kane's final check failed at: {failed_step}
- Kane's account: {summary}

Find the cause in the code. Then reply with ONLY a JSON object:
{{
  "cause": "one or two plain sentences for a non-developer: what in the code lets this happen",
  "options": [
    {{"title": "3 to 6 words",
      "change": "one or two plain sentences: what would change, and what the user would see",
      "files": ["paths relative to this folder, only files that exist"],
      "tradeoff": "one plain sentence: what this way is good at, and what it leaves open",
      "recommended": true or false}}
  ],
  "sealed_question": {{"objective": "see below", "why": "one plain sentence: which too-narrow repair this catches"}}
}}

Options: one to three genuinely different ways to repair it, smallest first. Mark exactly one as
recommended. Don't pad: if there is only one sensible way, give one.

sealed_question: one more Kane objective. It is the same bug reached another way: another value
(for example yesterday instead of last year), another page or form that saves the same thing, or
the same steps as another account. A repair that only handled Kane's exact steps should fail it; a
real repair should pass it. Write it like Kane's steps above:
- Start at a full URL. Log in with the same placeholders as Kane's steps, written the same way.
  Never write a real password.
- Choose every value yourself. No "if" or "for example". At most 10 actions, counting each field.
- Then: "Store what the page shows after that as 'what_happened'."
- End with ONE check: "Verify that <the correct behaviour>."
- Only behaviour the report already expects. No new features.
- Times: the user wrote in their own clock and time zone, which may not be the app's. Judge
  "past" and "future" by the app's clock above, never by the user's. A time on today's date must
  be at least 2 hours away from the app's time now. If the app's clock is unknown, use whole days
  (yesterday, next week), never a time earlier or later today.

{fields}"""


def make(app: App, inv: Investigation) -> dict:
    """Ask Claude for the plan (read-only), check it, and keep it on the case."""
    code_dir = (ROOT / app.code_dir).resolve()
    inv.repair_plan = {"status": "planning"}
    inv.save()
    kane = inv.kane or {}
    raw = claude.ask_json(PROMPT.format(
        report=inv.report, expected=(inv.plan or {}).get("expected"), clock=app_clock(app),
        objective=(inv.plan or {}).get("objective"), failed_step=kane.get("failed_step"),
        summary=kane.get("summary"), fields=fields.GUIDE),
        cwd=code_dir, tools="Read,Glob,Grep", timeout=600)
    inv.repair_plan = check(raw, code_dir, app, (inv.plan or {}).get("objective", ""))
    inv.save()
    return inv.repair_plan


def app_clock(app: App, now: datetime | None = None) -> str:
    """What "now" is for the app. On a hosted server it is often UTC while the user is not (Nov 24:
    a sealed question booked "today 08:00" from the user's 9am, but the app's clock said 02:35)."""
    now = now or datetime.now().astimezone()
    if urlparse(app.base_url).hostname in ("127.0.0.1", "localhost", "::1"):
        offset = now.strftime("%z")
        return (f"The app runs on this computer. Its clock says {now:%A %d %B %Y, %H:%M} "
                f"(UTC{offset[:3]}:{offset[3:]}).")
    return (f"Today is about {now:%A %d %B %Y}. The app runs on another computer, so its time of day "
            "and time zone are unknown.")


def check(raw: dict, code_dir: Path, app: App, objective: str = "") -> dict:
    """Keep only what holds up. The result always has a status: ready or error."""
    options = []
    for opt in raw.get("options") or []:
        if not isinstance(opt, dict) or len(options) == MAX_OPTIONS:
            continue
        files = [f for f in (_in_code(code_dir, f) for f in opt.get("files") or []) if f]
        if not (str(opt.get("title") or "").strip() and str(opt.get("change") or "").strip() and files):
            continue  # a way that names no real file is a guess, not a plan
        options.append({"id": LETTERS[len(options)], "title": str(opt["title"]).strip(),
                        "change": str(opt["change"]).strip(), "files": sorted(set(files)),
                        "tradeoff": str(opt.get("tradeoff") or "").strip(),
                        "recommended": opt.get("recommended") is True})
    plan = {"cause": str(raw.get("cause") or "").strip(), "cost_usd": raw.get("_cost_usd")}
    if not options:
        return {**plan, "status": "error",
                "error": "Claude's plan named no files that exist in the code, so it was set aside."}
    picked = next((o["id"] for o in options if o["recommended"]), options[0]["id"])
    for o in options:
        o["recommended"] = o["id"] == picked
    return {**plan, "status": "ready", "options": options, "recommended": picked,
            "sealed": sealed_question(raw.get("sealed_question"), app, objective)}


def sealed_question(raw, app: App, objective: str = "") -> dict | None:
    """Kane's sealed question, if it is a usable Kane objective. None otherwise."""
    if not isinstance(raw, dict):
        return None
    text = " ".join(str(raw.get("objective") or "").split())
    origin = app.base_url.rstrip("/")
    passwords = [a.get("password") for a in app.accounts.values() if a.get("password")]
    if (not text or origin not in text or text.count("Verify that") != 1 or len(text) > 1500
            or text == " ".join(objective.split()) or any(p in text for p in passwords)):
        return None
    return {"objective": text, "why": str(raw.get("why") or "").strip()}


def choose(plan: dict | None, option: str | None) -> dict | None:
    """The way the person picked, or Claude's recommendation when they didn't pick one."""
    options = (plan or {}).get("options") or []
    by_id = {o["id"]: o for o in options}
    return by_id.get((option or "").upper()) or by_id.get((plan or {}).get("recommended"))


def _in_code(code_dir: Path, name) -> str | None:
    """`name` as a path inside the code folder, if that file exists there."""
    if not isinstance(name, str) or not name.strip():
        return None
    name = name.strip().replace("\\", "/")
    while name.startswith("./"):
        name = name[2:]
    rel = PurePosixPath(name.lstrip("/"))
    if rel.parts and rel.parts[0] == code_dir.name:  # Claude sometimes names the folder too
        rel = PurePosixPath(*rel.parts[1:]) if len(rel.parts) > 1 else rel
    path = (code_dir / rel).resolve()
    if code_dir not in path.parents or not path.is_file():
        return None
    return path.relative_to(code_dir).as_posix()


def touched_files(patch: str) -> list[str]:
    """The files a diff changed, added or deleted."""
    found = set()
    for line in (patch or "").splitlines():
        for prefix in ("+++ b/", "--- a/"):
            if line.startswith(prefix):
                found.add(line[len(prefix):].strip())
    return sorted(found)


def kept_word(promised: list[str], patch: str) -> dict:
    """Did the repair change what the plan said it would? Worked out by code, not by Claude."""
    touched = touched_files(patch)

    def same(changed: str, planned: str) -> bool:
        return changed == planned or changed.endswith("/" + planned)  # diff paths may start at the repo
    extra = [t for t in touched if not any(same(t, p) for p in promised)]
    unused = [p for p in promised if not any(same(t, p) for t in touched)]
    return {"promised": list(promised), "touched": touched, "extra": extra, "unused": unused,
            "kept": bool(touched) and not extra}


def promise_line(promise: dict | None) -> str:
    """Whether the repair changed the files its plan named, in one plain line."""
    if not promise:
        return ""
    if not promise["touched"]:
        return "No: the repair changed no files."
    if promise["kept"]:
        return f"Yes: it changed only what the plan named ({', '.join(promise['touched'])})."
    return f"No: it also changed {', '.join(promise['extra'])}, which the plan didn't name."

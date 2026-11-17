"""The fix loop: Claude fixes the app from Kane's evidence, Kane runs the same steps again.

A bug only counts as fixed when the SAME Kane objective that failed during the reproduction now
passes. The fixer never sees the words "fix bug X": it gets the user's report and Kane's
evidence, so it has to work from what Kane actually saw. It may only edit the app's code folder.
After 3 failed attempts a human is asked.
"""

from __future__ import annotations

import difflib
import json
import subprocess
import time
from pathlib import Path


from . import apprunner, camera, claude, kane, regression
from . import evidence as kane_evidence
from .detective import ROOT, App, Investigation

MAX_FIX_ATTEMPTS = 3

FIX_PROMPT = """You are Bug Whisperer's fixer. A user reported a problem with this web app, and a
browser agent (Kane CLI) reproduced it. Fix the app's code so the correct behaviour happens.

The user's report:
<report>
{report}
</report>

What the app should do: {expected}

What Kane did and saw:
- Steps Kane was given: {objective}
- Kane's final check failed at: {failed_step}
- Kane's account of what happened: {summary}
{previous}
Rules:
- Only edit files in this folder (the app's code). Make the smallest change that fixes it.
- Don't add dependencies. Keep the app's existing style.
- Show the user a clear message where it helps (for example on a form error).
- Finish with one or two plain sentences: what was wrong and what you changed.
Kane will run the same steps again to check your fix; you don't decide whether it worked.
"""

RETRY_NOTE = """
Your previous attempt did not fix it. Kane ran the same steps again and saw this:
- Failed at: {failed_step}
- Kane's account: {summary}
"""


def fix(app: App, inv: Investigation, on_update=None) -> dict:
    if inv.verdict != "reproduced":
        raise ValueError("Only a reproduced bug can be fixed")
    if not app.code_dir:
        raise ValueError(f"{app.name} has no code connected, so it can only be reproduced")
    code_dir = (ROOT / app.code_dir).resolve()
    objective = inv.plan["objective"]
    record = {"status": "fixing", "attempts": [], "verdict": None,
              "before": {"kane_verdict": inv.kane.get("verdict"), "failed_step": inv.kane.get("failed_step")}}
    if inv.fix.get("attempts"):
        inv.fix_history.append(inv.fix)  # an earlier fix run: keep it as evidence
    inv.fix = record
    run_no = len(inv.fix_history) + 1  # keeps each fix run's logs and screenshots apart

    def notify(status: str) -> None:
        record["status"] = status
        inv.save()
        if on_update:
            on_update(status)
    previous = ""
    evidence = inv.kane

    for attempt in range(1, MAX_FIX_ATTEMPTS + 1):
        notify(f"fixing (attempt {attempt})")
        started = _snapshot(code_dir)
        reply = claude.ask(
            FIX_PROMPT.format(
                report=inv.report, expected=inv.plan.get("expected"), objective=objective,
                failed_step=evidence.get("failed_step"), summary=evidence.get("summary"),
                previous=previous),
            cwd=code_dir, tools="Read,Edit,Write,Glob,Grep", edits=True, timeout=900)
        patch = _diff(code_dir, started)
        notify(f"waiting for the app to reload (attempt {attempt})")
        if not apprunner.restart(app):
            evidence = {"verdict": "failed", "failed_step": "The app did not start after the change",
                        "summary": "The app did not start after your change. Its log ends with:\n"
                                   + _log_tail(app)}
            record["attempts"].append({"attempt": attempt, "fixer_said": reply.get("result", "")[-1500:],
                                       "fixer_cost_usd": reply.get("total_cost_usd"), "patch": patch,
                                       "kane": evidence})
            previous = RETRY_NOTE.format(failed_step=evidence["failed_step"], summary=evidence["summary"])
            continue
        apprunner.reset(app)

        notify(f"Kane re-checking (attempt {attempt})")
        # A unique name per re-check: Kane renames on a clash, which once left a failed run
        # posing as the regression test.
        name = f"bug-{inv.id}-r{run_no}a{attempt}"
        with camera.KaneCamera(inv.folder) as cam:  # Kane back at the scene, filmed live
            result = kane.run(objective, variables=app.variables(), max_steps=30, timeout=300,
                              name=name, cdp_endpoint=cam.endpoint,
                              log_path=inv.folder / f"verify-{run_no}-{attempt}.ndjson")
        name = regression.saved_name(name)
        evidence = _verify_brief(result)
        evidence.update(kane_evidence.extract_shots(result.session_dir,
                                                    inv.folder / f"shots-verify-{run_no}-{attempt}"))
        evidence["shots_dir"] = f"shots-verify-{run_no}-{attempt}"
        record["attempts"].append({
            "attempt": attempt, "fixer_said": reply.get("result", "")[-1500:],
            "fixer_cost_usd": reply.get("total_cost_usd"), "patch": patch, "kane": evidence,
        })
        inv.save()
        if result.verdict == "passed":
            # Keep the passing run as a regression test, without the secrets Kane wrote into it.
            test_file = regression.sanitize(name)
            record.update(verdict="fixed", regression_test=name,
                          regression_file=str(test_file.relative_to(ROOT)))
            from . import guard  # imported here: guard imports this module's neighbours
            guard.register({
                "case_id": inv.id, "app_file": inv.app_file, "test": name,
                "title": (inv.judgement.get("ticket") or {}).get("title") or inv.report[:80],
                "report": inv.report, "objective": objective,
                "closed": time.strftime("%Y-%m-%d %H:%M"),
            })
            break
        regression.discard(name)  # a re-check that didn't pass is not a regression test
        if result.verdict == "error":
            record.update(verdict="inconclusive")
            break
        previous = RETRY_NOTE.format(failed_step=evidence.get("failed_step"),
                                     summary=evidence.get("summary"))
    else:
        record.update(verdict="needs_human")
    notify("done")
    return record


SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build", ".next"}


def _in_git(code_dir: Path) -> bool:
    try:
        out = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=code_dir, capture_output=True, text=True)
    except OSError:  # git isn't installed
        return False
    return out.returncode == 0 and out.stdout.strip() == "true"


def _read_tree(code_dir: Path) -> dict[str, str]:
    """The app's text files, for a diff when its code isn't in git (a fresh `init --sample`)."""
    files = {}
    for path in sorted(code_dir.rglob("*")):
        if len(files) >= 5000:
            break
        if not path.is_file() or SKIP_DIRS & set(path.relative_to(code_dir).parts) or path.stat().st_size > 1_000_000:
            continue
        try:
            files[path.relative_to(code_dir).as_posix()] = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # a database, an image: not code to show in a diff
    return files


def _snapshot(code_dir: Path) -> str | dict:
    """The code before the fixer's work, so we can diff only that work: a git object (stash-free)
    when the code is in git, otherwise a copy of its text files."""
    if not _in_git(code_dir):
        return _read_tree(code_dir)
    out = subprocess.run(["git", "stash", "create"], cwd=code_dir, capture_output=True, text=True)
    return out.stdout.strip() or "HEAD"


def _diff(code_dir: Path, since: str | dict) -> str:
    if isinstance(since, dict):
        now = _read_tree(code_dir)
        chunks = []
        for rel in sorted(set(since) | set(now)):
            if since.get(rel) != now.get(rel):
                chunks.extend(difflib.unified_diff(
                    (since.get(rel) or "").splitlines(keepends=True), (now.get(rel) or "").splitlines(keepends=True),
                    fromfile=f"a/{code_dir.name}/{rel}", tofile=f"b/{code_dir.name}/{rel}"))
        return "".join(chunks)
    out = subprocess.run(["git", "diff", since, "--", "."], cwd=code_dir, capture_output=True,
                         text=True, encoding="utf-8", errors="replace")
    return out.stdout


def _log_tail(app: App, lines: int = 25) -> str:
    log = ROOT / "runs" / f"app-{apprunner._port(app)}.log"
    if not log.exists():
        return "(no log)"
    return "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])


def _verify_brief(result: kane.KaneResult) -> dict:
    failed = result.failed_step
    return {
        "verdict": result.verdict, "exit_code": result.exit_code, "reason": result.reason,
        "summary": result.summary, "final_state": result.final_state,
        "failed_step": failed.get("remark") if failed else None,
        "steps": [s.get("remark") for s in result.steps if s.get("remark")],
        "test_url": result.test_url, "credits": result.credits, "duration": result.duration,
    }


def load_investigation(folder: str | Path) -> Investigation:
    data = json.loads((Path(folder) / "investigation.json").read_text(encoding="utf-8"))
    known = Investigation.__dataclass_fields__
    return Investigation(**{k: v for k, v in data.items() if k in known})

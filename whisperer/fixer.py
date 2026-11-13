"""The fix loop: Claude fixes the app from Kane's evidence, Kane runs the same steps again.

A bug only counts as fixed when the SAME Kane objective that failed during the reproduction now
passes. The fixer never sees the words "fix bug X": it gets the user's report and Kane's
evidence, so it has to work from what Kane actually saw. It may only edit the app's code folder.
After 3 failed attempts a human is asked.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import httpx

from . import claude, kane, regression
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
    notify = on_update or (lambda _status: None)
    objective = inv.plan["objective"]
    record = {"status": "fixing", "attempts": [], "verdict": None,
              "before": {"kane_verdict": inv.kane.get("verdict"), "failed_step": inv.kane.get("failed_step")}}
    inv.fix = record
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
        _wait_until_up(app.base_url)

        notify(f"Kane re-checking (attempt {attempt})")
        name = f"bug-{inv.id}"
        result = kane.run(objective, variables=app.variables(), max_steps=30, timeout=300,
                          name=name, log_path=inv.folder / f"verify-{attempt}.ndjson")
        evidence = _verify_brief(result)
        record["attempts"].append({
            "attempt": attempt, "fixer_said": reply.get("result", "")[-1500:],
            "fixer_cost_usd": reply.get("total_cost_usd"), "patch": patch, "kane": evidence,
        })
        inv.save()
        if result.verdict == "passed":
            # Keep the passing run as a regression test, without the secrets Kane wrote into it.
            test_file = regression.sanitize(name)
            record.update(verdict="fixed", status="done", regression_test=name,
                          regression_file=str(test_file.relative_to(ROOT)))
            break
        if result.verdict == "error":
            record.update(verdict="inconclusive", status="done")
            break
        previous = RETRY_NOTE.format(failed_step=evidence.get("failed_step"),
                                     summary=evidence.get("summary"))
    else:
        record.update(verdict="needs_human", status="done")
    inv.save()
    notify(record["verdict"])
    return record


def _snapshot(code_dir: Path) -> str:
    """Stash-free snapshot: the current tree as a git object, so we can diff only the fixer's work."""
    out = subprocess.run(["git", "stash", "create"], cwd=code_dir, capture_output=True, text=True)
    return out.stdout.strip() or "HEAD"


def _diff(code_dir: Path, since: str) -> str:
    out = subprocess.run(["git", "diff", since, "--", "."], cwd=code_dir, capture_output=True,
                         text=True, encoding="utf-8", errors="replace")
    return out.stdout


def _wait_until_up(base_url: str, timeout: int = 60) -> None:
    time.sleep(3)  # give the auto-reloader time to notice the change
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(base_url, timeout=3).status_code < 500:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)


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
    return Investigation(**data)

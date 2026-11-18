"""The Lineup: when a closed case comes back, Kane finds the commit that brought it back.

A closed case leaves a saved Kane test. If the test passed at an earlier commit and fails now, one
of the commits in between broke it. Those commits are the suspects: every commit that changed the
app's code folder. Kane questions them the way `git bisect` does. A suspect is checked out in a
temporary git worktree, that version of the app is started, and the same saved test is replayed
against it (replays spend no credits).
- A pass clears that suspect and every suspect before it.
- A fail means the bug was already there, so the culprit is that suspect or one before it.
About log2(n) questionings name the culprit.

Before anyone is questioned, the witness is checked: the test must pass at the good commit and fail
at the bad one. If it doesn't, the Lineup says so and accuses no one. When Kane can't tell (the
replay errors and no fresh run is allowed), that suspect is skipped, as `git bisect skip` does. If
that leaves more than one commit, the Lineup names all of them instead of guessing.

Each suspect's record says whether Kane really questioned it, or whether another questioning ruled
it out.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from dataclasses import replace
from pathlib import Path

from . import apprunner, guard, kane, regression
from .detective import ROOT, RUNS, App

HELD_AT = RUNS / "held-at.json"  # case id -> the last commit where Kane saw it hold
MAX_DIFF_LINES = 400


def git(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    out = subprocess.run(["git", *args], cwd=cwd or ROOT, capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    if check and out.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {out.stderr.strip()}")
    return out.stdout


def resolve(rev: str) -> str:
    return git("rev-parse", "--verify", f"{rev}^{{commit}}").strip()


def commit_info(sha: str) -> dict:
    sha, short, author, date, subject = git(
        "show", "-s", "--format=%H%x1f%h%x1f%an%x1f%ad%x1f%s", "--date=format:%Y-%m-%d %H:%M", sha
    ).strip().split("\x1f", 4)
    return {"sha": sha, "short": short, "author": author, "date": date, "subject": subject}


def suspects(code_dir: str, good: str, bad: str) -> list[dict]:
    """Commits after `good` up to `bad` that changed the code folder, oldest first."""
    out = git("log", "--first-parent", "--reverse", "--format=%H", f"{good}..{bad}", "--", code_dir)
    return [{**commit_info(sha), "status": "waiting", "questioned": False} for sha in out.split()]


def bisect(n: int, question) -> tuple[int, int, set[int]]:
    """Find where the bug starts among suspects 0..n-1, oldest first.

    The bug is known absent before suspect 0 and present at suspect n-1. `question(i)` returns
    "passed" (no bug), "failed" (bug) or "error" (can't tell). Returns (lo, hi, skipped): the
    culprit is one of the suspects lo+1..hi. It is exactly hi when hi == lo + 1.
    """
    lo, hi, skipped = -1, n - 1, set()
    while hi - lo > 1:
        open_ = [i for i in range(lo + 1, hi) if i not in skipped]
        if not open_:
            break
        middle = (lo + hi) / 2
        i = min(open_, key=lambda j: abs(j - middle))
        verdict = question(i)
        if verdict == "passed":
            lo = i
        elif verdict == "failed":
            hi = i
        else:
            skipped.add(i)
    return lo, hi, skipped


def held_at() -> dict:
    return json.loads(HELD_AT.read_text(encoding="utf-8")) if HELD_AT.exists() else {}


def remember_held(case_id: str, code_dir: str | None) -> None:
    """Record the commit where a case held, so a later lineup knows where to start.
    Only when the code folder has no uncommitted changes: otherwise no commit holds what Kane saw."""
    try:
        if code_dir and git("status", "--porcelain", "--", code_dir).strip():
            return
        sha = resolve("HEAD")
    except (RuntimeError, OSError):
        return
    HELD_AT.parent.mkdir(parents=True, exist_ok=True)
    HELD_AT.write_text(json.dumps({**held_at(), case_id: sha}, indent=2), encoding="utf-8")


def question(app: App, sha: str, test: str, log_path: Path, objective: str | None = None) -> dict:
    """Run the app as it was at `sha` and replay the saved test against it."""
    tree = Path(tempfile.mkdtemp(prefix="bw-lineup-"))
    suspect = replace(app, code_dir=str(tree / app.code_dir))
    try:
        git("worktree", "add", "--detach", "--force", str(tree), sha)
        if not apprunner.restart(suspect):
            return {"verdict": "error", "reason": "this version of the app didn't start", "summary": None,
                    "failed_step": None, "errors": [], "duration": None}
        apprunner.reset(suspect)
        result = guard._brief(regression.replay(test, app.variables(), log_path=log_path))
        if result["verdict"] == "error" and objective:
            # Kane couldn't replay its recording here. A fresh run decides, and spends credits.
            apprunner.reset(suspect)
            fresh = kane.run(objective, variables=app.variables(), max_steps=30, timeout=300,
                             log_path=log_path.with_name(log_path.name.replace("-replay", "-fresh")))
            result = {**guard._brief(fresh), "fresh": True}
        return result
    finally:
        apprunner.stop(suspect)
        git("worktree", "remove", "--force", str(tree), check=False)
        shutil.rmtree(tree, ignore_errors=True)
        git("worktree", "prune", check=False)


def _save(data: dict, folder: Path) -> None:
    (folder / "lineup.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def run(check_id: str, good: str | None = None, bad: str = "HEAD", fresh: bool = False,
        on_update=None) -> dict:
    """Question the commits between `good` and `bad` until one is named. Returns the lineup record."""
    notify = on_update or (lambda _msg: None)
    case = next((c for c in guard.closed_cases() if c["case_id"] == check_id), None)
    if not case:
        raise ValueError(f"There's no closed case or self-check called {check_id}")
    app = App.load(ROOT / case["app_file"])
    if not (app.code_dir and app.start):
        raise ValueError(f"{app.name} has no code folder and start command, so its past versions can't be run")
    good = good or held_at().get(check_id)
    if not good:
        raise ValueError("Say where it still worked: --good <commit>")
    good_sha, bad_sha = resolve(good), resolve(bad)
    if good_sha == bad_sha or subprocess.run(["git", "merge-base", "--is-ancestor", good_sha, bad_sha],
                                             cwd=ROOT, capture_output=True).returncode != 0:
        raise ValueError(f"{good} is not an earlier commit than {bad}")
    rows = suspects(app.code_dir, good_sha, bad_sha)
    if not rows:
        raise ValueError(f"No commit between {good} and {bad} changed {app.code_dir}/")

    stamp = time.strftime("%Y%m%d-%H%M%S")
    folder = RUNS / f"lineup-{stamp}"
    folder.mkdir(parents=True, exist_ok=True)
    data = {"id": folder.name, "check": check_id, "title": case["title"], "objective": case.get("objective"),
            "test": case["test"], "app": app.name, "app_file": case["app_file"], "code_dir": app.code_dir,
            "created": time.strftime("%Y-%m-%d %H:%M"), "status": "questioning", "now": None,
            "good": {**commit_info(good_sha), "answer": None}, "bad": {**commit_info(bad_sha), "answer": None},
            "suspects": rows, "questionings": 0, "fresh_runs": 0, "verdict": None, "culprit": None}
    _save(data, folder)
    objective = case.get("objective") if fresh else None

    def ask(label: str, sha: str, row: dict) -> str:
        data["now"] = label
        row["status"] = "questioning"
        _save(data, folder)
        notify(f"questioning {sha[:7]} ({label})")
        apprunner.keep_claim(app)
        answer = question(app, sha, case["test"], folder / f"{sha[:7]}-replay.ndjson", objective)
        data["questionings"] += 1
        data["fresh_runs"] += 1 if answer.get("fresh") else 0
        row.update(answer=answer, questioned=True, asked_as=data["questionings"])
        notify(f"{sha[:7]}: {_words(answer['verdict'])}")
        return answer["verdict"]

    try:
        with apprunner.claim(app, f"lineup {folder.name}", wait=900):  # a revisit takes a few minutes
            return _question_all(data, folder, app, rows, good_sha, bad_sha, ask)
    except apprunner.PortBusy as e:
        raise ValueError(str(e))
    finally:
        if data["status"] != "done":  # interrupted: say so
            _finish(data, folder, "stopped")


def _question_all(data, folder, app, rows, good_sha, bad_sha, ask) -> dict:
    was_up = apprunner.is_up(app)
    try:
        if ask("the last good version", good_sha, data["good"]) != "passed":
            data["good"]["status"] = "cannot_tell" if data["good"]["answer"]["verdict"] == "error" else "present"
            return _finish(data, folder, "not_good" if data["good"]["status"] == "present" else "cannot_tell")
        data["good"]["status"] = "cleared"
        bad_row = rows[-1] if rows[-1]["sha"] == bad_sha else data["bad"]
        verdict = ask("the broken version", bad_sha, bad_row)
        if bad_row is not data["bad"]:
            data["bad"]["answer"] = bad_row["answer"]
        if verdict != "failed":
            bad_row["status"] = "cannot_tell" if verdict == "error" else "cleared"
            return _finish(data, folder, "not_bad" if verdict == "passed" else "cannot_tell")
        bad_row["status"] = "present"

        def interrogate(i: int) -> str:
            answer = ask(f"suspect {i + 1} of {len(rows)}", rows[i]["sha"], rows[i])
            _mark(rows, i, answer)
            return answer

        lo, hi, skipped = bisect(len(rows), interrogate)
        for i in skipped:
            if lo < i < hi:  # a skipped suspect before lo was cleared by a later pass anyway
                rows[i]["status"] = "cannot_tell"
        if hi == lo + 1:
            rows[hi]["status"] = "guilty"
            data["culprit"] = rows[hi]["sha"]
            data["diff"] = _diff(rows[hi]["sha"], app.code_dir)
            return _finish(data, folder, "found")
        for i in range(lo + 1, hi + 1):
            if rows[i]["status"] != "cannot_tell":
                rows[i]["status"] = "unresolved"
        return _finish(data, folder, "narrowed")
    finally:
        if was_up:
            apprunner.restart(app)


def _mark(rows: list[dict], i: int, verdict: str) -> None:
    """A pass clears everyone up to i; a fail means everyone from i on carries the bug."""
    if verdict == "passed":
        for row in rows[: i + 1]:
            row["status"] = "cleared"
    elif verdict == "failed":
        for row in rows[i:]:
            if row["status"] != "guilty":
                row["status"] = "present"
    else:
        rows[i]["status"] = "cannot_tell"


def _diff(sha: str, code_dir: str) -> dict:
    stat = git("show", "--format=", "--stat", sha, "--", code_dir).strip("\n")  # keeps the alignment
    lines = git("show", "--format=", sha, "--", code_dir).splitlines()
    return {"stat": stat, "patch": "\n".join(lines[:MAX_DIFF_LINES]),
            "cut": max(0, len(lines) - MAX_DIFF_LINES)}


VERDICTS = {
    "found": "Kane named the commit that broke it",
    "narrowed": "Kane narrowed it down, but couldn't question every suspect",
    "not_good": "The bug was already there at the 'good' commit: start further back",
    "not_bad": "Kane doesn't see the bug at the 'broken' commit. If it's in uncommitted changes, no commit is to blame",
    "stopped": "The lineup was stopped before Kane finished, so no one is accused",
    "cannot_tell": ("Kane couldn't replay the test on a known version, so no one is accused. An old page "
                    "often looks different from the one the test was recorded on: with --fresh, Kane checks "
                    "each version from scratch instead (spends credits)"),
}


def _finish(data: dict, folder: Path, verdict: str) -> dict:
    data.update(status="done", now=None, verdict=verdict, verdict_words=VERDICTS[verdict])
    _save(data, folder)
    return data


def _words(verdict: str) -> str:
    return {"passed": "cleared (the bug isn't there)", "failed": "the bug is there",
            "error": "Kane couldn't tell"}.get(verdict, verdict)


RESTATED = ("you asked", "the request", "the requested task")  # Kane repeating the task, not what he saw


def _first_sentence(text: str | None, limit: int = 170) -> str:
    """What Kane saw, in his own words: his first sentences, minus any that only repeat the task."""
    sentences = [s.strip() for s in " ".join((text or "").split()).replace(". ", ".\n").split("\n") if s.strip()]
    saw = [s for s in sentences if not s.lower().startswith(RESTATED)] or sentences
    out = ""
    for s in saw:
        if out and len(out) + 1 + len(s) > limit:
            break
        out = f"{out} {s}".strip()
    return out if len(out) <= limit else out[: limit - 1].rstrip() + "…"


def stage(data: dict) -> dict:
    """The lineup as a script for the 3D scene, from the real record only.

    `line` is every version in a row, oldest first: the last good one, the suspects, and the broken
    one, which is usually the last suspect. `steps` are Kane's questionings in the real order. Each
    step has Kane's own words and, after his answer, which suspects are still possible (`open`) and
    what is known about each version (`after`).
    """
    rows = data["suspects"]
    line = [{**_brief_row(data["good"]), "role": "good"}] + [{**_brief_row(r), "role": "suspect"} for r in rows]
    if rows and rows[-1]["sha"] == data["bad"]["sha"]:
        line[-1]["role"] = "bad"
    else:
        line.append({**_brief_row(data["bad"]), "role": "bad"})
    at = {row["sha"]: i for i, row in enumerate(line)}
    asked, seen = [], set()
    for row in sorted((r for r in [data["good"], data["bad"], *rows] if r.get("asked_as")), key=lambda r: r["asked_as"]):
        if row["asked_as"] not in seen:
            seen.add(row["asked_as"])
            asked.append(row)
    states, steps = ["waiting"] * len(line), []
    for row in asked:
        i, answer = at[row["sha"]], row["answer"]
        if answer["verdict"] == "passed":
            states[: i + 1] = ["cleared"] * (i + 1)
        elif answer["verdict"] == "failed":
            states[i:] = ["present"] * (len(line) - i)
        else:
            states[i] = "cannot_tell"
        lo = max((j for j, s in enumerate(states) if s == "cleared"), default=-1)
        hi = min((j for j, s in enumerate(states) if s == "present"), default=len(line) - 1)
        steps.append({"at": i, "asked_as": row["asked_as"], "verdict": answer["verdict"],
                      "fresh": bool(answer.get("fresh")),
                      "said": _first_sentence(answer.get("summary") or answer.get("failed_step") or answer.get("reason"), 125),
                      "after": list(states), "open": [lo + 1, hi]})
    return {"check": data["title"], "verdict": data["verdict"], "words": data.get("verdict_words", ""),
            "suspects": len(rows), "line": line, "steps": steps,
            "culprit": at.get(data.get("culprit")) if data.get("culprit") else None}


def _brief_row(row: dict) -> dict:
    return {"sha": row["sha"], "short": row["short"], "subject": row["subject"], "date": row["date"],
            "author": row.get("author", "")}


def all_lineups() -> list[dict]:
    """Every lineup: this machine's (runs/, not committed) and the ones kept as evidence in the
    repo (docs/evidence/*/lineup.json, so the hosted demo shows them too). Newest first."""
    found = {}
    paths = [*RUNS.glob("lineup-*/lineup.json"), *(ROOT / "docs" / "evidence").glob("*/lineup.json")]
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        data.setdefault("evidence", path.parent.name if "evidence" in path.parts else None)
        found.setdefault(data["id"], data)  # this machine's live copy first
    return sorted(found.values(), key=lambda d: d["id"], reverse=True)


def load(lineup_id: str) -> dict:
    found = next((d for d in all_lineups() if d["id"] == lineup_id), None)
    if not found:
        raise FileNotFoundError(lineup_id)
    return found

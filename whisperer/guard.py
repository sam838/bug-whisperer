"""Kane revisits old crime scenes: replay every closed case and report any that came back.

Each case Bug Whisperer closes leaves a saved Kane test (the passing re-check). The registry of
closed cases lives in .testmuai/closed-cases.json, committed next to the tests, so the guard
works in any clone of the repo.

Verdicts per case:
  holds      the saved steps replayed and passed: the bug is still fixed
  reopened   the replay failed, and Kane did not blame its own automation: the bug is back
  unknown    Kane couldn't tell (a setup problem, or Kane says its recording no longer fits the
             page). A fresh Kane run of the same objective then decides, because a changed page
             is not proof that the bug is back
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from . import apprunner, kane, regression
from .detective import ROOT, RUNS, App

REGISTRY = ROOT / ".testmuai" / "closed-cases.json"


def closed_cases(app_file: str | None = None) -> list[dict]:
    if not REGISTRY.exists():
        return []
    cases = json.loads(REGISTRY.read_text(encoding="utf-8")).get("cases", [])
    return [c for c in cases if app_file is None or c["app_file"] == app_file]


def register(case: dict) -> None:
    """Add (or replace) a closed case in the registry."""
    cases = [c for c in closed_cases() if c["case_id"] != case["case_id"]] + [case]
    REGISTRY.write_text(json.dumps({"cases": cases}, indent=2), encoding="utf-8")


def revisit(app_file: str | None = None, on_update=None) -> dict:
    """Replay every closed case (optionally for one app). Returns a report dict."""
    notify = on_update or (lambda _msg: None)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    folder = RUNS / f"guard-{stamp}"
    folder.mkdir(parents=True, exist_ok=True)
    results = []
    by_app: dict[str, list[dict]] = {}
    for case in closed_cases(app_file):
        by_app.setdefault(case["app_file"], []).append(case)

    for app_path, cases in by_app.items():
        app = App.load(ROOT / app_path)
        notify(f"restarting {app.name} so Kane tests the code as it is now")
        apprunner.restart(app)
        for case in cases:
            apprunner.reset(app)
            notify(f"revisiting case {case['case_id']}: {case['title']}")
            replay = regression.replay(case["test"], app.variables(),
                                       log_path=folder / f"{case['case_id']}-replay.ndjson")
            entry = {"case_id": case["case_id"], "title": case["title"], "app": app.name,
                     "replay": _brief(replay)}
            if replay.verdict == "passed":
                entry["verdict"] = "holds"
            elif replay.verdict == "failed":
                entry["verdict"] = "reopened"
            else:
                # Kane couldn't replay its recording (the page may have changed). Decide with a
                # fresh run of the same objective instead of guessing.
                notify(f"case {case['case_id']}: replay inconclusive, Kane is re-checking from scratch")
                apprunner.reset(app)
                fresh = kane.run(case["objective"], variables=app.variables(), max_steps=30,
                                 timeout=300, log_path=folder / f"{case['case_id']}-fresh.ndjson")
                entry["fresh"] = _brief(fresh)
                entry["verdict"] = {"passed": "holds", "failed": "reopened"}.get(fresh.verdict, "unknown")
            results.append(entry)
            _record_on_case(case["case_id"], entry, stamp)

    report = {"when": stamp, "results": results,
              "reopened": [r for r in results if r["verdict"] == "reopened"],
              "unknown": [r for r in results if r["verdict"] == "unknown"]}
    (folder / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _record_on_case(case_id: str, entry: dict, stamp: str) -> None:
    """Keep the revisit on the case's own page, if the case folder exists on this machine."""
    path = RUNS / case_id / "investigation.json"
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("guard", []).append({"when": stamp, "verdict": entry["verdict"],
                                         "replay": entry["replay"], "fresh": entry.get("fresh")})
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _brief(result: kane.KaneResult) -> dict:
    failed = result.failed_step
    summary = result.summary or (result.kane_diagnosis or {}).get("one_liner")
    return {"verdict": result.verdict, "reason": result.reason, "summary": summary,
            "failed_step": failed.get("remark") if failed else None, "errors": result.errors,
            "duration": result.duration}

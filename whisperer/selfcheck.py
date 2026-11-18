"""Kane checks Bug Whisperer itself: the detective investigates his own office.

Bug Whisperer's one rule is that nothing counts until Kane sees it. That holds for its own pages
too. Bug Whisperer is registered as an app (apps/bug-whisperer.json, code folder whisperer/), and a
few read-only checks of its own pages are saved as Kane tests, exactly like a closed case of the
clinic. They live in the same registry, so the same machinery replays them:

- `python -m whisperer selfcheck --record` runs each check once and saves it as a Kane test;
- `python -m whisperer selfcheck` replays them (no self-healing) through the revisit guard;
- the Claude Code Stop hook replays them whenever a session changes whisperer/, and doesn't let
  the session finish while one fails.

The checks run against a second copy of the site on port 8010 (started as apps/bug-whisperer.json
says, with WHISPERER_NO_BOOT so it starts no sample apps), so they never disturb the copy someone is
using, and they only read pages: no new cases, no Kane runs. The same start command works for any
past version of the code, which is what lets the Lineup (lineup.py) question old commits.
"""

from __future__ import annotations

import time

from . import apprunner, guard, kane, regression
from .detective import ROOT, App

APP_FILE = "apps/bug-whisperer.json"
SITE = "http://127.0.0.1:8010"
CASE = "20261113-124324-d930"  # case #3, closed: two patients booked into the same slot

CHECKS = [
    {"id": "self-front-desk", "title": "The front desk: an example report fills the case form",
     "objective": f"Go to {SITE}/. Click the first example button under 'Try a real one'. "
                  "Verify that the witness statement box now contains 'my receptionist booked mrs aisha' "
                  "and the page shows a 'Send Kane to investigate' button."},
    # Worded to hold for every version of the front desk, so the Lineup can replay it on old commits.
    {"id": "self-sample-reports", "title": "The front desk offers sample reports that fill the report box",
     "objective": f"Go to {SITE}/. Verify that the page shows at least one button that fills in a sample "
                  "bug report. Click the first of those buttons. Verify that the bug report text box is no "
                  "longer empty."},
    {"id": "self-case-files", "title": "The case files: the corkboard and Kane's rank",
     "objective": f"Go to {SITE}/inbox. Verify that the page shows Detective Kane's rank card "
                  "and at least one pinned case stamped 'Case closed'."},
    {"id": "self-closed-case", "title": "A closed case: its stamp, evidence board and scene map",
     "objective": f"Go to {SITE}/r/{CASE}. Verify that the page shows a 'Case closed' stamp, "
                  "a section called 'The evidence board' and a section called 'The scene map'."},
    {"id": "self-verified", "title": "The Verified page: the pre-registered experiments",
     "objective": f"Go to {SITE}/verified. Verify that the page says 6/6 pre-registered experiments "
                  "came out as expected and lists the experiment 'E3-false-privacy-claim'."},
    {"id": "self-case-report", "title": "The case report: steps, repair and a Save as PDF button",
     "objective": f"Go to {SITE}/r/{CASE}/report. Verify that the report has a section 'What Kane did, "
                  "in a real browser', a section 'The repair' and a 'Save as PDF' button."},
]


def app() -> App:
    return App.load(ROOT / APP_FILE)


def record(ids: list[str] | None = None, say=print) -> list[dict]:
    """Run each check (or only `ids`) once with Kane and save the passing ones as Kane tests."""
    site = app()
    apprunner.restart(site)  # the copy on port 8010, running the code as it is now
    out = []
    for check in [c for c in CHECKS if not ids or c["id"] in ids]:
        say(f"[selfcheck] recording {check['id']}…")
        result = kane.run(check["objective"], max_steps=15, timeout=180, name=check["id"])
        saved = regression.saved_name(check["id"])
        if result.verdict != "passed":
            regression.discard(saved)  # a failed recording is not a test
            say(f"[selfcheck] {check['id']}: {result.verdict}: {result.reason}")
            out.append({**check, "verdict": result.verdict, "reason": result.reason})
            continue
        regression.sanitize(saved)
        guard.register({"case_id": check["id"], "app_file": APP_FILE, "test": saved, "title": check["title"],
                        "report": "Self-check of Bug Whisperer's own pages", "objective": check["objective"],
                        "closed": time.strftime("%Y-%m-%d %H:%M"), "self_check": True})
        say(f"[selfcheck] {check['id']}: passed, saved as {saved}")
        out.append({**check, "verdict": "passed", "test": saved, "credits": result.credits})
    return out


def run(say=print) -> dict:
    """Replay the saved self-checks exactly, through the same guard as every closed case."""
    return guard.revisit(APP_FILE, on_update=lambda m: say(f"[kane] {m}"))

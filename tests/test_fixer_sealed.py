"""The fix loop with a repair plan: the fixer follows the picked way, never sees Kane's sealed
question until it has failed, and a case closes only when both of Kane's checks pass.
Claude, Kane, the app and the camera are all faked: no credits."""
import contextlib

import pytest

from whisperer import apprunner, detective, fixer, guard, kane, regression
from whisperer.detective import App, Investigation

APP = App(name="Clinic Records", base_url="http://127.0.0.1:8001", code_dir="clinic")
SEALED = "Go to http://127.0.0.1:8001/book. Book for yesterday. Verify that the page refuses the booking."
PLAN = {"status": "ready", "cause": "The server saves any date.", "recommended": "B",
        "options": [{"id": "A", "title": "Guard the calendar", "change": "Hide past days.", "files": ["templates/book.html"],
                     "tradeoff": "", "recommended": False},
                    {"id": "B", "title": "Guard the door", "change": "The server refuses past dates.", "files": ["app.py"],
                     "tradeoff": "", "recommended": True}],
        "sealed": {"objective": SEALED, "why": "Yesterday, not last year."}}


@pytest.fixture
def world(tmp_path, monkeypatch):
    """Fakes for everything the fix loop touches. Returns what it saw."""
    seen = {"prompts": [], "kane": [], "discarded": [], "registered": []}
    verdicts = []
    monkeypatch.setattr(detective, "RUNS", tmp_path)
    monkeypatch.setattr(fixer.claude, "ask", lambda prompt, **kw: seen["prompts"].append(prompt) or
                        {"result": "Refused past dates on the server.", "total_cost_usd": 0.1})
    monkeypatch.setattr(fixer, "_snapshot", lambda code_dir: "HEAD")
    monkeypatch.setattr(fixer, "_diff", lambda code_dir, since: "--- a/clinic/app.py\n+++ b/clinic/app.py\n+refuse\n")
    monkeypatch.setattr(apprunner, "restart", lambda app: True)
    monkeypatch.setattr(apprunner, "reset", lambda app: None)
    monkeypatch.setattr(fixer.camera, "KaneCamera", lambda folder: contextlib.nullcontext(type("Cam", (), {"endpoint": None})))
    monkeypatch.setattr(fixer.kane_evidence, "extract_shots", lambda session, folder: {})

    def run(objective, **kw):
        seen["kane"].append(objective)
        verdict = verdicts.pop(0)
        steps = [{"status": "failed", "remark": "assert: it was saved"}] if verdict == "failed" else []
        return kane.KaneResult(verdict=verdict, exit_code={"passed": 0, "failed": 1}.get(verdict, 2),
                               summary=f"Kane: {verdict}", steps=steps)
    monkeypatch.setattr(kane, "run", run)
    monkeypatch.setattr(regression, "saved_name", lambda name: name)
    monkeypatch.setattr(regression, "sanitize", lambda name: fixer.ROOT / ".testmuai" / "tests" / f"{name}.md")
    monkeypatch.setattr(regression, "discard", lambda name: seen["discarded"].append(name))
    monkeypatch.setattr(guard, "register", lambda case: seen["registered"].append(case))
    seen["verdicts"] = verdicts
    return seen


def case(**extra):
    return Investigation(report="it just saved a date in the past??", app=APP.name, app_file="apps/clinic.json",
                         verdict="reproduced", plan={"objective": "Book for 3 March 2025. Verify it is refused.",
                                                     "expected": "Past dates are refused."},
                         kane={"verdict": "failed", "failed_step": "assert: it was saved"}, **extra)


def test_the_fixer_follows_the_picked_way_and_never_sees_the_sealed_question_first(world):
    world["verdicts"] += ["passed", "failed", "passed", "passed"]  # re-check, sealed, re-check, sealed
    inv = case(repair_plan=PLAN)
    record = fixer.fix(APP, inv, option="B")
    first, second = world["prompts"]
    assert "Guard the door" in first and "app.py" in first
    assert SEALED not in first and "yesterday" not in first.lower()
    assert SEALED in second and "sealed question" in second  # revealed only after the repair missed it
    assert world["kane"] == [inv.plan["objective"], SEALED, inv.plan["objective"], SEALED]
    assert record["verdict"] == "fixed" and record["approach"]["id"] == "B"
    assert record["attempts"][0]["sealed"]["verdict"] == "failed"
    assert record["attempts"][1]["sealed"]["verdict"] == "passed"
    assert record["attempts"][0]["promise"]["kept"] is True
    assert record["sealed_test"].endswith("-sealed")
    # the first re-check passed, but its repair missed the sealed question: it is not a regression test
    assert any(name.endswith("r1a1") for name in world["discarded"])
    assert len(world["registered"]) == 1


def test_a_repair_that_keeps_missing_the_sealed_question_goes_to_a_person(world):
    world["verdicts"] += ["passed", "failed"] * 3
    record = fixer.fix(APP, case(repair_plan=PLAN))
    assert record["verdict"] == "needs_human" and "sealed question still failed" in record["note"]
    assert world["registered"] == []


def test_when_kane_cannot_finish_the_sealed_question_the_case_closes_but_claims_nothing_about_it(world):
    world["verdicts"] += ["passed", "error"]
    record = fixer.fix(APP, case(repair_plan=PLAN))
    assert record["verdict"] == "fixed" and record["attempts"][0]["sealed"]["verdict"] == "error"
    assert "sealed_test" not in record


def test_without_a_plan_the_loop_is_unchanged(world):
    world["verdicts"] += ["passed"]
    record = fixer.fix(APP, case())
    assert world["kane"] == ["Book for 3 March 2025. Verify it is refused."]
    assert record["verdict"] == "fixed" and record["approach"] is None
    assert record["attempts"][0]["promise"] is None and "sealed" not in record["attempts"][0]

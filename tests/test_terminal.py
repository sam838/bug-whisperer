"""Bug Whisperer in the terminal: following Kane live, the verdict, and the repair offer.
Kane and Claude are faked: no credits, no Chrome."""
import json

import pytest

from whisperer import detective, terminal
from whisperer.detective import App, Investigation

APP = App(name="Clinic Records", base_url="http://127.0.0.1:8001", code_dir="clinic")


@pytest.fixture
def runs(tmp_path, monkeypatch):
    monkeypatch.setattr(detective, "RUNS", tmp_path)
    monkeypatch.setattr(terminal, "RUNS", tmp_path)
    monkeypatch.setattr(terminal, "website_link", lambda inv_id, port=8000: f"site/{inv_id}")
    return tmp_path


def step(n, remark, status="done"):
    return json.dumps({"step": n, "status": status, "remark": remark})


def test_follow_says_each_finished_step_once_and_marks_failures(tmp_path):
    said = []
    follow = terminal.Follow(tmp_path, said.append)
    log = tmp_path / "reproduce-1.ndjson"
    log.write_text(json.dumps({"type": "stream_start"}) + "\n" + step(1, "Step 1", "running") + "\n"
                   + step(1, 'navigate: Opened http://127.0.0.1:8001/login') + "\n", encoding="utf-8")
    follow.poll()
    with log.open("a", encoding="utf-8") as f:
        f.write(step(2, "wait: queued plan") + "\n" + step(3, "assert: The appointment was not saved", "failed") + "\n"
                + '{"step": 4, "status": "done", "rem')  # a line still being written
    follow.poll()
    follow.poll()
    assert len(said) == 2
    assert said[0].startswith("   · ") and "127.0.0.1:8001" in said[0]
    assert said[1].startswith("   ✗ ")


def fake_investigation(verdict, **extra):
    def run(app, report, screenshot=None, on_update=None, inv=None):
        inv.status = "reproducing"; on_update(inv)
        (inv.folder / "reproduce-1.ndjson").write_text(step(1, "click: Clicked Book appointment") + "\n", encoding="utf-8")
        inv.status, inv.verdict = "done", verdict
        for key, value in extra.items():
            setattr(inv, key, value)
        inv.save()
        return inv
    return run


def test_a_confirmed_case_is_saved_like_a_website_case(runs, monkeypatch):
    monkeypatch.setattr(terminal, "investigate", fake_investigation(
        "reproduced", judgement={"explanation": "Past dates are accepted.",
                                 "ticket": {"title": "Past bookings", "steps": ["Book 3 March 2025"],
                                            "expected": "Refused", "actual": "Saved"}}))
    out = []
    inv = terminal.run_case(Investigation(report="it just saved it??", app=APP.name, app_file="apps/clinic.json"),
                            APP, out.append)
    text = "\n".join(out)
    assert "🕵️  Kane is at the scene" in text and "   · I clicked Book appointment" in text
    assert "🐛 CONFIRMED  Past dates are accepted." in text and "1. Book 3 March 2025" in text
    assert f"site/{inv.id}" in text
    saved = json.loads((runs / inv.id / "investigation.json").read_text(encoding="utf-8"))
    assert saved["app_file"] == "apps/clinic.json" and saved["verdict"] == "reproduced"


def test_an_error_is_inconclusive_never_a_verdict(runs, monkeypatch):
    def broken(*a, **k):
        raise RuntimeError("kane-cli is not installed")
    monkeypatch.setattr(terminal, "investigate", broken)
    out = []
    inv = terminal.run_case(Investigation(report="x", app=APP.name, app_file="apps/clinic.json"), APP, out.append)
    assert inv.verdict == "inconclusive"
    assert any("INCONCLUSIVE" in line for line in out) and any("not installed" in line for line in out)


def test_repair_is_only_offered_for_a_confirmed_bug_with_code(monkeypatch):
    repaired = []
    monkeypatch.setattr(terminal, "repair", lambda inv, app, out: repaired.append(inv))
    confirmed = Investigation(report="x", app=APP.name, verdict="reproduced")
    terminal.offer_repair(confirmed, App(name="Link only", base_url="https://x.test"), True, print)
    terminal.offer_repair(Investigation(report="x", app=APP.name, verdict="not_reproduced"), APP, True, print)
    assert repaired == []
    terminal.offer_repair(confirmed, APP, True, print)
    assert repaired == [confirmed]


def test_without_a_terminal_to_ask_it_says_how_to_repair_later(monkeypatch):
    monkeypatch.setattr(terminal.sys.stdin, "isatty", lambda: False, raising=False)
    out = []
    terminal.offer_repair(Investigation(report="x", app=APP.name, verdict="reproduced", id="20261117-120000-abcd"),
                          APP, None, out.append)
    assert out == ["\n   To repair it: bug-whisperer repair 20261117-120000-abcd"]


def test_choosing_the_app(tmp_path, monkeypatch):
    monkeypatch.setattr(terminal, "ROOT", tmp_path)
    with pytest.raises(SystemExit, match="init --sample"):
        terminal.choose_app(None)
    (tmp_path / "apps").mkdir()
    (tmp_path / "apps" / "clinic.json").write_text(json.dumps({"name": "Clinic Records"}), encoding="utf-8")
    assert terminal.choose_app(None).name == "clinic.json"
    (tmp_path / "apps" / "shop.json").write_text(json.dumps({"name": "My Shop"}), encoding="utf-8")
    with pytest.raises(SystemExit, match="clinic, shop"):
        terminal.choose_app(None)
    assert terminal.choose_app("my shop").name == "shop.json"


def test_cases_lists_the_newest_first_with_a_plain_stamp(runs):
    for inv_id, verdict, fix in [("20261117-100000-aaaa", "reproduced", {"verdict": "fixed"}),
                                 ("20261117-110000-bbbb", "needs_info", {})]:
        (runs / inv_id).mkdir()
        (runs / inv_id / "investigation.json").write_text(json.dumps(
            {"id": inv_id, "report": "cant  book", "app": "Clinic Records", "verdict": verdict, "fix": fix}), encoding="utf-8")
    rows = terminal.list_cases()
    assert rows[0].startswith("20261117-110000-bbbb") and "asked" in rows[0]
    assert "closed, fix proven" in rows[1] and "cant book" in rows[1]

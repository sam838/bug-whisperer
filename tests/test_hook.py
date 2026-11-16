"""Stop hook safety rules. No Kane, no Claude, no credits."""

import io
import json

from whisperer import guard, hook


def run_hook(monkeypatch, capsys, payload=None):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload or {"session_id": "t"})))
    assert hook.main() == 0  # a Stop hook always exits 0; the decision is in the JSON
    return json.loads(capsys.readouterr().out)


def test_bug_whisperers_own_sessions_are_never_blocked(monkeypatch, capsys):
    monkeypatch.setenv("WHISPERER_INTERNAL", "1")
    monkeypatch.setattr(guard, "closed_cases", lambda *a: (_ for _ in ()).throw(AssertionError))
    assert run_hook(monkeypatch, capsys) == {}


def test_no_closed_cases_means_nothing_to_check(monkeypatch, capsys):
    monkeypatch.delenv("WHISPERER_INTERNAL", raising=False)
    monkeypatch.setattr(guard, "closed_cases", lambda *a: [])
    assert run_hook(monkeypatch, capsys) == {}


def test_block_reason_carries_kanes_evidence_and_the_rules(monkeypatch):
    monkeypatch.setattr(guard, "closed_cases", lambda *a: [
        {"case_id": "c1", "report": "it saved a past date??", "objective": "Book 2025-03-03."}])
    reason = hook._reason([{"case_id": "c1", "title": "Past dates accepted", "replay": {
        "failed_step": "assert: error shown", "summary": "The app saved it."}}], attempt=1)
    assert "it saved a past date??" in reason and "The app saved it." in reason
    assert "Do not edit the saved Kane tests" in reason and "check 1 of 3" in reason


def test_only_the_apps_own_code_counts_as_a_change(tmp_path, monkeypatch):
    """Commits to other parts of the repo (like Bug Whisperer itself) must not trigger Kane revisits."""
    import subprocess
    from whisperer import hook

    def git(*args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=tmp_path,
                       check=True, capture_output=True)
    git("init", "-q")
    (tmp_path / "clinic").mkdir()
    (tmp_path / "clinic" / "app.py").write_text("print(1)\n", encoding="utf-8")
    git("add", "-A"); git("commit", "-qm", "app")
    monkeypatch.setattr(hook, "ROOT", tmp_path)
    before = hook._fingerprint("clinic")

    (tmp_path / "whisperer.py").write_text("x = 1\n", encoding="utf-8")
    git("add", "-A"); git("commit", "-qm", "work on something else")
    assert hook._fingerprint("clinic") == before

    (tmp_path / "clinic" / "app.py").write_text("print(2)\n", encoding="utf-8")
    assert hook._fingerprint("clinic") != before

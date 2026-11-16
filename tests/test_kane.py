"""Kane NDJSON parsing and verdicts, using a fake kane-cli (no credits, no Chrome)."""

import json
import sys

from whisperer import kane


def fake(lines, exit_code, tmp_path):
    script = tmp_path / "fake_kane.py"
    payload = "\n".join(json.dumps(x) if isinstance(x, dict) else x for x in lines)
    script.write_text(
        f"import sys\nprint({payload!r})\nsys.exit({exit_code})\n", encoding="utf-8")
    return [sys.executable, str(script)]


def run_fake(lines, exit_code, tmp_path):
    return kane._execute(fake(lines, exit_code, tmp_path), timeout=30,
                         log_path=tmp_path / "out.ndjson", on_event=None)


START = {"type": "stream_start", "v": 1, "surface": "run"}


def test_pass_needs_completion_and_exit_zero(tmp_path):
    r = run_fake([START, {"step": 1, "status": "done", "remark": "Opened page"},
                  {"type": "run_end", "status": "passed", "final_state": {"booked": "yes"}}],
                 0, tmp_path)
    assert r.verdict == "passed"
    assert r.final_state == {"booked": "yes"}
    assert len(r.steps) == 1


def test_failed_run_keeps_failed_step(tmp_path):
    r = run_fake([START, {"step": 2, "status": "failed", "remark": "No confirmation appeared"},
                  {"type": "run_end", "status": "failed", "reason": "Assertion failed"}], 1, tmp_path)
    assert r.verdict == "failed"
    assert r.failed_step["remark"] == "No confirmation appeared"


def test_setup_error_is_never_a_pass_or_fail(tmp_path):
    r = run_fake([START, {"type": "error", "message": "Not logged in"}], 2, tmp_path)
    assert r.verdict == "error"
    assert r.errors == ["Not logged in"]


def test_missing_completion_event_is_error(tmp_path):
    r = run_fake([START, "not json at all", {"step": 1, "status": "running"}], 0, tmp_path)
    assert r.verdict == "error"


def test_kane_automation_bug_is_not_an_app_failure(tmp_path):
    r = run_fake([START, {"type": "test_md_bug_verdict", "family": "automation_bug",
                          "one_liner": "Password variable did not populate"},
                  {"type": "test_md_done", "overall_status": "failed"}], 1, tmp_path)
    assert r.verdict == "error"
    assert "automation problem" in r.errors[-1]


def test_status_and_exit_code_must_agree(tmp_path):
    r = run_fake([START, {"type": "run_end", "status": "passed"}], 1, tmp_path)
    assert r.verdict == "error"


def test_kane_is_given_the_context_file(monkeypatch):
    seen = {}
    monkeypatch.setattr(kane, "kane_binary", lambda: "kane-cli")
    monkeypatch.setattr(kane, "_execute", lambda argv, **kw: seen.setdefault("argv", argv))
    kane.run("Open the shop")
    argv = seen["argv"]
    assert argv[argv.index("--local-context") + 1] == str(kane.CONTEXT)

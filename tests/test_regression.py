import os
import time

from whisperer import regression
from whisperer.regression import strip_secrets


def test_saved_name_finds_the_suffix_kane_added(tmp_path, monkeypatch):
    monkeypatch.setattr(regression, "TESTS", tmp_path)
    (tmp_path / "bug-1_test.md").write_text("old failed run", encoding="utf-8")
    newer = tmp_path / "bug-1-2_test.md"
    newer.write_text("the run that just happened", encoding="utf-8")
    later = time.time() + 5
    os.utime(newer, (later, later))
    assert regression.saved_name("bug-1") == "bug-1-2"


def test_discard_removes_a_failed_run(tmp_path, monkeypatch):
    monkeypatch.setattr(regression, "TESTS", tmp_path)
    (tmp_path / "bug-2_test.md").write_text("x", encoding="utf-8")
    (tmp_path / "output-bug-2").mkdir()
    regression.discard("bug-2")
    assert not any(tmp_path.iterdir())

FRONT = """---
mode: testing
variables:
  global.account1_email:
    value: sunrise@example.com
    secret: false
    syntax: '{{account1_email}}'
  secrets.user.account1_password:
    value: sunrise123
    secret: true
    syntax: '{{account1_password}}'
---

# Session: x
"""


def test_secret_variables_are_removed_and_others_kept():
    out = strip_secrets(FRONT)
    assert "sunrise123" not in out
    assert "secrets.user.account1_password" not in out
    assert "value: sunrise@example.com" in out
    assert out.endswith("---\n\n# Session: x\n")


def test_blanked_secret_from_older_versions_is_removed_too():
    old = FRONT.replace("value: sunrise123", "value: ''")
    assert "account1_password" not in strip_secrets(old).split("---")[1]

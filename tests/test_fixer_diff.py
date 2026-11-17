"""The repair's diff when the app's code isn't in git (a fresh `bug-whisperer init --sample`)."""
from whisperer import fixer


def test_diff_without_git_shows_only_the_fixers_change(tmp_path, monkeypatch):
    monkeypatch.setattr(fixer, "_in_git", lambda code_dir: False)
    code = tmp_path / "clinic"
    (code / "templates").mkdir(parents=True)
    (code / "app.py").write_text("def book(date):\n    return save(date)\n", encoding="utf-8")
    (code / "templates" / "a.html").write_text("<p>hi</p>\n", encoding="utf-8")
    (code / "clinic.db").write_bytes(b"\x00\xff\xfe binary")
    before = fixer._snapshot(code)
    (code / "app.py").write_text("def book(date):\n    if date < today():\n        raise PastDate\n    return save(date)\n",
                                 encoding="utf-8")
    (code / "clinic.db").write_bytes(b"\x00\xff\xfe changed")
    patch = fixer._diff(code, before)
    assert "+++ b/clinic/app.py" in patch and "+    if date < today():" in patch
    assert "a.html" not in patch and "clinic.db" not in patch


def test_no_change_means_an_empty_diff(tmp_path, monkeypatch):
    monkeypatch.setattr(fixer, "_in_git", lambda code_dir: False)
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    assert fixer._diff(tmp_path, fixer._snapshot(tmp_path)) == ""

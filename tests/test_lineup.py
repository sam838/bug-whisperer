"""The Lineup: Kane names the commit that broke a closed case. Real git, no Kane, no credits."""

import json
import math
import subprocess

import pytest

from whisperer import apprunner, guard, kane, lineup, regression


def test_bisect_names_the_culprit_wherever_it_is_and_asks_few_questions():
    for n in range(1, 18):
        for culprit in range(n):
            asked = []

            def question(i):
                asked.append(i)
                return "failed" if i >= culprit else "passed"

            lo, hi, skipped = lineup.bisect(n, question)
            assert (lo, hi, skipped) == (culprit - 1, culprit, set())
            assert len(asked) <= math.ceil(math.log2(n)) if n > 1 else not asked


def test_a_suspect_kane_cant_question_is_skipped_and_the_lineup_narrows_instead_of_guessing():
    answers = {3: "passed", 5: "failed", 4: "error"}
    lo, hi, skipped = lineup.bisect(8, lambda i: answers.get(i, "passed" if i < 4 else "failed"))
    assert (lo, hi, skipped) == (3, 5, {4})  # suspect 4 or 5: both are named, no guess


def git(repo, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=repo,
                          check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def history(tmp_path, monkeypatch):
    """A repo whose app/ folder loses its sample buttons in the fourth commit that touches it."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "apps").mkdir()
    (repo / "apps" / "site.json").write_text(json.dumps({
        "name": "Site", "base_url": "http://127.0.0.1:9", "code_dir": "app", "start": ["python", "serve.py"]}))
    (repo / "app").mkdir()
    shas = []
    for i, page in enumerate(["v1 SAMPLES", "v2 SAMPLES", "v3 SAMPLES", "v4 redesign", "v5", "v6", "v7"]):
        (repo / "app" / "page.html").write_text(page, encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", f"commit {i + 1}")
        shas.append(git(repo, "rev-parse", "HEAD"))
        (repo / "README.md").write_text(f"docs {i}", encoding="utf-8")  # not the app: never a suspect
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", f"docs {i + 1}")
    monkeypatch.setattr(lineup, "ROOT", repo)
    monkeypatch.setattr(lineup, "RUNS", repo / "runs")
    monkeypatch.setattr(lineup, "HELD_AT", repo / "runs" / "held-at.json")
    monkeypatch.setattr(apprunner, "RUNS", repo / "runs")
    monkeypatch.setattr(guard, "closed_cases", lambda *a: [
        {"case_id": "self-samples", "app_file": "apps/site.json", "test": "self-samples", "title": "Samples",
         "objective": "Click a sample."}])
    monkeypatch.setattr(apprunner, "is_up", lambda app: False)
    asked = []

    def question(app, sha, test, log_path, objective=None):
        asked.append(sha)
        page = git(repo, "show", f"{sha}:app/page.html")
        return {"verdict": "passed" if "SAMPLES" in page else "failed", "reason": None, "summary": "",
                "failed_step": None, "errors": [], "duration": 1.0}

    monkeypatch.setattr(lineup, "question", question)
    return repo, shas, asked


def test_the_lineup_names_the_commit_that_removed_it(history):
    repo, shas, asked = history
    record = lineup.run("self-samples", good=shas[0])
    assert record["verdict"] == "found"
    assert record["culprit"] == shas[3]
    assert record["diff"]["patch"] and "-v3 SAMPLES" in record["diff"]["patch"]
    statuses = {r["sha"]: r["status"] for r in record["suspects"]}
    assert statuses[shas[3]] == "guilty"
    assert [statuses[s] for s in shas[1:3]] == ["cleared", "cleared"]
    assert [statuses[s] for s in shas[4:]] == ["present"] * 3
    assert len(record["suspects"]) == 6  # the docs-only commits are never suspects
    # The witness was checked at both ends, and every questioning is on record.
    assert record["good"]["status"] == "cleared" and asked[0] == shas[0]
    assert record["questionings"] == len(asked) <= 2 + 3
    questioned = [r for r in record["suspects"] if r["questioned"]]
    assert all(r["answer"] for r in questioned)
    saved = json.loads((repo / "runs" / record["id"] / "lineup.json").read_text())
    assert saved["culprit"] == shas[3] and saved["status"] == "done"


def test_no_one_is_accused_when_the_good_commit_already_has_the_bug(history):
    repo, shas, asked = history
    record = lineup.run("self-samples", good=shas[4])
    assert record["verdict"] == "not_good" and record["culprit"] is None
    assert asked == [shas[4]]


def test_no_one_is_accused_when_the_broken_commit_works(history):
    repo, shas, asked = history
    record = lineup.run("self-samples", good=shas[0], bad=shas[2])
    assert record["verdict"] == "not_bad" and record["culprit"] is None


def test_the_lineup_starts_where_kane_last_saw_the_case_hold(history):
    repo, shas, asked = history
    with pytest.raises(ValueError, match="--good"):
        lineup.run("self-samples")
    git(repo, "checkout", "-q", shas[1])
    lineup.remember_held("self-samples", "app")
    git(repo, "checkout", "-q", "-")
    assert lineup.held_at() == {"self-samples": shas[1]}
    assert lineup.run("self-samples")["culprit"] == shas[3]


def test_uncommitted_changes_are_never_recorded_as_a_commit_that_held(history):
    repo, shas, asked = history
    (repo / "app" / "page.html").write_text("edited, not committed", encoding="utf-8")
    lineup.remember_held("self-samples", "app")
    assert lineup.held_at() == {}


def test_a_suspect_is_questioned_on_its_own_code_in_a_worktree_that_is_removed_after(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "app").mkdir()
    (repo / "app" / "page.html").write_text("old", encoding="utf-8")
    git(repo, "add", "-A"); git(repo, "commit", "-qm", "old")
    old = git(repo, "rev-parse", "HEAD")
    (repo / "app" / "page.html").write_text("new", encoding="utf-8")
    git(repo, "add", "-A"); git(repo, "commit", "-qm", "new")
    monkeypatch.setattr(lineup, "ROOT", repo)
    seen = {}

    def restart(app):
        seen["code"] = (lineup.Path(app.code_dir) / "page.html").read_text()
        return True

    monkeypatch.setattr(apprunner, "restart", restart)
    monkeypatch.setattr(apprunner, "reset", lambda app: None)
    monkeypatch.setattr(apprunner, "stop", lambda app: seen.setdefault("stopped", app.code_dir))
    monkeypatch.setattr(regression, "replay", lambda *a, **k: kane.KaneResult(verdict="failed", exit_code=1))
    from whisperer.detective import App
    answer = lineup.question(App(name="Site", base_url="http://x", code_dir="app", start=["x"]), old, "t",
                             tmp_path / "x-replay.ndjson")
    assert seen["code"] == "old" and answer["verdict"] == "failed"
    assert not lineup.Path(seen["stopped"]).exists()  # the worktree is gone
    assert len(git(repo, "worktree", "list").splitlines()) == 1



def test_only_one_job_at_a_time_may_claim_an_apps_port(tmp_path, monkeypatch):
    from whisperer.detective import App
    monkeypatch.setattr(apprunner, "RUNS", tmp_path)
    app = App(name="Site", base_url="http://127.0.0.1:8010")
    with apprunner.claim(app, "lineup A"):
        assert apprunner.holder(app) == "lineup A"
        with pytest.raises(apprunner.PortBusy, match="lineup A"):
            with apprunner.claim(app, "Kane's revisit"):
                pass
    assert apprunner.holder(app) is None
    with apprunner.claim(app, "Kane's revisit"):  # free again
        pass


def test_a_claim_left_by_a_job_that_died_does_not_block_the_port(tmp_path, monkeypatch):
    import os
    from whisperer.detective import App
    monkeypatch.setattr(apprunner, "RUNS", tmp_path)
    app = App(name="Site", base_url="http://127.0.0.1:8010")
    left = tmp_path / "port-8010.claim"
    left.write_text(json.dumps({"who": "lineup that crashed"}))
    old = left.stat().st_mtime - apprunner.STALE_CLAIM - 60
    os.utime(left, (old, old))
    with apprunner.claim(app, "Kane's revisit"):
        assert apprunner.holder(app) == "Kane's revisit"


def test_the_guard_never_tests_an_app_while_a_lineup_runs_an_old_version_of_it(tmp_path, monkeypatch):
    """Nov 18: the Stop hook replayed today's checks against the old version a lineup had started."""
    from whisperer.detective import App
    monkeypatch.setattr(apprunner, "RUNS", tmp_path)
    monkeypatch.setattr(guard, "RUNS", tmp_path)
    monkeypatch.setattr(guard, "closed_cases", lambda *a: [
        {"case_id": "self-verified", "app_file": "apps/bug-whisperer.json", "test": "self-verified", "title": "Verified"}])
    monkeypatch.setattr(apprunner, "restart", lambda app: pytest.fail("restarted an app a lineup is using"))
    monkeypatch.setattr(regression, "replay", lambda *a, **k: pytest.fail("tested an app a lineup is using"))
    site = App.load(lineup.ROOT / "apps" / "bug-whisperer.json")
    with apprunner.claim(site, "lineup lineup-1"):
        report = guard.revisit()
    assert [r["verdict"] for r in report["results"]] == ["unknown"]
    assert report["reopened"] == [] and "lineup lineup-1" in report["results"][0]["replay"]["reason"]


def test_an_interrupted_lineup_says_it_stopped_and_frees_the_port(history, monkeypatch):
    repo, shas, asked = history
    monkeypatch.setattr(apprunner, "RUNS", repo / "runs")
    monkeypatch.setattr(lineup, "question", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        lineup.run("self-samples", good=shas[0])
    record = lineup.all_lineups()[0]
    assert record["status"] == "done" and record["verdict"] == "stopped" and record["culprit"] is None
    assert not list((repo / "runs").glob("*.claim"))


def test_the_3d_script_follows_the_real_questionings_and_shows_the_halving(history):
    repo, shas, asked = history
    record = lineup.run("self-samples", good=shas[0])
    script = lineup.stage(record)
    line = script["line"]
    # the broken version (HEAD) is a docs-only commit here, so it stands at the end on its own
    assert line[0]["role"] == "good" and line[-1]["role"] == "bad" and len(line) == 1 + 6 + 1
    assert [line[s["at"]]["sha"] for s in script["steps"]] == asked  # the real order, nothing added
    sizes = [s["open"][1] - s["open"][0] + 1 for s in script["steps"]]
    assert sizes == sorted(sizes, reverse=True) and sizes[-1] == 1  # each answer narrows it to one
    assert line[script["culprit"]]["sha"] == shas[3]
    assert script["steps"][-1]["after"][script["culprit"]] == "present"


def test_kane_is_quoted_on_what_he_saw_not_on_repeating_the_task():
    said = lineup._first_sentence("You asked to fill in a sample report. The button was there. The box was filled. "
                                  "Extra words that make it much too long to show in a dialogue box at all, really, so they "
                                  "are left out of what Kane says, every single one of them, however true.")
    assert said == "The button was there. The box was filled."

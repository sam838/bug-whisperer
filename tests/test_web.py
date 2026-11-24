"""Website pages render from saved investigations. No Kane, no Claude, no credits."""

import json
import os

import pytest
from fastapi.testclient import TestClient

os.environ["WHISPERER_NO_BOOT"] = "1"  # don't start the sample app during tests
from whisperer import detective, web  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(detective, "RUNS", tmp_path)
    monkeypatch.setattr(web, "RUNS", tmp_path)
    monkeypatch.setattr(web, "enqueue", lambda kind, inv_id: None)  # never start real jobs
    return TestClient(web.app)


def save(tmp_path, **fields):
    inv = detective.Investigation(report="cant book!!! it saved a date in the past",
                                  app="Clinic Records", app_file="apps/clinic.json", **fields)
    inv.save()
    return inv


def test_home_lists_the_apps(client):
    page = client.get("/").text
    assert "Clinic Records" in page and "Send Kane to investigate" in page


def test_report_creates_a_queued_investigation(client, tmp_path):
    response = client.post("/report", data={"app_file": "apps/clinic.json", "report": "it broke"},
                           follow_redirects=False)
    assert response.status_code == 303
    inv_id = response.headers["location"].rsplit("/", 1)[-1]
    data = json.loads((tmp_path / inv_id / "investigation.json").read_text(encoding="utf-8"))
    assert data["status"] == "queued" and data["report"] == "it broke"


def test_unknown_app_is_refused(client):
    assert client.post("/report", data={"app_file": "../secrets.json", "report": "x"}).status_code == 400


def test_reproduced_report_offers_a_fix(client, tmp_path):
    inv = save(tmp_path, status="done", verdict="reproduced",
               judgement={"explanation": "The app saved it.", "ticket": {"title": "Past dates accepted",
                          "steps": ["Book"], "expected": "Refused", "actual": "Saved"}})
    page = client.get(f"/r/{inv.id}").text
    assert "Confirmed" in page and "Plan the repair" in page and "Past dates accepted" in page


def test_a_retry_in_progress_is_not_stamped_unsolved(client, tmp_path):
    lost = {"explanation": "Kane got stuck on the Book button.", "agent_lost": True}
    inv = save(tmp_path, status="re-planning", verdict="inconclusive", judgement=lost)
    page = client.get(f"/r/{inv.id}/live").text
    assert "First try didn" in page and ">Unsolved<" not in page
    inv.status = "done"
    inv.save()
    assert ">Unsolved<" in client.get(f"/r/{inv.id}/live").text


def test_fixed_report_shows_reply_and_no_fix_button(client, tmp_path):
    inv = save(tmp_path, status="done", verdict="reproduced", plan={"expected": "Refuse past dates."},
               fix={"status": "done", "verdict": "fixed", "attempts": [
                   {"attempt": 1, "fixer_said": "Added a check.", "patch": "+ new line",
                    "kane": {"verdict": "passed", "reason": "Objective completed"}}]})
    page = client.get(f"/r/{inv.id}").text
    assert "Case closed" in page and "Reply to the user" in page and "Repair it" not in page
    assert "Plan the repair" not in page


def test_finished_case_offers_a_replay_in_kanes_voice(client, tmp_path):
    inv = save(tmp_path, status="done", verdict="reproduced", kane={
        "shots_dir": "shots-reproduce-1", "shots": [
            {"file": "001.jpg", "status": "passed", "summary": 'click: Click "Book appointment"'},
            {"file": "002.jpg", "status": "passed", "summary": "wait: queued plan (2 steps)"},
            {"file": "003.jpg", "status": "failed", "summary": "assert: The app shows an error"}]})
    page = client.get(f"/r/{inv.id}").text
    assert "Watch Kane solve this case" in page
    assert "I clicked Book appointment." in page
    # inside the player's JSON, Jinja escapes the apostrophe as '
    assert "It wasn\\u0027t true." in page and "queued plan" not in page


def test_connect_app_keeps_passwords_out_of_the_app_file(client, tmp_path, monkeypatch):
    apps = tmp_path / "apps"
    apps.mkdir()
    monkeypatch.setattr(web, "APPS", apps)
    response = client.post("/apps", data={
        "name": "My Shop", "url": "https://shop.example.com/", "permission": "yes",
        "label1": "Customer", "email1": "c@example.com", "password1": "hunter2"},
        follow_redirects=False)
    assert response.status_code == 303
    saved = (apps / "my-shop.json").read_text(encoding="utf-8")
    assert "hunter2" not in saved and "c@example.com" in saved
    loaded = detective.App.load(apps / "my-shop.json")
    assert loaded.accounts["Customer"]["password"] == "hunter2"
    assert loaded.base_url == "https://shop.example.com" and loaded.code_dir is None


def test_connect_app_needs_permission_and_a_real_link(client, tmp_path, monkeypatch):
    apps = tmp_path / "apps"
    apps.mkdir()
    monkeypatch.setattr(web, "APPS", apps)
    page = client.post("/apps", data={"name": "X", "url": "javascript:alert(1)"})
    assert page.status_code == 400
    assert "permission" in page.text and "http" in page.text
    assert not list(apps.glob("*.json"))


def test_files_only_serves_images_inside_the_report(client, tmp_path):
    inv = save(tmp_path, status="done")
    (inv.folder / "notes.txt").write_text("private", encoding="utf-8")
    assert client.get(f"/files/{inv.id}/notes.txt").status_code == 404
    assert client.get(f"/files/{inv.id}/investigation.json").status_code == 404
    assert client.get(f"/files/{inv.id}/../../etc/passwd").status_code == 404


def test_live_tracker_follows_kanes_own_events(client, tmp_path):
    """While Kane works, the page tracks it from its NDJSON events: kind, status, step count, clock."""
    inv = save(tmp_path, status="reproducing")
    events = [
        {"type": "stream_start", "ts": "2026-11-16T08:00:00.000Z"},
        {"step": 1, "status": "done", "remark": "navigate: Navigate to http://127.0.0.1:8001/login"},
        {"step": 2, "status": "done", "remark": 'type: Type "{{secrets.user.account1_password}}" into "Password"'},
        {"step": 3, "status": "running", "remark": 'click: Click "Book appointment"'},
    ]
    (inv.folder / "reproduce-1.ndjson").write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    track = web.live_track(inv)
    assert [s["kind"] for s in track["steps"]] == ["go", "type", "click"]
    assert track["total"] == 3 and track["steps"][-1]["status"] == "running" and track["elapsed"] > 0
    page = client.get(f"/r/{inv.id}/live").text
    assert "Kane at the scene" in page and "I clicked Book appointment." in page and ">now<" in page
    assert "the test password" in page and "sunrise" not in page


def test_tracker_shows_kane_working_on_the_next_step(client, tmp_path):
    """Kane announces a step as it starts ('Step 3', running) and names it when it's done."""
    inv = save(tmp_path, status="reproducing")
    events = [{"type": "stream_start", "ts": "2026-11-16T08:00:00.000Z"},
              {"step": 1, "status": "done", "remark": "navigate: Navigate to http://127.0.0.1:8001/login"},
              {"step": 2, "status": "running", "remark": "Step 2"}]
    log = inv.folder / "reproduce-1.ndjson"
    log.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    track = web.live_track(inv)
    assert track["total"] == 1 and track["steps"][-1] == {
        "status": "running", "remark": "Working out the next move…", "kind": "think"}
    log.write_text(log.read_text(encoding="utf-8") + "\n" + json.dumps({"type": "run_end", "status": "passed"}),
                   encoding="utf-8")
    assert web.live_track(inv)["steps"][-1]["status"] == "done"  # finished: nothing left in progress


def test_tracker_names_the_kane_run_so_a_recheck_starts_counting_again(client, tmp_path):
    """The re-check after a repair is a new Kane run with its own step 1. The page names the run, so
    3D Kane acts its steps out even when it has fewer steps than the reproduction had."""
    import os, time
    inv = save(tmp_path, status="reproducing")
    step = lambda n: json.dumps({"step": n, "status": "done", "remark": "navigate: Navigate to http://127.0.0.1:8001/login"})
    (inv.folder / "reproduce-1.ndjson").write_text("\n".join(step(n) for n in range(1, 6)), encoding="utf-8")
    assert web.live_track(inv)["run"] == "reproduce-1"
    verify = inv.folder / "verify-1-1.ndjson"
    verify.write_text(step(1), encoding="utf-8")
    os.utime(verify, (time.time() + 5, time.time() + 5))
    track = web.live_track(inv)
    assert track["run"] == "verify-1-1" and track["total"] == 1
    assert 'data-run="verify-1-1"' in client.get(f"/r/{inv.id}/live").text


def test_case_files_are_pinned_on_a_corkboard(client, tmp_path):
    a = save(tmp_path, status="done", verdict="reproduced", id="20261116-100000-aaaa")
    b = save(tmp_path, status="done", verdict="not_reproduced", id="20261116-110000-bbbb")
    page = client.get("/inbox").text
    assert page.count('class="pinned pin-case"') == 2 and ">Confirmed<" in page and ">Open<" in page
    # same app, so one red string from the older case to the newer one
    assert f'[["{a.id}", "{b.id}"]]' in page.replace("&#34;", '"')


def test_closed_case_gets_an_evidence_wall_in_investigation_order(client, tmp_path):
    inv = save(tmp_path, status="done", verdict="reproduced", plan={"understanding": "A past date was saved."},
               judgement={"explanation": "The app saved it."},
               kane={"shots_dir": "s1", "shots": [{"file": "001.jpg", "status": "failed", "summary": "Saved"}]},
               fix={"status": "done", "verdict": "fixed", "regression_test": "bug-x-fixed",
                    "attempts": [{"attempt": 1, "fixer_said": "Added a check.", "patch": "--- a\n+++ b\n-old\n+new",
                                  "kane": {"verdict": "passed", "shots_dir": "s2",
                                           "shots": [{"file": "009.jpg", "status": "passed", "summary": "Error shown"}]}}]})
    board = web.evidence_board(inv, web._key_shot(inv.kane), web._key_shot(inv.fix["attempts"][-1]["kane"]))
    assert [p["id"] for p in board["pins"]] == ["statement", "reading", "scene", "verdict", "repair", "recheck", "closed"]
    assert board["links"] == [("statement", "reading"), ("reading", "scene"), ("scene", "verdict"),
                              ("verdict", "repair"), ("repair", "recheck"), ("recheck", "closed")]
    page = client.get(f"/r/{inv.id}").text
    assert "The evidence board" in page and "Kept on file: bug-x-fixed" in page and "+new" in page


def test_no_evidence_wall_while_kane_is_still_working(client, tmp_path):
    inv = save(tmp_path, status="reproducing")
    assert web.evidence_board(inv, None, None) is None


@pytest.mark.parametrize("closed, name, nxt", [(0, "Rookie", "Gumshoe"), (2, "Gumshoe", "Sleuth"),
                                               (6, "Inspector", "Chief Inspector"), (12, "Chief Inspector", None)])
def test_detective_rank_is_earned_by_closed_cases_only(closed, name, nxt):
    rank = web.detective_rank(closed)
    assert rank["name"] == name and rank["next"] == nxt and 0 <= rank["progress"] <= 100


def test_kane_only_says_what_is_really_happening(client, tmp_path):
    inv = save(tmp_path, status="reproducing")
    empty = {"steps": [], "total": 0, "hidden": 0, "elapsed": 0}
    assert web.kane_scene(inv, empty, False)["mode"] == "walking"
    steps = {**empty, "steps": [{"status": "done", "remark": "I typed 03/03/2025 into Date.", "kind": "type"}]}
    assert web.kane_scene(inv, steps, False)["line"] == "I typed 03/03/2025 into Date."
    inv.status = "done"
    assert web.kane_scene(inv, empty, False) is None


def test_scene_map_rooms_are_the_pages_kane_really_visited():
    kane = {"shots": [
        {"url": "http://127.0.0.1:8001/login", "status": "passed", "summary": "navigate: Navigate to http://127.0.0.1:8001/login"},
        {"url": "http://127.0.0.1:8001/login", "status": "passed", "summary": 'wait: queued plan (2 steps): type "Email"'},
        {"url": "http://127.0.0.1:8001/login", "status": "passed", "summary": "click: Clicking Log in button"},
        {"url": "http://127.0.0.1:8001/appointments/new?patient_id=3", "status": "passed", "summary": 'type: Type "03032025" into "Date"'},
        {"url": "http://127.0.0.1:8001/patients/10", "status": "failed", "summary": "assert: The app shows an error"},
    ]}
    rooms = web.scene_trail(kane, "Verify that the app shows an error saying the date is in the past.")
    assert [r["name"] for r in rooms] == ["Login", "Appointments · New", "Patients · #10"]
    assert rooms[1]["path"] == "/appointments/new?patient_id=3"
    assert [a["text"] for a in rooms[0]["actions"]] == ["I went to /login.", "I clicked Log in button."]
    assert [r["clue"] for r in rooms] == [False, False, True]
    assert rooms[2]["actions"][0]["text"] == "I checked: The app shows an error saying the date is in the past."


def test_a_new_case_opens_with_a_chapter_card(client, tmp_path):
    inv = save(tmp_path, status="queued")
    page = client.get(f"/r/{inv.id}").text
    assert 'data-chapter="' in page and "Detective Kane takes the case" in page
    inv.status = "done"
    inv.save()
    assert "data-chapter" not in client.get(f"/r/{inv.id}").text  # only when a case is really opened


def test_a_closed_case_offers_its_3d_reconstruction_built_from_its_evidence(client, tmp_path):
    inv = save(tmp_path, status="done", verdict="reproduced", plan={"understanding": "A past date was saved."},
               judgement={"explanation": "The app saved it."},
               kane={"shots_dir": "s1", "shots": [{"file": "001.jpg", "status": "failed", "summary": "Saved"}]})
    page = client.get(f"/r/{inv.id}").text
    assert "data-recon" in page and "Play the reconstruction" in page
    data = page.split('class="recon-data">', 1)[1].split("</script>", 1)[0]
    assert [p["id"] for p in json.loads(data)["pins"]] == ["statement", "reading", "scene", "verdict"]


def test_people_get_kanes_not_found_page_and_scripts_get_json(client):
    page = client.get("/r/20261116-145849-dbes", headers={"accept": "text/html"})
    assert page.status_code == 404 and "No case file at this address" in page.text
    api = client.get("/r/20261116-145849-dbes")
    assert api.status_code == 404 and api.json() == {"detail": "No such report"}


def test_verified_page_shows_the_recorded_proof(client):
    page = client.get("/verified")
    assert page.status_code == 200 and "Checked by Kane, not by us" in page.text
    assert "E1-fixed-bug-stays-fixed" in page.text and "Stop hook" in page.text


def test_a_finished_case_exports_a_report(client, tmp_path):
    inv = save(tmp_path, status="done", verdict="reproduced", plan={"understanding": "A past date was saved.", "objective": "x"},
               judgement={"explanation": "The app saved it.", "ticket": {"title": "Past dates accepted",
                          "steps": ["Book"], "expected": "Refused", "actual": "Saved"}},
               kane={"steps": ['click: Click "Book appointment"'], "shots_dir": "s", "shots": [{"file": "1.jpg", "status": "failed", "summary": "Saved"}]})
    assert "Case report (PDF)" in client.get(f"/r/{inv.id}/live").text
    page = client.get(f"/r/{inv.id}/report").text
    assert "Past dates accepted" in page and "I clicked Book appointment." in page and "Save as PDF" in page
    md = client.get(f"/r/{inv.id}/report.md")
    assert md.headers["content-disposition"].startswith("attachment")
    assert "**CONFIRMED**" in md.text and "**Confirmed.** The app saved it." in md.text and "1. I clicked Book appointment." in md.text


def test_no_export_while_kane_is_still_working(client, tmp_path):
    inv = save(tmp_path, status="reproducing")
    assert "Case report (PDF)" not in client.get(f"/r/{inv.id}/live").text


def test_bug_whisperer_does_not_offer_itself_as_an_app_to_investigate(client):
    assert all(a["file"] != "apps/bug-whisperer.json" for a in web.list_apps())
    assert "Bug Whisperer (itself)" not in client.get("/").text


def test_self_checks_are_kept_apart_from_the_bugs_bug_whisperer_fixed(tmp_path, monkeypatch):
    import json as _json
    from whisperer import proof
    registry = tmp_path / ".testmuai" / "closed-cases.json"
    registry.parent.mkdir()
    registry.write_text(_json.dumps({"cases": [
        {"case_id": "c1", "title": "Past dates", "test": "bug-1", "closed": "x", "app_file": "apps/clinic.json"},
        {"case_id": "self-front-desk", "title": "Front desk", "test": "self-front-desk", "objective": "o",
         "app_file": "apps/bug-whisperer.json", "self_check": True}]}), encoding="utf-8")
    revisits = tmp_path / "docs" / "proof" / "revisits"
    revisits.mkdir(parents=True)
    (revisits / "guard-20261117-090000.json").write_text(_json.dumps({"results": [
        {"case_id": "self-front-desk", "app": "Bug Whisperer (itself)", "verdict": "holds"},
        {"case_id": "c1", "app": "Clinic Records", "verdict": "holds"}]}), encoding="utf-8")
    monkeypatch.setattr(proof, "ROOT", tmp_path)
    monkeypatch.setattr(proof, "PROOF", tmp_path / "docs" / "proof")
    monkeypatch.setattr(proof, "RUNS", tmp_path / "runs")
    assert [t["title"] for t in proof._regression_tests()] == ["Past dates"]
    sc = proof._self_checks()
    assert sc["passing"] == 1 and sc["last_run"] == "2026-11-17 09:00"
    assert proof._revisits()["replays"] == 1  # the self-check isn't counted as a revisit of a closed case


def lineup_record(status="done", verdict="found"):
    def row(i, state, asked=None, verdict=None):
        r = {"sha": f"{i:040x}", "short": f"{i:07x}", "author": "sam", "date": "2026-11-17 10:21",
             "subject": f"commit {i}", "status": state, "questioned": bool(asked)}
        if asked:
            r.update(asked_as=asked, answer={"verdict": verdict, "failed_step": "No sample buttons on the page",
                                             "summary": "", "reason": None, "errors": [], "duration": 21.4})
        return r
    rows = [row(1, "cleared"), row(2, "cleared", 3, "passed"), row(3, "guilty", 4, "failed"), row(4, "present", 2, "failed")]
    if status != "done":
        rows[2].update(status="questioning", asked_as=None)
    return {"id": "lineup-20261118-120000", "check": "self-sample-reports", "title": "Sample reports",
            "objective": "x", "test": "self-sample-reports", "app": "Bug Whisperer (itself)",
            "app_file": "apps/bug-whisperer.json", "code_dir": "whisperer", "created": "2026-11-18 12:00",
            "status": status, "now": "suspect 3 of 4" if status != "done" else None,
            "good": {**row(0, "cleared", 1, "passed")}, "bad": rows[3], "suspects": rows,
            "questionings": 4, "fresh_runs": 0, "verdict": verdict if status == "done" else None,
            "verdict_words": "Kane named the commit that broke it", "culprit": rows[2]["sha"],
            "diff": {"stat": " whisperer/templates/report.html | 8 --------", "patch": "@@ -1 +1 @@\n-    <div class=\"examples\">", "cut": 0}}


def test_the_lineup_page_names_the_culprit_and_every_questioning_in_order(client, tmp_path, monkeypatch):
    from whisperer import lineup
    monkeypatch.setattr(lineup, "RUNS", tmp_path)
    (tmp_path / "lineup-20261118-120000").mkdir()
    (tmp_path / "lineup-20261118-120000" / "lineup.json").write_text(json.dumps(lineup_record()))
    page = client.get("/lineup/lineup-20261118-120000").text
    assert "Culprit found" in page and "The culprit" in page and "“commit 3”" in page
    told = page.split("The questionings, in order")[1]
    assert told.index("#1") < told.index("#2") < told.index("#3") < told.index("#4")
    assert "Last good version" in page and "(ruled out)" in page  # commit 1 was never questioned
    assert "No sample buttons on the page" in page and "Kane questioned <b>4</b> of 5 versions" in page and 'class="del"' in page
    assert "Sample reports" in client.get("/lineups").text
    assert "data-lineup3d" in page and "Play the lineup" in page  # a finished lineup can be played in 3D


def test_a_lineup_in_progress_keeps_refreshing_and_accuses_no_one_yet(client, tmp_path, monkeypatch):
    from whisperer import lineup
    monkeypatch.setattr(lineup, "RUNS", tmp_path)
    (tmp_path / "lineup-20261118-120000").mkdir()
    (tmp_path / "lineup-20261118-120000" / "lineup.json").write_text(json.dumps(lineup_record(status="questioning")))
    live = client.get("/lineup/lineup-20261118-120000/live").text
    assert 'data-active="true"' in live and "suspect 3 of 4" in live
    assert "The culprit" not in live and "Culprit found" not in live
    assert "data-lineup3d" not in live  # nothing to play until Kane has finished


def test_an_unknown_lineup_is_not_found(client):
    assert client.get("/lineup/lineup-nope", headers={"accept": "application/json"}).status_code == 404


PLAN = {"status": "ready", "cause": "The server saves any date.", "recommended": "B",
        "options": [{"id": "A", "title": "Guard the calendar", "change": "Hide past days.", "files": ["templates/book.html"],
                     "tradeoff": "Nicer, but the server still takes them.", "recommended": False},
                    {"id": "B", "title": "Guard the door", "change": "The server refuses past dates.", "files": ["app.py"],
                     "tradeoff": "Nothing gets past it.", "recommended": True}],
        "sealed": {"objective": "Go to http://127.0.0.1:8001/book. Verify that yesterday is refused.",
                   "why": "A repair for last year only would miss yesterday."}}


def test_the_repair_plan_shows_each_way_and_the_sealed_question_before_anything_changes(client, tmp_path):
    inv = save(tmp_path, status="done", verdict="reproduced", repair_plan=PLAN)
    page = client.get(f"/r/{inv.id}").text
    assert "Claude's repair plan" in page and "The server saves any date." in page
    assert "Guard the calendar" in page and "Guard the door" in page and "Claude's pick" in page
    assert page.count("Repair it this way") == 2 and "sealed question" in page and "yesterday is refused" in page


def test_repair_follows_the_way_the_person_picked(client, tmp_path):
    inv = save(tmp_path, status="done", verdict="reproduced", repair_plan=PLAN)
    assert client.post(f"/r/{inv.id}/fix", data={"option": "a"}, follow_redirects=False).status_code == 303
    assert detective_load(tmp_path, inv.id)["fix"]["option"] == "A"
    inv = save(tmp_path, status="done", verdict="reproduced", repair_plan=PLAN)
    client.post(f"/r/{inv.id}/fix", data={"option": "Z"}, follow_redirects=False)
    assert detective_load(tmp_path, inv.id)["fix"]["option"] == "B"  # an unknown way: Claude's pick


def test_a_plan_being_written_keeps_the_page_refreshing_and_hides_repair(client, tmp_path, monkeypatch):
    inv = save(tmp_path, status="done", verdict="reproduced", repair_plan={"status": "planning"})
    monkeypatch.setattr(web, "waiting", [inv.id])
    page = client.get(f"/r/{inv.id}/live").text
    assert 'data-active="true"' in page and "reading the code to plan the repair" in page
    assert "Repair it this way" not in page and "Repair without a plan" not in page
    assert client.post(f"/r/{inv.id}/fix", follow_redirects=False).status_code == 400
    monkeypatch.setattr(web, "waiting", [])  # the server restarted mid-plan: offer to plan again
    page = client.get(f"/r/{inv.id}/live").text
    assert 'data-active="false"' in page and "Plan the repair" in page


def test_the_closed_case_shows_the_kept_word_and_the_sealed_question(client, tmp_path):
    attempt = {"attempt": 1, "fixer_said": "Refused past dates.", "patch": "--- a/clinic/app.py\n+++ b/clinic/app.py\n+check",
               "promise": {"promised": ["app.py"], "touched": ["clinic/app.py"], "extra": [], "unused": [], "kept": True},
               "kane": {"verdict": "passed"}, "sealed": {"verdict": "passed", "summary": "Yesterday was refused."}}
    inv = save(tmp_path, status="done", verdict="reproduced", plan={"expected": "Refuse past dates."}, repair_plan=PLAN,
               fix={"status": "done", "verdict": "fixed", "approach": PLAN["options"][1], "attempts": [attempt]})
    page = client.get(f"/r/{inv.id}").text
    assert "Following plan B: Guard the door" in page and "Kept its word?" in page
    assert "changed only what the plan named" in page and "held. The same bug, reached another way" in page
    assert "Kane's sealed question" in client.get(f"/r/{inv.id}/report.md").text


def detective_load(tmp_path, inv_id):
    return json.loads((tmp_path / inv_id / "investigation.json").read_text(encoding="utf-8"))


def test_live_part_is_fingerprinted_so_an_unchanged_page_is_not_redrawn(client, tmp_path):
    inv = save(tmp_path, status="done", verdict="reproduced", judgement={"explanation": "The app saved it."},
               repair_plan={"status": "planning"})
    first, again = client.get(f"/r/{inv.id}/live"), client.get(f"/r/{inv.id}/live")
    sig = first.headers["X-Live-Sig"]
    assert sig and again.headers["X-Live-Sig"] == sig
    assert f'data-sig="{sig}"' in client.get(f"/r/{inv.id}").text  # the page starts on the same version
    inv.judgement = {"explanation": "Kane saw it save the date again."}
    inv.save()
    changed = client.get(f"/r/{inv.id}/live")
    assert "saw it save the date again" in changed.text and changed.headers["X-Live-Sig"] != sig

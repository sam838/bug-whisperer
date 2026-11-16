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
    assert "Confirmed" in page and "Repair it" in page and "Past dates accepted" in page


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

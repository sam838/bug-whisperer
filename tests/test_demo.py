"""Hosted demo rules: passcode for live runs, daily limit, no connecting strangers' apps."""

import os

import pytest
from fastapi.testclient import TestClient

os.environ["WHISPERER_NO_BOOT"] = "1"
from whisperer import apprunner, demo, detective, web  # noqa: E402


@pytest.fixture
def hosted(tmp_path, monkeypatch):
    monkeypatch.setenv("WHISPERER_HOSTED", "1")
    monkeypatch.setenv("DEMO_PASSCODE", "kane-judges")
    monkeypatch.setenv("DEMO_DAILY_LIMIT", "1")
    monkeypatch.setattr(detective, "RUNS", tmp_path)
    monkeypatch.setattr(web, "RUNS", tmp_path)
    monkeypatch.setattr(demo, "USAGE", tmp_path / "usage.json")
    monkeypatch.setattr(web, "enqueue", lambda kind, inv_id: None)
    return TestClient(web.app)


REPORT = {"app_file": "apps/clinic.json", "report": "it broke"}


def test_live_case_needs_the_passcode(hosted):
    r = hosted.post("/report", data=REPORT, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/unlock"


def test_wrong_passcode_is_refused(hosted):
    r = hosted.post("/unlock", data={"passcode": "guess"}, follow_redirects=False)
    assert r.headers["location"] == "/unlock?wrong=1"


def test_right_passcode_unlocks_then_daily_limit_applies(hosted):
    hosted.post("/unlock", data={"passcode": "kane-judges"})
    first = hosted.post("/report", data=REPORT, follow_redirects=False)
    assert first.status_code == 303 and first.headers["location"].startswith("/r/")
    second = hosted.post("/report", data=REPORT, follow_redirects=False)
    assert second.status_code == 429 and "done for today" in second.text


def test_connecting_apps_is_off_on_the_public_demo(hosted):
    hosted.post("/unlock", data={"passcode": "kane-judges"})
    assert hosted.post("/apps", data={"name": "X", "url": "https://x.example"}).status_code == 403


def test_browsing_cases_needs_no_passcode(hosted):
    assert hosted.get("/inbox").status_code == 200
    assert "Live demo" in hosted.get("/").text


def test_the_app_never_sees_bug_whisperers_secrets(monkeypatch):
    monkeypatch.setenv("LT_ACCESS_KEY", "secret")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "secret")
    env = apprunner.app_env()
    assert "LT_ACCESS_KEY" not in env and "CLAUDE_CODE_OAUTH_TOKEN" not in env

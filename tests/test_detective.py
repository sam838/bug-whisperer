"""The claim double-check decides the verdict from Kane's result, never from a guess."""

import pytest

from whisperer import detective, kane


@pytest.fixture
def inv(tmp_path, monkeypatch):
    monkeypatch.setattr(detective, "RUNS", tmp_path)
    return detective.Investigation(report="you sell canon cameras", app="Shop")


APP = detective.App(name="Shop", base_url="https://shop.example.com")


@pytest.mark.parametrize("kane_verdict, outcome, verdict", [
    ("passed", "confirmed", "reproduced"),
    ("failed", "not_true", "not_reproduced"),
    ("error", "unknown", "inconclusive"),
])
def test_claim_check(inv, monkeypatch, kane_verdict, outcome, verdict):
    monkeypatch.setattr(kane, "run", lambda *a, **k: kane.KaneResult(verdict=kane_verdict, exit_code=0))
    assert detective.check_claim(APP, inv, "Search canon. Verify a Canon product is listed.",
                                 lambda status: None) == verdict
    assert inv.claim["outcome"] == outcome


def test_judge_is_told_a_step_that_never_happened_proves_nothing():
    """On the server, Kane 'clicked' Book but the form never submitted; that once got a Confirmed."""
    assert "the form was" in detective.JUDGE_PROMPT and "never submitted" in detective.JUDGE_PROMPT
    assert "Read Kane's own summary first" in detective.JUDGE_PROMPT

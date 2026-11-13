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

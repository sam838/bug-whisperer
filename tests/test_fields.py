"""The field guide only says what browsers really do: every checked example is typed key by key into
real Chrome, in locales whose date boxes are mm/dd (US) and dd/mm (UK, Indonesia). No Kane credits.
Skipped where Chrome isn't installed."""

import pytest

from whisperer import detective, fields

LOCALES = ["en-US", "en-GB", "id-ID"]


@pytest.fixture(scope="module")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        try:
            chrome = p.chromium.launch(channel="chrome", headless=True)
        except Exception:  # no Chrome on this machine
            pytest.skip("Chrome is not installed")
        yield chrome
        chrome.close()


@pytest.mark.parametrize("locale", LOCALES)
def test_checked_examples_work_in_real_chrome(browser, locale):
    page = browser.new_context(locale=locale).new_page()
    for input_type, keys, expected in fields.CHECKED:
        page.set_content(f'<input id="f" type="{input_type}">')
        page.focus("#f")
        for part in keys:
            if part.startswith("{"):
                page.keyboard.press(part.strip("{}"))
            else:
                page.keyboard.type(part)
        assert page.eval_on_selector("#f", "e => e.value") == expected, (locale, input_type, keys)


def test_the_dash_format_really_breaks_a_date_box(browser):
    """Why the guide exists: typing an ISO date into a US date box gives nonsense."""
    page = browser.new_context(locale="en-US").new_page()
    page.set_content('<input id="f" type="date">')
    page.focus("#f")
    page.keyboard.type("2025-03-03")
    assert page.eval_on_selector("#f", "e => e.value") != "2025-03-03"


def test_planner_sees_what_to_fill():
    prompt = detective.PLAN_PROMPT.format(name="Shop", base_url="https://x", about="", accounts="",
                                          report="r", screenshot="", fields=fields.GUIDE, feedback="")
    assert "Fill EVERY field on the form, optional ones too" in prompt


def test_no_mid_run_checkpoints_are_asked_for():
    """A 'check' in the middle becomes a Kane checkpoint; one that fails ends the run early."""
    assert "Don't add extra checks" in fields.GUIDE
    assert 'add "Check that every field is filled' not in detective.RETRY_FEEDBACK


def test_claude_names_values_and_leaves_the_typing_to_kane():
    assert "11 November 2027" in fields.GUIDE and "11112027" not in fields.GUIDE


def test_kane_context_teaches_the_same_checked_examples():
    """Kane reads .testmuai/context.md itself: it must teach the examples checked in real Chrome."""
    from whisperer import kane
    text = kane.CONTEXT.read_text(encoding="utf-8")
    for value in ("11112027", "03032025", "1430", "0900", "452027", "1,500"):
        assert value in text

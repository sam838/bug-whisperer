"""Kane's voice: real remarks from our Kane runs, turned into first-person lines."""

import pytest

from whisperer.voice import speak


@pytest.mark.parametrize("remark, line", [
    ("navigate: Navigate to http://127.0.0.1:8001/login", "I went to http://127.0.0.1:8001/login."),
    ('type: Type "{{global.account1_email}}" into "Email"', "I typed the test email into Email."),
    ('type: Type "{{secrets.user.account1_password}}" into "Password"',
     "I typed the test password into Password."),
    ('type: Type "2025-03-03" into "Date"', "I typed 2025-03-03 into Date."),
    ('select: Select "Aisha Rahman" in "Patient"', "I picked Aisha Rahman in Patient."),
    ('click: Click "Book appointment"', "I clicked Book appointment."),
    ("click: Clicking Log in button", "I clicked Log in button."),
    ("assert: The app shows an error saying the date is in the past",
     "I checked: The app shows an error saying the date is in the past."),
    ("analyze: The appointment was not saved.", "I looked closely: The appointment was not saved."),
])
def test_kane_speaks_in_the_first_person(remark, line):
    assert speak(remark) == line


@pytest.mark.parametrize("remark", [
    'wait: queued plan (3 steps): type "Email"; type "Password"; click "Log in"',
    "analyze: ANALYZE(visual, 'something')",
    "Step 12",
    "",
    None,
])
def test_bookkeeping_is_not_spoken(remark):
    assert speak(remark) is None


@pytest.mark.parametrize("remark, line", [
    ("navigate: Go to the new appointment booking page", "I went to the new appointment booking page."),
    ('click: Clicking button to save the appointment; role=button; text="Book appoi',
     "I clicked button to save the appointment."),
    ("press: Press Tab", "I pressed Tab."),
    ("Press Space", "I pressed Space."),
    ("focus: move keyboard focus from the Time input toward the save button",
     "I moved keyboard focus from the Time input toward the save button."),
])
def test_odd_server_remarks_read_naturally(remark, line):
    assert speak(remark) == line


def test_icon_font_characters_are_dropped():
    assert speak('click: Click " Search"') == "I clicked Search."


def test_real_passwords_never_appear():
    assert "sunrise123" not in (speak('type: Type "{{secrets.user.account1_password}}" into "Password"') or "")

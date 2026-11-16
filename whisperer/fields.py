"""Forms, split between the two agents: Claude decides WHAT to fill, Kane knows HOW to type it.

- GUIDE (below) is for Claude when it writes Kane's steps: which fields, which values.
- .testmuai/context.md is for Kane, read on every run: how to type into each kind of box. Kane
  types key by key, and the browser's date and time pickers take keys segment by segment: typing
  "2027-11-11" into a US date box gives 50303-02-20, and the browser silently refuses the form.

CHECKED holds the typing examples Kane's context teaches. tests/test_fields.py types each one into
real Chrome in US, UK and Indonesian locales, so Kane is only taught what browsers really do.
"""

# (input type, keys typed; "{Tab}" is a key press, what the box must end up holding)
CHECKED = [
    ("date", ["11112027"], "2027-11-11"),
    ("date", ["03032025"], "2025-03-03"),
    ("time", ["1430"], "14:30"),
    ("time", ["0900"], "09:00"),
    ("datetime-local", ["11112027", "{Tab}", "1430"], "2027-11-11T14:30"),
    ("month", ["11", "{Tab}", "2027"], "2027-11"),
    ("week", ["452027"], "2027-W45"),
    ("number", ["1500"], "1500"),
]

GUIDE = """What to fill (Kane already knows how to type into each kind of box, including the browser's
date and time pickers, so name the values plainly):
- Fill every field the form needs, in page order, one short sentence each, even fields the report
  doesn't mention (a booking usually needs a date AND a time). Kane can't see the browser's
  "please fill in this field" bubble, so a field left out makes Kane click a submit button that
  seems to do nothing.
- Before the submit click add: "Check that every field is filled."
- Dates in words, with the year: "Set the Date field to 11 November 2027." Never "today" or
  "tomorrow". Unless the report is about a specific date, choose one at least a year ahead whose
  day and month are the same number (11 November, 3 March), so it reads the same in mm/dd and
  dd/mm boxes and still means the same thing when replayed months later.
- Times on the 24-hour clock: "Set the Time field to 14:30."
- Numbers as plain digits, no thousands separators: "1500".
- Dropdowns by their exact option text: "Select '<option>' in the <label> dropdown."
- Avoid file uploads unless the report is about uploading."""

"""How to fill each kind of form field, for Claude when it writes Kane's steps.

Kane types like a person, key by key. That's fine for text boxes, but the browser's own date, time
and month pickers take keys segment by segment: typing "2027-11-11" into a US date box gives
50303-02-20, and the browser then silently refuses the form. These rules work on any website.

The CHECKED examples were typed into real Chrome in US, UK and Indonesian locales
(tests/test_fields.py repeats that), so the guide says only what browsers actually do.
"""

# (input type, keys Kane types; "{Tab}" is a key press, what the box must end up holding)
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

GUIDE = """How to fill each kind of field (Kane types key by key, like a person):
- Text, email, password, search, text area: "Type <value> into the <label> field."
- Number: digits only, no thousands separators or currency signs: "Type 1500" ("1,500" becomes 1.5).
- Phone, card and other formatted boxes: digits only, no spaces or dashes.
- Date box (the browser's own picker, showing mm/dd/yyyy or dd/mm/yyyy): digits only, no dashes:
  "Type 11112027 into the Date field." Typing 2027-11-11 gives a broken date. Choose dates whose
  day and month are the same number (11 Nov, 3 Mar), so the digits are right in either order. For a
  date from the report where they differ, say to type the digits in the order the box shows.
- Time box: four digits, 24-hour clock: "Type 1430 into the Time field." (Typing 0230PM gives 02:30.)
- Date and time in one box: "Type 11112027, press Tab, then type 1430 into the <label> field."
- Month box: "Type 11, press Tab, then type 2027 into the <label> field."
- Week box: week number then year: "Type 452027 into the <label> field."
- Dropdown list: "Select '<exact option text>' in the <label> dropdown."
- Search-as-you-type box: "Type '<first letters>' into the <label> field, then click '<full option>'
  in the list that appears."
- Pop-up calendar that won't take typing: "Click the <label> field, move to <month year> with the
  calendar's arrows, and click <day>."
- Checkbox, radio button, switch: "Tick '<label>'." / "Choose '<option>'." / "Turn on '<label>'."
- Slider: "Click the <label> slider and press the right arrow key until it shows <value>."
- File upload: avoid, unless the report is about uploading.
- Required fields: Kane can't see the browser's "please fill in this field" bubble, so a missed
  field leaves it clicking a button that seems to do nothing. Fill every field the form needs
  (date AND time), even ones the report doesn't mention, and before the submit click add:
  "Check that every field is filled.\""""

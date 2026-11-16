# Filling in forms

These hold on every website. They come from runs where a booking silently failed because a date
was typed the wrong way, and each typed example was checked in real Chrome with US (mm/dd) and UK
or Indonesian (dd/mm) date formats.

## The browser's own date, time and month boxes
They take keys segment by segment, not as text. Typing `2027-11-11` into a date box gives a broken
date (a US box ends up holding 50303-02-20).

- **Date box** (shows `mm/dd/yyyy` or `dd/mm/yyyy`): click it and type the digits only, in the
  order the box shows. 11 November 2027 is `11112027`. 3 March 2025 is `03032025`.
- **Time box**: four digits on the 24-hour clock. 2:30 pm is `1430`, 9 am is `0900`. Don't type
  AM or PM: `0230PM` ends up as 02:30 in the morning.
- **Date and time in one box**: the date digits, press Tab, then the time digits.
- **Month box**: the month number, press Tab, then the year.
- **Week box**: the week number then the year: week 45 of 2027 is `452027`.
- After typing, look at the box. It must show the date or time you meant. If it doesn't, clear
  it and type the digits again in the order the box shows.

## Other fields
- **Numbers**: digits only, without thousands separators or currency signs. `1,500` becomes 1.5.
- **Phone, card and other formatted boxes**: digits only, without spaces or dashes.
- **Search-as-you-type boxes**: type the first letters, wait for the list, then click the option.
- **Pop-up calendars that won't take typing**: open the calendar, move to the right month with
  its arrows, and click the day.

## When a submit button seems to do nothing
The browser's "please fill in this field" bubble doesn't show up in your screenshots. If the page
stays on the form after you click submit, a required field is empty or invalid. Look over every
field, fill the empty one, and submit again, instead of clicking the same button over and over.

# Evidence 006: the repair plan and Kane's sealed question, end to end on the live site

**What this shows:** one full case on the hosted demo, with the two steps added last: Claude's
repair plan (read-only, before anything changes) and Kane's sealed question (one more check the
fixer never sees). Kane reproduced the bug, Claude repaired it from Kane's evidence, Kane repeated
the same steps, and then Kane asked the sealed question. Both passed, so the case closed.

- Case `20261124-123326-9973`, Clinic Records, opened 2026-11-24 12:33 (server time, UTC)
- [case-report.md](case-report.md): the case report as the site exports it
- [case-page.html](case-page.html): the case page, saved before the next deploy wiped the server's
  disk. It also holds the link to Kane's run on TestMu AI.
- [screens/](screens/): Kane's screenshots from the three runs (reproduce, re-check, sealed question)

## The report

> booked mr tan for today at 7:00 this morning but it was already 9am when i did it. the system
> just saved it, no warning. i thought you fixed booking in the past??

We wrote this report ourselves on the live site. The bug is real: the clinic app as the AI first
built it never compares a booking with the current time. The hosted site resets the clinic to that
first version for every case, so Kane reproduced it with a date that is clearly past
(11 November 2020).

## What happened

| Step | Who | Result |
|---|---|---|
| Reproduce | Kane, real browser | ✗ the booking was saved with no warning. **Confirmed.** |
| Repair plan | Claude, read-only | Cause in plain words and the ways to repair it. Picked: plan A, *reject past date and time on save* (`clinic/app.py`) |
| Repair | Claude | 6 lines in `validate_appointment`: combine date and time and reject anything not later than now |
| Kept its word? | code, not Claude | **Yes:** it changed only the file the plan named |
| Back to the scene | Kane, same steps | ✓ *"Please choose a date and time in the future."* |
| Sealed question | Kane, new steps | ✓ another patient (James Carter), **today** at 08:00 while the server's clock said about 12:45. Rejected with the same warning. |

The sealed question is the part a too-narrow repair would fail: a fix that only refused past *days*
would have saved a booking earlier on the same day.

## Why the sealed question now asks about "today" safely

The first live try of this step (case `20261124-021902-6482`, earlier the same day) was a false
fail. Claude wrote the sealed question from the user's clock ("today 08:00", 9am for the user),
but the server's clock said 02:35 UTC, so 08:00 was still in the future and the app was right to
accept it. Kane failed a correct repair.

Commit `3c1f10e` fixed this: the plan prompt now carries the app's own clock. A local app gives its
time and time zone. A hosted app gives only the date, and the sealed question then uses whole days.
A time on today's date must be at least 2 hours from the app's time now. This case ran after that
fix.

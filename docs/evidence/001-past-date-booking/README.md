# Evidence 001: appointments could be booked in the past

**Status: ✅ fixed and re-checked by Kane CLI** (Nov 13, 2026)

| | Kane CLI result | File |
|---|---|---|
| Reproduce (try 1) | ⚠️ inconclusive: Kane ran out of steps (21 of 20), so nothing was claimed | [first-try-ran-out-of-steps.json](first-try-ran-out-of-steps.json) |
| Reproduce (try 2) | ❌ **failed**: the app saved a 3 March 2025 booking with no error. **Bug reproduced** | [reproduce-1.ndjson](reproduce-1.ndjson) |
| Fix | Claude Code (headless), given only the report and Kane's evidence, changed one function | [fix.patch](fix.patch) |
| Re-check, same objective | ✅ **passed**: the app now refuses the booking | [verify-1.ndjson](verify-1.ndjson) |
| Replay of the saved test (try 1) | ⚠️ inconclusive: our own mistake. We had blanked the password in the saved test, and Kane flagged it as an *automation bug, not an app bug* | [replay-1.ndjson](replay-1.ndjson) |
| Replay of the saved test (try 2) | ✅ **passed** in 20 s, no credits used, no password stored in the test | [replay-2.ndjson](replay-2.ndjson) |

All of it, step by step: [investigation.json](investigation.json).

**Where the bug came from:** the AI builder (see `docs/CLINIC_BUILD_PROMPT.md`) checked that a
date was valid but never that it wasn't in the past. We didn't plant it.

## The report, as written

> hi. my receptionist booked mrs aisha for 3 march 2025 by accident (we meant 2027) and the
> system just saved it?? no warning nothing. it should not let us book in the past right. we are
> sunrise clinic

## What Kane saw before the fix

> The form did not reject the 3 March 2025 appointment date. After booking, the patient page
> shows the 03 Mar 2025 · 10:00 appointment, and no past-date error is shown.

## What the fixer said

> The app was saving bookings on any valid date, including dates that had already passed, so the
> 3 March 2025 booking went through with no warning. I added a check in `validate_appointment`
> that turns down dates before today. The booking form now stays open with "The appointment date
> cannot be in the past. The appointment was not saved." and nothing is saved.

## The regression test

`.testmuai/tests/bug-20261113-112727_test.md` is the passing run, saved by Kane. Bug Whisperer
removes secret variables from it (Kane writes them in plain text), and passes them in with
`--variables` when it replays. The replay uses `--no-adaptive-heal`, so if this bug comes back,
the test fails instead of healing around it.

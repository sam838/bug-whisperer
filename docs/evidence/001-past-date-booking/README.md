# Evidence 001: appointments can be booked in the past

**Status: 🐛 reproduced by Kane CLI** (Nov 13, 2026). Not fixed yet.

**Where the bug came from:** the AI builder (see `docs/CLINIC_BUILD_PROMPT.md`) checked that a
date is valid but never that it isn't in the past. We didn't plant it.

## The report, as written

> hi. my receptionist booked mrs aisha for 3 march 2025 by accident (we meant 2027) and the
> system just saved it?? no warning nothing. it should not let us book in the past right. we are
> sunrise clinic

## What happened

| Try | Result | Why |
|---|---|---|
| 1 ([first-try-ran-out-of-steps.json](first-try-ran-out-of-steps.json)) | ⚠️ inconclusive | Kane ran out of steps (21 of 20) before its final check. The judge marked it as not proven, so nothing was claimed |
| 2 ([investigation.json](investigation.json)) | 🐛 **reproduced** | Shorter plan, more steps. Kane booked Aisha on 2025-03-03 10:00, the app saved it (POST → 303), and no error was shown. Kane's final check failed |

Kane's own summary of try 2:

> The form did not reject the 3 March 2025 appointment date. After booking, the patient page
> shows the 03 Mar 2025 · 10:00 appointment, and no past-date error is shown.

- Raw Kane output: [reproduce-1.ndjson](reproduce-1.ndjson). Passwords are masked by Kane as
  `{{secrets.user.account1_password}}`.
- Cost: 39 Kane credits and 119 s for try 2.

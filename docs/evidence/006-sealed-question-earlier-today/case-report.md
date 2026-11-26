# Case #6: Past-dated appointments are accepted without a warning

**CASE CLOSED** · Clinic Records · opened 2026-11-24 12:33 · report 20261124-123326-9973

## The report

> booked mr tan for today at 7:00 this morning but it was already 9am when i did it. the system just saved it, no warning. i thought you fixed booking in the past??

**What the user most likely did:** The user booked an appointment for Mr Tan at 07:00 on the current day after 9am had already passed, and the system saved the past-dated appointment with no validation warning.

**What should happen:** The system should reject booking an appointment whose date and time are already in the past and show a warning instead of silently saving it.

## What Kane did, in a real browser

1. I went to http://127.0.0.1:8001/login.
2. I typed the test email into Email.
3. I typed the test password into Password.
4. I clicked Log in button in the login form.
5. I clicked Appointments link in the top navigation bar.
6. I clicked + Book appointment.
7. I picked Aisha Rahman in the Patient dropdown.
8. I typed date as 11 November 2020.
9. I typed 07:00 into the Time field.
10. I clicked Book appointment button.
11. I waited to see what the page did.
12. I checked: The appointment was rejected with a warning that the date and time are in the past.

## Verdict

**Confirmed.** The booking form was filled out with a date and time in the past and submitted successfully (the server returned a normal save/redirect), with no warning shown anywhere on the page afterward. This matches exactly what the user reported: booking a past appointment is silently saved instead of being rejected.

## The repair

**The plan picked:** A. Reject past date and time on save: In the same validation function that already checks the date/time format, also combine the chosen date and time and compare it to the clinic's current date and time; if it's not later, add a warning like 'Please choose a date and time in the future' and the form re-shows with the appointment not saved.

The edit looks syntactically correct. The booking form let past date/times through because `validate_appointment` only checked date/time format, never compared against the current time; I added a check in that same function that combines the chosen date and time and rejects it with "Please choose a date and time in the future." if it isn't later than the clinic's current time (via the existing `utcnow()` helper).

```diff
diff --git a/clinic/app.py b/clinic/app.py
index 46b0718..511fdd9 100644
--- a/clinic/app.py
+++ b/clinic/app.py
@@ -243,14 +243,19 @@ def validate_patient(full_name: str, date_of_birth: str) -> list[str]:
 
 def validate_appointment(appt_date: str, appt_time: str) -> list[str]:
     errors = []
+    parsed_date = None
     try:
-        date.fromisoformat(appt_date)
+        parsed_date = date.fromisoformat(appt_date)
     except ValueError:
         errors.append("Please choose a valid date.")
+    parsed_time = None
     try:
-        datetime.strptime(appt_time, "%H:%M")
+        parsed_time = datetime.strptime(appt_time, "%H:%M").time()
     except ValueError:
         errors.append("Please choose a valid time.")
+    if parsed_date is not None and parsed_time is not None:
+        if datetime.combine(parsed_date, parsed_time) <= utcnow():
+            errors.append("Please choose a date and time in the future.")
     return errors
```

**Kept its word?** Yes: it changed only what the plan named (clinic/app.py).

**Kane went back and repeated the same steps:** passed. The requested appointment was prepared for Aisha on 11 November 2020 at 07:00, with no notes.
After selecting Book, the appointment was not created because the chosen date and time were in the past.
The page displayed: “Please choose a date and time in the future.”

**Kane's sealed question** (the fixer never saw it): Start at http://127.0.0.1:8001/login. Log in with email {{account1_email}} and password {{account1_password}}. Go to the page to book a new appointment. Select 'James Carter' in the Patient dropdown. Set the Date field to 24 November 2026. Set the Time field to 08:00. Set the Reason field to 'Follow-up visit'. Click the Book button. Store what the page shows after that as 'what_happened'. Verify that the appointment was rejected with a warning that the date and time are in the past.

Result: passed. Logged in and opened the form to book a new appointment.
Selected James Carter, entered 24 November 2026 at 08:00, and added “Follow-up visit” as the reason.
Submitted the appointment request, but it was rejected because the page said: “Please choose a date and time in the future.”

**Kept on file as a regression test:** `bug-20261124-123326-9973-r1a1`

## Bug ticket

### Past-dated appointments are accepted without a warning

**Steps**
1. Log in with a valid account
2. Go to the new appointment booking page
3. Select any patient
4. Set the Date and Time fields to a date/time that is already in the past
5. Click the Book button

**Expected:** The system rejects the booking and shows a warning that the selected date and time are in the past.

**Actual:** The system saves the appointment anyway and redirects to the patient's page with no warning shown.

Reproduced by Kane CLI (Bug Whisperer report 20261124-123326-9973).

---
Proved by Kane CLI: 4 run(s), about 372 s, 118.6 credits. Generated by Bug Whisperer on 2026-11-24 12:50.

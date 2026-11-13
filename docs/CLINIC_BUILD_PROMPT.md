# How the clinic app was built

The clinic app in `clinic/` is the **sample app**: the app whose users send bug reports to
Bug Whisperer. It is not part of Bug Whisperer itself.

It was written by a separate Claude Code session (headless, `claude -p`), which got only the
request below: the kind of request a busy founder types. No person edited the code afterwards.
Its session log is in `clinic-build-session.json`. From here on, the clinic code changes only
through Bug Whisperer's fix loop, so every change can be traced to a bug report.

The exact prompt, word for word:

---

Build a simple web app for small clinics.

Several clinics share the app. Each clinic signs up with an email and password, then logs in.
After logging in, a clinic can:

- add patients (full name, phone, date of birth, diagnosis, notes)
- see its patient list
- open a patient's page, edit it, and delete it
- book appointments for its patients (date, time, reason) and see its appointments
- export its patient list as a CSV file
- print a patient summary page

Use Python with FastAPI, Jinja2 templates and SQLite. Keep it simple and make it look clean.
Put everything in this folder. Add a requirements.txt and a README that says how to run it.
The app must run on port 8001 with: `uvicorn app:app --port 8001`

Add a seed script, `seed.py`, that creates two clinics with a few patients and appointments each:

- Sunrise Clinic: sunrise@example.com / sunrise123
- Harbor Clinic: harbor@example.com / harbor123

# Clinic Records

A small web app for clinics to keep patient records and appointments.
Several clinics can use the same app; each clinic only sees its own data.

Built with Python, FastAPI, Jinja2 templates and SQLite.

## Features

- Clinic sign up and log in (email + password)
- Add, view, edit and delete patients (full name, phone, date of birth, diagnosis, notes)
- Search the patient list
- Book and cancel appointments (date, time, reason) and see upcoming and past appointments
- Export the patient list as a CSV file
- Print a patient summary page

## Run it

You need Python 3.10 or newer.

```bash
# 1. Create a virtual environment (optional, recommended)
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

# 2. Install the dependencies
pip install -r requirements.txt

# 3. (Optional) Add demo data
python seed.py

# 4. Start the app
uvicorn app:app --port 8001
```

Open http://localhost:8001 in your browser.

## Demo accounts

After running `python seed.py` you can log in with:

| Clinic         | Email               | Password   |
|----------------|---------------------|------------|
| Sunrise Clinic | sunrise@example.com | sunrise123 |
| Harbor Clinic  | harbor@example.com  | harbor123  |

Running `seed.py` again resets these two clinics. Other clinics are not changed.

## Files

```
app.py            FastAPI app: routes, database, login sessions
seed.py           Creates the two demo clinics
templates/        Jinja2 HTML templates
static/style.css  Styles (including print styles)
clinic.db         SQLite database (created automatically on first run)
```

To start with an empty database, stop the app and delete `clinic.db`.

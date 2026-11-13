"""Small multi-clinic patient records app.

Run with:  uvicorn app:app --port 8001
"""

import csv
import hashlib
import hmac
import io
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "clinic.db"
SESSION_COOKIE = "clinic_session"
SESSION_DAYS = 7

app = FastAPI(title="Clinic Records")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS clinics (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    clinic_id  INTEGER NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS patients (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id     INTEGER NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    full_name     TEXT NOT NULL,
    phone         TEXT NOT NULL DEFAULT '',
    date_of_birth TEXT NOT NULL DEFAULT '',
    diagnosis     TEXT NOT NULL DEFAULT '',
    notes         TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_patients_clinic ON patients(clinic_id);

CREATE TABLE IF NOT EXISTS appointments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id  INTEGER NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    date       TEXT NOT NULL,
    time       TEXT NOT NULL,
    reason     TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_appointments_clinic ON appointments(clinic_id);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.executescript(SCHEMA)


init_db()


# --------------------------------------------------------------------------
# Passwords and sessions
# --------------------------------------------------------------------------

PBKDF2_ITERATIONS = 200_000


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, expected = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations))
    except ValueError:
        return False
    return hmac.compare_digest(digest.hex(), expected)


def create_session(clinic_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = (utcnow() + timedelta(days=SESSION_DAYS)).isoformat()
    with db() as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (utcnow().isoformat(),))
        conn.execute(
            "INSERT INTO sessions (token, clinic_id, expires_at) VALUES (?, ?, ?)",
            (token, clinic_id, expires),
        )
    return token


def current_clinic(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    with db() as conn:
        return conn.execute(
            """SELECT c.id, c.name, c.email FROM sessions s
               JOIN clinics c ON c.id = s.clinic_id
               WHERE s.token = ? AND s.expires_at > ?""",
            (token, utcnow().isoformat()),
        ).fetchone()


class LoginRequired(Exception):
    pass


class NotFound(Exception):
    pass


@app.exception_handler(LoginRequired)
async def _login_required(request: Request, exc: LoginRequired):
    return RedirectResponse("/login", status_code=303)


@app.exception_handler(NotFound)
async def _not_found(request: Request, exc: NotFound):
    return render(request, "not_found.html", status_code=404, clinic=current_clinic(request))


def require_clinic(request: Request):
    clinic = current_clinic(request)
    if clinic is None:
        raise LoginRequired()
    return clinic


def login_response(clinic_id: int) -> RedirectResponse:
    response = RedirectResponse("/patients", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        create_session(clinic_id),
        max_age=SESSION_DAYS * 24 * 3600,
        httponly=True,
        samesite="lax",
    )
    return response


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def render(request: Request, template: str, status_code: int = 200, **context):
    return templates.TemplateResponse(request, template, context, status_code=status_code)


def redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def age_from_dob(dob: str):
    try:
        born = date.fromisoformat(dob)
    except (ValueError, TypeError):
        return None
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def pretty_date(value: str) -> str:
    try:
        return date.fromisoformat(value).strftime("%d %b %Y")
    except (ValueError, TypeError):
        return value or ""


templates.env.filters["age"] = age_from_dob
templates.env.filters["pretty_date"] = pretty_date


def get_patient(conn: sqlite3.Connection, clinic_id: int, patient_id: int):
    patient = conn.execute(
        "SELECT * FROM patients WHERE id = ? AND clinic_id = ?", (patient_id, clinic_id)
    ).fetchone()
    if patient is None:
        raise NotFound()
    return patient


def validate_patient(full_name: str, date_of_birth: str) -> list[str]:
    errors = []
    if not full_name.strip():
        errors.append("Full name is required.")
    if date_of_birth:
        try:
            if date.fromisoformat(date_of_birth) > date.today():
                errors.append("Date of birth cannot be in the future.")
        except ValueError:
            errors.append("Date of birth must be a valid date.")
    return errors


def validate_appointment(appt_date: str, appt_time: str) -> list[str]:
    errors = []
    try:
        if date.fromisoformat(appt_date) < date.today():
            errors.append("The appointment date cannot be in the past. The appointment was not saved.")
    except ValueError:
        errors.append("Please choose a valid date.")
    try:
        datetime.strptime(appt_time, "%H:%M")
    except ValueError:
        errors.append("Please choose a valid time.")
    return errors


# --------------------------------------------------------------------------
# Auth routes
# --------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return redirect("/patients" if current_clinic(request) else "/login")


@app.get("/signup", response_class=HTMLResponse)
def signup_form(request: Request):
    if current_clinic(request):
        return redirect("/patients")
    return render(request, "signup.html", form={})


@app.post("/signup", response_class=HTMLResponse)
def signup(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    confirm: str = Form(""),
):
    name, email = name.strip(), email.strip().lower()
    errors = []
    if not name:
        errors.append("Clinic name is required.")
    if "@" not in email or "." not in email.split("@")[-1]:
        errors.append("Please enter a valid email address.")
    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if password != confirm:
        errors.append("Passwords do not match.")

    if not errors:
        with db() as conn:
            exists = conn.execute("SELECT 1 FROM clinics WHERE email = ?", (email,)).fetchone()
            if exists:
                errors.append("An account with this email already exists.")
            else:
                cur = conn.execute(
                    "INSERT INTO clinics (name, email, password_hash) VALUES (?, ?, ?)",
                    (name, email, hash_password(password)),
                )
                clinic_id = cur.lastrowid
    if errors:
        return render(
            request, "signup.html", status_code=400, errors=errors, form={"name": name, "email": email}
        )
    return login_response(clinic_id)


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    if current_clinic(request):
        return redirect("/patients")
    return render(request, "login.html", email="")


@app.post("/login", response_class=HTMLResponse)
def login(request: Request, email: str = Form(""), password: str = Form("")):
    email = email.strip().lower()
    with db() as conn:
        clinic = conn.execute(
            "SELECT id, password_hash FROM clinics WHERE email = ?", (email,)
        ).fetchone()
    if clinic is None or not verify_password(password, clinic["password_hash"]):
        return render(
            request, "login.html", status_code=400, error="Wrong email or password.", email=email
        )
    return login_response(clinic["id"])


@app.post("/logout")
def logout(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        with db() as conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    response = redirect("/login")
    response.delete_cookie(SESSION_COOKIE)
    return response


# --------------------------------------------------------------------------
# Patients
# --------------------------------------------------------------------------


@app.get("/patients", response_class=HTMLResponse)
def patient_list(request: Request, q: str = ""):
    clinic = require_clinic(request)
    q = q.strip()
    with db() as conn:
        if q:
            like = f"%{q}%"
            patients = conn.execute(
                """SELECT * FROM patients WHERE clinic_id = ?
                   AND (full_name LIKE ? OR phone LIKE ? OR diagnosis LIKE ?)
                   ORDER BY full_name COLLATE NOCASE""",
                (clinic["id"], like, like, like),
            ).fetchall()
        else:
            patients = conn.execute(
                "SELECT * FROM patients WHERE clinic_id = ? ORDER BY full_name COLLATE NOCASE",
                (clinic["id"],),
            ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM patients WHERE clinic_id = ?", (clinic["id"],)
        ).fetchone()[0]
        upcoming = conn.execute(
            "SELECT COUNT(*) FROM appointments WHERE clinic_id = ? AND date >= ?",
            (clinic["id"], date.today().isoformat()),
        ).fetchone()[0]
    return render(
        request,
        "patients.html",
        clinic=clinic,
        patients=patients,
        q=q,
        total=total,
        upcoming=upcoming,
        active="patients",
    )


@app.get("/patients/new", response_class=HTMLResponse)
def patient_new_form(request: Request):
    clinic = require_clinic(request)
    return render(request, "patient_form.html", clinic=clinic, patient={}, active="patients")


@app.post("/patients/new", response_class=HTMLResponse)
def patient_create(
    request: Request,
    full_name: str = Form(""),
    phone: str = Form(""),
    date_of_birth: str = Form(""),
    diagnosis: str = Form(""),
    notes: str = Form(""),
):
    clinic = require_clinic(request)
    form = dict(
        full_name=full_name.strip(),
        phone=phone.strip(),
        date_of_birth=date_of_birth.strip(),
        diagnosis=diagnosis.strip(),
        notes=notes.strip(),
    )
    errors = validate_patient(form["full_name"], form["date_of_birth"])
    if errors:
        return render(
            request, "patient_form.html", status_code=400, clinic=clinic, patient=form,
            errors=errors, active="patients",
        )
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO patients (clinic_id, full_name, phone, date_of_birth, diagnosis, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (clinic["id"], form["full_name"], form["phone"], form["date_of_birth"],
             form["diagnosis"], form["notes"]),
        )
    return redirect(f"/patients/{cur.lastrowid}")


@app.get("/patients/export.csv")
def patient_export(request: Request):
    clinic = require_clinic(request)
    with db() as conn:
        patients = conn.execute(
            "SELECT * FROM patients WHERE clinic_id = ? ORDER BY full_name COLLATE NOCASE",
            (clinic["id"],),
        ).fetchall()

    def safe(value: str) -> str:
        # Stop spreadsheet apps from treating a cell as a formula.
        value = value or ""
        if value[:1] in ("+", "-") and all(c.isdigit() or c in " +-()." for c in value):
            return value  # plain phone number or number, leave as is
        return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["ID", "Full name", "Phone", "Date of birth", "Diagnosis", "Notes", "Created"])
    for p in patients:
        writer.writerow([
            p["id"], safe(p["full_name"]), safe(p["phone"]), p["date_of_birth"],
            safe(p["diagnosis"]), safe(p["notes"]), p["created_at"],
        ])
    filename = f"patients-{date.today().isoformat()}.csv"
    return Response(
        content="﻿" + buffer.getvalue(),  # BOM so Excel opens UTF-8 correctly
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/patients/{patient_id}", response_class=HTMLResponse)
def patient_detail(request: Request, patient_id: int):
    clinic = require_clinic(request)
    with db() as conn:
        patient = get_patient(conn, clinic["id"], patient_id)
        appointments = conn.execute(
            """SELECT * FROM appointments WHERE patient_id = ? AND clinic_id = ?
               ORDER BY date DESC, time DESC""",
            (patient_id, clinic["id"]),
        ).fetchall()
    return render(
        request, "patient_detail.html", clinic=clinic, patient=patient,
        appointments=appointments, today=date.today().isoformat(), active="patients",
    )


@app.get("/patients/{patient_id}/edit", response_class=HTMLResponse)
def patient_edit_form(request: Request, patient_id: int):
    clinic = require_clinic(request)
    with db() as conn:
        patient = get_patient(conn, clinic["id"], patient_id)
    return render(request, "patient_form.html", clinic=clinic, patient=dict(patient), active="patients")


@app.post("/patients/{patient_id}/edit", response_class=HTMLResponse)
def patient_update(
    request: Request,
    patient_id: int,
    full_name: str = Form(""),
    phone: str = Form(""),
    date_of_birth: str = Form(""),
    diagnosis: str = Form(""),
    notes: str = Form(""),
):
    clinic = require_clinic(request)
    form = dict(
        id=patient_id,
        full_name=full_name.strip(),
        phone=phone.strip(),
        date_of_birth=date_of_birth.strip(),
        diagnosis=diagnosis.strip(),
        notes=notes.strip(),
    )
    with db() as conn:
        get_patient(conn, clinic["id"], patient_id)
        errors = validate_patient(form["full_name"], form["date_of_birth"])
        if errors:
            return render(
                request, "patient_form.html", status_code=400, clinic=clinic, patient=form,
                errors=errors, active="patients",
            )
        conn.execute(
            """UPDATE patients SET full_name = ?, phone = ?, date_of_birth = ?, diagnosis = ?,
               notes = ?, updated_at = datetime('now') WHERE id = ? AND clinic_id = ?""",
            (form["full_name"], form["phone"], form["date_of_birth"], form["diagnosis"],
             form["notes"], patient_id, clinic["id"]),
        )
    return redirect(f"/patients/{patient_id}")


@app.post("/patients/{patient_id}/delete")
def patient_delete(request: Request, patient_id: int):
    clinic = require_clinic(request)
    with db() as conn:
        get_patient(conn, clinic["id"], patient_id)
        conn.execute(
            "DELETE FROM patients WHERE id = ? AND clinic_id = ?", (patient_id, clinic["id"])
        )
    return redirect("/patients")


@app.get("/patients/{patient_id}/print", response_class=HTMLResponse)
def patient_print(request: Request, patient_id: int):
    clinic = require_clinic(request)
    with db() as conn:
        patient = get_patient(conn, clinic["id"], patient_id)
        appointments = conn.execute(
            """SELECT * FROM appointments WHERE patient_id = ? AND clinic_id = ?
               ORDER BY date DESC, time DESC""",
            (patient_id, clinic["id"]),
        ).fetchall()
    return render(
        request, "patient_print.html", clinic=clinic, patient=patient,
        appointments=appointments, printed_on=datetime.now().strftime("%d %b %Y, %H:%M"),
    )


# --------------------------------------------------------------------------
# Appointments
# --------------------------------------------------------------------------


@app.get("/appointments", response_class=HTMLResponse)
def appointment_list(request: Request):
    clinic = require_clinic(request)
    today = date.today().isoformat()
    with db() as conn:
        rows = conn.execute(
            """SELECT a.*, p.full_name AS patient_name FROM appointments a
               JOIN patients p ON p.id = a.patient_id AND p.clinic_id = a.clinic_id
               WHERE a.clinic_id = ? ORDER BY a.date, a.time""",
            (clinic["id"],),
        ).fetchall()
    upcoming = [r for r in rows if r["date"] >= today]
    past = list(reversed([r for r in rows if r["date"] < today]))
    return render(
        request, "appointments.html", clinic=clinic, upcoming=upcoming, past=past,
        today=today, active="appointments",
    )


def _appointment_form_context(conn, clinic, form, errors=None):
    patients = conn.execute(
        "SELECT id, full_name FROM patients WHERE clinic_id = ? ORDER BY full_name COLLATE NOCASE",
        (clinic["id"],),
    ).fetchall()
    return dict(clinic=clinic, patients=patients, form=form, errors=errors or [],
                active="appointments")


@app.get("/appointments/new", response_class=HTMLResponse)
def appointment_new_form(request: Request, patient_id: int | None = None):
    clinic = require_clinic(request)
    form = {"patient_id": patient_id, "date": date.today().isoformat(), "time": "09:00", "reason": ""}
    with db() as conn:
        ctx = _appointment_form_context(conn, clinic, form)
    return render(request, "appointment_form.html", **ctx)


@app.post("/appointments/new", response_class=HTMLResponse)
def appointment_create(
    request: Request,
    patient_id: str = Form(""),
    appt_date: str = Form(""),
    appt_time: str = Form(""),
    reason: str = Form(""),
):
    clinic = require_clinic(request)
    form = {"patient_id": patient_id, "date": appt_date.strip(), "time": appt_time.strip()[:5],
            "reason": reason.strip()}
    errors = validate_appointment(form["date"], form["time"])
    with db() as conn:
        patient = None
        if patient_id.isdigit():
            patient = conn.execute(
                "SELECT id FROM patients WHERE id = ? AND clinic_id = ?",
                (int(patient_id), clinic["id"]),
            ).fetchone()
        if patient is None:
            errors.insert(0, "Please choose a patient.")
        else:
            form["patient_id"] = patient["id"]
        if not errors and conn.execute(
            "SELECT 1 FROM appointments WHERE clinic_id = ? AND date = ? AND time = ?",
            (clinic["id"], form["date"], form["time"]),
        ).fetchone():
            errors.append(
                f"The {form['time']} slot on {form['date']} is already taken. "
                "Please choose another time. The appointment was not saved."
            )
        if errors:
            ctx = _appointment_form_context(conn, clinic, form, errors)
            return render(request, "appointment_form.html", status_code=400, **ctx)
        conn.execute(
            """INSERT INTO appointments (clinic_id, patient_id, date, time, reason)
               VALUES (?, ?, ?, ?, ?)""",
            (clinic["id"], patient["id"], form["date"], form["time"], form["reason"]),
        )
    return redirect(f"/patients/{patient['id']}")


@app.post("/appointments/{appointment_id}/delete")
def appointment_delete(request: Request, appointment_id: int, next: str = Form("/appointments")):
    clinic = require_clinic(request)
    with db() as conn:
        cur = conn.execute(
            "DELETE FROM appointments WHERE id = ? AND clinic_id = ?", (appointment_id, clinic["id"])
        )
        if cur.rowcount == 0:
            raise NotFound()
    # Only allow redirecting back inside this app.
    if not next.startswith("/") or next.startswith(("//", "/\\")):
        next = "/appointments"
    return redirect(next)

"""Create two demo clinics with some patients and appointments.

Run with:  python seed.py

Safe to run more than once: each demo clinic is deleted and recreated
(along with its patients and appointments). Other clinics are not touched.
"""

from datetime import date, timedelta

from app import db, hash_password, init_db

today = date.today()


def day(offset: int) -> str:
    return (today + timedelta(days=offset)).isoformat()


CLINICS = [
    {
        "name": "Sunrise Clinic",
        "email": "sunrise@example.com",
        "password": "sunrise123",
        "patients": [
            {
                "full_name": "Maria Santos",
                "phone": "+1 555 0101",
                "date_of_birth": "1984-03-12",
                "diagnosis": "Type 2 diabetes",
                "notes": "On metformin 500 mg twice daily.\nCheck HbA1c every 3 months.",
                "appointments": [(day(-30), "09:00", "Blood test"), (day(3), "10:30", "Diabetes follow-up")],
            },
            {
                "full_name": "James Carter",
                "phone": "+1 555 0102",
                "date_of_birth": "1957-11-02",
                "diagnosis": "Hypertension",
                "notes": "BP 150/95 at last visit. Started amlodipine 5 mg.",
                "appointments": [(day(1), "14:00", "Blood pressure check")],
            },
            {
                "full_name": "Aisha Rahman",
                "phone": "+1 555 0103",
                "date_of_birth": "1996-07-21",
                "diagnosis": "Asthma",
                "notes": "Uses salbutamol inhaler as needed. Allergic to penicillin.",
                "appointments": [(day(7), "11:15", "Inhaler review")],
            },
            {
                "full_name": "Tom Becker",
                "phone": "+1 555 0104",
                "date_of_birth": "2015-01-30",
                "diagnosis": "Seasonal allergies",
                "notes": "Parent: Anna Becker. Cetirizine in spring.",
                "appointments": [],
            },
        ],
    },
    {
        "name": "Harbor Clinic",
        "email": "harbor@example.com",
        "password": "harbor123",
        "patients": [
            {
                "full_name": "Liam O'Connor",
                "phone": "+1 555 0201",
                "date_of_birth": "1979-05-08",
                "diagnosis": "Lower back pain",
                "notes": "Desk worker. Referred to physiotherapy.",
                "appointments": [(day(2), "08:30", "Physio referral review")],
            },
            {
                "full_name": "Sofia Rossi",
                "phone": "+1 555 0202",
                "date_of_birth": "1990-09-17",
                "diagnosis": "Pregnancy, 24 weeks",
                "notes": "First pregnancy. Glucose tolerance test due.",
                "appointments": [(day(-14), "10:00", "Routine check"), (day(5), "09:45", "Glucose tolerance test")],
            },
            {
                "full_name": "Kenji Watanabe",
                "phone": "+1 555 0203",
                "date_of_birth": "1948-12-25",
                "diagnosis": "Atrial fibrillation",
                "notes": "On warfarin. INR target 2.0–3.0.",
                "appointments": [(day(0), "15:30", "INR check")],
            },
        ],
    },
]


def seed() -> None:
    init_db()
    with db() as conn:
        for clinic in CLINICS:
            conn.execute("DELETE FROM clinics WHERE email = ?", (clinic["email"],))
            clinic_id = conn.execute(
                "INSERT INTO clinics (name, email, password_hash) VALUES (?, ?, ?)",
                (clinic["name"], clinic["email"], hash_password(clinic["password"])),
            ).lastrowid
            for p in clinic["patients"]:
                patient_id = conn.execute(
                    """INSERT INTO patients (clinic_id, full_name, phone, date_of_birth, diagnosis, notes)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (clinic_id, p["full_name"], p["phone"], p["date_of_birth"], p["diagnosis"], p["notes"]),
                ).lastrowid
                for appt_date, appt_time, reason in p["appointments"]:
                    conn.execute(
                        """INSERT INTO appointments (clinic_id, patient_id, date, time, reason)
                           VALUES (?, ?, ?, ?, ?)""",
                        (clinic_id, patient_id, appt_date, appt_time, reason),
                    )
            print(f"Seeded {clinic['name']}: {clinic['email']} / {clinic['password']} "
                  f"({len(clinic['patients'])} patients)")


if __name__ == "__main__":
    seed()

import hashlib
from db.database import get_connection


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def create_doctor(username: str, password: str, full_name: str, job: str):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO doctors (username, password, full_name, job) VALUES (?,?,?,?)",
            (username, _hash(password), full_name, job)
        )
        conn.commit()
        return True, "Account created successfully."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def authenticate(username: str, password: str):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM doctors WHERE username=? AND password=?",
        (username, _hash(password))
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_doctor_by_id(doctor_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM doctors WHERE id=?", (doctor_id,)).fetchone()
    conn.close()
    return dict(row) if row else None
import os
from db.database import get_connection

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "patients")


def _patient_folder(patient_id: int, last_name: str, first_name: str) -> str:
    name = f"P{patient_id:04d}_{last_name}_{first_name}"
    path = os.path.join(DATA_DIR, name)
    os.makedirs(os.path.join(path, "images"), exist_ok=True)
    return path


def create_patient(first_name, last_name, age, sexe, tissue, marqueur, doctor_id):
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO patients (first_name, last_name, age, sexe, tissue, marqueur, doctor_id, folder_path)
               VALUES (?,?,?,?,?,?,?, '')""",
            (first_name, last_name, age, sexe, tissue, marqueur, doctor_id)
        )
        patient_id = cur.lastrowid
        folder = _patient_folder(patient_id, last_name, first_name)
        conn.execute("UPDATE patients SET folder_path=? WHERE id=?", (folder, patient_id))
        conn.commit()
        return patient_id
    finally:
        conn.close()


def get_all_patients(doctor_id: int = None):
    conn = get_connection()
    if doctor_id:
        rows = conn.execute(
            "SELECT * FROM patients WHERE doctor_id=? ORDER BY last_name, first_name", (doctor_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM patients ORDER BY last_name, first_name"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_patient_by_id(patient_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM patients WHERE id=?", (patient_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def search_patients(query: str, doctor_id: int = None):
    conn = get_connection()
    q = f"%{query}%"
    if doctor_id:
        rows = conn.execute(
            """SELECT * FROM patients WHERE doctor_id=? AND
               (first_name LIKE ? OR last_name LIKE ? OR tissue LIKE ? OR marqueur LIKE ?)
               ORDER BY last_name""",
            (doctor_id, q, q, q, q)
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM patients WHERE
               first_name LIKE ? OR last_name LIKE ? OR tissue LIKE ? OR marqueur LIKE ?
               ORDER BY last_name""",
            (q, q, q, q)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_analysis(patient_id, doctor_id, image_path, analysis_type,
                 result_label=None, result_prob=None, dab_coverage=None,
                 dab_regions=None, mean_intensity=None, notes=None):
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO analyses
               (patient_id, doctor_id, image_path, analysis_type,
                result_label, result_prob, dab_coverage, dab_regions, mean_intensity, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (patient_id, doctor_id, image_path, analysis_type,
             result_label, result_prob, dab_coverage, dab_regions, mean_intensity, notes)
        )
        conn.commit()
    finally:
        conn.close()


def get_analyses_for_patient(patient_id: int):
    conn = get_connection()
    rows = conn.execute(
        """SELECT a.*, d.full_name as doctor_name
           FROM analyses a JOIN doctors d ON a.doctor_id = d.id
           WHERE a.patient_id=? ORDER BY a.created_at DESC""",
        (patient_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_analyses(doctor_id: int = None):
    conn = get_connection()
    if doctor_id:
        rows = conn.execute(
            """SELECT a.*, p.first_name, p.last_name, d.full_name as doctor_name
               FROM analyses a
               JOIN patients p ON a.patient_id = p.id
               JOIN doctors d ON a.doctor_id = d.id
               WHERE a.doctor_id=? ORDER BY a.created_at DESC""",
            (doctor_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT a.*, p.first_name, p.last_name, d.full_name as doctor_name
               FROM analyses a
               JOIN patients p ON a.patient_id = p.id
               JOIN doctors d ON a.doctor_id = d.id
               ORDER BY a.created_at DESC"""
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "pathovision.db")


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS doctors (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT    NOT NULL UNIQUE,
            password    TEXT    NOT NULL,
            full_name   TEXT    NOT NULL,
            job         TEXT    NOT NULL,
            created_at  TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS patients (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name  TEXT    NOT NULL,
            last_name   TEXT    NOT NULL,
            age         INTEGER,
            sexe        TEXT    CHECK(sexe IN ('Male','Female')),
            tissue      TEXT,
            marqueur    TEXT,
            folder_path TEXT,
            created_at  TEXT    DEFAULT (datetime('now')),
            doctor_id   INTEGER NOT NULL REFERENCES doctors(id)
        );

        CREATE TABLE IF NOT EXISTS analyses (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id      INTEGER NOT NULL REFERENCES patients(id),
            doctor_id       INTEGER NOT NULL REFERENCES doctors(id),
            image_path      TEXT    NOT NULL,
            analysis_type   TEXT    NOT NULL CHECK(analysis_type IN ('Histology','IHC')),
            result_label    TEXT,
            result_prob     REAL,
            dab_coverage    REAL,
            dab_regions     INTEGER,
            mean_intensity  REAL,
            notes           TEXT,
            created_at      TEXT    DEFAULT (datetime('now'))
        );
    """)

    conn.commit()
    conn.close()
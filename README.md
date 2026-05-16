# 🔬 ColxPath

**AI-Powered Cancer Detection Platform for Pathology Professionals**

ColxPath is a desktop application built with PySide6 that assists pathologists and oncologists in analyzing histology and IHC (immunohistochemistry) tissue images using AI and computer vision.

---

## Features

- **Authentication** — Secure doctor login and signup with hashed passwords
- **Histology Analysis** — AI-based cancer detection (Pathologique / Non Pathologique) on H&E stained images
- **IHC / DAB Analysis** — Automated DAB stain extraction and quantification with visual overlays
- **Patient Management** — Add patients, link analyses to their records, track follow-ups
- **History** — Browse all past analyses across all patients, filterable by doctor
- **PDF Reports** — Export a full patient report with analysis history and results

---

## Project Structure

```
ColxPath/
├── main.py                        # App entry point
├── core/
│   ├── dab_extractor.py           # DAB/brown stain CV analysis
│   ├── predictor.py               # Keras model inference
│   └── pdf_generator.py           # PDF report generation
├── db/
│   ├── database.py                # SQLite schema and connection
│   ├── doctor_dao.py              # Doctor CRUD (auth)
│   └── patient_dao.py             # Patient and analysis CRUD
├── ui/
│   ├── auth/
│   │   ├── login_window.py
│   │   └── signup_window.py
│   ├── patients/
│   │   ├── patient_selector.py
│   │   ├── patient_form.py
│   │   └── patient_history.py
│   ├── analysis/
│   │   ├── histology_window.py
│   │   └── ihc_window.py
│   ├── history/
│   │   └── history_window.py
│   └── home_page.py
├── models/                        # Place your model.h5 here
├── assets/                        # Stylesheets and icons
└── data/                          # Auto-generated at runtime
    ├── pathovision.db
    └── patients/                  # One folder per patient
```

---

## Installation

**Requirements:** Python 3.9+

```bash
pip install PySide6 opencv-python numpy tensorflow reportlab
```

---

## Setup

1. Clone the repository:
```bash
git clone https://github.com/samado-laouar/PathoVision.git
cd ColxPath
```

2. Add your trained Keras model:
```
models/colon_cancer_cnn_final.h5
```

3. Run the app:
```bash
python main.py
```

---

## Usage

1. **Sign up** as a doctor (full name, username, password, specialty)
2. **Log in** to access the dashboard
3. From the **Home** screen, choose an analysis type or open History
4. **Load an image**, then **select or create a patient**
5. Run the analysis and **save the result** to the patient's record
6. Open any patient's history to view past analyses or **export a PDF report**

---

## Tech Stack

| Component | Technology |
|---|---|
| UI Framework | PySide6 (Qt6) |
| AI Model | TensorFlow / Keras |
| Image Processing | OpenCV, NumPy |
| Database | SQLite |
| PDF Generation | ReportLab |
| Language | Python 3.9+ |

---

## Notes

- The `data/` folder and `models/` folder are excluded from version control
- Patient images are automatically copied to `data/patients/<PatientFolder>/images/`
- PDF reports are saved to the patient's folder as `report.pdf`

---

*Built as part of a final year project (PFE) — AI-assisted pathology analysis.*

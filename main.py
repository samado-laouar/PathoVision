import sys
import os

if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

if sys.stdout is not None and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, OSError):
        pass

from PySide6.QtWidgets import QApplication, QStackedWidget, QMessageBox
from PySide6.QtCore import Qt

from db.database import init_db
from ui.auth.login_window import LoginWindow
from ui.auth.signup_window import SignupWindow
from ui.home_page import HomePage
from ui.analysis.histology_window import HistologyWindow
from ui.analysis.ihc_window import IHCWindow
from ui.history.history_window import HistoryWindow
from ui.patients.patient_history import PatientHistory
from core.pdf_generator import generate_patient_report


class AppWindow(QStackedWidget):
    # Page indices
    PAGE_LOGIN    = 0
    PAGE_SIGNUP   = 1
    PAGE_HOME     = 2
    PAGE_HISTO    = 3
    PAGE_IHC      = 4
    PAGE_HISTORY  = 5
    PAGE_PATIENT  = 6

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PathoVision — AI Cancer Detection")
        self.doctor = None

        # Auth pages (no doctor context yet)
        self.login_page  = LoginWindow()
        self.signup_page = SignupWindow()

        self.addWidget(self.login_page)   # 0
        self.addWidget(self.signup_page)  # 1

        # Placeholders — replaced after login
        self._home     = None
        self._histo    = None
        self._ihc      = None
        self._history  = None
        self._patient_hist = None

        # Auth wiring
        self.login_page.login_successful.connect(self._on_login)
        self.login_page.go_signup.connect(lambda: self.setCurrentIndex(self.PAGE_SIGNUP))
        self.signup_page.go_login.connect(lambda: self.setCurrentIndex(self.PAGE_LOGIN))

        self.showMaximized()

    # ── called once after successful login ────────────────────────
    def _on_login(self, doctor: dict):
        self.doctor = doctor
        self._build_main_pages()
        self.setCurrentIndex(self.PAGE_HOME)

    def _build_main_pages(self):
        # Remove old main pages if re-logging in
        while self.count() > 2:
            w = self.widget(2)
            self.removeWidget(w)
            w.deleteLater()

        d = self.doctor

        self._home = HomePage(d)
        self._histo = HistologyWindow(d)
        self._ihc   = IHCWindow(d)
        self._history = HistoryWindow(d)
        self._patient_hist = PatientHistory()

        for w in [self._home, self._histo, self._ihc, self._history, self._patient_hist]:
            self.addWidget(w)

        # Navigation wiring
        self._home.go_histology.connect(lambda: self.setCurrentIndex(self.PAGE_HISTO))
        self._home.go_ihc.connect(lambda: self.setCurrentIndex(self.PAGE_IHC))
        self._home.go_history.connect(self._open_history)
        self._home.logout.connect(self._logout)

        self._histo.go_home.connect(lambda: self.setCurrentIndex(self.PAGE_HOME))
        self._ihc.go_home.connect(lambda: self.setCurrentIndex(self.PAGE_HOME))

        self._history.patient_clicked.connect(self._open_patient_history)

        self._patient_hist.back_requested.connect(lambda: self.setCurrentIndex(self.PAGE_HISTORY))
        self._patient_hist.generate_pdf_requested.connect(self._generate_pdf)

    def _open_history(self):
        self._history.refresh()
        self.setCurrentIndex(self.PAGE_HISTORY)

    def _open_patient_history(self, patient_id: int):
        from db.patient_dao import get_patient_by_id
        patient = get_patient_by_id(patient_id)
        if patient:
            self._patient_hist.load_patient(patient)
            self.setCurrentIndex(self.PAGE_PATIENT)

    def _generate_pdf(self, patient: dict, analyses: list):
        try:
            path = generate_patient_report(patient, analyses)
            QMessageBox.information(self, "PDF Exported", f"Report saved to:\n{path}")
        except ImportError:
            QMessageBox.warning(
                self, "Missing Dependency",
                "reportlab is required for PDF export.\n\nRun: pip install reportlab"
            )
        except Exception as e:
            QMessageBox.critical(self, "PDF Error", str(e))

    def _logout(self):
        self.doctor = None
        self.setCurrentIndex(self.PAGE_LOGIN)


if __name__ == "__main__":
    init_db()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = AppWindow()
    window.show()
    sys.exit(app.exec())
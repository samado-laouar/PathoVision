from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QMessageBox, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal

from db.patient_dao import get_all_patients, search_patients
from ui.patients.patient_form import PatientForm
from ui._style import DIALOG_QSS, C


class PatientSelector(QDialog):
    patient_selected = Signal(dict)

    def __init__(self, doctor: dict, parent=None):
        super().__init__(parent)
        self.doctor = doctor
        self.setWindowTitle("Select Patient")
        self.setMinimumSize(780, 540)
        self._build_ui()
        self.setStyleSheet(DIALOG_QSS + _PS_EXTRA)
        self._load_patients()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        # Header
        header = QHBoxLayout()
        title = QLabel("Select a Patient")
        title.setObjectName("dialogTitle")
        new_btn = QPushButton("New Patient")
        new_btn.setObjectName("primaryBtn")
        new_btn.setFixedHeight(38)
        new_btn.setCursor(Qt.PointingHandCursor)
        new_btn.clicked.connect(self._open_new_patient)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(new_btn)
        layout.addLayout(header)

        # Search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by name, tissue or marker...")
        self.search_input.setObjectName("searchInput")
        self.search_input.setFixedHeight(40)
        self.search_input.textChanged.connect(self._on_search)
        layout.addWidget(self.search_input)

        # Table
        self.table = QTableWidget()
        self.table.setObjectName("patientTable")
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Last Name", "First Name", "Age", "Sex", "Tissue", "Marker"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.doubleClicked.connect(self._confirm_selection)
        layout.addWidget(self.table)

        # Bottom buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.setFixedHeight(38)
        cancel_btn.clicked.connect(self.reject)
        select_btn = QPushButton("Select Patient")
        select_btn.setObjectName("primaryBtn")
        select_btn.setFixedHeight(38)
        select_btn.clicked.connect(self._confirm_selection)
        btn_row.addWidget(cancel_btn)
        btn_row.addSpacing(8)
        btn_row.addWidget(select_btn)
        layout.addLayout(btn_row)

    def _load_patients(self, query=""):
        if query:
            patients = search_patients(query, self.doctor["id"])
        else:
            patients = get_all_patients(self.doctor["id"])
        self._populate_table(patients)

    def _populate_table(self, patients):
        self.table.setRowCount(0)
        self._patients = patients
        for row, p in enumerate(patients):
            self.table.insertRow(row)
            for col, val in enumerate([
                p["id"], p["last_name"], p["first_name"],
                p["age"], p["sexe"], p["tissue"], p["marqueur"]
            ]):
                item = QTableWidgetItem(str(val) if val is not None else "")
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, col, item)

    def _on_search(self, text):
        self._load_patients(text.strip())

    def _confirm_selection(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "No Selection", "Please select a patient first.")
            return
        self.patient_selected.emit(self._patients[row])
        self.accept()

    def _open_new_patient(self):
        form = PatientForm(self.doctor, parent=self)
        if form.exec():
            self._load_patients()


# ── Extra styles ───────────────────────────────────────────────────────────────
_PS_EXTRA = f"""
    QDialog {{ background: {C['surface']}; }}
"""
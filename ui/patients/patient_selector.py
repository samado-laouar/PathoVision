from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QMessageBox, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from db.patient_dao import get_all_patients, search_patients
from ui.patients.patient_form import PatientForm


class PatientSelector(QDialog):
    """Modal dialog — pick an existing patient or create a new one."""
    patient_selected = Signal(dict)

    def __init__(self, doctor: dict, parent=None):
        super().__init__(parent)
        self.doctor = doctor
        self.setWindowTitle("Select Patient")
        self.setMinimumSize(760, 520)
        self._build_ui()
        self._apply_styles()
        self._load_patients()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        title = QLabel("Select a Patient")
        title.setObjectName("dialogTitle")
        new_btn = QPushButton("＋  New Patient")
        new_btn.setObjectName("primaryBtn")
        new_btn.setFixedHeight(38)
        new_btn.setCursor(Qt.PointingHandCursor)
        new_btn.clicked.connect(self._open_new_patient)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(new_btn)
        layout.addLayout(header)

        # Search bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍  Search by name, tissue or marker...")
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
        patient = self._patients[row]
        self.patient_selected.emit(patient)
        self.accept()

    def _open_new_patient(self):
        form = PatientForm(self.doctor, parent=self)
        if form.exec():
            self._load_patients()

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog { background: #F8FAFB; font-family: 'Segoe UI'; }
            #dialogTitle { font-size: 20px; font-weight: 700; color: #1A2B45; }

            #searchInput {
                border: 1.5px solid #D5D8DC; border-radius: 8px;
                padding: 0 14px; font-size: 14px; background: #FFF;
            }
            #searchInput:focus { border-color: #2E86C1; }

            #patientTable {
                border: 1px solid #E5E7EB; border-radius: 8px;
                gridline-color: #F0F0F0; font-size: 13px;
            }
            QHeaderView::section {
                background: #EBF5FB; color: #1A5276;
                font-weight: 600; font-size: 13px;
                padding: 8px; border: none;
                border-bottom: 2px solid #AED6F1;
            }
            QTableWidget::item:selected { background: #D6EAF8; color: #1A2B45; }
            QTableWidget { alternate-background-color: #F7FBFE; }

            #primaryBtn {
                background: #2E86C1; color: white; border: none;
                border-radius: 7px; font-size: 13px; font-weight: 600; padding: 0 18px;
            }
            #primaryBtn:hover { background: #1A5276; }
            #secondaryBtn {
                background: #ECF0F1; color: #2C3E50; border: 1px solid #D5D8DC;
                border-radius: 7px; font-size: 13px; padding: 0 18px;
            }
            #secondaryBtn:hover { background: #D5D8DC; }
        """)
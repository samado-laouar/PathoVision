from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSpacerItem, QSizePolicy, QMessageBox, QFrame
)
from PySide6.QtCore import Qt

from db.patient_dao import create_patient
from ui._style import DIALOG_QSS, C


TISSUES   = ["Colon", "Rectum", "Stomach", "Liver", "Lung", "Breast", "Prostate", "Other"]
MARQUEURS = ["CDX2", "CK20", "MLH1", "MSH2", "MSH6", "PMS2", "Ki-67", "p53", "Other"]


class PatientForm(QDialog):
    def __init__(self, doctor: dict, parent=None):
        super().__init__(parent)
        self.doctor = doctor
        self.setWindowTitle("New Patient")
        self.setMinimumWidth(520)
        self._build_ui()
        self.setStyleSheet(DIALOG_QSS)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(0)

        title = QLabel("Add New Patient")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("separator")
        layout.addWidget(sep)
        layout.addSpacerItem(QSpacerItem(0, 18, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # Row: First + Last name
        row1 = QHBoxLayout()
        row1.setSpacing(16)
        fn = QVBoxLayout()
        fn.setSpacing(5)
        fn.addWidget(self._lbl("First Name *"))
        self.fn_input = self._edit("First name")
        fn.addWidget(self.fn_input)
        ln = QVBoxLayout()
        ln.setSpacing(5)
        ln.addWidget(self._lbl("Last Name *"))
        self.ln_input = self._edit("Last name")
        ln.addWidget(self.ln_input)
        row1.addLayout(fn)
        row1.addLayout(ln)
        layout.addLayout(row1)
        layout.addSpacerItem(QSpacerItem(0, 14, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # Row: Age + Sex
        row2 = QHBoxLayout()
        row2.setSpacing(16)
        age_col = QVBoxLayout()
        age_col.setSpacing(5)
        age_col.addWidget(self._lbl("Age"))
        self.age_input = self._edit("e.g. 54")
        age_col.addWidget(self.age_input)
        sex_col = QVBoxLayout()
        sex_col.setSpacing(5)
        sex_col.addWidget(self._lbl("Sex"))
        self.sex_combo = self._combo(["Male", "Female"])
        sex_col.addWidget(self.sex_combo)
        row2.addLayout(age_col)
        row2.addLayout(sex_col)
        layout.addLayout(row2)
        layout.addSpacerItem(QSpacerItem(0, 14, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # Row: Tissue + Marker
        row3 = QHBoxLayout()
        row3.setSpacing(16)
        tis_col = QVBoxLayout()
        tis_col.setSpacing(5)
        tis_col.addWidget(self._lbl("Tissue *"))
        self.tissue_combo = self._combo(TISSUES)
        tis_col.addWidget(self.tissue_combo)
        mar_col = QVBoxLayout()
        mar_col.setSpacing(5)
        mar_col.addWidget(self._lbl("Marker *"))
        self.marqueur_combo = self._combo(MARQUEURS)
        mar_col.addWidget(self.marqueur_combo)
        row3.addLayout(tis_col)
        row3.addLayout(mar_col)
        layout.addLayout(row3)
        layout.addSpacerItem(QSpacerItem(0, 28, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("secondaryBtn")
        cancel.setFixedHeight(40)
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save Patient")
        save.setObjectName("primaryBtn")
        save.setFixedHeight(40)
        save.clicked.connect(self._handle_save)
        btn_row.addWidget(cancel)
        btn_row.addSpacing(8)
        btn_row.addWidget(save)
        layout.addLayout(btn_row)

    def _lbl(self, text):
        l = QLabel(text)
        l.setObjectName("fieldLabel")
        return l

    def _edit(self, placeholder):
        e = QLineEdit()
        e.setPlaceholderText(placeholder)
        e.setFixedHeight(42)
        e.setObjectName("formInput")
        return e

    def _combo(self, items):
        c = QComboBox()
        c.setObjectName("formInput")
        c.setFixedHeight(42)
        c.addItems(items)
        return c

    def _handle_save(self):
        fn = self.fn_input.text().strip()
        ln = self.ln_input.text().strip()
        if not fn or not ln:
            QMessageBox.warning(self, "Required", "First and last name are required.")
            return
        age_text = self.age_input.text().strip()
        age      = int(age_text) if age_text.isdigit() else None
        sexe     = self.sex_combo.currentText()
        tissue   = self.tissue_combo.currentText()
        marqueur = self.marqueur_combo.currentText()
        create_patient(fn, ln, age, sexe, tissue, marqueur, self.doctor["id"])
        QMessageBox.information(self, "Saved", f"Patient {fn} {ln} added successfully.")
        self.accept()
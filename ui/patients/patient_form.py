import re
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSpacerItem, QSizePolicy, QMessageBox, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette

from ui._style import BASE_QSS, DIALOG_QSS
from db.patient_dao import create_patient


TISSUES   = ["Colon", "Rectum", "Stomach", "Liver", "Lung", "Breast", "Prostate", "Other"]
MARQUEURS = ["CDX2", "CK20", "MLH1", "MSH2", "MSH6", "PMS2", "Ki-67", "p53", "Other"]


# ── Validation rules ──────────────────────────────────────────────────────────
_NAME_RE = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ'\- ]{2,60}$")


def _validate_name(v: str, label: str = "Name") -> str:
    v = v.strip()
    if not v:
        return f"{label} is required."
    if not _NAME_RE.match(v):
        return f"{label}: letters, spaces, hyphens only (2–60 chars)."
    return ""


def _validate_age(v: str) -> str:
    v = v.strip()
    if not v:
        return ""  # optional
    if not v.isdigit():
        return "Age must be a number."
    age = int(v)
    if not (0 <= age <= 120):
        return "Age must be between 0 and 120."
    return ""


# ── Reusable Validated Field ─────────────────────────────────────────────────
class _ValidatedField(QFrame):
    def __init__(self, placeholder: str, parent=None):
        super().__init__(parent)
        self.setObjectName("fieldWrapper")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.setFixedHeight(44)
        self.edit.setObjectName("formInput")
        self.edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.error_lbl = QLabel("")
        self.error_lbl.setObjectName("errorLabel")
        self.error_lbl.setFixedHeight(16)
        self.error_lbl.setVisible(False)

        # Red error text
        palette = self.error_lbl.palette()
        palette.setColor(QPalette.WindowText, QColor("#e74c3c"))
        self.error_lbl.setPalette(palette)

        lay.addWidget(self.edit)
        lay.addWidget(self.error_lbl)

        self.edit.textChanged.connect(self.clear_error)

    def text(self) -> str:
        return self.edit.text().strip()

    def set_error(self, msg: str):
        if msg:
            self.edit.setProperty("invalid", True)
            self.error_lbl.setText(msg)
            self.error_lbl.setVisible(True)
        else:
            self.clear_error()

        self.edit.style().unpolish(self.edit)
        self.edit.style().polish(self.edit)

    def clear_error(self):
        self.edit.setProperty("invalid", False)
        self.error_lbl.setText("")
        self.error_lbl.setVisible(False)
        self.edit.style().unpolish(self.edit)
        self.edit.style().polish(self.edit)


# ── Combo Field Wrapper ─────────────────────────────────────────────────────
class _ComboField(QFrame):
    def __init__(self, placeholder: str, items: list, parent=None):
        super().__init__(parent)
        self.setObjectName("fieldWrapper")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self.combo = QComboBox()
        self.combo.setObjectName("formInput")
        self.combo.setFixedHeight(44)
        self.combo.addItems(items)
        self.combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.error_lbl = QLabel("")
        self.error_lbl.setObjectName("errorLabel")
        self.error_lbl.setFixedHeight(16)
        self.error_lbl.setVisible(False)

        # Red error text
        palette = self.error_lbl.palette()
        palette.setColor(QPalette.WindowText, QColor("#e74c3c"))
        self.error_lbl.setPalette(palette)

        lay.addWidget(self.combo)
        lay.addWidget(self.error_lbl)

    def currentText(self) -> str:
        return self.combo.currentText()

    def set_error(self, msg: str):
        if msg:
            self.combo.setProperty("invalid", True)
            self.error_lbl.setText(msg)
            self.error_lbl.setVisible(True)
        else:
            self.clear_error()

        self.combo.style().unpolish(self.combo)
        self.combo.style().polish(self.combo)

    def clear_error(self):
        self.combo.setProperty("invalid", False)
        self.error_lbl.setText("")
        self.error_lbl.setVisible(False)
        self.combo.style().unpolish(self.combo)
        self.combo.style().polish(self.combo)


# ── Patient Form ─────────────────────────────────────────────────────────────
class PatientForm(QDialog):
    def __init__(self, doctor: dict, parent=None):
        super().__init__(parent)
        self.doctor = doctor
        self.setWindowTitle("New Patient")
        self.setMinimumWidth(560)

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
        layout.addSpacerItem(QSpacerItem(0, 20, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # ── Row 1: First Name + Last Name (Equal Width) ───────────────────────
        row1 = QHBoxLayout()
        row1.setSpacing(16)
        row1.setAlignment(Qt.AlignTop)

        fn_col = QVBoxLayout()
        fn_col.setSpacing(4)
        fn_col.setAlignment(Qt.AlignTop)
        fn_col.addWidget(self._lbl("First Name *"))
        self.fn_field = _ValidatedField("First name")
        self.fn_field.edit.textChanged.connect(
            lambda: self.fn_field.set_error(_validate_name(self.fn_field.text(), "First name"))
        )
        fn_col.addWidget(self.fn_field)

        ln_col = QVBoxLayout()
        ln_col.setSpacing(4)
        ln_col.setAlignment(Qt.AlignTop)
        ln_col.addWidget(self._lbl("Last Name *"))
        self.ln_field = _ValidatedField("Last name")
        self.ln_field.edit.textChanged.connect(
            lambda: self.ln_field.set_error(_validate_name(self.ln_field.text(), "Last name"))
        )
        ln_col.addWidget(self.ln_field)

        # Equal width for First Name and Last Name
        row1.addLayout(fn_col)
        row1.addLayout(ln_col)

        layout.addLayout(row1)
        layout.addSpacerItem(QSpacerItem(0, 12, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # ── Row 2: Age + Sex ──────────────────────────────────────────────────
        row2 = QHBoxLayout()
        row2.setSpacing(16)
        row2.setAlignment(Qt.AlignTop)

        age_col = QVBoxLayout()
        age_col.setSpacing(4)
        age_col.setAlignment(Qt.AlignTop)
        age_col.addWidget(self._lbl("Age (optional)"))
        self.age_field = _ValidatedField("e.g. 54")
        self.age_field.edit.textChanged.connect(
            lambda: self.age_field.set_error(_validate_age(self.age_field.text()))
        )
        age_col.addWidget(self.age_field)

        sex_col = QVBoxLayout()
        sex_col.setSpacing(4)
        sex_col.setAlignment(Qt.AlignTop)
        sex_col.addWidget(self._lbl("Sex"))
        self.sex_combo = _ComboField("", ["Male", "Female"])
        sex_col.addWidget(self.sex_combo)

        row2.addLayout(age_col)
        row2.addLayout(sex_col)
        layout.addLayout(row2)
        layout.addSpacerItem(QSpacerItem(0, 12, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # ── Row 3: Tissue + Marker ────────────────────────────────────────────
        row3 = QHBoxLayout()
        row3.setSpacing(16)
        row3.setAlignment(Qt.AlignTop)

        tis_col = QVBoxLayout()
        tis_col.setSpacing(4)
        tis_col.setAlignment(Qt.AlignTop)
        tis_col.addWidget(self._lbl("Tissue *"))
        self.tissue_combo = _ComboField("", TISSUES)
        tis_col.addWidget(self.tissue_combo)

        mar_col = QVBoxLayout()
        mar_col.setSpacing(4)
        mar_col.setAlignment(Qt.AlignTop)
        mar_col.addWidget(self._lbl("Primary Marker"))
        self.marqueur_combo = _ComboField("", MARQUEURS)
        mar_col.addWidget(self.marqueur_combo)

        row3.addLayout(tis_col)
        row3.addLayout(mar_col)
        layout.addLayout(row3)
        layout.addSpacerItem(QSpacerItem(0, 32, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignRight)
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.setFixedHeight(42)
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Save Patient")
        save_btn.setObjectName("primaryBtn")
        save_btn.setFixedHeight(42)
        save_btn.clicked.connect(self._handle_save)

        btn_row.addWidget(cancel_btn)
        btn_row.addSpacing(12)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("fieldLabel")
        return lbl

    def _handle_save(self):
        fn = self.fn_field.text()
        ln = self.ln_field.text()
        age = self.age_field.text()

        errors = {
            self.fn_field: _validate_name(fn, "First name"),
            self.ln_field: _validate_name(ln, "Last name"),
            self.age_field: _validate_age(age),
        }

        if any(errors.values()):
            for field, msg in errors.items():
                field.set_error(msg)
            return

        age_int = int(age) if age else None
        sexe = self.sex_combo.currentText()
        tissue = self.tissue_combo.currentText()
        marqueur = self.marqueur_combo.currentText()

        create_patient(fn, ln, age_int, sexe, tissue, marqueur, self.doctor["id"])
        
        QMessageBox.information(self, "Success", 
                                f"Patient {fn} {ln} added successfully.")
        self.accept()
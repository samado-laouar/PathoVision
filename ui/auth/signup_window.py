import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QMessageBox, QComboBox, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap

from db.doctor_dao import create_doctor


# ── Validation Rules ──────────────────────────────────────────────────────────
_NAME_RE     = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ'\- ]{2,60}$")
_USER_RE     = re.compile(r"^[A-Za-z0-9_.\-]{3,30}$")
_PW_UPPER    = re.compile(r"[A-Z]")
_PW_DIGIT    = re.compile(r"[0-9]")


def _validate_fullname(v: str) -> str:
    if not v:
        return "Full name is required."
    if not _NAME_RE.match(v):
        return "Only letters, spaces, hyphens and apostrophes (2–60 chars)."
    return ""


def _validate_username(v: str) -> str:
    if not v:
        return "Username is required."
    if not _USER_RE.match(v):
        return "3–30 chars: letters, digits, _ . - only."
    return ""


def _validate_password(v: str) -> str:
    if not v:
        return "Password is required."
    if len(v) < 8:
        return "At least 8 characters."
    if not _PW_UPPER.search(v):
        return "Must contain at least one uppercase letter."
    if not _PW_DIGIT.search(v):
        return "Must contain at least one digit."
    return ""


def _validate_confirm(pw: str, confirm: str) -> str:
    if not confirm:
        return "Please confirm your password."
    if pw != confirm:
        return "Passwords do not match."
    return ""


# ── Reusable Validated Field ─────────────────────────────────────────────────
class _ValidatedField(QFrame):
    def __init__(self, placeholder: str, password: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("fieldWrapper")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.setFixedHeight(44)
        self.edit.setObjectName("formInput")
        if password:
            self.edit.setEchoMode(QLineEdit.Password)

        self.error_lbl = QLabel("")
        self.error_lbl.setObjectName("errorLabel")
        self.error_lbl.setFixedHeight(16)
        self.error_lbl.hide()

        layout.addWidget(self.edit)
        layout.addWidget(self.error_lbl)

        self.edit.textChanged.connect(self._on_text_changed)

    def text(self) -> str:
        return self.edit.text().strip()

    def _on_text_changed(self):
        self.clear_error()

    def set_error(self, message: str):
        if message:
            self.edit.setProperty("invalid", True)
            self.error_lbl.setText(message)
            self.error_lbl.show()
        else:
            self.clear_error()

        # Refresh style
        self.edit.style().unpolish(self.edit)
        self.edit.style().polish(self.edit)

    def clear_error(self):
        self.edit.setProperty("invalid", False)
        self.error_lbl.setText("")
        self.error_lbl.hide()
        self.edit.style().unpolish(self.edit)
        self.edit.style().polish(self.edit)


# ── Signup Window ────────────────────────────────────────────────────────────
class SignupWindow(QWidget):
    signup_successful = Signal()
    go_login = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ColxPath — Create Account")
        self.setMinimumSize(940, 680)
        self._build_ui()
        self._apply_styles()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Left Brand Panel
        left = QFrame()
        left.setObjectName("brandPanel")
        left.setFixedWidth(400)

        ll = QVBoxLayout(left)
        ll.setAlignment(Qt.AlignCenter)
        ll.setContentsMargins(48, 0, 48, 0)
        ll.setSpacing(0)

        # Logo
        logo_lbl = QLabel()
        logo_lbl.setAlignment(Qt.AlignCenter)
        pix = QPixmap("assets/logo4.png")
        if not pix.isNull():
            logo_lbl.setPixmap(pix.scaled(256, 256, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo_lbl.setText("C")
            logo_lbl.setFont(QFont("DM Sans", 52, QFont.Bold))
            logo_lbl.setStyleSheet("color: white;")

        tagline = QLabel("Pathology platform for cancer diagnosis.")
        tagline.setObjectName("brandTagline")
        tagline.setAlignment(Qt.AlignCenter)

        ll.addStretch()
        ll.addWidget(logo_lbl)
        ll.addSpacing(16)
        ll.addWidget(tagline)
        ll.addStretch()

        # Right Form Panel
        right = QFrame()
        right.setObjectName("formPanel")
        rl = QVBoxLayout(right)
        rl.setAlignment(Qt.AlignCenter)
        rl.setContentsMargins(60, 40, 60, 40)
        rl.setSpacing(0)

        # Title
        title = QLabel("Create Account")
        title.setObjectName("formTitle")
        subtitle = QLabel("Fill in your details to get started")
        subtitle.setObjectName("formSubtitle")

        rl.addWidget(title)
        rl.addWidget(subtitle)
        rl.addSpacerItem(QSpacerItem(0, 32, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # ── Full Name + Job/Specialty Row ───────────────────────────────────
        row1 = QHBoxLayout()
        row1.setSpacing(16)
        row1.setAlignment(Qt.AlignTop)

        # Full Name
        fn_col = QVBoxLayout()
        fn_col.setSpacing(4)
        fn_col.setAlignment(Qt.AlignTop)
        fn_col.addWidget(self._lbl("Full Name"))
        self.fullname_field = _ValidatedField("Jane Smith")
        self.fullname_field.edit.textChanged.connect(self._live_validate_fullname)
        fn_col.addWidget(self.fullname_field)

        # Job / Specialty
        job_col = QVBoxLayout()
        job_col.setSpacing(4)
        job_col.setAlignment(Qt.AlignTop)
        job_col.addWidget(self._lbl("Job / Specialty"))

        self.job_combo = QComboBox()
        self.job_combo.setObjectName("formInput")
        self.job_combo.setFixedHeight(44)
        self.job_combo.addItems([
            "Pathologist", "Oncologist", "Surgeon",
            "Radiologist", "Researcher", "Other"
        ])

        # Wrapper to keep same height as validated fields
        job_wrapper = QVBoxLayout()
        job_wrapper.setSpacing(3)
        job_wrapper.addWidget(self.job_combo)
        
        # Dummy error label to maintain alignment
        self.job_error_lbl = QLabel("")
        self.job_error_lbl.setObjectName("errorLabel")
        self.job_error_lbl.setFixedHeight(16)
        job_wrapper.addWidget(self.job_error_lbl)

        job_col.addLayout(job_wrapper)

        row1.addLayout(fn_col)
        row1.addLayout(job_col)
        rl.addLayout(row1)

        rl.addSpacerItem(QSpacerItem(0, 12, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # Username
        rl.addWidget(self._lbl("Username"))
        self.username_field = _ValidatedField("Choose a username")
        self.username_field.edit.textChanged.connect(self._live_validate_username)
        rl.addWidget(self.username_field)
        rl.addSpacerItem(QSpacerItem(0, 12, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # Password + Confirm Password
        row2 = QHBoxLayout()
        row2.setSpacing(16)

        pw_col = QVBoxLayout()
        pw_col.setSpacing(4)
        pw_col.setAlignment(Qt.AlignTop)
        pw_col.addWidget(self._lbl("Password"))
        self.pw_field = _ValidatedField("Min 8 chars, 1 uppercase, 1 digit", password=True)
        self.pw_field.edit.textChanged.connect(self._live_validate_password)
        pw_col.addWidget(self.pw_field)

        cpw_col = QVBoxLayout()
        cpw_col.setSpacing(4)
        cpw_col.setAlignment(Qt.AlignTop)
        cpw_col.addWidget(self._lbl("Confirm Password"))
        self.cpw_field = _ValidatedField("Repeat your password", password=True)
        self.cpw_field.edit.textChanged.connect(self._live_validate_confirm)
        cpw_col.addWidget(self.cpw_field)

        row2.addLayout(pw_col)
        row2.addLayout(cpw_col)
        rl.addLayout(row2)

        rl.addSpacerItem(QSpacerItem(0, 28, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # Submit Button
        self.submit_btn = QPushButton("Create Account")
        self.submit_btn.setObjectName("primaryBtn")
        self.submit_btn.setFixedHeight(48)
        self.submit_btn.setCursor(Qt.PointingHandCursor)
        self.submit_btn.clicked.connect(self._handle_signup)
        rl.addWidget(self.submit_btn)

        rl.addSpacerItem(QSpacerItem(0, 20, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # Login Link
        bottom_row = QHBoxLayout()
        bottom_row.setAlignment(Qt.AlignCenter)
        already = QLabel("Already have an account?")
        already.setObjectName("mutedText")
        login_link = QPushButton("Sign in")
        login_link.setObjectName("linkBtn")
        login_link.setCursor(Qt.PointingHandCursor)
        login_link.clicked.connect(self.go_login.emit)

        bottom_row.addWidget(already)
        bottom_row.addWidget(login_link)
        rl.addLayout(bottom_row)

        rl.addStretch()

        root.addWidget(left)
        root.addWidget(right, 1)

    def _lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("fieldLabel")
        return lbl

    # ── Live Validation ─────────────────────────────────────────────────────
    def _live_validate_fullname(self):
        self.fullname_field.set_error(
            _validate_fullname(self.fullname_field.text())
        )

    def _live_validate_username(self):
        self.username_field.set_error(
            _validate_username(self.username_field.text())
        )

    def _live_validate_password(self):
        self.pw_field.set_error(_validate_password(self.pw_field.text()))
        if self.cpw_field.text():
            self._live_validate_confirm()

    def _live_validate_confirm(self):
        self.cpw_field.set_error(
            _validate_confirm(self.pw_field.text(), self.cpw_field.text())
        )

    # ── Submit Handler ──────────────────────────────────────────────────────
    def _handle_signup(self):
        full_name = self.fullname_field.text()
        username = self.username_field.text()
        password = self.pw_field.text()
        confirm = self.cpw_field.text()
        job = self.job_combo.currentText()

        errors = {
            self.fullname_field: _validate_fullname(full_name),
            self.username_field: _validate_username(username),
            self.pw_field: _validate_password(password),
            self.cpw_field: _validate_confirm(password, confirm),
        }

        if any(errors.values()):
            for field, msg in errors.items():
                field.set_error(msg)
            return

        ok, msg = create_doctor(username, password, full_name, job)
        if ok:
            QMessageBox.information(self, "Success", 
                                    "Account created successfully!\nYou can now log in.")
            self.signup_successful.emit()
            self.go_login.emit()
        else:
            if "UNIQUE" in msg.upper():
                self.username_field.set_error("This username is already taken.")
            else:
                QMessageBox.critical(self, "Error", msg)

    # ── Styles ──────────────────────────────────────────────────────────────
    def _apply_styles(self):
        self.setStyleSheet("""
            QWidget { font-family: 'Segoe UI'; }

            #brandPanel {
                background: #6626a6;
            }
            #brandTagline {
                color: rgba(203,213,225,0.75);
                font-size: 14.5px;
            }

            #formPanel { background: #FFFFFF; }
            #formTitle { 
                font-size: 28px; 
                font-weight: 700; 
                color: #1A2B45; 
            }
            #formSubtitle { 
                font-size: 14.5px; 
                color: #64748B; 
                margin-top: 4px;
            }

            #fieldLabel { 
                font-size: 13px; 
                font-weight: 600; 
                color: #2C3E50; 
                margin-bottom: 5px;
            }

            #formInput {
                border: 1.5px solid #DDE3EA;
                border-radius: 8px;
                padding: 0 14px;
                font-size: 14px;
                color: #1A2B45;
                background: #FFFFFF;
            }
            #formInput:focus {
                border-color: #791ad8;
            }

            QLineEdit#formInput[invalid="true"] {
                border-color: #E74C3C;
                background: #FEF9F9;
            }

            #errorLabel {
                color: #E74C3C;
                font-size: 11px;
                padding-left: 4px;
            }

            QComboBox#formInput {
                padding-left: 10px;
            }
            QComboBox#formInput::drop-down {
                border: none;
                width: 28px;
            }

            #primaryBtn {
                background: #791ad8; 
                color: white; 
                border: none;
                border-radius: 8px; 
                font-size: 15px; 
                font-weight: 600;
            }
            #primaryBtn:hover   { background: #61249e; }
            #primaryBtn:pressed { background: #521e85; }

            #mutedText { 
                color: #64748B; 
                font-size: 13.5px; 
            }
            #linkBtn {
                background: none; 
                border: none; 
                color: #791ad8;
                font-size: 13.5px; 
                font-weight: 600;
                padding: 0 4px;
            }
            #linkBtn:hover { color: #61249e; }
        """)
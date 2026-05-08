from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QMessageBox, QComboBox, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap

from db.doctor_dao import create_doctor
from ui._style import AUTH_QSS, C


class SignupWindow(QWidget):
    signup_successful = Signal()
    go_login          = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ColxPath — Create Account")
        self.setMinimumSize(920, 660)
        self._build_ui()
        self.setStyleSheet(AUTH_QSS)

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left brand panel ──────────────────────────────────────────────────
        left = QFrame()
        left.setObjectName("brandPanel")
        left.setFixedWidth(400)
        ll = QVBoxLayout(left)
        ll.setAlignment(Qt.AlignCenter)
        ll.setSpacing(0)
        ll.setContentsMargins(48, 0, 48, 0)

        logo_lbl = QLabel()
        logo_lbl.setAlignment(Qt.AlignCenter)
        pix = QPixmap("assets/logo.png")
        if not pix.isNull():
            logo_lbl.setPixmap(pix.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo_lbl.setText("C")
            logo_lbl.setFont(QFont("DM Sans", 52, QFont.Bold))
            logo_lbl.setStyleSheet("color: white;")

        brand = QLabel("ColxPath")
        brand.setObjectName("brandTitle")
        brand.setAlignment(Qt.AlignCenter)

        tagline = QLabel("Join the platform trusted by\npathology professionals.")
        tagline.setObjectName("brandTagline")
        tagline.setAlignment(Qt.AlignCenter)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("color: rgba(255,255,255,0.10); margin: 24px 0;")

        badge = QLabel("SECURE  ·  PRIVATE  ·  CLINICAL-GRADE")
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            "font-size: 10px; font-weight: 700; letter-spacing: 2px;"
            "color: rgba(203,213,225,0.35);"
        )

        ll.addStretch()
        ll.addWidget(logo_lbl)
        ll.addSpacing(20)
        ll.addWidget(brand)
        ll.addSpacing(10)
        ll.addWidget(tagline)
        ll.addWidget(divider)
        ll.addWidget(badge)
        ll.addStretch()

        # ── Right form panel ──────────────────────────────────────────────────
        right = QFrame()
        right.setObjectName("formPanel")
        rl = QVBoxLayout(right)
        rl.setAlignment(Qt.AlignCenter)
        rl.setContentsMargins(64, 40, 64, 40)
        rl.setSpacing(0)

        title = QLabel("Create Account")
        title.setObjectName("formTitle")
        subtitle = QLabel("Fill in your details to get started")
        subtitle.setObjectName("formSubtitle")
        rl.addWidget(title)
        rl.addWidget(subtitle)
        rl.addSpacerItem(QSpacerItem(0, 24, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # Row: Full Name + Job
        row1 = QHBoxLayout()
        row1.setSpacing(16)
        fn_col = QVBoxLayout()
        fn_col.setSpacing(5)
        fn_col.addWidget(self._lbl("Full Name"))
        self.fullname_input = self._edit("Dr. Jane Smith")
        fn_col.addWidget(self.fullname_input)

        job_col = QVBoxLayout()
        job_col.setSpacing(5)
        job_col.addWidget(self._lbl("Job / Specialty"))
        self.job_combo = QComboBox()
        self.job_combo.setObjectName("formInput")
        self.job_combo.setFixedHeight(44)
        self.job_combo.addItems([
            "Pathologist", "Oncologist", "Surgeon",
            "Radiologist", "Researcher", "Other"
        ])
        job_col.addWidget(self.job_combo)

        row1.addLayout(fn_col)
        row1.addLayout(job_col)
        rl.addLayout(row1)
        rl.addSpacerItem(QSpacerItem(0, 14, QSizePolicy.Minimum, QSizePolicy.Fixed))

        rl.addWidget(self._lbl("Username"))
        self.username_input = self._edit("Choose a username")
        rl.addWidget(self.username_input)
        rl.addSpacerItem(QSpacerItem(0, 14, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # Row: Password + Confirm
        row2 = QHBoxLayout()
        row2.setSpacing(16)
        pw_col = QVBoxLayout()
        pw_col.setSpacing(5)
        pw_col.addWidget(self._lbl("Password"))
        self.pw_input = self._edit("Create a password", password=True)
        pw_col.addWidget(self.pw_input)

        cpw_col = QVBoxLayout()
        cpw_col.setSpacing(5)
        cpw_col.addWidget(self._lbl("Confirm Password"))
        self.cpw_input = self._edit("Repeat your password", password=True)
        cpw_col.addWidget(self.cpw_input)

        row2.addLayout(pw_col)
        row2.addLayout(cpw_col)
        rl.addLayout(row2)
        rl.addSpacerItem(QSpacerItem(0, 26, QSizePolicy.Minimum, QSizePolicy.Fixed))

        self.submit_btn = QPushButton("Create Account")
        self.submit_btn.setObjectName("primaryBtn")
        self.submit_btn.setFixedHeight(46)
        self.submit_btn.setCursor(Qt.PointingHandCursor)
        self.submit_btn.clicked.connect(self._handle_signup)
        rl.addWidget(self.submit_btn)
        rl.addSpacerItem(QSpacerItem(0, 16, QSizePolicy.Minimum, QSizePolicy.Fixed))

        back_row = QHBoxLayout()
        back_row.setAlignment(Qt.AlignCenter)
        already = QLabel("Already have an account?")
        already.setObjectName("mutedText")
        self.login_link = QPushButton("Sign in")
        self.login_link.setObjectName("linkBtn")
        self.login_link.setCursor(Qt.PointingHandCursor)
        self.login_link.clicked.connect(self.go_login.emit)
        back_row.addWidget(already)
        back_row.addWidget(self.login_link)
        rl.addLayout(back_row)
        rl.addStretch()

        root.addWidget(left)
        root.addWidget(right, 1)

    def _lbl(self, text):
        l = QLabel(text)
        l.setObjectName("fieldLabel")
        l.setContentsMargins(0, 0, 0, 5)
        return l

    def _edit(self, placeholder, password=False):
        e = QLineEdit()
        e.setPlaceholderText(placeholder)
        e.setFixedHeight(44)
        e.setObjectName("formInput")
        if password:
            e.setEchoMode(QLineEdit.Password)
        return e

    def _handle_signup(self):
        full_name = self.fullname_input.text().strip()
        username  = self.username_input.text().strip()
        password  = self.pw_input.text().strip()
        confirm   = self.cpw_input.text().strip()
        job       = self.job_combo.currentText()

        if not all([full_name, username, password, confirm]):
            QMessageBox.warning(self, "Missing Fields", "Please fill in all fields.")
            return
        if password != confirm:
            QMessageBox.warning(self, "Password Mismatch", "Passwords do not match.")
            return
        if len(password) < 6:
            QMessageBox.warning(self, "Weak Password", "Password must be at least 6 characters.")
            return

        ok, msg = create_doctor(username, password, full_name, job)
        if ok:
            QMessageBox.information(self, "Success", "Account created. You can now log in.")
            self.signup_successful.emit()
            self.go_login.emit()
        else:
            if "UNIQUE" in msg:
                QMessageBox.critical(self, "Username Taken", "That username is already in use.")
            else:
                QMessageBox.critical(self, "Error", msg)
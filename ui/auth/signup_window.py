from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QMessageBox, QComboBox, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from db.doctor_dao import create_doctor


class SignupWindow(QWidget):
    signup_successful = Signal()
    go_login = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PathoVision — Create Account")
        self.setMinimumSize(900, 640)
        self._build_ui()
        self._apply_styles()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left brand panel ────────────────────────────────────────
        left = QFrame()
        left.setObjectName("brandPanel")
        left.setFixedWidth(420)
        ll = QVBoxLayout(left)
        ll.setAlignment(Qt.AlignCenter)
        ll.setSpacing(14)

        logo = QLabel("🔬")
        logo.setAlignment(Qt.AlignCenter)
        logo.setFont(QFont("Segoe UI", 52))

        brand = QLabel("PathoVision")
        brand.setObjectName("brandTitle")
        brand.setAlignment(Qt.AlignCenter)

        tagline = QLabel("Join the platform trusted by\npathology professionals.")
        tagline.setObjectName("brandTagline")
        tagline.setAlignment(Qt.AlignCenter)

        ll.addStretch()
        ll.addWidget(logo)
        ll.addWidget(brand)
        ll.addWidget(tagline)
        ll.addStretch()

        # ── Right form panel ────────────────────────────────────────
        right = QFrame()
        right.setObjectName("formPanel")
        rl = QVBoxLayout(right)
        rl.setAlignment(Qt.AlignCenter)
        rl.setContentsMargins(60, 40, 60, 40)
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
        fn_col.addWidget(self._lbl("Full Name"))
        self.fullname_input = self._edit("Dr. Jane Smith")
        fn_col.addWidget(self.fullname_input)

        job_col = QVBoxLayout()
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

        # Username
        rl.addWidget(self._lbl("Username"))
        self.username_input = self._edit("Choose a username")
        rl.addWidget(self.username_input)
        rl.addSpacerItem(QSpacerItem(0, 14, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # Row: Password + Confirm
        row2 = QHBoxLayout()
        row2.setSpacing(16)
        pw_col = QVBoxLayout()
        pw_col.addWidget(self._lbl("Password"))
        self.pw_input = self._edit("Create a password", password=True)
        pw_col.addWidget(self.pw_input)

        cpw_col = QVBoxLayout()
        cpw_col.addWidget(self._lbl("Confirm Password"))
        self.cpw_input = self._edit("Repeat your password", password=True)
        cpw_col.addWidget(self.cpw_input)

        row2.addLayout(pw_col)
        row2.addLayout(cpw_col)
        rl.addLayout(row2)
        rl.addSpacerItem(QSpacerItem(0, 24, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # Submit
        self.submit_btn = QPushButton("Create Account")
        self.submit_btn.setObjectName("primaryBtn")
        self.submit_btn.setFixedHeight(48)
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
            QMessageBox.information(self, "Success", "Account created! You can now log in.")
            self.signup_successful.emit()
            self.go_login.emit()
        else:
            if "UNIQUE" in msg:
                QMessageBox.critical(self, "Username Taken", "That username is already in use.")
            else:
                QMessageBox.critical(self, "Error", msg)

    def _apply_styles(self):
        self.setStyleSheet("""
            QWidget { background: #F8FAFB; font-family: 'Segoe UI'; }

            #brandPanel {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #1A5276, stop:1 #2E86C1);
            }
            #brandTitle {
                color: white; font-size: 32px; font-weight: 700; letter-spacing: 1px;
            }
            #brandTagline { color: rgba(255,255,255,0.75); font-size: 14px; }

            #formPanel { background: #FFFFFF; }
            #formTitle { font-size: 28px; font-weight: 700; color: #1A2B45; }
            #formSubtitle { font-size: 14px; color: #7F8C8D; margin-top: 4px; }
            #fieldLabel { font-size: 13px; font-weight: 600; color: #2C3E50; margin-bottom: 6px; }

            #formInput {
                border: 1.5px solid #D5D8DC; border-radius: 8px;
                padding: 0 14px; font-size: 14px; color: #1A2B45; background: #FDFEFE;
            }
            #formInput:focus { border-color: #2E86C1; background: #EBF5FB; }
            QComboBox#formInput { padding-left: 10px; }
            QComboBox#formInput::drop-down { border: none; width: 24px; }

            #primaryBtn {
                background: #2E86C1; color: white; border: none;
                border-radius: 8px; font-size: 15px; font-weight: 600;
            }
            #primaryBtn:hover { background: #1A5276; }
            #primaryBtn:pressed { background: #154360; }

            #mutedText { color: #7F8C8D; font-size: 13px; }
            #linkBtn {
                background: none; border: none; color: #2E86C1;
                font-size: 13px; font-weight: 600; padding: 0 4px;
                text-decoration: underline;
            }
            #linkBtn:hover { color: #1A5276; }
        """)
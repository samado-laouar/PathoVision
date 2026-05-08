from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QMessageBox, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap

from db.doctor_dao import authenticate
from ui._style import AUTH_QSS, C


class LoginWindow(QWidget):
    login_successful = Signal(dict)
    go_signup        = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ColxPath — Login")
        self.setMinimumSize(920, 600)
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

        # Logo image (logo.png dropped in assets/)
        logo_lbl = QLabel()
        logo_lbl.setAlignment(Qt.AlignCenter)
        pix = QPixmap("assets/logo.png")
        if not pix.isNull():
            logo_lbl.setPixmap(pix.scaled(256, 256, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo_lbl.setText("C")
            logo_lbl.setFont(QFont("DM Sans", 52, QFont.Bold))
            logo_lbl.setStyleSheet("color: white;" )

        # brand = QLabel("ColxPath")
        # brand.setObjectName("brandTitle")
        # brand.setAlignment(Qt.AlignCenter)

        tagline = QLabel("Pathology platform for cancer diagnosis.")
        tagline.setObjectName("brandTagline")
        tagline.setAlignment(Qt.AlignCenter)

        # divider = QFrame()
        # divider.setFrameShape(QFrame.HLine)
        # divider.setStyleSheet(f"color: rgba(255,255,255,0.10); margin: 24px 0;")

        # badge = QLabel("TRUSTED BY PATHOLOGISTS")
        # badge.setAlignment(Qt.AlignCenter)
        # badge.setStyleSheet(
        #     "font-size: 10px; font-weight: 700; letter-spacing: 2px;"
        #     "color: rgba(203,213,225,0.35);"
        # )

        ll.addStretch()
        ll.addWidget(logo_lbl)
        # ll.addSpacing(10)
        # ll.addWidget(brand)
        # ll.addSpacing(10)
        ll.addWidget(tagline)
        # ll.addWidget(divider)
        # ll.addWidget(badge)
        ll.addStretch()

        # ── Right form panel ──────────────────────────────────────────────────
        right = QFrame()
        right.setObjectName("formPanel")
        rl = QVBoxLayout(right)
        rl.setAlignment(Qt.AlignCenter)
        rl.setContentsMargins(64, 48, 64, 48)
        rl.setSpacing(0)

        title = QLabel("Welcome back")
        title.setObjectName("formTitle")

        subtitle = QLabel("Sign in to your account")
        subtitle.setObjectName("formSubtitle")

        rl.addWidget(title)
        rl.addWidget(subtitle)
        rl.addSpacerItem(QSpacerItem(0, 32, QSizePolicy.Minimum, QSizePolicy.Fixed))

        rl.addWidget(self._lbl("Username"))
        self.username_input = self._edit("Enter your username")
        rl.addWidget(self.username_input)
        rl.addSpacerItem(QSpacerItem(0, 16, QSizePolicy.Minimum, QSizePolicy.Fixed))

        rl.addWidget(self._lbl("Password"))
        self.password_input = self._edit("Enter your password", password=True)
        rl.addWidget(self.password_input)
        rl.addSpacerItem(QSpacerItem(0, 28, QSizePolicy.Minimum, QSizePolicy.Fixed))

        self.login_btn = QPushButton("Sign In")
        self.login_btn.setObjectName("primaryBtn")
        self.login_btn.setFixedHeight(46)
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.clicked.connect(self._handle_login)
        rl.addWidget(self.login_btn)
        rl.addSpacerItem(QSpacerItem(0, 18, QSizePolicy.Minimum, QSizePolicy.Fixed))

        signup_row = QHBoxLayout()
        signup_row.setAlignment(Qt.AlignCenter)
        no_account = QLabel("Don't have an account?")
        no_account.setObjectName("mutedText")
        self.signup_link = QPushButton("Create one")
        self.signup_link.setObjectName("linkBtn")
        self.signup_link.setCursor(Qt.PointingHandCursor)
        self.signup_link.clicked.connect(self.go_signup.emit)
        signup_row.addWidget(no_account)
        signup_row.addWidget(self.signup_link)
        rl.addLayout(signup_row)
        rl.addStretch()

        self.password_input.returnPressed.connect(self._handle_login)
        self.username_input.returnPressed.connect(self._handle_login)

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

    def _handle_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        if not username or not password:
            QMessageBox.warning(self, "Missing Fields", "Please fill in all fields.")
            return
        doctor = authenticate(username, password)
        if doctor:
            self.login_successful.emit(doctor)
        else:
            QMessageBox.critical(self, "Login Failed", "Invalid username or password.")
            self.password_input.clear()
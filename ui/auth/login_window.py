from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QMessageBox, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap, QIcon
from db.doctor_dao import authenticate


class LoginWindow(QWidget):
    login_successful = Signal(dict)   # emits doctor dict
    go_signup = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PathoVision — Login")
        self.setMinimumSize(900, 600)
        self._build_ui()
        self._apply_styles()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left panel (brand) ──────────────────────────────────────
        left = QFrame()
        left.setObjectName("brandPanel")
        left.setFixedWidth(420)
        left_layout = QVBoxLayout(left)
        left_layout.setAlignment(Qt.AlignCenter)
        left_layout.setSpacing(14)

        logo_label = QLabel("🔬")
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setFont(QFont("Segoe UI", 52))

        brand = QLabel("PathoVision")
        brand.setObjectName("brandTitle")
        brand.setAlignment(Qt.AlignCenter)

        tagline = QLabel("AI-Powered Cancer Detection\nfor Pathology Professionals")
        tagline.setObjectName("brandTagline")
        tagline.setAlignment(Qt.AlignCenter)

        left_layout.addStretch()
        left_layout.addWidget(logo_label)
        left_layout.addWidget(brand)
        left_layout.addWidget(tagline)
        left_layout.addStretch()

        # ── Right panel (form) ──────────────────────────────────────
        right = QFrame()
        right.setObjectName("formPanel")
        right_layout = QVBoxLayout(right)
        right_layout.setAlignment(Qt.AlignCenter)
        right_layout.setContentsMargins(60, 40, 60, 40)
        right_layout.setSpacing(0)

        title = QLabel("Welcome Back")
        title.setObjectName("formTitle")
        title.setAlignment(Qt.AlignLeft)

        subtitle = QLabel("Sign in to your account")
        subtitle.setObjectName("formSubtitle")

        right_layout.addWidget(title)
        right_layout.addWidget(subtitle)
        right_layout.addSpacerItem(QSpacerItem(0, 32, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # Username
        right_layout.addWidget(self._field_label("Username"))
        self.username_input = self._line_edit("Enter your username")
        right_layout.addWidget(self.username_input)
        right_layout.addSpacerItem(QSpacerItem(0, 16, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # Password
        right_layout.addWidget(self._field_label("Password"))
        self.password_input = self._line_edit("Enter your password", password=True)
        right_layout.addWidget(self.password_input)
        right_layout.addSpacerItem(QSpacerItem(0, 28, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # Login button
        self.login_btn = QPushButton("Sign In")
        self.login_btn.setObjectName("primaryBtn")
        self.login_btn.setFixedHeight(48)
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.clicked.connect(self._handle_login)
        right_layout.addWidget(self.login_btn)
        right_layout.addSpacerItem(QSpacerItem(0, 16, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # Signup link
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
        right_layout.addLayout(signup_row)
        right_layout.addStretch()

        root.addWidget(left)
        root.addWidget(right, 1)

        # Enter key triggers login
        self.password_input.returnPressed.connect(self._handle_login)
        self.username_input.returnPressed.connect(self._handle_login)

    def _field_label(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("fieldLabel")
        return lbl

    def _line_edit(self, placeholder, password=False):
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setFixedHeight(44)
        edit.setObjectName("formInput")
        if password:
            edit.setEchoMode(QLineEdit.Password)
        return edit

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

    def _apply_styles(self):
        self.setStyleSheet("""
            QWidget { background: #F8FAFB; font-family: 'Segoe UI'; }

            #brandPanel {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #1A5276, stop:1 #2E86C1);
            }
            #brandTitle {
                color: white;
                font-size: 32px;
                font-weight: 700;
                letter-spacing: 1px;
            }
            #brandTagline {
                color: rgba(255,255,255,0.75);
                font-size: 14px;
                line-height: 1.6;
            }

            #formPanel { background: #FFFFFF; }
            #formTitle { font-size: 28px; font-weight: 700; color: #1A2B45; }
            #formSubtitle { font-size: 14px; color: #7F8C8D; margin-top: 4px; }

            #fieldLabel { font-size: 13px; font-weight: 600; color: #2C3E50;
                          margin-bottom: 6px; }

            #formInput {
                border: 1.5px solid #D5D8DC;
                border-radius: 8px;
                padding: 0 14px;
                font-size: 14px;
                color: #1A2B45;
                background: #FDFEFE;
            }
            #formInput:focus {
                border-color: #2E86C1;
                background: #EBF5FB;
            }

            #primaryBtn {
                background: #2E86C1;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 15px;
                font-weight: 600;
                letter-spacing: 0.5px;
            }
            #primaryBtn:hover { background: #1A5276; }
            #primaryBtn:pressed { background: #154360; }

            #mutedText { color: #7F8C8D; font-size: 13px; }
            #linkBtn {
                background: none;
                border: none;
                color: #2E86C1;
                font-size: 13px;
                font-weight: 600;
                padding: 0 4px;
                text-decoration: underline;
            }
            #linkBtn:hover { color: #1A5276; }
        """)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGridLayout, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class HomePage(QWidget):
    go_histology = Signal()
    go_ihc       = Signal()
    go_history   = Signal()
    logout       = Signal()

    def __init__(self, doctor: dict, parent=None):
        super().__init__(parent)
        self.doctor = doctor
        self._build_ui()
        self._apply_styles()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top navbar ──────────────────────────────────────────────
        navbar = QFrame()
        navbar.setObjectName("navbar")
        navbar.setFixedHeight(64)
        nav_layout = QHBoxLayout(navbar)
        nav_layout.setContentsMargins(28, 0, 28, 0)

        brand = QLabel("🔬  PathoVision")
        brand.setObjectName("navBrand")

        doctor_name = self.doctor.get("full_name", "Doctor")
        doctor_job  = self.doctor.get("job", "")
        self.doctor_label = QLabel(f"  {doctor_name}  ·  {doctor_job}")
        self.doctor_label.setObjectName("navDoctor")

        logout_btn = QPushButton("Log Out")
        logout_btn.setObjectName("logoutBtn")
        logout_btn.setFixedHeight(34)
        logout_btn.setCursor(Qt.PointingHandCursor)
        logout_btn.clicked.connect(self.logout.emit)

        nav_layout.addWidget(brand)
        nav_layout.addStretch()
        nav_layout.addWidget(self.doctor_label)
        nav_layout.addSpacing(16)
        nav_layout.addWidget(logout_btn)
        root.addWidget(navbar)

        # ── Main content ────────────────────────────────────────────
        content = QWidget()
        content.setObjectName("content")
        cl = QVBoxLayout(content)
        cl.setAlignment(Qt.AlignCenter)
        cl.setContentsMargins(60, 48, 60, 48)
        cl.setSpacing(10)

        greeting = QLabel(f"Welcome, {doctor_name}")
        greeting.setObjectName("greeting")
        greeting.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("What would you like to do today?")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignCenter)

        cl.addWidget(greeting)
        cl.addWidget(subtitle)
        cl.addSpacerItem(QSpacerItem(0, 36, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # Cards
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(24)
        cards_layout.setAlignment(Qt.AlignCenter)

        cards_layout.addWidget(self._card(
            "🧬", "Histology Analysis",
            "Analyze H&E stained tissue\nsamples for cancer detection.",
            self.go_histology.emit, "Analyze"
        ))
        cards_layout.addWidget(self._card(
            "🟤", "IHC Analysis",
            "Quantify DAB staining and\nextract immunohistochemical markers.",
            self.go_ihc.emit, "Analyze"
        ))
        cards_layout.addWidget(self._card(
            "📋", "Patient History",
            "Browse all past analyses\nand patient records.",
            self.go_history.emit, "Open"
        ))

        cl.addLayout(cards_layout)
        root.addWidget(content, 1)

        # ── Footer ──────────────────────────────────────────────────
        footer = QFrame()
        footer.setObjectName("footer")
        footer.setFixedHeight(36)
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(28, 0, 28, 0)
        ver = QLabel("PathoVision v1.0  ·  AI Cancer Detection Platform")
        ver.setObjectName("footerText")
        fl.addStretch()
        fl.addWidget(ver)
        fl.addStretch()
        root.addWidget(footer)

    def _card(self, icon, title, desc, callback, btn_label):
        card = QFrame()
        card.setObjectName("card")
        card.setFixedSize(260, 280)
        cl = QVBoxLayout(card)
        cl.setAlignment(Qt.AlignCenter)
        cl.setSpacing(10)
        cl.setContentsMargins(24, 28, 24, 24)

        icon_lbl = QLabel(icon)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setFont(QFont("Segoe UI", 38))

        title_lbl = QLabel(title)
        title_lbl.setObjectName("cardTitle")
        title_lbl.setAlignment(Qt.AlignCenter)

        desc_lbl = QLabel(desc)
        desc_lbl.setObjectName("cardDesc")
        desc_lbl.setAlignment(Qt.AlignCenter)
        desc_lbl.setWordWrap(True)

        btn = QPushButton(btn_label)
        btn.setObjectName("cardBtn")
        btn.setFixedHeight(40)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(callback)

        cl.addWidget(icon_lbl)
        cl.addWidget(title_lbl)
        cl.addWidget(desc_lbl)
        cl.addStretch()
        cl.addWidget(btn)
        return card

    def _apply_styles(self):
        self.setStyleSheet("""
            QWidget { font-family: 'Segoe UI'; }
            #navbar {
                background: #FFFFFF;
                border-bottom: 1px solid #E5E7EB;
            }
            #navBrand { font-size: 18px; font-weight: 700; color: #1A5276; }
            #navDoctor { font-size: 13px; color: #5D6D7E; }
            #logoutBtn {
                background: #F2F3F4; color: #2C3E50; border: 1px solid #D5D8DC;
                border-radius: 6px; font-size: 13px; padding: 0 14px;
            }
            #logoutBtn:hover { background: #E8DAEF; color: #922B21; }

            #content { background: #F0F4F8; }
            #greeting { font-size: 30px; font-weight: 700; color: #1A2B45; }
            #subtitle { font-size: 15px; color: #5D6D7E; }

            #card {
                background: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 14px;
            }
            #card:hover {
                border-color: #2E86C1;
                background: #FAFCFF;
            }
            #cardTitle { font-size: 16px; font-weight: 700; color: #1A2B45; }
            #cardDesc { font-size: 13px; color: #7F8C8D; line-height: 1.5; }
            #cardBtn {
                background: #EBF5FB; color: #2E86C1; border: none;
                border-radius: 8px; font-size: 13px; font-weight: 600;
            }
            #cardBtn:hover { background: #2E86C1; color: white; }

            #footer { background: #FFFFFF; border-top: 1px solid #E5E7EB; }
            #footerText { font-size: 12px; color: #AAB7B8; }
        """)
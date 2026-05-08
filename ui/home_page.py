from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap

from ui._style import BASE_QSS, C


class HomePage(QWidget):
    go_histology = Signal()
    go_ihc       = Signal()
    go_history   = Signal()
    logout       = Signal()

    def __init__(self, doctor: dict, parent=None):
        super().__init__(parent)
        self.doctor = doctor
        self._build_ui()
        self.setStyleSheet(BASE_QSS + _HOME_EXTRA)

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Navbar ────────────────────────────────────────────────────────────
        navbar = QFrame()
        navbar.setObjectName("navbar")
        navbar.setFixedHeight(60)
        nl = QHBoxLayout(navbar)
        nl.setContentsMargins(32, 0, 32, 0)
        nl.setSpacing(0)

        # Logo + wordmark
        logo_lbl = QLabel()
        pix = QPixmap("assets/logo3.png")
        if not pix.isNull():
            logo_lbl.setPixmap(pix.scaled(120, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        brand_col = QVBoxLayout()
        brand_col.setSpacing(0)
        brand_col.setContentsMargins(0, 0, 0, 0)
        brand_name = QLabel("ColxPath")
        brand_name.setObjectName("navBrand")
        brand_sub = QLabel("PATHOLOGY PLATFORM")
        brand_sub.setObjectName("navBrandSub")
        brand_col.addWidget(brand_name)
        brand_col.addWidget(brand_sub)

        doctor_name = self.doctor.get("full_name", "Doctor")
        doctor_job  = self.doctor.get("job", "")
        doctor_lbl  = QLabel(f"Dr. {doctor_name}  ·  {doctor_job}")
        doctor_lbl.setObjectName("navDoctor")

        logout_btn = QPushButton("Log Out")
        logout_btn.setObjectName("logoutBtn")
        logout_btn.setFixedHeight(32)
        logout_btn.setCursor(Qt.PointingHandCursor)
        logout_btn.clicked.connect(self.logout.emit)

        nl.addWidget(logo_lbl)
        nl.addLayout(brand_col)
        nl.addStretch()
        nl.addWidget(doctor_lbl)
        nl.addSpacing(20)
        nl.addWidget(logout_btn)
        root.addWidget(navbar)

        # ── Content ───────────────────────────────────────────────────────────
        content = QWidget()
        content.setObjectName("homeContent")
        cl = QVBoxLayout(content)
        cl.setAlignment(Qt.AlignCenter)
        cl.setContentsMargins(60, 52, 60, 52)
        cl.setSpacing(8)

        greeting = QLabel(f"Good day, Dr. {doctor_name}")
        greeting.setObjectName("greeting")
        greeting.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("Select an analysis type or review your patient records.")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignCenter)

        cl.addWidget(greeting)
        cl.addWidget(subtitle)
        cl.addSpacerItem(QSpacerItem(0, 40, QSizePolicy.Minimum, QSizePolicy.Fixed))

        cards_row = QHBoxLayout()
        cards_row.setSpacing(20)
        cards_row.setAlignment(Qt.AlignCenter)

        cards_row.addWidget(self._card(
            icon_file="assets/icon_histology.png",
            fallback_char="H",
            title="Histology Analysis",
            desc="Analyze H&E stained tissue samples\nfor cancer classification.",
            callback=self.go_histology.emit,
            btn_label="Open",
            accent=C["primary"],
        ))
        cards_row.addWidget(self._card(
            icon_file="assets/icon_ihc.png",
            fallback_char="I",
            title="IHC Analysis",
            desc="Quantify DAB staining and extract\nimmunohistochemical markers.",
            callback=self.go_ihc.emit,
            btn_label="Open",
            accent="#059669",
        ))
        cards_row.addWidget(self._card(
            icon_file="assets/icon_history.png",
            fallback_char="R",
            title="Patient Records",
            desc="Browse past analyses and\npatient history.",
            callback=self.go_history.emit,
            btn_label="Open",
            accent="#7C3AED",
        ))

        cl.addLayout(cards_row)
        root.addWidget(content, 1)

        # ── Footer ────────────────────────────────────────────────────────────
        footer = QFrame()
        footer.setObjectName("footer")
        footer.setFixedHeight(38)
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(32, 0, 32, 0)
        ver = QLabel("ColxPath v1.0  ·  AI-Assisted Pathology Analysis")
        ver.setObjectName("footerText")
        fl.addStretch()
        fl.addWidget(ver)
        fl.addStretch()
        root.addWidget(footer)

    def _card(self, icon_file, fallback_char, title, desc, callback, btn_label, accent):
        card = QFrame()
        card.setObjectName("card")
        card.setFixedSize(268, 296)
        cl = QVBoxLayout(card)
        cl.setAlignment(Qt.AlignTop)
        cl.setSpacing(0)
        cl.setContentsMargins(0, 0, 0, 0)

        # Accent stripe at top
        stripe = QFrame()
        stripe.setFixedHeight(4)
        stripe.setStyleSheet(f"background: {accent}; border-radius: 0px;")
        cl.addWidget(stripe)

        inner = QVBoxLayout()
        inner.setAlignment(Qt.AlignCenter)
        inner.setSpacing(10)
        inner.setContentsMargins(26, 24, 26, 22)

        # Icon
        icon_lbl = QLabel()
        icon_lbl.setAlignment(Qt.AlignCenter)
        pix = QPixmap(icon_file)
        if not pix.isNull():
            icon_lbl.setPixmap(pix.scaled(44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            icon_lbl.setText(fallback_char)
            icon_lbl.setFont(QFont("DM Sans", 32, QFont.Bold))
            icon_lbl.setStyleSheet(f"color: {accent};")

        title_lbl = QLabel(title)
        title_lbl.setObjectName("cardTitle")
        title_lbl.setAlignment(Qt.AlignCenter)

        desc_lbl = QLabel(desc)
        desc_lbl.setObjectName("cardDesc")
        desc_lbl.setAlignment(Qt.AlignCenter)
        desc_lbl.setWordWrap(True)

        btn = QPushButton(btn_label)
        btn.setFixedHeight(38)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {accent};
                border: 1.5px solid {accent};
                border-radius: 7px;
                font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{
                background: {accent};
                color: white;
            }}
        """)
        btn.clicked.connect(callback)

        inner.addWidget(icon_lbl)
        inner.addWidget(title_lbl)
        inner.addWidget(desc_lbl)
        inner.addStretch()
        inner.addWidget(btn)
        cl.addLayout(inner)
        return card


# ── Home-specific extra styles ─────────────────────────────────────────────────
_HOME_EXTRA = f"""
    #homeContent {{ background: {C['surface']}; }}

    #card {{
        background: {C['card']};
        border: 1px solid {C['border']};
        border-radius: 12px;
    }}
    #card:hover {{
        border-color: {C['primary']};
        background: #FAFCFF;
    }}
    #cardTitle {{
        font-size: 15px; font-weight: 700;
        color: {C['ink']}; letter-spacing: -0.1px;
    }}
    #cardDesc {{
        font-size: 12px; color: {C['ink_soft']};
        line-height: 1.6;
    }}
"""
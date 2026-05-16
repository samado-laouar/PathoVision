from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from db.patient_dao import get_analyses_for_patient
from ui._style import BASE_QSS, C


class PatientHistory(QWidget):
    back_requested        = Signal()
    generate_pdf_requested = Signal(dict, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._patient  = None
        self._analyses = []
        self._build_ui()
        self.setStyleSheet(BASE_QSS + _PH_EXTRA)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Navbar
        navbar = QFrame()
        navbar.setObjectName("navbar")
        navbar.setFixedHeight(56)
        nl = QHBoxLayout(navbar)
        nl.setContentsMargins(24, 0, 24, 0)
        self.back_btn = QPushButton("← Back")
        self.back_btn.setObjectName("backBtn")
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self.back_requested.emit)
        self.patient_title = QLabel("")
        self.patient_title.setObjectName("navTitle")
        self.pdf_btn = QPushButton("Export PDF Report")
        self.pdf_btn.setObjectName("pdfBtn")
        self.pdf_btn.setFixedHeight(32)
        self.pdf_btn.setCursor(Qt.PointingHandCursor)
        self.pdf_btn.clicked.connect(self._request_pdf)
        nl.addWidget(self.back_btn)
        nl.addSpacing(12)
        nl.addWidget(self.patient_title)
        nl.addStretch()
        nl.addWidget(self.pdf_btn)
        layout.addWidget(navbar)

        # Content area
        content = QWidget()
        content.setObjectName("phContent")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(24, 20, 24, 20)
        cl.setSpacing(16)

        # Patient info card
        self.info_card = QFrame()
        self.info_card.setObjectName("infoCard")
        info_layout = QHBoxLayout(self.info_card)
        info_layout.setContentsMargins(24, 16, 24, 16)
        info_layout.setSpacing(36)
        self.info_labels = {}
        for field in ["Full Name", "Age", "Sex", "Tissue", "Marker", "Since"]:
            col = QVBoxLayout()
            col.setSpacing(3)
            key_lbl = QLabel(field)
            key_lbl.setObjectName("infoKey")
            val_lbl = QLabel("—")
            val_lbl.setObjectName("infoVal")
            col.addWidget(key_lbl)
            col.addWidget(val_lbl)
            info_layout.addLayout(col)
            self.info_labels[field] = val_lbl
        info_layout.addStretch()
        cl.addWidget(self.info_card)

        section = QLabel("Analysis History")
        section.setObjectName("sectionLabel")
        cl.addWidget(section)

        self.table = QTableWidget()
        self.table.setObjectName("historyTable")
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Date", "Type", "Result", "Confidence",
            "DAB Coverage", "DAB Regions", "Mean Intensity", "Doctor"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        cl.addWidget(self.table)
        layout.addWidget(content, 1)

    def load_patient(self, patient: dict):
        self._patient  = patient
        self._analyses = get_analyses_for_patient(patient["id"])

        full_name = f"{patient['first_name']} {patient['last_name']}"
        self.patient_title.setText(full_name)
        self.info_labels["Full Name"].setText(full_name)
        self.info_labels["Age"].setText(str(patient.get("age") or "—"))
        self.info_labels["Sex"].setText(patient.get("sexe") or "—")
        self.info_labels["Tissue"].setText(patient.get("tissue") or "—")
        self.info_labels["Marker"].setText(patient.get("marqueur") or "—")
        date = patient.get("created_at", "—")
        self.info_labels["Since"].setText(date[:10] if date else "—")

        self.table.setRowCount(0)
        for row, a in enumerate(self._analyses):
            self.table.insertRow(row)
            prob    = a.get("result_prob")
            conf_s  = f"{prob * 100:.1f}%" if prob is not None else "—"
            dab     = a.get("dab_coverage")
            dab_s   = f"{dab:.2f}%" if dab is not None else "—"
            mi      = a.get("mean_intensity")
            mi_s    = f"{mi:.1f}" if mi is not None else "—"
            values = [
                (a.get("created_at") or "")[:16],
                a.get("analysis_type") or "—",
                a.get("result_label") or "—",
                conf_s, dab_s,
                str(a.get("dab_regions") or "—"),
                mi_s,
                a.get("doctor_name") or "—",
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                if col == 2:
                    if val == "Pathologique":
                        item.setForeground(QColor(C["danger"]))
                    elif val == "Non Pathologique":
                        item.setForeground(QColor(C["success"]))
                self.table.setItem(row, col, item)

    def _request_pdf(self):
        if self._patient:
            self.generate_pdf_requested.emit(self._patient, self._analyses)


# ── Extra styles ───────────────────────────────────────────────────────────────
_PH_EXTRA = f"""
    QWidget {{  }}
    #phContent {{  }}

    #pdfBtn {{
        background: rgba(255,255,255,0.08);
        color: {C['nav_text']};
        border: 1px solid rgba(255,255,255,0.15);
        border-radius: 6px; font-size: 12px; font-weight: 500;
        padding: 0 12px;
    }}
    #pdfBtn:hover {{
        background: {C['primary']};
        color: white;
        border-color: {C['primary']};
    }}

    #infoCard {{
        background: {C['card']};
        border: 1px solid {C['border']};
        border-radius: 10px;
    }}
    #infoKey {{
        font-size: 10px; font-weight: 700;
        color: {C['ink_soft']};
        letter-spacing: 0.8px;
        text-transform: uppercase;
    }}
    #infoVal {{
        font-size: 14px; font-weight: 600;
        color: {C['ink']};
    }}
"""
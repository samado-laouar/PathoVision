from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame, QSplitter
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from db.patient_dao import get_patient_by_id, get_analyses_for_patient
import os


class PatientHistory(QWidget):
    back_requested = Signal()
    generate_pdf_requested = Signal(dict, list)   # patient, analyses

    def __init__(self, parent=None):
        super().__init__(parent)
        self._patient = None
        self._analyses = []
        self._build_ui()
        self._apply_styles()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)

        # Top bar
        top = QHBoxLayout()
        self.back_btn = QPushButton("← Back")
        self.back_btn.setObjectName("backBtn")
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self.back_requested.emit)
        self.patient_title = QLabel("")
        self.patient_title.setObjectName("pageTitle")
        self.pdf_btn = QPushButton("📄  Export PDF Report")
        self.pdf_btn.setObjectName("primaryBtn")
        self.pdf_btn.setFixedHeight(38)
        self.pdf_btn.setCursor(Qt.PointingHandCursor)
        self.pdf_btn.clicked.connect(self._request_pdf)
        top.addWidget(self.back_btn)
        top.addSpacing(16)
        top.addWidget(self.patient_title)
        top.addStretch()
        top.addWidget(self.pdf_btn)
        layout.addLayout(top)

        # Patient info card
        self.info_card = QFrame()
        self.info_card.setObjectName("infoCard")
        info_layout = QHBoxLayout(self.info_card)
        info_layout.setSpacing(32)

        self.info_labels = {}
        for field in ["Full Name", "Age", "Sex", "Tissue", "Marker", "Since"]:
            col = QVBoxLayout()
            col.setSpacing(2)
            key_lbl = QLabel(field)
            key_lbl.setObjectName("infoKey")
            val_lbl = QLabel("—")
            val_lbl.setObjectName("infoVal")
            col.addWidget(key_lbl)
            col.addWidget(val_lbl)
            info_layout.addLayout(col)
            self.info_labels[field] = val_lbl

        info_layout.addStretch()
        layout.addWidget(self.info_card)

        # Analyses table
        section = QLabel("Analysis History")
        section.setObjectName("sectionLabel")
        layout.addWidget(section)

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
        layout.addWidget(self.table)

    def load_patient(self, patient: dict):
        self._patient = patient
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
            prob = a.get("result_prob")
            conf_str = f"{prob*100:.1f}%" if prob is not None else "—"
            dab = a.get("dab_coverage")
            dab_str = f"{dab:.2f}%" if dab is not None else "—"
            mi = a.get("mean_intensity")
            mi_str = f"{mi:.1f}" if mi is not None else "—"

            values = [
                (a.get("created_at") or "")[:16],
                a.get("analysis_type") or "—",
                a.get("result_label") or "—",
                conf_str, dab_str,
                str(a.get("dab_regions") or "—"),
                mi_str,
                a.get("doctor_name") or "—"
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                # Color code result
                if col == 2:
                    if val == "Pathologique":
                        item.setForeground(Qt.red)
                    elif val == "Non Pathologique":
                        item.setForeground(Qt.darkGreen)
                self.table.setItem(row, col, item)

    def _request_pdf(self):
        if self._patient:
            self.generate_pdf_requested.emit(self._patient, self._analyses)

    def _apply_styles(self):
        self.setStyleSheet("""
            QWidget { background: #F8FAFB; font-family: 'Segoe UI'; }
            #pageTitle { font-size: 22px; font-weight: 700; color: #1A2B45; }
            #sectionLabel { font-size: 15px; font-weight: 600; color: #2E86C1; }

            #infoCard {
                background: #FFFFFF; border: 1px solid #E5E7EB;
                border-radius: 10px; padding: 16px 24px;
            }
            #infoKey { font-size: 11px; color: #95A5A6; font-weight: 600;
                       text-transform: uppercase; letter-spacing: 0.5px; }
            #infoVal { font-size: 15px; font-weight: 600; color: #1A2B45; }

            #historyTable {
                border: 1px solid #E5E7EB; border-radius: 8px;
                gridline-color: #F0F0F0; font-size: 13px;
            }
            QHeaderView::section {
                background: #EBF5FB; color: #1A5276; font-weight: 600;
                font-size: 13px; padding: 8px; border: none;
                border-bottom: 2px solid #AED6F1;
            }
            QTableWidget::item:selected { background: #D6EAF8; color: #1A2B45; }
            QTableWidget { alternate-background-color: #F7FBFE; }

            #backBtn {
                background: none; border: none; color: #2E86C1;
                font-size: 14px; font-weight: 600; padding: 0;
            }
            #backBtn:hover { color: #1A5276; }

            #primaryBtn {
                background: #2E86C1; color: white; border: none;
                border-radius: 7px; font-size: 13px; font-weight: 600; padding: 0 16px;
            }
            #primaryBtn:hover { background: #1A5276; }
        """)
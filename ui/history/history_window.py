from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QComboBox, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from db.patient_dao import get_all_analyses
from ui._style import BASE_QSS, C


class HistoryWindow(QWidget):
    patient_clicked = Signal(int)
    go_home         = Signal()

    def __init__(self, doctor: dict, parent=None):
        super().__init__(parent)
        self.doctor = doctor
        self._build_ui()
        self.setStyleSheet(BASE_QSS + _HIST_EXTRA)

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
        back_btn = QPushButton("← Home")
        back_btn.setObjectName("backBtn")
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(self.go_home.emit)
        nav_title = QLabel("All Analyses")
        nav_title.setObjectName("navTitle")
        nl.addWidget(back_btn)
        nl.addSpacing(12)
        nl.addWidget(nav_title)
        nl.addStretch()
        layout.addWidget(navbar)

        # Toolbar
        toolbar = QFrame()
        toolbar.setObjectName("toolbar")
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(24, 12, 24, 12)
        tl.setSpacing(10)

        title = QLabel("All Analyses")
        title.setObjectName("pageTitle")

        self.filter_combo = QComboBox()
        self.filter_combo.setObjectName("filterCombo")
        self.filter_combo.setFixedHeight(36)
        self.filter_combo.addItems(["All Doctors", "My Analyses Only"])
        self.filter_combo.currentIndexChanged.connect(self.refresh)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search patient name...")
        self.search_input.setObjectName("searchInput")
        self.search_input.setFixedHeight(36)
        self.search_input.setMinimumWidth(220)
        self.search_input.textChanged.connect(self._on_search)

        tl.addWidget(title)
        tl.addStretch()
        tl.addWidget(self.filter_combo)
        tl.addWidget(self.search_input)
        layout.addWidget(toolbar)

        # Table
        table_wrapper = QWidget()
        table_wrapper.setObjectName("tableArea")
        tw = QVBoxLayout(table_wrapper)
        tw.setContentsMargins(24, 0, 24, 16)
        tw.setSpacing(8)

        self.table = QTableWidget()
        self.table.setObjectName("historyTable")
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Date", "Patient", "Type", "Result", "Confidence",
            "DAB Coverage", "Regions", "Mean Intensity", "Doctor"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.doubleClicked.connect(self._on_row_double_click)
        tw.addWidget(self.table)

        hint = QLabel("Double-click a row to open the patient's full history.")
        hint.setObjectName("hintText")
        tw.addWidget(hint)
        layout.addWidget(table_wrapper, 1)

    def refresh(self):
        idx = self.filter_combo.currentIndex()
        doctor_id = self.doctor["id"] if idx == 1 else None
        self._all_data = get_all_analyses(doctor_id)
        self._populate(self._all_data)

    def _on_search(self, text):
        text = text.lower()
        filtered = [
            a for a in (self._all_data if hasattr(self, "_all_data") else [])
            if text in f"{a.get('first_name','')} {a.get('last_name','')}".lower()
        ]
        self._populate(filtered)

    def _populate(self, data):
        self.table.setRowCount(0)
        self._current_data = data
        for row, a in enumerate(data):
            self.table.insertRow(row)
            prob  = a.get("result_prob")
            conf  = f"{prob * 100:.1f}%" if prob is not None else "—"
            dab   = a.get("dab_coverage")
            dab_s = f"{dab:.2f}%" if dab is not None else "—"
            mi    = a.get("mean_intensity")
            mi_s  = f"{mi:.1f}" if mi is not None else "—"
            values = [
                (a.get("created_at") or "")[:16],
                f"{a.get('first_name','')} {a.get('last_name','')}",
                a.get("analysis_type") or "—",
                a.get("result_label") or "—",
                conf, dab_s,
                str(a.get("dab_regions") or "—"),
                mi_s,
                a.get("doctor_name") or "—",
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                if col == 3:
                    if val == "Pathologique":
                        item.setForeground(QColor(C["danger"]))
                    elif val == "Non Pathologique":
                        item.setForeground(QColor(C["success"]))
                self.table.setItem(row, col, item)

    def _on_row_double_click(self):
        row = self.table.currentRow()
        if row >= 0 and hasattr(self, "_current_data"):
            patient_id = self._current_data[row].get("patient_id")
            if patient_id:
                self.patient_clicked.emit(patient_id)


# ── Extra styles ───────────────────────────────────────────────────────────────
_HIST_EXTRA = f"""
    QWidget {{ }}
    #toolbar {{
        background: {C['card']};
        border-bottom: 1px solid {C['border']};
    }}
    #tableArea {{ background: {C['surface']}; padding-top: 16px; }}
"""
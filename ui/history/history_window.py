from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QComboBox
)
from PySide6.QtCore import Qt, Signal
from db.patient_dao import get_all_analyses


class HistoryWindow(QWidget):
    patient_clicked = Signal(int)   # emits patient_id
    go_home = Signal()

    def __init__(self, doctor: dict, parent=None):
        super().__init__(parent)
        self.doctor = doctor
        self._build_ui()
        self._apply_styles()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(14)

        # Header
        header = QHBoxLayout()
        back_btn = QPushButton("← Home")
        back_btn.setObjectName("backBtn")
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(self.go_home.emit)
        title = QLabel("All Analyses")
        title.setObjectName("pageTitle")
        self.filter_combo = QComboBox()
        self.filter_combo.setObjectName("filterCombo")
        self.filter_combo.setFixedHeight(36)
        self.filter_combo.addItems(["All Doctors", "My Analyses Only"])
        self.filter_combo.currentIndexChanged.connect(self.refresh)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍  Search patient name...")
        self.search_input.setObjectName("searchInput")
        self.search_input.setFixedHeight(36)
        self.search_input.textChanged.connect(self._on_search)
        header.addWidget(back_btn)
        header.addSpacing(16)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.filter_combo)
        header.addWidget(self.search_input)
        layout.addLayout(header)

        # Table
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
        self.table.doubleClicked.connect(self._on_row_double_click)
        layout.addWidget(self.table)

        hint = QLabel("Double-click a row to open the patient's full history.")
        hint.setObjectName("hintText")
        layout.addWidget(hint)

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
            prob = a.get("result_prob")
            conf = f"{prob*100:.1f}%" if prob is not None else "—"
            dab  = a.get("dab_coverage")
            dab_s = f"{dab:.2f}%" if dab is not None else "—"
            mi = a.get("mean_intensity")
            mi_s = f"{mi:.1f}" if mi is not None else "—"
            values = [
                (a.get("created_at") or "")[:16],
                f"{a.get('first_name','')} {a.get('last_name','')}",
                a.get("analysis_type") or "—",
                a.get("result_label") or "—",
                conf, dab_s,
                str(a.get("dab_regions") or "—"),
                mi_s,
                a.get("doctor_name") or "—"
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                if col == 3:
                    if val == "Pathologique":
                        item.setForeground(Qt.red)
                    elif val == "Non Pathologique":
                        item.setForeground(Qt.darkGreen)
                self.table.setItem(row, col, item)

    def _on_row_double_click(self):
        row = self.table.currentRow()
        if row >= 0 and hasattr(self, "_current_data"):
            patient_id = self._current_data[row].get("patient_id")
            if patient_id:
                self.patient_clicked.emit(patient_id)

    def _apply_styles(self):
        self.setStyleSheet("""
            QWidget { background: #F8FAFB; font-family: 'Segoe UI'; }
            #pageTitle { font-size: 22px; font-weight: 700; color: #1A2B45; }
            #hintText { font-size: 12px; color: #95A5A6; }
            #searchInput {
                border: 1.5px solid #D5D8DC; border-radius: 7px;
                padding: 0 12px; font-size: 13px; background: #FFF; min-width: 220px;
            }
            #searchInput:focus { border-color: #2E86C1; }
            #filterCombo {
                border: 1.5px solid #D5D8DC; border-radius: 7px;
                padding: 0 8px; font-size: 13px; background: #FFF;
            }
            #backBtn { background: none; border: none; color: #2E86C1;
                       font-size: 14px; font-weight: 600; padding: 0; }
            #backBtn:hover { color: #1A5276; }
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
        """)
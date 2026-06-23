"""
reports_tab.py - Historical posture reports viewer.
"""

from datetime import date, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QFrame, QPushButton, QCalendarWidget
)
from PyQt6.QtCore import Qt, QDate

from core import database as db


class ReportsTab(QWidget):
    """Shows a selectable date report with stats table and export option."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.load_report(date.today())

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(20)

        # ── Left: calendar ──────────────────────────────────────────────────
        left = QVBoxLayout()
        lbl = QLabel("Select Date")
        lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #8b949e;")
        left.addWidget(lbl)

        self._calendar = QCalendarWidget()
        self._calendar.setMaximumDate(QDate.currentDate())
        self._calendar.setStyleSheet("""
            QCalendarWidget { background: #161b22; color: #e6edf3; border: 1px solid #30363d; border-radius: 8px; }
            QCalendarWidget QAbstractItemView { background: #161b22; color: #e6edf3; selection-background-color: #1f3a6e; }
            QCalendarWidget QToolButton { color: #e6edf3; background: transparent; }
            QCalendarWidget QMenu { background: #161b22; color: #e6edf3; }
            QCalendarWidget QSpinBox { background: #21262d; color: #e6edf3; }
        """)
        self._calendar.selectionChanged.connect(self._on_date_selected)
        left.addWidget(self._calendar)
        left.addStretch()
        root.addLayout(left)

        # ── Right: data ─────────────────────────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(12)

        title = QLabel("Daily Report")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #e6edf3;")
        self._date_lbl = QLabel(date.today().strftime("%A, %B %d %Y"))
        self._date_lbl.setStyleSheet("color: #8b949e; font-size: 13px;")
        right.addWidget(title)
        right.addWidget(self._date_lbl)
        right.addWidget(self._h_line())

        # Stat table
        self._table = QTableWidget(6, 2)
        self._table.setHorizontalHeaderLabels(["Metric", "Value"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setMaximumHeight(260)

        metrics = [
            "Posture Score",
            "Total Sitting Time",
            "Slouch Events",
            "Total Slouch Duration",
            "Longest Slouch",
            "Active Sessions",
        ]
        for i, m in enumerate(metrics):
            self._table.setItem(i, 0, QTableWidgetItem(f"  {m}"))
            self._table.setItem(i, 1, QTableWidgetItem("—"))

        right.addWidget(self._table)

        export_btn = QPushButton("📄  Export PDF Report")
        export_btn.clicked.connect(self._on_export)
        right.addWidget(export_btn)

        right.addStretch()
        root.addLayout(right)

    # ── Public / internal ─────────────────────────────────────────────────────

    def _on_date_selected(self):
        qd = self._calendar.selectedDate()
        d = date(qd.year(), qd.month(), qd.day())
        self.load_report(d)

    def load_report(self, target_date: date):
        data = db.get_daily_report(target_date)
        self._date_lbl.setText(target_date.strftime("%A, %B %d %Y"))

        score  = data.get("daily_posture_score", 100.0)
        sit    = data.get("total_sitting_duration_sec", 0)
        count  = data.get("slouch_count", 0)
        slch   = data.get("total_slouch_duration_sec", 0)
        longest = data.get("longest_slouch_duration_sec", 0)

        values = [
            f"{score:.1f} / 100",
            self._fmt_time(sit),
            str(count),
            self._fmt_time(slch),
            f"{longest} sec",
            "—",  # sessions count placeholder
        ]
        for i, v in enumerate(values):
            self._table.setItem(i, 1, QTableWidgetItem(f"  {v}"))

    def _on_export(self):
        """Placeholder PDF export — will be wired to reportlab in v3."""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, "Export",
            "PDF export will be available in Version 3.\n"
            "Data is stored in config/posture.db for manual export."
        )

    @staticmethod
    def _fmt_time(seconds: int) -> str:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:
            return f"{h}h {m}m"
        elif m > 0:
            return f"{m}m {s}s"
        return f"{s}s"

    @staticmethod
    def _h_line() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("border-color: #30363d;")
        return line

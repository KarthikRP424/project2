"""
dashboard_tab.py - Daily posture analytics dashboard.

Shows today's posture score as a radial gauge, 4 stat cards,
and a 7-day trend bar chart powered by PyQtGraph.
"""

import math
from datetime import timedelta, date

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QGridLayout
)
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QBrush, QLinearGradient

try:
    import pyqtgraph as pg
    pg.setConfigOption("background", "#0d1117")
    pg.setConfigOption("foreground", "#8b949e")
    _PG_AVAILABLE = True
except ImportError:
    _PG_AVAILABLE = False

from core import database as db


class ScoreGauge(QWidget):
    """Custom circular arc gauge that shows posture score 0–100."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._score = 100.0
        self.setMinimumSize(180, 180)

    def set_score(self, score: float):
        self._score = max(0.0, min(100.0, score))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        side = min(self.width(), self.height()) - 20
        x = (self.width() - side) // 2
        y = (self.height() - side) // 2
        rect = QRectF(x, y, side, side)

        # Track arc (background)
        pen = QPen(QColor("#21262d"), 14, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, 225 * 16, -270 * 16)

        # Score arc (foreground gradient)
        score_color = self._score_to_color(self._score)
        pen2 = QPen(QColor(score_color), 14, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen2)
        span = int(-270 * 16 * (self._score / 100.0))
        p.drawArc(rect, 225 * 16, span)

        # Center text
        p.setPen(QColor("#e6edf3"))
        font = QFont("Segoe UI", int(side * 0.22), QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{int(self._score)}")

        # Label below score
        p.setPen(QColor("#8b949e"))
        font2 = QFont("Segoe UI", int(side * 0.08))
        p.setFont(font2)
        label_rect = QRectF(x, y + side * 0.6, side, side * 0.25)
        p.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, "Posture Score")

    @staticmethod
    def _score_to_color(score: float) -> str:
        if score >= 80:
            return "#22c55e"
        elif score >= 55:
            return "#f59e0b"
        else:
            return "#ef4444"


class StatCard(QFrame):
    """A compact metric card with title, value, and optional unit."""

    def __init__(self, title: str, value: str = "—", unit: str = "", color: str = "#4f8ef7", parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setObjectName("stat_card")
        self.setStyleSheet(f"""
            QFrame#stat_card {{
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 12px;
                padding: 4px;
            }}
            QFrame#stat_card:hover {{ border-color: {color}; }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        self._title_lbl = QLabel(title)
        self._title_lbl.setStyleSheet("color: #8b949e; font-size: 12px; font-weight: 500;")

        self._value_lbl = QLabel(value)
        self._value_lbl.setStyleSheet(
            f"color: {color}; font-size: 26px; font-weight: 700;"
        )

        self._unit_lbl = QLabel(unit)
        self._unit_lbl.setStyleSheet("color: #484f58; font-size: 11px;")

        layout.addWidget(self._title_lbl)
        layout.addWidget(self._value_lbl)
        layout.addWidget(self._unit_lbl)

    def update_value(self, value: str):
        self._value_lbl.setText(value)


class DashboardTab(QWidget):
    """Main analytics dashboard with gauge, stat cards, and weekly bar chart."""

    def __init__(self, on_new_session=None, parent=None):
        super().__init__(parent)
        self._on_new_session = on_new_session
        self._build_ui()

        # Refresh dashboard every 30 seconds
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(30_000)
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(20)

        # ── Header ─────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("Dashboard")
        title.setObjectName("section_title")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #e6edf3;")
        sub = QLabel("Track your daily posture health")
        sub.setObjectName("subtitle")

        hdr.addWidget(title)
        hdr.addStretch()
        if self._on_new_session:
            btn = QPushButton("▶  Start Session")
            btn.setObjectName("btn_primary")
            btn.clicked.connect(self._on_new_session)
            hdr.addWidget(btn)

        root.addLayout(hdr)
        root.addWidget(self._h_line())

        # ── Gauge + Stat cards ─────────────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(16)

        self._gauge = ScoreGauge()
        top.addWidget(self._gauge)

        grid = QGridLayout()
        grid.setSpacing(12)

        self._card_score   = StatCard("Today's Score",   "100",  "/100",  "#22c55e")
        self._card_time    = StatCard("Session Time",     "0",    "min",   "#4f8ef7")
        self._card_slouch  = StatCard("Slouch Events",    "0",    "today", "#f59e0b")
        self._card_longest = StatCard("Longest Slouch",   "0",    "sec",   "#ef4444")

        grid.addWidget(self._card_score,   0, 0)
        grid.addWidget(self._card_time,    0, 1)
        grid.addWidget(self._card_slouch,  1, 0)
        grid.addWidget(self._card_longest, 1, 1)

        top.addLayout(grid)
        root.addLayout(top)

        # ── Weekly chart ───────────────────────────────────────────────────
        chart_lbl = QLabel("7-Day Posture Score Trend")
        chart_lbl.setStyleSheet("color: #8b949e; font-weight: 600; font-size: 13px;")
        root.addWidget(chart_lbl)

        if _PG_AVAILABLE:
            self._chart = pg.PlotWidget()
            self._chart.setMinimumHeight(200)
            self._chart.showGrid(x=False, y=True, alpha=0.2)
            self._chart.setYRange(0, 105)
            self._chart.getAxis("bottom").setTextPen("#8b949e")
            self._chart.getAxis("left").setTextPen("#8b949e")
            self._chart.setBackground("#161b22")
            self._bar_item = None
            root.addWidget(self._chart)
        else:
            root.addWidget(QLabel("Install pyqtgraph for weekly chart."))

        root.addStretch()

    def refresh(self):
        """Reload today's stats from DB and update all widgets."""
        today = db.get_daily_report()
        score = today.get("daily_posture_score", 100.0)
        total_sec = today.get("total_sitting_duration_sec", 0)
        slouch_count = today.get("slouch_count", 0)
        longest = today.get("longest_slouch_duration_sec", 0)

        self._gauge.set_score(score)
        self._card_score.update_value(str(int(score)))
        self._card_time.update_value(str(total_sec // 60))
        self._card_slouch.update_value(str(slouch_count))
        self._card_longest.update_value(str(longest))

        self._update_chart()

    def update_stats(self, data: dict):
        """Live update from session (called by main window)."""
        score = data.get("score", 100.0)
        self._gauge.set_score(score)
        self._card_score.update_value(str(int(score)))
        self._card_time.update_value(str(data.get("elapsed_min", 0)))
        self._card_slouch.update_value(str(data.get("slouch_count", 0)))

    def _update_chart(self):
        if not _PG_AVAILABLE:
            return
        weekly = db.get_weekly_data()
        scores = [d.get("daily_posture_score", 0.0) for d in weekly]
        days   = [(date.today() - timedelta(days=6 - i)).strftime("%a") for i in range(7)]

        if self._bar_item:
            self._chart.removeItem(self._bar_item)

        colors = [
            (34, 197, 94) if s >= 80 else (245, 158, 11) if s >= 55 else (239, 68, 68)
            for s in scores
        ]
        brushes = [pg.mkBrush(*c) for c in colors]
        self._bar_item = pg.BarGraphItem(
            x=range(7), height=scores, width=0.6,
            brushes=brushes, pen=pg.mkPen(None)
        )
        self._chart.addItem(self._bar_item)
        ax = self._chart.getAxis("bottom")
        ax.setTicks([list(enumerate(days))])

    @staticmethod
    def _h_line() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("border-color: #30363d;")
        return line

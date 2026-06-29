"""
monitor_tab.py - Live posture monitoring tab.

Shows the webcam feed with skeleton overlay, current angle and status,
calibration controls, and mode selector.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSlider, QFrame, QProgressBar, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QFont, QColor


MODES = ["Camera AI", "Android Sensor", "ESP32 Wearable"]

STATUS_COLORS = {
    "GOOD":         ("#22c55e", "#052e16"),
    "SLIGHT":       ("#f59e0b", "#1c1a05"),
    "warning":      ("#f97316", "#2c1103"),
    "BAD":          ("#ef4444", "#2e0505"),
    "dangerous":    ("#ef4444", "#2e0505"),
    "NO_DETECTION": ("#8b949e", "#1a1f26"),
}


class MonitorTab(QWidget):
    """Live monitoring panel: webcam feed + real-time posture controls."""

    # ── Signals (to main window) ──────────────────────────────────────────────
    mode_changed      = pyqtSignal(str)
    calibrate_clicked = pyqtSignal()
    start_clicked     = pyqtSignal()
    stop_clicked      = pyqtSignal()
    threshold_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._session_active = False
        self._calib_countdown = 0
        self._calib_timer = QTimer(self)
        self._calib_timer.timeout.connect(self._tick_calibration)
        self._build_ui()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(20)

        # ── Left: camera feed ───────────────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(8)

        title = QLabel("Live Monitor")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #e6edf3;")
        left.addWidget(title)

        self._feed_label = QLabel()
        self._feed_label.setFixedSize(640, 480)
        self._feed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._feed_label.setStyleSheet(
            "background-color: #161b22; border: 2px solid #30363d; border-radius: 12px;"
        )
        self._feed_label.setText("📷 Camera feed will appear here\nPress Start to begin")
        self._feed_label.setWordWrap(True)
        left.addWidget(self._feed_label)

        root.addLayout(left)

        # ── Right: controls ─────────────────────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(12)
        right.setContentsMargins(0, 0, 0, 0)

        # Mode selector
        mode_grp = self._group_box("Detection Mode")
        mg_layout = QVBoxLayout()
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(MODES)
        self._mode_combo.currentTextChanged.connect(self.mode_changed.emit)
        mg_layout.addWidget(self._mode_combo)
        mode_grp.setLayout(mg_layout)
        right.addWidget(mode_grp)

        # Status panel
        stat_grp = self._group_box("Posture Status")
        sg_layout = QVBoxLayout()
        sg_layout.setSpacing(10)

        self._status_badge = QLabel("NOT STARTED")
        self._status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_badge.setStyleSheet(
            "font-size: 20px; font-weight: 700; color: #8b949e;"
            "background: #1a1f26; border-radius: 8px; padding: 10px;"
        )
        sg_layout.addWidget(self._status_badge)

        self._angle_label = QLabel("Angle: -- °")
        self._angle_label.setStyleSheet("color: #8b949e; font-size: 14px;")
        self._angle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._deviation_label = QLabel("Deviation: -- °")
        self._deviation_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        self._deviation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._bad_count_label = QLabel("Bad Posture Count: 0")
        self._bad_count_label.setStyleSheet("color: #8b949e; font-size: 13px; font-weight: bold;")
        self._bad_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._alert_status_label = QLabel("Alert Status: Idle")
        self._alert_status_label.setStyleSheet("color: #8b949e; font-size: 13px; font-weight: bold;")
        self._alert_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._held_bar = QProgressBar()
        self._held_bar.setRange(0, 100)
        self._held_bar.setValue(0)
        self._held_bar.setTextVisible(False)
        self._held_bar.setFixedHeight(8)
        self._held_bar.setStyleSheet("""
            QProgressBar { background: #21262d; border-radius: 4px; border: none; }
            QProgressBar::chunk { background: #4f8ef7; border-radius: 4px; }
        """)

        sg_layout.addWidget(self._angle_label)
        sg_layout.addWidget(self._deviation_label)
        sg_layout.addWidget(self._bad_count_label)
        sg_layout.addWidget(self._alert_status_label)
        sg_layout.addWidget(QLabel("Bad posture hold progress:"))
        sg_layout.addWidget(self._held_bar)
        stat_grp.setLayout(sg_layout)
        right.addWidget(stat_grp)

        # Calibrate
        calib_grp = self._group_box("Calibration")
        cl_layout = QVBoxLayout()
        cl_layout.setSpacing(6)
        calib_hint = QLabel("Sit upright and click Calibrate.\nHold still for 5 seconds.")
        calib_hint.setStyleSheet("color: #8b949e; font-size: 12px;")
        calib_hint.setWordWrap(True)

        self._calib_btn = QPushButton("🎯  Calibrate Good Posture")
        self._calib_btn.setObjectName("btn_primary")
        self._calib_btn.clicked.connect(self._on_calibrate_click)

        self._calib_status = QLabel("")
        self._calib_status.setStyleSheet("color: #22c55e; font-size: 12px;")
        self._calib_status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cl_layout.addWidget(calib_hint)
        cl_layout.addWidget(self._calib_btn)
        cl_layout.addWidget(self._calib_status)
        calib_grp.setLayout(cl_layout)
        right.addWidget(calib_grp)

        # Threshold slider
        thresh_grp = self._group_box("Alert Threshold")
        th_layout = QVBoxLayout()
        self._thresh_slider = QSlider(Qt.Orientation.Horizontal)
        self._thresh_slider.setRange(5, 60)
        self._thresh_slider.setValue(10)
        self._thresh_slider.setTickInterval(5)
        self._thresh_label = QLabel("Alert after  10  seconds of bad posture")
        self._thresh_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        self._thresh_slider.valueChanged.connect(self._on_threshold_change)
        th_layout.addWidget(self._thresh_label)
        th_layout.addWidget(self._thresh_slider)
        thresh_grp.setLayout(th_layout)
        right.addWidget(thresh_grp)

        # Start / Stop
        self._start_btn = QPushButton("▶  Start Monitoring")
        self._start_btn.setObjectName("btn_success")
        self._start_btn.clicked.connect(self._on_start_stop)
        right.addWidget(self._start_btn)

        right.addStretch()
        right_widget = QWidget()
        right_widget.setLayout(right)
        right_widget.setMaximumWidth(340)
        root.addWidget(right_widget)

    # ── Public API ────────────────────────────────────────────────────────────

    def update_frame(self, img: QImage):
        """Update the webcam preview with a new annotated frame."""
        pix = QPixmap.fromImage(img).scaled(
            640, 480,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._feed_label.setPixmap(pix)

    def update_status(self, status: str, angle: float, deviation: float, bad_count: int = 0, alert_status: str = "Idle"):
        """Refresh the status badge, angle labels, bad posture count, and alert status."""
        fg, bg = STATUS_COLORS.get(status, ("#8b949e", "#1a1f26"))
        labels = {
            "GOOD":         "✅  GOOD POSTURE",
            "SLIGHT":       "⚠️  SLIGHT BEND",
            "warning":      "⚠️  POSTURE WARNING",
            "BAD":          "🚨  BAD POSTURE",
            "dangerous":    "🚨  DANGEROUS POSTURE",
            "NO_DETECTION": "🔍  NOT CALIBRATED",
        }
        self._status_badge.setText(labels.get(status, status))
        self._status_badge.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {fg};"
            f"background: {bg}; border-radius: 8px; padding: 10px;"
        )
        self._angle_label.setText(f"Angle: {angle:.1f} °")
        self._deviation_label.setText(f"Deviation from reference: {deviation:.1f} °")
        self._bad_count_label.setText(f"Bad Posture Count: {bad_count}")
        self._alert_status_label.setText(f"Alert Status: {alert_status}")

        # Progress bar: held duration as % of threshold
        from core.alert_manager import AlertManager
        # Value updated by main window via update_held_progress
        
    def update_held_progress(self, held_sec: float, threshold_sec: int):
        pct = int(min(100, (held_sec / max(1, threshold_sec)) * 100))
        self._held_bar.setValue(pct)
        if pct > 80:
            self._held_bar.setStyleSheet("""
                QProgressBar { background: #21262d; border-radius: 4px; border: none; }
                QProgressBar::chunk { background: #ef4444; border-radius: 4px; }
            """)
        else:
            self._held_bar.setStyleSheet("""
                QProgressBar { background: #21262d; border-radius: 4px; border: none; }
                QProgressBar::chunk { background: #4f8ef7; border-radius: 4px; }
            """)

    def show_calibration_result(self, angle: float):
        self._calib_status.setText(f"✓ Calibrated at {angle:.1f}°")
        self._calib_btn.setText("🎯  Re-Calibrate")
        self._calib_btn.setEnabled(True)
        self._calib_countdown = 0

    # ── Internals ─────────────────────────────────────────────────────────────

    def _on_start_stop(self):
        if not self._session_active:
            self._session_active = True
            self._start_btn.setText("⏹  Stop Monitoring")
            self._start_btn.setObjectName("btn_danger")
            self._start_btn.setStyleSheet(
                "background-color: #b91c1c; border-color: #b91c1c; color: white; "
                "font-weight: 600; padding: 10px 24px; border-radius: 8px;"
            )
            self.start_clicked.emit()
        else:
            self._session_active = False
            self._start_btn.setText("▶  Start Monitoring")
            self._start_btn.setObjectName("btn_success")
            self._start_btn.setStyleSheet(
                "background-color: #166534; border-color: #166534; color: white; "
                "font-weight: 600; padding: 10px 24px; border-radius: 8px;"
            )
            self.stop_clicked.emit()

    def _on_calibrate_click(self):
        self._calib_countdown = 5
        self._calib_btn.setEnabled(False)
        self._calib_btn.setText("Collecting… 5s")
        self._calib_timer.start(1000)
        self.calibrate_clicked.emit()

    def _tick_calibration(self):
        self._calib_countdown -= 1
        if self._calib_countdown > 0:
            self._calib_btn.setText(f"Collecting… {self._calib_countdown}s")
        else:
            self._calib_timer.stop()
            self._calib_btn.setText("Processing…")

    def _on_threshold_change(self, value: int):
        self._thresh_label.setText(f"Alert after  {value}  seconds of bad posture")
        self.threshold_changed.emit(value)

    @staticmethod
    def _group_box(title: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("group_box")
        frame.setStyleSheet("""
            QFrame#group_box {
                border: 1px solid #30363d;
                border-radius: 10px;
                padding: 8px;
            }
        """)
        lbl = QLabel(f"  {title}")
        lbl.setStyleSheet(
            "color: #8b949e; font-size: 11px; font-weight: 600; letter-spacing: 0.05em;"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.addWidget(lbl)
        return frame

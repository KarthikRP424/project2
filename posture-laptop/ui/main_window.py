"""
main_window.py - PostureGuard PyQt6 main application window.

Houses the sidebar navigation and content area with all tabs.
Orchestrates workers (CameraWorker, SensorWorker) and sessions.
"""

import os
import time
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QStackedWidget, QStatusBar, QFrame, QApplication, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPalette, QColor

from ui.dashboard_tab  import DashboardTab
from ui.monitor_tab    import MonitorTab
from ui.devices_tab    import DevicesTab
from ui.reports_tab    import ReportsTab
from ui.settings_tab   import SettingsTab, load_settings
from workers.camera_worker import CameraWorker
from workers.sensor_worker import SensorWorker
from core import database as db


class SystemWarningPopup(QWidget):
    """A floating, always-on-top, non-blocking toast warning popup."""
    
    def __init__(self, title: str, message: str, severity: str, parent=None):
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        # Style based on severity
        bg_colors = {
            "warning": "#1c1a05",
            "bad": "#2e0505",
            "dangerous": "#400404"
        }
        border_colors = {
            "warning": "#f59e0b",
            "bad": "#ef4444",
            "dangerous": "#ff0000"
        }
        text_colors = {
            "warning": "#f59e0b",
            "bad": "#ef4444",
            "dangerous": "#ff3333"
        }
        
        bg = bg_colors.get(severity, "#161b22")
        border = border_colors.get(severity, "#30363d")
        text_col = text_colors.get(severity, "#e6edf3")
        
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg};
                border: 2px solid {border};
                border-radius: 8px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {text_col};")
        
        msg_lbl = QLabel(message)
        msg_lbl.setStyleSheet("font-size: 12px; color: #e6edf3;")
        msg_lbl.setWordWrap(True)
        
        layout.addWidget(title_lbl)
        layout.addWidget(msg_lbl)
        
        self.setFixedSize(320, 90)
        
        # Position in top-right corner of primary screen
        screen = QApplication.primaryScreen()
        rect = screen.availableGeometry()
        x = rect.width() - self.width() - 20
        y = 50
        self.move(x, y)
        
        # Auto close after 3 seconds
        QTimer.singleShot(3000, self.close)


class MainWindow(QMainWindow):
    """Top-level application window with sidebar and stacked content."""

    def __init__(self):
        super().__init__()
        self._settings           = load_settings()
        self._user_id            = db.create_or_get_user(self._settings.get("username", "default"))
        self._session_id         = 0
        self._session_start_time = 0.0
        self._slouch_count       = 0
        self._last_status        = "NO_DETECTION"
        self._session_score      = 100.0
        self._threshold_sec      = self._settings.get("alert_threshold", 10)
        # Cached stats for periodic dashboard refresh (avoids per-frame updates)
        self._cached_stats: dict = {}

        self._cam_worker: CameraWorker     = None
        self._sensor_worker: SensorWorker  = None

        self.setWindowTitle("PostureGuard  –  Smart Posture Correction")
        self.setMinimumSize(1280, 780)

        self._load_stylesheet()
        self._build_ui()
        self._start_sensor_worker()

        # Live progress bar refresh (every 500 ms) — very cheap
        self._progress_timer = QTimer(self)
        self._progress_timer.timeout.connect(self._refresh_held_progress)
        self._progress_timer.start(500)

        # Dashboard stats refresh (every 5 s during session) — avoids per-frame DB queries
        self._dashboard_timer = QTimer(self)
        self._dashboard_timer.timeout.connect(self._periodic_dashboard_refresh)
        self._dashboard_timer.start(5000)

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Sidebar
        outer.addWidget(self._build_sidebar())

        # Content area
        self._stack = QStackedWidget()
        self._stack.setObjectName("content_area")

        self._dashboard = DashboardTab(on_new_session=self._on_start_session)
        self._monitor   = MonitorTab()
        self._devices   = DevicesTab()
        self._reports   = ReportsTab()
        self._settings_tab = SettingsTab()

        self._stack.addWidget(self._dashboard)   # 0
        self._stack.addWidget(self._monitor)     # 1
        self._stack.addWidget(self._devices)     # 2
        self._stack.addWidget(self._reports)     # 3
        self._stack.addWidget(self._settings_tab) # 4

        outer.addWidget(self._stack)

        # Status bar
        self.statusBar().showMessage("Ready  •  No active session")
        self._android_status_lbl = QLabel("📱 Android: Not connected")
        self._android_status_lbl.setStyleSheet("color: #484f58; font-size: 11px; padding: 0 12px;")
        self.statusBar().addPermanentWidget(self._android_status_lbl)

        # Connect monitor tab signals
        self._monitor.start_clicked.connect(self._on_start_session)
        self._monitor.stop_clicked.connect(self._on_stop_session)
        self._monitor.calibrate_clicked.connect(self._on_calibrate)
        self._monitor.threshold_changed.connect(self._on_threshold_change)

        # Connect devices tab signals
        self._devices.scan_requested.connect(self._on_ble_scan)
        self._devices.connect_requested.connect(self._on_ble_connect)
        self._devices.disconnect_requested.connect(self._on_ble_disconnect)

        # Connect settings
        self._settings_tab.settings_saved.connect(self._on_settings_saved)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Logo
        logo = QLabel("🧘 PostureGuard")
        logo.setObjectName("logo_label")
        logo.setStyleSheet(
            "color: #4f8ef7; font-size: 18px; font-weight: 700; "
            "padding: 24px 16px 4px 16px;"
        )
        ver = QLabel("v1.0  –  Smart Posture AI")
        ver.setObjectName("version_label")
        ver.setStyleSheet("color: #484f58; font-size: 10px; padding: 0 16px 16px 16px;")

        layout.addWidget(logo)
        layout.addWidget(ver)
        layout.addWidget(self._sidebar_divider())

        nav_items = [
            ("🏠", "Dashboard",    0),
            ("📡", "Live Monitor", 1),
            ("🔵", "Devices",      2),
            ("📊", "Reports",      3),
            ("⚙️", "Settings",    4),
        ]
        self._nav_buttons = []
        for icon, label, idx in nav_items:
            btn = QPushButton(f"  {icon}  {label}")
            btn.setCheckable(True)
            btn.setProperty("active", False)
            btn.clicked.connect(lambda checked, i=idx: self._switch_tab(i))
            btn.setStyleSheet(self._nav_btn_style(False))
            layout.addWidget(btn)
            self._nav_buttons.append(btn)

        self._nav_buttons[0].setChecked(True)
        self._set_active_nav(0)

        layout.addStretch()

        # Session indicator
        self._session_lbl = QLabel("⚪  No Active Session")
        self._session_lbl.setStyleSheet(
            "color: #484f58; font-size: 11px; padding: 12px 16px;"
        )
        self._session_lbl.setWordWrap(True)
        layout.addWidget(self._sidebar_divider())
        layout.addWidget(self._session_lbl)

        return sidebar

    # ── Navigation ────────────────────────────────────────────────────────────

    def _switch_tab(self, index: int):
        self._stack.setCurrentIndex(index)
        self._set_active_nav(index)
        # Refresh dashboard immediately when the user navigates to it
        if index == 0:
            self._dashboard.refresh()

    def _set_active_nav(self, active_idx: int):
        for i, btn in enumerate(self._nav_buttons):
            active = i == active_idx
            btn.setStyleSheet(self._nav_btn_style(active))

    @staticmethod
    def _nav_btn_style(active: bool) -> str:
        if active:
            return (
                "QPushButton { background-color: #1f3a6e; border: none; border-left: 3px solid #4f8ef7; "
                "border-radius: 0px; color: #4f8ef7; font-size: 13px; font-weight: 600; "
                "padding: 12px 16px; text-align: left; margin: 2px 0; }"
            )
        return (
            "QPushButton { background: transparent; border: none; border-radius: 8px; "
            "color: #8b949e; font-size: 13px; font-weight: 500; "
            "padding: 12px 16px; text-align: left; margin: 2px 8px; }"
            "QPushButton:hover { background-color: #21262d; color: #e6edf3; }"
        )

    # ── Session lifecycle ─────────────────────────────────────────────────────

    @pyqtSlot()
    def _on_start_session(self):
        if self._cam_worker and self._cam_worker.isRunning():
            return
        mode = "CAMERA"
        self._session_id         = db.start_session(self._user_id, mode)
        self._session_score      = 100.0
        self._cached_stats       = {}
        self._session_start_time = time.time()
        self._slouch_count = 0
        self._cam_worker = CameraWorker(
            camera_index=self._settings.get("camera_index", 0),
            user_id=self._user_id,
            session_id=self._session_id,
            dangerous_threshold=float(self._settings.get("dangerous_threshold", 25.0)),
        )
        self._cam_worker.set_threshold(self._threshold_sec)

        # Wire signals
        self._cam_worker.frame_ready.connect(self._monitor.update_frame)
        self._cam_worker.status_update.connect(self._on_status_update)
        self._cam_worker.alert_fired.connect(self._on_alert_fired)
        self._cam_worker.calibration_done.connect(self._on_calibration_done)
        self._cam_worker.error_occurred.connect(self._on_camera_error)
        self._cam_worker.show_popup.connect(self.show_system_warning)

        # Load existing calibration if available
        cal = db.get_calibration(self._user_id, "CAMERA")
        if cal:
            self._cam_worker.analyzer.set_reference(cal["angle1"])

        self._cam_worker.start()
        self._session_lbl.setText("🟢  Session Active")
        self.statusBar().showMessage("Monitoring active  •  Keep good posture!")

        # Switch to monitor tab
        self._switch_tab(1)

    @pyqtSlot()
    def _on_stop_session(self):
        if self._cam_worker:
            self._cam_worker.stop()
            self._cam_worker.wait(2000)
            elapsed = int(time.time() - self._session_start_time)
            db.end_session(self._session_id, self._session_score, elapsed)
            self._cam_worker = None

        self._session_lbl.setText("⚪  No Active Session")
        self.statusBar().showMessage("Session ended  •  Check dashboard for stats")
        self._monitor.update_held_progress(0, self._threshold_sec)
        self._dashboard.refresh()

    @pyqtSlot()
    def _on_calibrate(self):
        if self._cam_worker and self._cam_worker.isRunning():
            self._cam_worker.start_calibration()

    @pyqtSlot(int)
    def _on_threshold_change(self, value: int):
        self._threshold_sec = value
        if self._cam_worker:
            self._cam_worker.set_threshold(value)

    # ── Status/alert handlers ─────────────────────────────────────────────────

    @pyqtSlot(str, float, float, int, str)
    def _on_status_update(self, status: str, angle: float, deviation: float, bad_count: int, alert_status: str):
        # Deduct score on transition into dangerous (not every frame)
        if status == "dangerous" and self._last_status != "dangerous":
            self._session_score = max(0.0, self._session_score - 5.0)

        self._last_status  = status
        self._slouch_count = bad_count

        # Update the Live Monitor panel labels (already throttled to 500 ms by the worker)
        self._monitor.update_status(status, angle, deviation, bad_count, alert_status)

        # Cache stats for the periodic dashboard refresh (do NOT call dashboard here)
        elapsed_min = int((time.time() - self._session_start_time) / 60) if self._session_start_time else 0
        self._cached_stats = {
            "score":        self._session_score,
            "elapsed_min":  elapsed_min,
            "slouch_count": self._slouch_count,
        }

    @pyqtSlot(str, float)
    def _on_alert_fired(self, status: str, held_sec: float):
        # Non-blocking status bar message only — never use QMessageBox here
        # (a modal dialog blocks the entire event loop and freezes the camera)
        self.statusBar().showMessage(
            f"⚠️  Bad posture held for {int(held_sec)}s — please sit straight!", 8000
        )

    @pyqtSlot(str, str, str)
    def show_system_warning(self, title: str, message: str, severity: str):
        """Displays a custom frameless, always-on-top popup overlay."""
        self._popup_win = SystemWarningPopup(title, message, severity)
        self._popup_win.show()

        # Trigger Android vibration
        if self._sensor_worker and self._settings.get("alert_vibration", True):
            self._sensor_worker.send_android_vibrate()
        # Trigger BLE alert
        if self._sensor_worker and self._cam_worker:
            self._sensor_worker.send_ble_alert()

    @pyqtSlot(float)
    def _on_calibration_done(self, angle: float):
        self._monitor.show_calibration_result(angle)
        self.statusBar().showMessage(f"✓ Calibration complete  •  Reference: {angle:.1f}°", 5000)

    @pyqtSlot(str)
    def _on_camera_error(self, msg: str):
        QMessageBox.critical(self, "Camera Error", msg)
        self._on_stop_session()

    def _periodic_dashboard_refresh(self):
        """Called by QTimer every 5 s. Only updates if a session is active."""
        if self._cam_worker and self._cam_worker.isRunning() and self._cached_stats:
            self._dashboard.update_stats(self._cached_stats)

    def _refresh_held_progress(self):
        if self._cam_worker and self._cam_worker.isRunning():
            held = self._cam_worker.alert_mgr.get_held_duration()
            self._monitor.update_held_progress(held, self._threshold_sec)

    # ── BLE / devices ─────────────────────────────────────────────────────────

    def _start_sensor_worker(self):
        self._sensor_worker = SensorWorker()
        self._sensor_worker.ble_status.connect(self._devices.set_ble_status)
        self._sensor_worker.android_status.connect(self._on_android_status)
        self._sensor_worker.ble_devices_found.connect(self._devices.populate_devices)
        self._sensor_worker.sensor_data.connect(self._on_sensor_data)
        self._sensor_worker.start()

    @pyqtSlot()
    def _on_ble_scan(self):
        if self._sensor_worker:
            self._sensor_worker.scan_ble()

    @pyqtSlot(str)
    def _on_ble_connect(self, address: str):
        if self._sensor_worker:
            self._sensor_worker.connect_ble(address)

    @pyqtSlot()
    def _on_ble_disconnect(self):
        if self._sensor_worker:
            self._sensor_worker.disconnect_ble()

    @pyqtSlot(float, float)
    def _on_sensor_data(self, pitch: float, roll: float):
        # Sensor data received — could be used to update UI or as backup detection
        pass

    @pyqtSlot(str)
    def _on_android_status(self, status: str):
        self._android_status_lbl.setText(f"📱 {status}")
        self._devices.set_android_status(status)

    # ── Settings ──────────────────────────────────────────────────────────────

    @pyqtSlot(dict)
    def _on_settings_saved(self, new_settings: dict):
        self._settings = new_settings
        self._threshold_sec = new_settings.get("alert_threshold", 10)
        new_username = new_settings.get("username", "default")
        self._user_id = db.create_or_get_user(new_username)
        self.statusBar().showMessage("Settings saved", 3000)

    # ── Stylesheet ────────────────────────────────────────────────────────────

    def _load_stylesheet(self):
        qss_path = os.path.join(os.path.dirname(__file__), "style.qss")
        if os.path.exists(qss_path):
            with open(qss_path) as f:
                self.setStyleSheet(f.read())

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        if self._cam_worker and self._cam_worker.isRunning():
            self._on_stop_session()
        if self._sensor_worker and self._sensor_worker.isRunning():
            self._sensor_worker.stop()
            self._sensor_worker.wait(3000)
        event.accept()

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _sidebar_divider() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("border-color: #21262d; margin: 4px 0;")
        return line

"""
settings_tab.py - User preferences panel.

Saves settings to config/settings.json.
"""

import json
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSlider, QCheckBox, QComboBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "settings.json")

DEFAULT_SETTINGS = {
    "username":         "default",
    "alert_threshold":  10,
    "alert_sound":      True,
    "alert_vibration":  True,
    "camera_index":     0,
    "sensitivity":      10,
    "notification_style": "both",
    "dangerous_threshold": 25,
}


def load_settings() -> dict:
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH) as f:
                saved = json.load(f)
            return {**DEFAULT_SETTINGS, **saved}
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()


def save_settings(data: dict):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(data, f, indent=2)


class SettingsTab(QWidget):
    """User preferences: username, thresholds, alert style."""

    settings_saved = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = load_settings()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(20)

        title = QLabel("Settings")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #e6edf3;")
        root.addWidget(title)
        root.addWidget(self._h_line())

        # ── Profile ─────────────────────────────────────────────────────────
        root.addWidget(self._section("👤  Profile"))
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Username:"))
        self._name_edit = QLineEdit(self._settings.get("username", "default"))
        name_row.addWidget(self._name_edit)
        root.addLayout(name_row)

        cam_row = QHBoxLayout()
        cam_row.addWidget(QLabel("Camera Index:"))
        self._cam_combo = QComboBox()
        for i in range(4):
            self._cam_combo.addItem(f"Camera {i}", i)
        self._cam_combo.setCurrentIndex(self._settings.get("camera_index", 0))
        cam_row.addWidget(self._cam_combo)
        root.addLayout(cam_row)

        # ── Alerts ──────────────────────────────────────────────────────────
        root.addWidget(self._section("🔔  Alerts"))

        thresh_row = QHBoxLayout()
        thresh_row.addWidget(QLabel("Alert Threshold (seconds):"))
        self._thresh_slider = QSlider(Qt.Orientation.Horizontal)
        self._thresh_slider.setRange(5, 60)
        self._thresh_slider.setValue(self._settings.get("alert_threshold", 10))
        self._thresh_val_lbl = QLabel(str(self._thresh_slider.value()))
        self._thresh_val_lbl.setStyleSheet("color: #4f8ef7; font-weight: 700; min-width: 28px;")
        self._thresh_slider.valueChanged.connect(
            lambda v: self._thresh_val_lbl.setText(str(v))
        )
        thresh_row.addWidget(self._thresh_slider)
        thresh_row.addWidget(self._thresh_val_lbl)
        root.addLayout(thresh_row)

        dangerous_row = QHBoxLayout()
        dangerous_row.addWidget(QLabel("Dangerous Angle Threshold (degrees):"))
        self._dangerous_slider = QSlider(Qt.Orientation.Horizontal)
        self._dangerous_slider.setRange(10, 45)
        self._dangerous_slider.setValue(self._settings.get("dangerous_threshold", 25))
        self._dangerous_val_lbl = QLabel(str(self._dangerous_slider.value()))
        self._dangerous_val_lbl.setStyleSheet("color: #ef4444; font-weight: 700; min-width: 28px;")
        self._dangerous_slider.valueChanged.connect(
            lambda v: self._dangerous_val_lbl.setText(str(v))
        )
        dangerous_row.addWidget(self._dangerous_slider)
        dangerous_row.addWidget(self._dangerous_val_lbl)
        root.addLayout(dangerous_row)

        self._sound_cb = QCheckBox("Enable sound alert on laptop")
        self._sound_cb.setChecked(self._settings.get("alert_sound", True))
        self._sound_cb.setStyleSheet("color: #e6edf3;")

        self._vibrate_cb = QCheckBox("Enable vibration alert on Android phone")
        self._vibrate_cb.setChecked(self._settings.get("alert_vibration", True))
        self._vibrate_cb.setStyleSheet("color: #e6edf3;")

        root.addWidget(self._sound_cb)
        root.addWidget(self._vibrate_cb)

        notif_row = QHBoxLayout()
        notif_row.addWidget(QLabel("Notification style:"))
        self._notif_combo = QComboBox()
        self._notif_combo.addItems(["sound", "popup", "both"])
        style = self._settings.get("notification_style", "both")
        self._notif_combo.setCurrentText(style)
        notif_row.addWidget(self._notif_combo)
        root.addLayout(notif_row)

        # ── Save ────────────────────────────────────────────────────────────
        save_btn = QPushButton("💾  Save Settings")
        save_btn.setObjectName("btn_primary")
        save_btn.clicked.connect(self._on_save)
        root.addWidget(save_btn)

        self._saved_lbl = QLabel("")
        self._saved_lbl.setStyleSheet("color: #22c55e; font-size: 12px;")
        root.addWidget(self._saved_lbl)

        root.addStretch()

    def _on_save(self):
        self._settings.update({
            "username":           self._name_edit.text().strip() or "default",
            "alert_threshold":    self._thresh_slider.value(),
            "alert_sound":        self._sound_cb.isChecked(),
            "alert_vibration":    self._vibrate_cb.isChecked(),
            "camera_index":       self._cam_combo.currentData(),
            "notification_style": self._notif_combo.currentText(),
            "dangerous_threshold": self._dangerous_slider.value(),
        })
        save_settings(self._settings)
        self._saved_lbl.setText("✓ Settings saved successfully")
        self.settings_saved.emit(self._settings)

    def get_settings(self) -> dict:
        return self._settings.copy()

    @staticmethod
    def _section(title: str) -> QLabel:
        lbl = QLabel(title)
        lbl.setStyleSheet(
            "color: #8b949e; font-size: 12px; font-weight: 700; "
            "letter-spacing: 0.06em; padding-top: 6px;"
        )
        return lbl

    @staticmethod
    def _h_line() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("border-color: #30363d;")
        return line

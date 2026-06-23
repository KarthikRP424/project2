"""
devices_tab.py - BLE and Android device management panel.
"""

import socket
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFrame, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal


class DevicesTab(QWidget):
    """Scan for ESP32 BLE wearables and display Android connection info."""

    scan_requested      = pyqtSignal()
    connect_requested   = pyqtSignal(str)   # address
    disconnect_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._devices = {}  # name -> address
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(20)

        title = QLabel("Device Manager")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #e6edf3;")
        root.addWidget(title)
        root.addWidget(self._h_line())

        row = QHBoxLayout()
        row.setSpacing(20)

        # ── BLE devices panel ───────────────────────────────────────────────
        ble_frame = QFrame()
        ble_frame.setStyleSheet(
            "background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 4px;"
        )
        ble_layout = QVBoxLayout(ble_frame)
        ble_layout.setContentsMargins(16, 14, 16, 14)
        ble_layout.setSpacing(10)

        ble_title = QLabel("🔵  ESP32 BLE Wearable")
        ble_title.setStyleSheet("font-size: 15px; font-weight: 600; color: #e6edf3;")
        ble_layout.addWidget(ble_title)

        self._ble_status = QLabel("Status: Not connected")
        self._ble_status.setStyleSheet("color: #8b949e; font-size: 12px;")
        ble_layout.addWidget(self._ble_status)

        scan_row = QHBoxLayout()
        self._scan_btn = QPushButton("🔍  Scan Devices")
        self._scan_btn.clicked.connect(self._on_scan)
        self._connect_btn = QPushButton("⚡  Connect")
        self._connect_btn.setObjectName("btn_primary")
        self._connect_btn.clicked.connect(self._on_connect)
        self._connect_btn.setEnabled(False)
        self._disconnect_btn = QPushButton("Disconnect")
        self._disconnect_btn.setObjectName("btn_danger")
        self._disconnect_btn.clicked.connect(self.disconnect_requested.emit)
        self._disconnect_btn.setEnabled(False)
        scan_row.addWidget(self._scan_btn)
        scan_row.addWidget(self._connect_btn)
        scan_row.addWidget(self._disconnect_btn)
        ble_layout.addLayout(scan_row)

        self._device_list = QListWidget()
        self._device_list.setMinimumHeight(180)
        self._device_list.itemSelectionChanged.connect(self._on_selection_change)
        ble_layout.addWidget(QLabel("Discovered devices:"))
        ble_layout.addWidget(self._device_list)

        row.addWidget(ble_frame)

        # ── Android panel ───────────────────────────────────────────────────
        and_frame = QFrame()
        and_frame.setStyleSheet(
            "background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 4px;"
        )
        and_layout = QVBoxLayout(and_frame)
        and_layout.setContentsMargins(16, 14, 16, 14)
        and_layout.setSpacing(10)

        and_title = QLabel("📱  Android Companion App")
        and_title.setStyleSheet("font-size: 15px; font-weight: 600; color: #e6edf3;")
        and_layout.addWidget(and_title)

        self._and_status = QLabel("Status: Waiting for connection")
        self._and_status.setStyleSheet("color: #8b949e; font-size: 12px;")
        and_layout.addWidget(self._and_status)

        # Show local IP
        local_ip = self._get_local_ip()
        ip_lbl = QLabel(f"Connect your Android app to:")
        ip_lbl.setStyleSheet("color: #8b949e; font-size: 12px;")
        and_layout.addWidget(ip_lbl)

        ip_box = QLabel(f"ws://{local_ip}:8765")
        ip_box.setStyleSheet(
            "background: #0d1117; color: #4f8ef7; font-size: 15px; font-weight: 600;"
            "border: 1px solid #30363d; border-radius: 6px; padding: 8px 12px;"
        )
        ip_box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        and_layout.addWidget(ip_box)

        steps_lbl = QLabel(
            "Steps:\n"
            "1. Install PostureGuard Android app\n"
            "2. Open Settings → enter the IP above\n"
            "3. Tap Start Streaming on the app"
        )
        steps_lbl.setStyleSheet("color: #8b949e; font-size: 12px; line-height: 1.6;")
        steps_lbl.setWordWrap(True)
        and_layout.addWidget(steps_lbl)

        and_layout.addStretch()
        row.addWidget(and_frame)

        root.addLayout(row)
        root.addStretch()

    # ── Public API ────────────────────────────────────────────────────────────

    def populate_devices(self, devices: list):
        """Populate BLE device list from scan results [(name, addr), ...]."""
        self._device_list.clear()
        self._devices.clear()
        if not devices:
            self._device_list.addItem(QListWidgetItem("No PostureGuard devices found"))
            return
        for name, addr in devices:
            item = QListWidgetItem(f"  {name}  —  {addr}")
            self._device_list.addItem(item)
            self._devices[f"  {name}  —  {addr}"] = addr

    def set_ble_status(self, status: str):
        self._ble_status.setText(f"Status: {status}")
        is_connected = "Connected" in status
        self._disconnect_btn.setEnabled(is_connected)
        self._connect_btn.setEnabled(not is_connected)

    def set_android_status(self, status: str):
        self._and_status.setText(f"Status: {status}")

    # ── Internals ─────────────────────────────────────────────────────────────

    def _on_scan(self):
        self._scan_btn.setText("Scanning…")
        self._scan_btn.setEnabled(False)
        self._device_list.clear()
        self._device_list.addItem("Scanning for devices…")
        self.scan_requested.emit()
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(7000, lambda: (
            self._scan_btn.setText("🔍  Scan Devices"),
            self._scan_btn.setEnabled(True),
        ))

    def _on_connect(self):
        selected = self._device_list.currentItem()
        if selected:
            addr = self._devices.get(selected.text(), "")
            if addr:
                self.connect_requested.emit(addr)
                self._connect_btn.setEnabled(False)

    def _on_selection_change(self):
        self._connect_btn.setEnabled(self._device_list.currentItem() is not None)

    @staticmethod
    def _get_local_ip() -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    @staticmethod
    def _h_line() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("border-color: #30363d;")
        return line

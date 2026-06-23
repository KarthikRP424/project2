"""
sensor_worker.py - QThread that runs the asyncio event loop for BLE and WebSocket.

Bridges the async world (bleak BLE, websockets) with Qt's signal/slot system.
Emits sensor_data(pitch, roll) whenever new IMU data arrives from either source.
"""

import asyncio
import logging
from PyQt6.QtCore import QThread, pyqtSignal

from core.ble_client import BLEPostureClient
from core.socket_server import AndroidSocketServer

log = logging.getLogger(__name__)


class SensorWorker(QThread):
    """
    Runs an asyncio event loop in a background thread.
    Hosts both the BLE client (for ESP32 wearable) and
    the WebSocket server (for Android companion app).
    """

    # ── Signals ───────────────────────────────────────────────────────────────
    sensor_data       = pyqtSignal(float, float)       # pitch, roll
    ble_status        = pyqtSignal(str)                 # human-readable BLE status
    android_status    = pyqtSignal(str)                 # android connection status
    ble_devices_found = pyqtSignal(list)                # [(name, addr), ...]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loop: asyncio.AbstractEventLoop = None
        self._running = False

        self.ble_client    = BLEPostureClient()
        self.socket_server = AndroidSocketServer()

        # Wire callbacks → Qt signals
        self.ble_client.on_data    = self._on_ble_data
        self.socket_server.on_sensor_data = self._on_android_data

    # ── Control ───────────────────────────────────────────────────────────────

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._running = True

        # Start WebSocket server (always on)
        self._loop.run_until_complete(self.socket_server.start())
        self.android_status.emit(
            f"Waiting on ws://{self.socket_server.get_local_ip()}:8765"
        )

        # Keep loop running indefinitely
        try:
            self._loop.run_forever()
        finally:
            self._loop.close()
            self._running = False

    def stop(self):
        """Shut down the asyncio loop cleanly."""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._shutdown)

    def _shutdown(self):
        asyncio.ensure_future(self.socket_server.stop(), loop=self._loop)
        asyncio.ensure_future(self.ble_client.disconnect(), loop=self._loop)
        self._loop.stop()

    # ── BLE actions (called from UI thread, scheduled into async loop) ────────

    def scan_ble(self):
        """Trigger BLE device scan asynchronously."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._do_scan(), self._loop)

    def connect_ble(self, address: str):
        """Connect to an ESP32 by BLE address."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._do_connect(address), self._loop)

    def disconnect_ble(self):
        if self._loop:
            asyncio.run_coroutine_threadsafe(self.ble_client.disconnect(), self._loop)

    def send_ble_alert(self):
        """Trigger buzz on wearable."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self.ble_client.send_alert_command(), self._loop
            )

    def send_android_vibrate(self):
        """Send haptic command to Android."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self.socket_server.send_vibrate_to_all(), self._loop
            )

    # ── Async helpers ─────────────────────────────────────────────────────────

    async def _do_scan(self):
        self.ble_status.emit("Scanning for BLE devices…")
        devices = await self.ble_client.scan_devices(timeout=6.0)
        self.ble_devices_found.emit(devices)
        if devices:
            self.ble_status.emit(f"Found {len(devices)} device(s)")
        else:
            self.ble_status.emit("No PostureGuard devices found")

    async def _do_connect(self, address: str):
        try:
            self.ble_status.emit(f"Connecting to {address}…")
            await self.ble_client.connect(address)
            self.ble_status.emit(f"Connected ✓ {address}")
        except Exception as e:
            self.ble_status.emit(f"BLE error: {e}")

    # ── Data callbacks (called from asyncio thread → emit to Qt) ─────────────

    def _on_ble_data(self, pitch: float, roll: float, battery: float):
        self.sensor_data.emit(pitch, roll)

    def _on_android_data(self, pitch: float, roll: float):
        self.sensor_data.emit(pitch, roll)
        if self.socket_server.get_client_count() > 0:
            self.android_status.emit("Android Connected ✓")

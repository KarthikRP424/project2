"""
ble_client.py - Async BLE client for ESP32 PostureGuard wearable.

Uses `bleak` to scan for, connect to, and receive IMU orientation
packets (pitch, roll, battery) from the custom ESP32 GATT server.
Also supports sending command bytes back to the wearable.
"""

import asyncio
import struct
import logging
from typing import Callable, Optional, List, Tuple

log = logging.getLogger(__name__)

# ── Custom BLE UUIDs (must match ESP32 firmware) ─────────────────────────────
SERVICE_UUID   = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
DATA_CHAR_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"  # Notify
CMD_CHAR_UUID  = "cba1d00f-8c3b-4c3d-b4f2-9e8a5b28a2a5"  # Write

# ── Command bytes ─────────────────────────────────────────────────────────────
CMD_CALIBRATE  = b"\x01"
CMD_SLEEP      = b"\x02"
CMD_ALERT_BUZZ = b"\x03"


class BLEPostureClient:
    """
    BLE GATT client for the PostureGuard ESP32 wearable.

    Set `on_data` callback before connecting:
        client.on_data = lambda pitch, roll, bat: ...

    Usage (inside asyncio event loop):
        devices = await client.scan_devices()
        await client.connect(devices[0][1])
        # data flows via callback
        await client.send_alert_command()
        await client.disconnect()
    """

    def __init__(self):
        self.on_data: Optional[Callable[[float, float, float], None]] = None
        self._client = None
        self._connected = False

    # ── Scanning ──────────────────────────────────────────────────────────────

    async def scan_devices(self, timeout: float = 5.0) -> List[Tuple[str, str]]:
        """
        Scan for BLE devices advertising our custom service.

        Returns list of (name, address) tuples.
        """
        try:
            from bleak import BleakScanner
            devices = await BleakScanner.discover(timeout=timeout, return_adv=False)
            found = []
            for d in devices:
                name = d.name or "Unknown"
                # Filter by name prefix OR service UUID
                if "PostureGuard" in name or "Posture" in name:
                    found.append((name, d.address))
                    log.info(f"Found posture device: {name} @ {d.address}")
            return found
        except Exception as e:
            log.error(f"BLE scan failed: {e}")
            return []

    # ── Connection ────────────────────────────────────────────────────────────

    async def connect(self, address: str):
        """Connect to the ESP32 and subscribe to IMU notifications."""
        try:
            from bleak import BleakClient
            self._client = BleakClient(address, disconnected_callback=self._on_disconnect)
            await self._client.connect()
            self._connected = True
            log.info(f"Connected to {address}")

            # Subscribe to data characteristic notifications
            await self._client.start_notify(DATA_CHAR_UUID, self._on_imu_packet)
            log.info("Subscribed to IMU notification stream")
        except Exception as e:
            self._connected = False
            log.error(f"BLE connect failed: {e}")
            raise

    async def disconnect(self):
        """Gracefully disconnect from the wearable."""
        if self._client and self._connected:
            try:
                await self._client.stop_notify(DATA_CHAR_UUID)
                await self._client.disconnect()
            except Exception as e:
                log.warning(f"BLE disconnect warning: {e}")
            finally:
                self._connected = False
                self._client = None

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None

    # ── Commands ──────────────────────────────────────────────────────────────

    async def send_alert_command(self):
        """Trigger the ESP32 buzzer alert."""
        await self._write_command(CMD_ALERT_BUZZ)

    async def send_calibrate_command(self):
        """Tell the ESP32 to run its internal offset calibration."""
        await self._write_command(CMD_CALIBRATE)

    async def send_sleep_command(self):
        """Put the ESP32 into deep sleep."""
        await self._write_command(CMD_SLEEP)

    async def _write_command(self, data: bytes):
        if not self.is_connected:
            return
        try:
            await self._client.write_gatt_char(CMD_CHAR_UUID, data, response=False)
        except Exception as e:
            log.warning(f"BLE write error: {e}")

    # ── Internal callbacks ────────────────────────────────────────────────────

    def _on_imu_packet(self, sender, data: bytearray):
        """
        Parse incoming 12-byte BLE packet:
            [float pitch 4B][float roll 4B][float battery 4B]
        All values are little-endian IEEE 754 floats.
        """
        if len(data) < 12:
            return
        try:
            pitch, roll, battery = struct.unpack_from("<fff", data, 0)
            if self.on_data:
                self.on_data(pitch, roll, battery)
        except struct.error as e:
            log.warning(f"Malformed BLE packet ({len(data)}B): {e}")

    def _on_disconnect(self, client):
        log.warning("BLE device disconnected unexpectedly")
        self._connected = False

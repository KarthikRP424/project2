"""
socket_server.py - WebSocket server that receives sensor data from the Android companion app.

The Android app connects as a WebSocket client, streaming JSON packets:
    {"pitch": float, "roll": float, "timestamp": int}

The laptop server can send commands back:
    {"command": "vibrate", "pattern": [0, 200, 100, 200]}
"""

import asyncio
import json
import logging
import socket
from typing import Callable, Optional, Set

log = logging.getLogger(__name__)

try:
    import websockets
    _WS_AVAILABLE = True
except ImportError:
    _WS_AVAILABLE = False


class AndroidSocketServer:
    """
    WebSocket server that listens for Android sensor data.

    Set `on_sensor_data` callback to receive (pitch, roll) tuples.
    Call `await start()` to launch; `await stop()` to shut down.
    """

    DEFAULT_PORT = 8765

    def __init__(self):
        self.on_sensor_data: Optional[Callable[[float, float], None]] = None
        self._clients: Set = set()
        self._server = None
        self._running = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self, host: str = "0.0.0.0", port: int = DEFAULT_PORT):
        """Start the WebSocket server."""
        if not _WS_AVAILABLE:
            log.error("websockets library not installed. Run: pip install websockets")
            return

        self._running = True
        try:
            self._server = await websockets.serve(
                self._handle_client, host, port, ping_interval=20, ping_timeout=10
            )
            local_ip = self._get_local_ip()
            log.info(f"Android WebSocket server running on ws://{local_ip}:{port}")
        except Exception as e:
            log.error(f"Failed to start WebSocket server: {e}")
            self._running = False

    async def stop(self):
        """Stop the server and close all client connections."""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            log.info("WebSocket server stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    @staticmethod
    def _get_local_ip() -> str:
        """Get the machine's local network IP for QR display."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def get_local_ip(self) -> str:
        return self._get_local_ip()

    # ── Client handler ────────────────────────────────────────────────────────

    async def _handle_client(self, websocket, path=None):
        """Handle one Android client connection lifecycle."""
        peer = websocket.remote_address
        log.info(f"Android client connected: {peer}")
        self._clients.add(websocket)

        try:
            async for raw in websocket:
                if not self._running:
                    break
                await self._process_message(raw, websocket)
        except Exception as e:
            log.warning(f"Client {peer} error: {e}")
        finally:
            self._clients.discard(websocket)
            log.info(f"Android client disconnected: {peer}")

    async def _process_message(self, raw: str, websocket):
        """Parse JSON message and invoke sensor callback."""
        try:
            data = json.loads(raw)
            pitch = float(data.get("pitch", 0.0))
            roll  = float(data.get("roll", 0.0))
            if self.on_sensor_data:
                self.on_sensor_data(pitch, roll)
        except (json.JSONDecodeError, ValueError) as e:
            log.debug(f"Bad message: {e}")

    # ── Outbound commands ─────────────────────────────────────────────────────

    async def send_vibrate_to_all(self, pattern: list = None):
        """
        Send vibration command to all connected Android clients.
        Pattern is in milliseconds: [delay, vibrate, pause, vibrate, ...]
        """
        if pattern is None:
            pattern = [0, 300, 100, 300]
        cmd = json.dumps({"command": "vibrate", "pattern": pattern})
        dead = set()
        for ws in self._clients.copy():
            try:
                await ws.send(cmd)
            except Exception:
                dead.add(ws)
        self._clients -= dead

    def get_client_count(self) -> int:
        return len(self._clients)

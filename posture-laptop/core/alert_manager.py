"""
alert_manager.py - Manages posture alert timing, spam prevention, and sound playback.

Tracks how long the user has been in bad/slight posture and fires
an alert callback when the configurable threshold is exceeded.
"""

import time
import threading
import sys
from typing import Callable, Optional

# Status constants (match analyzer.py)
STATUS_GOOD   = "GOOD"
STATUS_SLIGHT = "SLIGHT"
STATUS_BAD    = "BAD"
STATUS_NONE   = "NO_DETECTION"


class AlertManager:
    """
    Manages posture alert timing and notification dispatch.

    Call `update(status)` every frame from the camera/sensor worker.
    Provide an `on_alert` callback that receives (status, duration_sec).

    Anti-spam: once an alert fires, it won't fire again for `cooldown_sec`.
    """

    def __init__(
        self,
        threshold_sec: int = 10,
        cooldown_sec: int = 30,
        on_alert: Optional[Callable] = None,
    ):
        self.threshold_sec   = threshold_sec
        self.cooldown_sec    = cooldown_sec
        self.on_alert        = on_alert   # fn(status: str, held_sec: float)

        self._bad_start_time: Optional[float] = None
        self._last_alert_time: float = 0.0
        self._current_status: str    = STATUS_NONE
        self._lock = threading.Lock()

    # ── Public API ────────────────────────────────────────────────────────────

    def set_threshold(self, seconds: int):
        """Change the bad-posture duration threshold."""
        self.threshold_sec = max(3, int(seconds))

    def update(self, status: str) -> bool:
        """
        Feed the latest posture status.

        Returns True if an alert was fired this frame.
        """
        now = time.monotonic()
        fired = False

        with self._lock:
            prev = self._current_status
            self._current_status = status

            alert_worthy = status in (STATUS_BAD, STATUS_SLIGHT)

            if alert_worthy:
                if self._bad_start_time is None:
                    self._bad_start_time = now
                held = now - self._bad_start_time
                since_last = now - self._last_alert_time

                if held >= self.threshold_sec and since_last >= self.cooldown_sec:
                    self._last_alert_time = now
                    fired = True
                    if self.on_alert:
                        threading.Thread(
                            target=self.on_alert,
                            args=(status, held),
                            daemon=True,
                        ).start()
            else:
                self._bad_start_time = None

        if fired:
            self._play_sound()

        return fired

    def get_held_duration(self) -> float:
        """Return seconds the user has been in bad/slight posture (0 if good)."""
        with self._lock:
            if self._bad_start_time is None:
                return 0.0
            return time.monotonic() - self._bad_start_time

    def reset(self):
        """Reset all state (call on session start)."""
        with self._lock:
            self._bad_start_time  = None
            self._last_alert_time = 0.0
            self._current_status  = STATUS_NONE

    # ── Sound ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _play_sound():
        """Play a short system beep. Falls back gracefully on all platforms."""
        try:
            if sys.platform == "win32":
                import winsound
                winsound.Beep(880, 300)   # 880 Hz for 300 ms
                time.sleep(0.1)
                winsound.Beep(660, 200)
            else:
                # macOS / Linux: use print bell or afplay
                print("\a", end="", flush=True)
        except Exception:
            pass

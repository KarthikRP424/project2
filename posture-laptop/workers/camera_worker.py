"""
camera_worker.py - QThread worker that drives the webcam capture loop.

Separates the blocking OpenCV I/O from the Qt main thread.
Emits Qt signals for: video frames, posture status, alerts, and calibration results.

Performance design:
  - Video frames emitted every frame for smooth preview.
  - Status/UI update signals throttled to max every 500 ms.
  - Popup + sound alerts fire at most once every 10 seconds (cooldown).
  - DB events written only on posture state *transitions* (not every frame).
"""

import time
import numpy as np
import cv2
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker
from PyQt6.QtGui import QImage

from core.analyzer import (
    PostureAnalyzer,
    STATUS_GOOD, STATUS_BAD, STATUS_SLIGHT, STATUS_NONE,
    STATUS_WARNING, STATUS_DANGEROUS,
)
from core.alert_manager import AlertManager
from core import database as db

CALIBRATION_DURATION_SEC = 5

# Statuses that are "bad enough" to trigger alert popup / sound
_ALERT_STATUSES = {STATUS_WARNING, STATUS_BAD, STATUS_DANGEROUS}

# Statuses that are considered "slouching" for DB event tracking
_SLOUCH_STATUSES = {STATUS_SLIGHT, STATUS_WARNING, STATUS_BAD, STATUS_DANGEROUS}


class CameraWorker(QThread):
    """
    Background thread that:
    1. Reads webcam frames as fast as the camera + MediaPipe allows.
    2. Runs MediaPipe FHP analysis on each frame.
    3. Throttles UI/DB/alert side-effects to avoid lag.
    4. Emits signals to update the UI safely from the main thread.
    """

    # ── Qt Signals ────────────────────────────────────────────────────────────
    frame_ready      = pyqtSignal(QImage)                  # Every frame
    status_update    = pyqtSignal(str, float, float, int, str)  # Throttled 500 ms
    alert_fired      = pyqtSignal(str, float)              # On threshold breach
    calibration_done = pyqtSignal(float)                   # After calibration
    error_occurred   = pyqtSignal(str)                     # On fatal error
    show_popup       = pyqtSignal(str, str, str)           # Throttled 10 s

    def __init__(
        self,
        camera_index: int = 0,
        user_id: int = 1,
        session_id: int = 0,
        dangerous_threshold: float = 25.0,
        parent=None,
    ):
        super().__init__(parent)
        self.camera_index         = camera_index
        self.user_id              = user_id
        self.session_id           = session_id
        self.dangerous_threshold  = dangerous_threshold

        self._running     = False
        self._calibrating = False
        self._calib_start = 0.0
        self._mutex       = QMutex()

        self.analyzer  = PostureAnalyzer(dangerous_threshold=dangerous_threshold)
        self.alert_mgr = AlertManager(
            threshold_sec=10,
            on_alert=lambda s, h: self.alert_fired.emit(s, h),
        )

        # Slouch event DB tracking (one open event at a time)
        self._current_event_id: int   = 0
        self._event_start_time: float = 0.0
        self._in_slouch: bool         = False
        self._peak_deviation: float   = 0.0
        self._slouch_event_count: int = 0

    # ── Control ───────────────────────────────────────────────────────────────

    def start_calibration(self):
        """Trigger a 5-second calibration window."""
        with QMutexLocker(self._mutex):
            self.analyzer.start_calibration_collection()
            self._calibrating = True
            self._calib_start = time.monotonic()

    def set_threshold(self, seconds: int):
        self.alert_mgr.set_threshold(seconds)

    def stop(self):
        self._running = False

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        from core.analyzer import _MP_AVAILABLE
        if not _MP_AVAILABLE or self.analyzer._pose is None:
            self.error_occurred.emit(
                "MediaPipe Pose detection is not available or failed to initialize. "
                "Please ensure you are using Python 3.11 and all dependencies are installed."
            )
            return

        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            self.error_occurred.emit(
                f"Camera index {self.camera_index} could not be opened."
            )
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)   # Always grab the latest frame

        self._running = True
        self.analyzer.reset()
        self.alert_mgr.reset()

        # ── Throttle state ────────────────────────────────────────────────────
        last_ui_emit_time    = 0.0   # UI label updates  (max every 500 ms)
        last_alert_time      = 0.0   # Popup + beep       (max every 10 s)
        prev_status          = STATUS_NONE
        alert_status_text    = "Monitoring"

        while self._running:
            ret, frame = cap.read()
            if not ret:
                self.error_occurred.emit("Camera read failed — check connection.")
                break

            result      = self.analyzer.analyze_frame(frame)
            annotated   = result["annotated_frame"]
            status      = result["status"]
            angle       = result["angle"] or 0.0
            deviation   = result["deviation"]
            now         = time.monotonic()

            # ── 1. Emit video frame every frame (smooth preview) ──────────────
            qt_img = self._ndarray_to_qimage(annotated)
            self.frame_ready.emit(qt_img)

            # ── 2. Alert popup + beep (max once per 10 s cooldown) ────────────
            if status in _ALERT_STATUSES:
                if now - last_alert_time >= 10.0:
                    title, msg, sev = self._build_popup_content(status)
                    self.show_popup.emit(title, msg, sev)
                    self.alert_mgr._play_sound()   # runs in daemon thread
                    last_alert_time     = now
                    alert_status_text   = "🚨 ALERT FIRED"
                else:
                    remaining = int(10.0 - (now - last_alert_time))
                    alert_status_text = f"⚠️ Cooldown {remaining}s"
            elif status == STATUS_SLIGHT:
                alert_status_text = "Slight Bend..."
            else:
                alert_status_text = "Monitoring"

            # ── 3. DB event tracking (only on state *transitions*) ─────────────
            self._track_slouch_event(status, deviation)

            # ── 4. Calibration check ───────────────────────────────────────────
            self._check_calibration()

            # ── 5. UI label update (max once per 500 ms) ─────────────────────
            if now - last_ui_emit_time >= 0.5 or status != prev_status:
                self.status_update.emit(
                    status, angle, deviation,
                    self._slouch_event_count, alert_status_text
                )
                last_ui_emit_time = now
                prev_status       = status

            # Small yield so Qt event loop can process signals between frames
            self.msleep(1)

        cap.release()

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _build_popup_content(status: str):
        if status == STATUS_WARNING:
            return ("Posture Warning",
                    "Posture Warning: Please sit straight",
                    "warning")
        if status == STATUS_BAD:
            return ("Bad Posture Detected",
                    "Bad Posture Detected: Sit straight now",
                    "bad")
        # STATUS_DANGEROUS
        return ("Dangerous Posture",
                "Dangerous Posture: Sit straight immediately",
                "dangerous")

    def _check_calibration(self):
        with QMutexLocker(self._mutex):
            if not self._calibrating:
                return
            elapsed = time.monotonic() - self._calib_start
            if elapsed >= CALIBRATION_DURATION_SEC:
                angle = self.analyzer.calibrate_from_samples()
                self._calibrating = False
                if angle is not None:
                    db.save_calibration(self.user_id, "CAMERA", angle)
                    self.calibration_done.emit(angle)

    def _track_slouch_event(self, status: str, deviation: float):
        """Write to DB only on posture state transitions (not every frame)."""
        if self.session_id == 0:
            return

        is_bad = status in _SLOUCH_STATUSES

        if is_bad and not self._in_slouch:
            # Transition: good → bad  →  open a new event
            self._in_slouch        = True
            self._event_start_time = time.time()
            self._peak_deviation   = deviation

            etype = {
                STATUS_DANGEROUS: "CRITICAL_SLOUCH",
                STATUS_SLIGHT:    "SLIGHT_SLOUCH",
            }.get(status, "BAD_POSTURE")

            self._current_event_id  = db.log_slouch_event(self.session_id, etype, deviation)
            self._slouch_event_count += 1

        elif is_bad and self._in_slouch:
            # Still bad — just track peak deviation (no extra DB write)
            if deviation > self._peak_deviation:
                self._peak_deviation = deviation

        elif not is_bad and self._in_slouch:
            # Transition: bad → good  →  close the event
            self._in_slouch = False
            duration = int(time.time() - self._event_start_time)
            db.end_slouch_event(self._current_event_id, duration, self._peak_deviation)
            self._current_event_id = 0
            self._peak_deviation   = 0.0

    @staticmethod
    def _ndarray_to_qimage(bgr: np.ndarray) -> QImage:
        """Convert a BGR numpy array to a QImage (RGB888)."""
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        return QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()

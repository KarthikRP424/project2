"""
camera_worker.py - QThread worker that drives the webcam capture loop.

Separates the blocking OpenCV I/O from the Qt main thread.
Emits Qt signals for: video frames, posture status, alerts, and calibration results.
"""

import time
import numpy as np
import cv2
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker
from PyQt6.QtGui import QImage

from core.analyzer import PostureAnalyzer, STATUS_GOOD, STATUS_BAD, STATUS_SLIGHT, STATUS_NONE
from core.alert_manager import AlertManager
from core import database as db

CALIBRATION_DURATION_SEC = 5


class CameraWorker(QThread):
    """
    Background thread that:
    1. Reads webcam frames at up to 30 FPS.
    2. Runs MediaPipe FHP analysis on each frame.
    3. Applies alert logic.
    4. Emits signals to update the UI safely.
    """

    # ── Qt Signals ────────────────────────────────────────────────────────────
    frame_ready      = pyqtSignal(QImage)          # Annotated webcam frame
    status_update    = pyqtSignal(str, float, float)  # (status, angle, deviation)
    alert_fired      = pyqtSignal(str, float)         # (status, held_sec)
    calibration_done = pyqtSignal(float)              # reference angle
    error_occurred   = pyqtSignal(str)                # human-readable error

    def __init__(
        self,
        camera_index: int = 0,
        user_id: int = 1,
        session_id: int = 0,
        parent=None,
    ):
        super().__init__(parent)
        self.camera_index  = camera_index
        self.user_id       = user_id
        self.session_id    = session_id

        self._running       = False
        self._calibrating   = False
        self._calib_start   = 0.0
        self._mutex         = QMutex()

        self.analyzer = PostureAnalyzer()
        self.alert_mgr = AlertManager(
            threshold_sec=10,
            on_alert=lambda s, h: self.alert_fired.emit(s, h),
        )

        # Slouch event tracking
        self._current_event_id: int = 0
        self._event_start_time: float = 0.0
        self._in_slouch: bool = False
        self._peak_deviation: float = 0.0

    # ── Control ───────────────────────────────────────────────────────────────

    def start_calibration(self):
        """Trigger a 5-second calibration window."""
        with QMutexLocker(self._mutex):
            self.analyzer.start_calibration_collection()
            self._calibrating  = True
            self._calib_start  = time.monotonic()

    def set_threshold(self, seconds: int):
        self.alert_mgr.set_threshold(seconds)

    def stop(self):
        self._running = False

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            self.error_occurred.emit(
                f"Camera index {self.camera_index} could not be opened."
            )
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        self._running = True
        self.analyzer.reset()
        self.alert_mgr.reset()

        while self._running:
            ret, frame = cap.read()
            if not ret:
                self.error_occurred.emit("Camera read failed — check connection.")
                break

            result = self.analyzer.analyze_frame(frame)
            annotated = result["annotated_frame"]

            # Emit video frame to UI
            qt_img = self._ndarray_to_qimage(annotated)
            self.frame_ready.emit(qt_img)

            # Emit posture status
            status    = result["status"]
            angle     = result["angle"] or 0.0
            deviation = result["deviation"]
            self.status_update.emit(status, angle, deviation)

            # Alert logic
            self.alert_mgr.update(status)

            # Slouch event DB logging
            self._track_slouch_event(status, deviation)

            # Calibration window management
            self._check_calibration()

            self.msleep(33)  # ~30 FPS cap

        cap.release()

    # ── Helpers ───────────────────────────────────────────────────────────────

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
        """Open/close slouch event rows in SQLite."""
        if self.session_id == 0:
            return

        is_bad = status in (STATUS_BAD, STATUS_SLIGHT)

        if is_bad and not self._in_slouch:
            self._in_slouch = True
            self._event_start_time = time.time()
            self._peak_deviation = deviation
            self._current_event_id = db.log_slouch_event(
                self.session_id,
                "BAD_POSTURE" if status == STATUS_BAD else "SLIGHT_SLOUCH",
                deviation,
            )
        elif is_bad and self._in_slouch:
            if deviation > self._peak_deviation:
                self._peak_deviation = deviation
        elif not is_bad and self._in_slouch:
            self._in_slouch = False
            duration = int(time.time() - self._event_start_time)
            db.end_slouch_event(self._current_event_id, duration, self._peak_deviation)
            self._current_event_id = 0
            self._peak_deviation = 0.0

    @staticmethod
    def _ndarray_to_qimage(bgr: np.ndarray) -> QImage:
        """Convert a BGR numpy array to a QImage (RGB888)."""
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        return QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()

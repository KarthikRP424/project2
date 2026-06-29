"""
analyzer.py - MediaPipe Pose-based posture analysis engine.

Calculates Forward Head Posture (FHP) angle from webcam frames,
applies Exponential Moving Average (EMA) smoothing, and classifies
posture state relative to a user-calibrated baseline.
"""

import math
import numpy as np
import cv2
from typing import Optional

try:
    # mediapipe >= 0.10.14 removed the mp.solutions top-level alias.
    # We import the sub-modules directly, which works on all recent versions.
    from mediapipe.python.solutions import pose as _mp_pose_module
    from mediapipe.python.solutions import drawing_utils as _mp_draw_module
    from mediapipe.python.solutions import drawing_styles as _mp_styles_module
    _MP_AVAILABLE = True
except Exception as _mp_import_err:
    print(f"[PostureGuard] MediaPipe import failed: {_mp_import_err}")
    _MP_AVAILABLE = False
    _mp_pose_module = None
    _mp_draw_module = None
    _mp_styles_module = None


# ── MediaPipe landmark indices ──────────────────────────────────────────────
_LEFT_EAR       = 7
_RIGHT_EAR      = 8
_LEFT_SHOULDER  = 11
_RIGHT_SHOULDER = 12
_LEFT_EYE       = 2
_RIGHT_EYE      = 5

# ── Posture status constants ─────────────────────────────────────────────────
STATUS_GOOD   = "GOOD"
STATUS_SLIGHT = "SLIGHT"
STATUS_WARNING = "warning"
STATUS_BAD    = "BAD"
STATUS_NONE   = "NO_DETECTION"
STATUS_DANGEROUS = "dangerous"

# ── Color palette (BGR) ─────────────────────────────────────────────────────
COLOR_GOOD   = (50, 220, 100)
COLOR_SLIGHT = (30, 180, 255)
COLOR_WARNING = (0, 140, 255)
COLOR_BAD    = (50, 50, 240)
COLOR_DANGEROUS = (0, 0, 255)
COLOR_TEXT   = (230, 230, 230)


class PostureAnalyzer:
    """
    Real-time posture analyzer using MediaPipe Pose.

    Usage:
        analyzer = PostureAnalyzer()
        result = analyzer.analyze_frame(bgr_frame)
        # result keys: angle, status, annotated_frame, raw_angle
    """

    def __init__(self, ema_beta: float = 0.20, good_threshold: float = 10.0,
                 bad_threshold: float = 20.0, dangerous_threshold: float = 25.0):
        """
        Args:
            ema_beta:        EMA smoothing factor (0–1). Lower = smoother, higher = more reactive.
            good_threshold:  Degrees within reference considered 'Good' posture.
            bad_threshold:   Degrees from reference that triggers 'Bad' status.
            dangerous_threshold: Absolute angle (degrees) below which posture is dangerous.
        """
        self.ema_beta = ema_beta
        self.good_threshold = good_threshold
        self.bad_threshold = bad_threshold
        self.dangerous_threshold = dangerous_threshold

        self._reference_angle: Optional[float] = None
        self._ema_angle: Optional[float] = None
        self._calibration_samples: list = []

        if _MP_AVAILABLE:
            try:
                self._mp_pose = _mp_pose_module
                self._mp_draw = _mp_draw_module
                self._mp_styles = _mp_styles_module
                self._pose = self._mp_pose.Pose(
                    static_image_mode=False,
                    model_complexity=0,        # 0=lite (fast), 1=full, 2=heavy
                    smooth_landmarks=True,
                    enable_segmentation=False,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
                print("[PostureGuard] MediaPipe Pose initialized successfully.")
            except Exception as e:
                import traceback
                print(f"[PostureGuard] Error initializing MediaPipe Pose: {e}")
                traceback.print_exc()
                self._pose = None   # pose=None triggers NO_DETECTION path safely
        else:
            self._pose = None

    # ── Public API ────────────────────────────────────────────────────────────

    def set_reference(self, angle: float):
        """Set the calibrated good-posture reference angle."""
        self._reference_angle = angle
        self._ema_angle = angle  # Seed the EMA at the reference

    def analyze_frame(self, frame: np.ndarray) -> dict:
        """
        Analyze a single BGR webcam frame.

        Returns:
            dict with keys:
                'angle'           – smoothed FHP angle (float, or None)
                'raw_angle'       – unsmoothed angle (float, or None)
                'status'          – STATUS_GOOD / STATUS_SLIGHT / STATUS_BAD / STATUS_NONE
                'deviation'       – degrees from reference (float)
                'annotated_frame' – BGR frame with skeleton + status overlay
        """
        result = {
            "angle": None,
            "raw_angle": None,
            "status": STATUS_NONE,
            "deviation": 0.0,
            "annotated_frame": frame.copy(),
        }

        if not _MP_AVAILABLE or self._pose is None:
            self._draw_no_mp_message(result["annotated_frame"])
            return result

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        pose_results = self._pose.process(rgb)
        rgb.flags.writeable = True

        annotated = frame.copy()

        if not pose_results.pose_landmarks:
            self._draw_overlay(annotated, None, None, STATUS_NONE, 0)
            result["annotated_frame"] = annotated
            return result

        lm = pose_results.pose_landmarks.landmark
        h, w = frame.shape[:2]

        # Draw full skeleton
        self._mp_draw.draw_landmarks(
            annotated,
            pose_results.pose_landmarks,
            self._mp_pose.POSE_CONNECTIONS,
            landmark_drawing_spec=self._mp_styles.get_default_pose_landmarks_style(),
        )

        # Extract key points (use average of left+right for robustness)
        ear_x, ear_y         = self._avg_landmark(lm, _LEFT_EAR, _RIGHT_EAR, w, h)
        shoulder_x, shoulder_y = self._avg_landmark(lm, _LEFT_SHOULDER, _RIGHT_SHOULDER, w, h)

        if ear_x is None:
            result["annotated_frame"] = annotated
            return result

        # FHP angle: arctan2(dy, dx) where dy = shoulder_y - ear_y, dx = ear_x - shoulder_x
        raw_angle = math.degrees(math.atan2(shoulder_y - ear_y, ear_x - shoulder_x))
        self._calibration_samples.append(raw_angle)

        # EMA smoothing
        if self._ema_angle is None:
            self._ema_angle = raw_angle
        else:
            self._ema_angle = self.ema_beta * raw_angle + (1 - self.ema_beta) * self._ema_angle

        result["raw_angle"] = raw_angle
        result["angle"] = self._ema_angle

        # Classify posture based on absolute angle ranges
        deviation = 0.0
        status = STATUS_NONE
        if self._ema_angle is not None:
            if self._reference_angle is not None:
                deviation = abs(self._reference_angle - self._ema_angle)
            
            if self._ema_angle >= 80.0:
                status = STATUS_GOOD
            elif self._ema_angle >= 70.0:
                status = STATUS_SLIGHT
            elif self._ema_angle >= 60.0:
                status = STATUS_WARNING
            elif self._ema_angle >= 25.0:
                status = STATUS_BAD
            else:
                status = STATUS_DANGEROUS
        else:
            status = STATUS_NONE

        result["status"] = status
        result["deviation"] = deviation

        # Draw joint markers and HUD
        cv2.circle(annotated, (int(ear_x), int(ear_y)), 10, COLOR_GOOD, -1)
        cv2.circle(annotated, (int(shoulder_x), int(shoulder_y)), 10, COLOR_SLIGHT, -1)
        cv2.line(annotated, (int(ear_x), int(ear_y)),
                 (int(shoulder_x), int(shoulder_y)), (255, 255, 100), 2)

        self._draw_overlay(annotated, self._ema_angle, deviation, status, h)
        result["annotated_frame"] = annotated
        return result

    def calibrate_from_samples(self) -> Optional[float]:
        """
        Compute reference angle from collected samples since last call.
        Returns the average angle (float) or None if not enough data.
        """
        if len(self._calibration_samples) < 10:
            return None
        avg = float(np.mean(self._calibration_samples))
        self._calibration_samples.clear()
        self.set_reference(avg)
        return avg

    def start_calibration_collection(self):
        """Reset sample buffer to start a fresh calibration window."""
        self._calibration_samples.clear()

    def reset(self):
        """Reset EMA state (call on new session start)."""
        self._ema_angle = self._reference_angle  # Seed from reference if set

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _avg_landmark(lm, idx_a: int, idx_b: int, w: int, h: int):
        """Average pixel coords of two symmetric landmarks."""
        try:
            xa = lm[idx_a].x * w
            ya = lm[idx_a].y * h
            xb = lm[idx_b].x * w
            yb = lm[idx_b].y * h
            return (xa + xb) / 2, (ya + yb) / 2
        except (IndexError, AttributeError):
            return None, None

    def _draw_overlay(self, frame: np.ndarray, angle, deviation, status: str, h: int):
        """Render HUD overlay on frame."""
        color_map = {
            STATUS_GOOD: COLOR_GOOD,
            STATUS_SLIGHT: COLOR_SLIGHT,
            STATUS_WARNING: COLOR_WARNING,
            STATUS_BAD: COLOR_BAD,
            STATUS_DANGEROUS: COLOR_DANGEROUS,
            STATUS_NONE: (150, 150, 150),
        }
        color = color_map.get(status, (150, 150, 150))

        label_map = {
            STATUS_GOOD: "GOOD POSTURE",
            STATUS_SLIGHT: "SLIGHT BEND",
            STATUS_WARNING: "POSTURE WARNING",
            STATUS_BAD: "BAD POSTURE",
            STATUS_DANGEROUS: "DANGEROUS POSTURE - SIT STRAIGHT",
            STATUS_NONE: "Calibrate First",
        }
        label = label_map.get(status, "")

        # Background pill (dynamic width for warnings/danger status)
        rect_width = 540 if status in (STATUS_DANGEROUS, STATUS_WARNING) else 330
        cv2.rectangle(frame, (8, 8), (rect_width, 80), (20, 20, 30), -1)
        cv2.rectangle(frame, (8, 8), (rect_width, 80), color, 2)

        cv2.putText(frame, label, (18, 38), cv2.FONT_HERSHEY_SIMPLEX,
                    0.9, color, 2, cv2.LINE_AA)

        angle_txt = f"Angle: {angle:.1f} deg" if angle is not None else "Angle: --"
        dev_txt   = f"Deviation: {deviation:.1f} deg" if deviation else ""
        cv2.putText(frame, angle_txt, (18, 62), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, COLOR_TEXT, 1, cv2.LINE_AA)
        if dev_txt:
            cv2.putText(frame, dev_txt, (175, 62), cv2.FONT_HERSHEY_SIMPLEX,
                        0.55, color, 1, cv2.LINE_AA)

    @staticmethod
    def _draw_no_mp_message(frame: np.ndarray):
        cv2.putText(frame, "MediaPipe not installed", (30, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (50, 50, 240), 2)

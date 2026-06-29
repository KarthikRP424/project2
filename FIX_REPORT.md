# FIX_REPORT - PostureGuard Laptop Application Fixes

This report outlines the structural fixes, dependency alignments, and runtime modifications implemented to restore the laptop posture monitoring application.

---

## 1. What Was Broken
* **AttributeError Crash:** Clicking **Start Monitoring** crashed the app with: `AttributeError: module 'mediapipe' has no attribute 'solutions'`.
* **Runtime Incompatibility:** The user environment was running Python 3.14.6 (pre-release/newer build). Compiles of packages like `mediapipe` do not yet have stable wheels or fully functional bindings for Python 3.14 on Windows, resulting in partial imports (e.g. missing `solutions`).
* **Lack of Graceful Fallbacks:** If MediaPipe imports or initialization failed, the thread started regardless and crashed the main GUI thread, rather than notifying the user.

---

## 2. What Files Were Changed
* [requirements.txt](file:///c:/Users/DELL/Desktop/project2/posture-laptop/requirements.txt): Pinned `numpy>=1.24.0,<2.0.0` and `mediapipe>=0.10.11,<0.11.0` to prevent modern numpy 2.x API breaking changes and ensure stable MediaPipe releases.
* [core/analyzer.py](file:///c:/Users/DELL/Desktop/project2/posture-laptop/core/analyzer.py): Wrapped MediaPipe import in checks for `hasattr(mp, "solutions")` and wrapped `mp.solutions.pose.Pose` creation in try-except blocks to catch runtime attribute/link errors.
* [workers/camera_worker.py](file:///c:/Users/DELL/Desktop/project2/posture-laptop/workers/camera_worker.py): Added a check at the beginning of the `run()` thread method to verify if MediaPipe was successfully loaded. If missing, it emits an `error_occurred` signal and halts gracefully.
* [setup_windows.ps1](file:///c:/Users/DELL/Desktop/project2/posture-laptop/setup_windows.ps1) **[NEW]**: Automated setup script for PowerShell that installs/checks Python 3.11, sets up a clean `venv`, upgrades pip, and installs requirements.
* [README.md](file:///c:/Users/DELL/Desktop/project2/README.md): Documented the Python 3.11 requirement, manual/automated setup steps, and PowerShell commands.

---

## 3. Why Python 3.11 is Required
* **MediaPipe Wheel Availability:** MediaPipe publishes stable compiled binary wheels for Python 3.8 to 3.11 on Windows.
* **Pre-release Python Instability:** Python 3.14 is a development version. Compiled C-extensions (like OpenCV, NumPy, MediaPipe) are highly likely to hit ABI incompatibilities or load failures on Windows when run under Python 3.14.

---

## 4. How MediaPipe Was Fixed
1. We identified a local installation of Python 3.11 on the system at `C:\Users\DELL\AppData\Local\Programs\Python\Python311\python.exe`.
2. We recreated the virtual environment (`venv`) using this Python 3.11 executable.
3. We secured the dependencies inside the Python 3.11 environment.
4. We implemented safe check guards inside `analyzer.py` to prevent importing/invoking methods on a partially loaded/broken MediaPipe package.

---

## 5. Exact Commands to Run the Project
Open **PowerShell** in the `posture-laptop` folder:
```powershell
# Run the automated setup wizard (checks/installs Python 3.11, configures venv, installs requirements)
.\setup_windows.ps1

# OR manually do:
.\venv\Scripts\Activate.ps1
python main.py
```

---

## 6. What Features are Working Now
1. **Local Camera AI Mode:** Reads laptop webcam feed in real-time, extracts Pose landmarks, calculates head/neck tilt angles (Forward Head Posture), and overlays status directly.
2. **Posture Calibration:** Prompts users to sit upright for 5 seconds to calibrate their personal baseline posture reference angle.
3. **Good/Bad/Dangerous Posture Classification:** Classifies posture in real time using absolute angle ranges:
   - `angle >= 80` ➔ `✅ GOOD POSTURE`
   - `70 <= angle < 80` ➔ `⚠️ SLIGHT BEND`
   - `60 <= angle < 70` ➔ `⚠️ POSTURE WARNING` (triggers popup)
   - `25 <= angle < 60` ➔ `🚨 BAD POSTURE` (triggers popup)
   - `< 25` ➔ `🚨 DANGEROUS POSTURE` (triggers popup)
4. **System-Wide Always-On-Top Popups:** Displays a floating, custom frameless toast warning in the top-right corner of the screen when posture falls into warning/bad/danger ranges, showing over other applications (e.g. VS Code, browser) and auto-closing after 3 seconds.
5. **Smart Beep Alerts with 10-Second Cooldown:** Sounds a warning beep (`winsound.Beep`) when a system popup appears, restricted by a 10-second cooldown to avoid flooding alerts.
6. **Dynamic Dashboard Scoring:** Posture score starts at 100. Each new dangerous posture event reduces the posture score by 5 (down to a minimum of 0). Score and Slouch event counts update immediately in the Live Monitor and persist to the Dashboard.
7. **SQLite habit tracking:** All slouch/warning events (logged as `SLIGHT_SLOUCH`, `BAD_POSTURE`, or `CRITICAL_SLOUCH`) and sessions are logged locally to SQLite (`posture.db`).
8. **Optional Bluetooth/Companion Scan:** Devices/scanning tabs remain open and optional. Users do not need an Android phone or ESP32 connected to run the basic camera posture monitoring.

---

## 7. What is Pending for Android and ESP32
* **posture-android:** Connecting the companion app to the laptop's WebSocket server `ws://<local-ip>:8765` to send pitch/roll values and receive haptic feedback.
* **posture-wearable:** Flashing the NimBLE + MPU6050 Arduino C++ code to an ESP32 board, connecting via the **Devices** tab in the desktop application, and receiving real-time posture orientation values.


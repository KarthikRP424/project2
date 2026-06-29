# PostureGuard — Fix Report

## Performance Fix: Lag & Hanging After Warning / Dashboard Logic

**Date:** 2026-06-30
**Status:** ✅ Fixed

---

### Problem Summary

After adding dashboard update, warning popup, angle threshold logic, and audio beep alerts, the app became **extremely slow or appeared to freeze** when clicking "Start Monitoring".

---

### Root Causes Identified (5 Issues)

#### 1. `dashboard.update_stats()` called on every camera frame
**File:** `ui/main_window.py` — `_on_status_update`

The `_on_status_update` slot was wired directly to the `status_update` signal from `CameraWorker`. Because the signal was emitted on every processed frame, `dashboard.update_stats()` (which triggers full widget redraws and DB queries) was being called **8–10 times per second**.

**Fix:** Removed `dashboard.update_stats()` from the per-frame slot. Added a `QTimer` that fires every **5 seconds** to push cached stats to the dashboard. Also refresh the dashboard instantly when the user navigates to the Dashboard tab.

---

#### 2. `winsound.Beep()` blocking the camera thread
**File:** `core/alert_manager.py` — `_play_sound()`

`winsound.Beep(880, 300)` is **synchronous** — it blocks the calling thread for the full duration (300 ms + 100 ms sleep + 200 ms = ~600 ms). Since this was called from inside the `CameraWorker` thread, every alert froze the camera feed for over half a second.

**Fix:** Moved `winsound.Beep()` into a **daemon thread** using `threading.Thread(target=..., daemon=True).start()`. The camera loop now continues uninterrupted during the beep.

---

#### 3. MediaPipe `model_complexity=1` (full model) was too slow
**File:** `core/analyzer.py` — `PostureAnalyzer.__init__`

Benchmark results before the fix:
```
avg = 536 ms/frame  (~2 FPS)
```

`model_complexity=1` uses the full pose model (heavy). For posture detection using head/shoulder landmarks only, `model_complexity=0` (lite model) is sufficient and ~3–5× faster.

**Fix:** Changed `model_complexity=1` → `model_complexity=0`.

---

#### 4. Camera input resolution was too large (640×480)
**File:** `workers/camera_worker.py`

Larger frames = more pixels for MediaPipe to process per frame, directly increasing inference time.

**Fix:** Reduced to `320×240`. Also added `CAP_PROP_BUFFERSIZE = 1` so the capture always reads the **latest** frame and doesn't queue up stale frames.

---

#### 5. Artificial `msleep(33)` delay stacked on top of slow MediaPipe
**File:** `workers/camera_worker.py`

The `msleep(33)` was originally intended to cap frame rate at 30 FPS. However, since MediaPipe analysis alone was taking 350–900 ms, this extra delay was completely unnecessary and only added more lag.

**Fix:** Replaced with `msleep(1)` — a minimal yield to keep the Qt event loop responsive without adding extra delay.

---

#### 6. Blocking `QMessageBox` in `_on_alert_fired`
**File:** `ui/main_window.py` — `_on_alert_fired`

`QMessageBox(self).show()` (and especially `exec()`) runs a **nested event loop**. This blocks all Qt signal processing while the dialog is visible, including camera frame rendering.

**Fix:** Replaced with a non-blocking `statusBar().showMessage()` call. System-level popup alerts are already handled by the `SystemWarningPopup` class (frameless, always-on-top, auto-closes after 3 seconds via `QTimer.singleShot`).

---

### Throttling & Cooldown Summary

| Action | Before | After |
|---|---|---|
| UI label updates | Every frame (~10×/s) | Max every **500 ms** (throttled in worker) |
| Dashboard stats refresh | Every frame (~10×/s) | Every **5 seconds** via QTimer |
| Popup alert shown | Every frame if bad posture | Max once per **10 seconds** (cooldown) |
| Beep sound | Every frame if bad posture, blocking | Max once per **10 seconds**, daemon thread |
| SQLite DB writes | Every frame (open event repeated) | Only on posture **state transitions** |

---

### State Logic Added (`camera_worker.py`)

```python
# Per-frame — always runs
result = analyzer.analyze_frame(frame)
frame_ready.emit(qt_img)              # smooth video preview

# Max every 500 ms
if now - last_ui_emit_time >= 0.5 or status != prev_status:
    status_update.emit(...)

# Max every 10 s
if status in ALERT_STATUSES and now - last_alert_time >= 10.0:
    show_popup.emit(...)
    alert_mgr._play_sound()           # runs in daemon thread
    last_alert_time = now

# Only on state transitions (good→bad, bad→good)
_track_slouch_event(status, deviation)   # one DB write per event
```

---

### Benchmark Results

| Metric | Before | After |
|---|---|---|
| Avg frame time | **536 ms** | **~96 ms** |
| Effective FPS | ~2 FPS | ~8–10 FPS |
| Camera freeze on alert | ~600 ms | 0 ms |
| Dashboard DB calls/min | ~600 | ~12 |

---

### Files Changed

| File | Change |
|---|---|
| `core/analyzer.py` | `model_complexity` 1 → 0, confidence threshold 0.6 → 0.5 |
| `core/alert_manager.py` | `_play_sound()` runs in daemon thread (non-blocking) |
| `workers/camera_worker.py` | Full rewrite with proper throttle state variables |
| `ui/main_window.py` | Removed per-frame dashboard call; added 5 s QTimer; fixed blocking QMessageBox |

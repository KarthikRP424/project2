"""
database.py - SQLite database manager for Smart Posture Correction System.
Handles all database operations: sessions, slouch events, calibrations, and daily reports.
"""

import sqlite3
import os
from datetime import date, datetime
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "posture.db")


def _get_connection() -> sqlite3.Connection:
    """Return a thread-safe SQLite connection with row factory."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize all database tables. Safe to call multiple times."""
    conn = _get_connection()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            username  TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS calibrations (
            calibration_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            detection_mode  TEXT NOT NULL
                CHECK(detection_mode IN ('CAMERA','ANDROID_SENSOR','ESP32_WEARABLE')),
            reference_angle_1 REAL NOT NULL,
            reference_angle_2 REAL,
            calibrated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS posture_sessions (
            session_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id             INTEGER NOT NULL,
            start_time          TIMESTAMP NOT NULL,
            end_time            TIMESTAMP,
            detection_mode      TEXT,
            total_duration_sec  INTEGER DEFAULT 0,
            average_posture_score REAL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS slouch_events (
            event_id            INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id          INTEGER NOT NULL,
            start_timestamp     TIMESTAMP NOT NULL,
            end_timestamp       TIMESTAMP,
            duration_sec        INTEGER DEFAULT 0,
            peak_deviation_angle REAL,
            event_type          TEXT DEFAULT 'BAD_POSTURE'
                CHECK(event_type IN ('SLIGHT_SLOUCH','BAD_POSTURE','CRITICAL_SLOUCH')),
            FOREIGN KEY (session_id) REFERENCES posture_sessions(session_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS daily_reports (
            report_date             DATE PRIMARY KEY,
            total_sitting_duration_sec INTEGER DEFAULT 0,
            total_slouch_duration_sec  INTEGER DEFAULT 0,
            slouch_count            INTEGER DEFAULT 0,
            daily_posture_score     REAL DEFAULT 100.0,
            longest_slouch_duration_sec INTEGER DEFAULT 0
        );
    """)
    conn.commit()
    conn.close()


def create_or_get_user(username: str = "default") -> int:
    """Return existing user_id or create a new user record."""
    conn = _get_connection()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE username=?", (username,))
    row = c.fetchone()
    if row:
        uid = row["user_id"]
    else:
        c.execute("INSERT INTO users (username) VALUES (?)", (username,))
        conn.commit()
        uid = c.lastrowid
    conn.close()
    return uid


def start_session(user_id: int, mode: str) -> int:
    """Open a new posture session and return session_id."""
    conn = _get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO posture_sessions (user_id, start_time, detection_mode) VALUES (?,?,?)",
        (user_id, datetime.now().isoformat(), mode),
    )
    conn.commit()
    sid = c.lastrowid
    conn.close()
    return sid


def end_session(session_id: int, score: float, total_sec: int):
    """Close an active session and write final metrics."""
    conn = _get_connection()
    conn.execute(
        """UPDATE posture_sessions
           SET end_time=?, total_duration_sec=?, average_posture_score=?
           WHERE session_id=?""",
        (datetime.now().isoformat(), total_sec, round(score, 1), session_id),
    )
    conn.commit()
    conn.close()
    _update_daily_report(date.today())


def log_slouch_event(session_id: int, event_type: str, deviation_angle: float) -> int:
    """Insert a new slouch event row and return its event_id."""
    conn = _get_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO slouch_events (session_id, start_timestamp, peak_deviation_angle, event_type)
           VALUES (?,?,?,?)""",
        (session_id, datetime.now().isoformat(), round(deviation_angle, 2), event_type),
    )
    conn.commit()
    eid = c.lastrowid
    conn.close()
    return eid


def end_slouch_event(event_id: int, duration_sec: int, peak_angle: float):
    """Close a slouch event with final duration and peak deviation."""
    conn = _get_connection()
    conn.execute(
        """UPDATE slouch_events
           SET end_timestamp=?, duration_sec=?, peak_deviation_angle=?
           WHERE event_id=?""",
        (datetime.now().isoformat(), duration_sec, round(peak_angle, 2), event_id),
    )
    conn.commit()
    conn.close()


def save_calibration(user_id: int, mode: str, angle1: float, angle2: Optional[float] = None):
    """Upsert calibration reference for a given user and mode."""
    conn = _get_connection()
    conn.execute(
        """INSERT INTO calibrations (user_id, detection_mode, reference_angle_1, reference_angle_2)
           VALUES (?,?,?,?)
           ON CONFLICT DO NOTHING""",
        (user_id, mode, round(angle1, 3), round(angle2, 3) if angle2 else None),
    )
    # Update if already exists
    conn.execute(
        """UPDATE calibrations
           SET reference_angle_1=?, reference_angle_2=?, calibrated_at=CURRENT_TIMESTAMP
           WHERE user_id=? AND detection_mode=?""",
        (round(angle1, 3), round(angle2, 3) if angle2 else None, user_id, mode),
    )
    conn.commit()
    conn.close()


def get_calibration(user_id: int, mode: str) -> Optional[dict]:
    """Return calibration angles dict or None if not calibrated."""
    conn = _get_connection()
    c = conn.cursor()
    c.execute(
        """SELECT reference_angle_1, reference_angle_2, calibrated_at
           FROM calibrations WHERE user_id=? AND detection_mode=?
           ORDER BY calibrated_at DESC LIMIT 1""",
        (user_id, mode),
    )
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "angle1": row["reference_angle_1"],
            "angle2": row["reference_angle_2"],
            "calibrated_at": row["calibrated_at"],
        }
    return None


def get_daily_report(target_date: date = None) -> dict:
    """Return daily stats dict for the given date (default today)."""
    if target_date is None:
        target_date = date.today()
    conn = _get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM daily_reports WHERE report_date=?", (target_date.isoformat(),))
    row = c.fetchone()
    conn.close()
    if row:
        return dict(row)
    return {
        "report_date": target_date.isoformat(),
        "total_sitting_duration_sec": 0,
        "total_slouch_duration_sec": 0,
        "slouch_count": 0,
        "daily_posture_score": 100.0,
        "longest_slouch_duration_sec": 0,
    }


def get_weekly_data() -> list:
    """Return list of 7 daily report dicts ending today."""
    from datetime import timedelta
    today = date.today()
    result = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        result.append(get_daily_report(d))
    return result


def _update_daily_report(target_date: date):
    """Recalculate and upsert the daily_reports row from session + event data."""
    conn = _get_connection()
    c = conn.cursor()

    # Get all sessions for today
    c.execute(
        """SELECT SUM(total_duration_sec) AS total_sit,
                  AVG(average_posture_score) AS avg_score
           FROM posture_sessions
           WHERE DATE(start_time)=?""",
        (target_date.isoformat(),),
    )
    session_row = c.fetchone()
    total_sit = session_row["total_sit"] or 0
    avg_score = session_row["avg_score"] or 100.0

    # Slouch stats
    c.execute(
        """SELECT COUNT(*) AS cnt,
                  SUM(duration_sec) AS total_slouch,
                  MAX(duration_sec) AS longest
           FROM slouch_events
           WHERE DATE(start_timestamp)=?""",
        (target_date.isoformat(),),
    )
    ev = c.fetchone()
    slouch_count = ev["cnt"] or 0
    total_slouch = ev["total_slouch"] or 0
    longest = ev["longest"] or 0

    conn.execute(
        """INSERT INTO daily_reports VALUES (?,?,?,?,?,?)
           ON CONFLICT(report_date) DO UPDATE SET
               total_sitting_duration_sec=excluded.total_sitting_duration_sec,
               total_slouch_duration_sec=excluded.total_slouch_duration_sec,
               slouch_count=excluded.slouch_count,
               daily_posture_score=excluded.daily_posture_score,
               longest_slouch_duration_sec=excluded.longest_slouch_duration_sec""",
        (target_date.isoformat(), total_sit, total_slouch, slouch_count, round(avg_score, 1), longest),
    )
    conn.commit()
    conn.close()

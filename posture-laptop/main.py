"""
main.py - PostureGuard Desktop Application entry point.

Usage:
    python main.py

Requirements:
    pip install -r requirements.txt
"""

import sys
import os
import logging

# ── Ensure project root is on sys.path ───────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from PyQt6.QtWidgets import QApplication, QSplashScreen, QLabel
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPalette, QPixmap, QPainter

from core import database as db
from ui.main_window import MainWindow


def apply_dark_palette(app: QApplication):
    """Apply a system-level dark palette so native widgets match the QSS theme."""
    palette = QPalette()
    dark    = QColor("#0d1117")
    surface = QColor("#161b22")
    border  = QColor("#30363d")
    text    = QColor("#e6edf3")
    accent  = QColor("#4f8ef7")
    dim     = QColor("#8b949e")

    palette.setColor(QPalette.ColorRole.Window,          dark)
    palette.setColor(QPalette.ColorRole.WindowText,      text)
    palette.setColor(QPalette.ColorRole.Base,            surface)
    palette.setColor(QPalette.ColorRole.AlternateBase,   dark)
    palette.setColor(QPalette.ColorRole.ToolTipBase,     surface)
    palette.setColor(QPalette.ColorRole.ToolTipText,     text)
    palette.setColor(QPalette.ColorRole.Text,            text)
    palette.setColor(QPalette.ColorRole.Button,          surface)
    palette.setColor(QPalette.ColorRole.ButtonText,      text)
    palette.setColor(QPalette.ColorRole.BrightText,      QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Link,            accent)
    palette.setColor(QPalette.ColorRole.Highlight,       accent)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, dim)

    app.setPalette(palette)


def create_splash(app: QApplication) -> QSplashScreen:
    """Create a branded splash screen while the app initializes."""
    pix = QPixmap(480, 260)
    pix.fill(QColor("#0d1117"))

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Background card
    painter.setBrush(QColor("#161b22"))
    painter.setPen(QColor("#30363d"))
    painter.drawRoundedRect(20, 20, 440, 220, 16, 16)

    # Title
    painter.setPen(QColor("#4f8ef7"))
    f1 = QFont("Segoe UI", 28, QFont.Weight.Bold)
    painter.setFont(f1)
    painter.drawText(20, 80, 440, 60, Qt.AlignmentFlag.AlignCenter, "🧘 PostureGuard")

    # Subtitle
    painter.setPen(QColor("#8b949e"))
    f2 = QFont("Segoe UI", 12)
    painter.setFont(f2)
    painter.drawText(20, 130, 440, 40, Qt.AlignmentFlag.AlignCenter,
                     "Smart AI Posture Correction System")

    # Loading text
    painter.setPen(QColor("#484f58"))
    f3 = QFont("Segoe UI", 10)
    painter.setFont(f3)
    painter.drawText(20, 190, 440, 30, Qt.AlignmentFlag.AlignCenter,
                     "Initializing database and services…")
    painter.end()

    splash = QSplashScreen(pix)
    splash.setWindowFlags(Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint)
    return splash


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PostureGuard")
    app.setOrganizationName("PostureGuard")
    app.setStyle("Fusion")           # Consistent cross-platform rendering
    apply_dark_palette(app)

    # ── Splash ────────────────────────────────────────────────────────────────
    splash = create_splash(app)
    splash.show()
    app.processEvents()

    # ── Database init ─────────────────────────────────────────────────────────
    db.init_db()

    # ── Launch main window ────────────────────────────────────────────────────
    window = MainWindow()

    def _show_main():
        splash.finish(window)
        window.show()

    QTimer.singleShot(1800, _show_main)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

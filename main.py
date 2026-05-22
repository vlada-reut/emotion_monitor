from __future__ import annotations

import sys

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from services.config_service import load_settings
from ui.main_window import MainWindow


def apply_light_theme(app: QApplication) -> None:
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#f4f7fb"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#1d2d44"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f8fbff"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#1d2d44"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#1d2d44"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#1d2d44"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#d9e8ff"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#16345a"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#8a9aae"))
    app.setPalette(palette)

    app.setStyleSheet(
        """
        QComboBox QAbstractItemView,
        QListView,
        QTreeView,
        QTableView,
        QMenu,
        QToolTip {
            background: #ffffff;
            color: #1d2d44;
            border: 1px solid #d8e2ee;
            selection-background-color: #e8f0ff;
            selection-color: #16345a;
        }
        QComboBox {
            background: #ffffff;
        }
        """
    )


def main() -> None:
    settings = load_settings()
    app = QApplication(sys.argv)
    apply_light_theme(app)
    window = MainWindow(settings)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

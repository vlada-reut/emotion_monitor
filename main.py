from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from services.config_service import load_settings
from ui.main_window import MainWindow


def main() -> None:
    settings = load_settings()
    app = QApplication(sys.argv)
    window = MainWindow(settings)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

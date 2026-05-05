from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app_paths import get_database_path, get_resource_base_dir
from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    base_dir = get_resource_base_dir()
    database_path = get_database_path()
    window = MainWindow(database_path, base_dir)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

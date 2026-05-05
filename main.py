from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir / "data"
    window = MainWindow(data_dir / "order_helper.sqlite3", base_dir)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

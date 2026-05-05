from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "Amway Order Helper"
APP_DIR_NAME = "amway-order-helper"


def get_resource_base_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def get_user_data_dir() -> Path:
    home = Path.home()
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        return base / APP_DIR_NAME
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / APP_DIR_NAME
    return Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share")) / APP_DIR_NAME


def get_database_path() -> Path:
    return get_user_data_dir() / "order_helper.sqlite3"

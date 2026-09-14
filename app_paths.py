from __future__ import annotations

import json
import os
import sys
from pathlib import Path


APP_NAME = "Amway Order Helper"
APP_DIR_NAME = "amway-order-helper"
DATABASE_CONFIG_NAME = "database_location.json"


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


def get_default_database_path() -> Path:
    return get_user_data_dir() / "order_helper.sqlite3"


def get_database_config_path() -> Path:
    return get_user_data_dir() / DATABASE_CONFIG_NAME


def get_database_path() -> Path:
    config_path = get_database_config_path()
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return get_default_database_path()
        configured_path = Path(str(payload.get("database_path", ""))).expanduser()
        if configured_path.is_absolute():
            return configured_path
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    return get_default_database_path()


def save_database_path(path: Path) -> Path:
    normalized_path = path.expanduser()
    if not normalized_path.is_absolute():
        raise ValueError("Путь к базе данных должен быть полным.")
    normalized_path = normalized_path.resolve(strict=False)

    config_path = get_database_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = config_path.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps({"database_path": str(normalized_path)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary_path, config_path)
    return normalized_path

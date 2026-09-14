from pathlib import Path

import pytest

import app_paths


def test_database_path_defaults_to_platform_data_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(app_paths, "get_user_data_dir", lambda: tmp_path)

    assert app_paths.get_database_path() == tmp_path / "order_helper.sqlite3"


def test_custom_database_path_is_persisted_outside_database(tmp_path, monkeypatch) -> None:
    config_directory = tmp_path / "config"
    custom_database = tmp_path / "shared" / "orders.db"
    monkeypatch.setattr(app_paths, "get_user_data_dir", lambda: config_directory)

    saved_path = app_paths.save_database_path(custom_database)

    assert saved_path == custom_database.resolve(strict=False)
    assert app_paths.get_database_path() == custom_database.resolve(strict=False)
    assert app_paths.get_database_config_path().is_file()


def test_invalid_database_config_falls_back_to_default(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(app_paths, "get_user_data_dir", lambda: tmp_path)
    config_path = app_paths.get_database_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("not json", encoding="utf-8")

    assert app_paths.get_database_path() == app_paths.get_default_database_path()


def test_database_path_must_be_absolute(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(app_paths, "get_user_data_dir", lambda: tmp_path)

    with pytest.raises(ValueError, match="полным"):
        app_paths.save_database_path(Path("relative.db"))

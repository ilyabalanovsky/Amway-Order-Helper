from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from db.database import Database
from models import AppSettings
from ui.main_window import AppContext
from ui.settings_tab import SettingsTab


class RefreshCounter:
    def __init__(self) -> None:
        self.calls = 0

    def refresh(self) -> None:
        self.calls += 1


class DefaultsCounter:
    def __init__(self) -> None:
        self.calls = 0

    def apply_default_settings(self) -> None:
        self.calls += 1


@pytest.fixture(scope="module")
def qapp():
    application = QApplication.instance() or QApplication([])
    yield application


def test_successful_database_switch_preserves_data_and_refreshes_tabs(tmp_path, monkeypatch) -> None:
    source = Database(tmp_path / "source.sqlite3")
    source.initialize()
    with source.connect() as connection:
        connection.execute("INSERT INTO partner_groups (name) VALUES (?)", ("Группа",))
        connection.commit()

    partners_tab = RefreshCounter()
    history_tab = RefreshCounter()
    main_window = SimpleNamespace(
        database=source,
        partners_tab=partners_tab,
        history_tab=history_tab,
    )
    context = AppContext(source, tmp_path, main_window)
    target = tmp_path / "custom" / "orders.sqlite3"
    saved_paths: list[Path] = []
    monkeypatch.setattr(
        "ui.main_window.save_database_path",
        lambda path: saved_paths.append(path) or path,
    )

    result = context.change_database_path(target)

    assert result == target.resolve(strict=False)
    assert context.database.path == target.resolve(strict=False)
    assert main_window.database is context.database
    assert saved_paths == [target.resolve(strict=False)]
    assert partners_tab.calls == 1
    assert history_tab.calls == 1
    with context.database.connect() as connection:
        assert connection.execute("SELECT name FROM partner_groups").fetchone()["name"] == "Группа"


def test_failed_database_switch_keeps_current_database(tmp_path, monkeypatch) -> None:
    source = Database(tmp_path / "source.sqlite3")
    source.initialize()
    invalid_target = tmp_path / "invalid.sqlite3"
    invalid_target.write_text("это не SQLite", encoding="utf-8")
    partners_tab = RefreshCounter()
    history_tab = RefreshCounter()
    main_window = SimpleNamespace(
        database=source,
        partners_tab=partners_tab,
        history_tab=history_tab,
    )
    context = AppContext(source, tmp_path, main_window)
    save_calls: list[Path] = []
    monkeypatch.setattr(
        "ui.main_window.save_database_path",
        lambda path: save_calls.append(path) or path,
    )

    with pytest.raises(sqlite3.DatabaseError):
        context.change_database_path(invalid_target)

    assert context.database is source
    assert main_window.database is source
    assert save_calls == []
    assert partners_tab.calls == 0
    assert history_tab.calls == 0


class FakeSettingsContext:
    def __init__(self, database_path: Path, switch_error: Exception | None = None) -> None:
        self.database = SimpleNamespace(path=database_path)
        self.main_window = SimpleNamespace(order_tab=DefaultsCounter())
        self.switch_error = switch_error
        self.saved_settings: AppSettings | None = None

    def load_settings(self) -> AppSettings:
        return AppSettings()

    def change_database_path(self, path: Path) -> Path:
        if self.switch_error is not None:
            raise self.switch_error
        self.database.path = path.resolve(strict=False)
        return self.database.path

    def save_settings(self, settings: AppSettings) -> None:
        self.saved_settings = settings

    def reset_settings(self) -> None:
        pass


def test_settings_shows_success_modal_after_database_switch(tmp_path, monkeypatch, qapp) -> None:
    context = FakeSettingsContext(tmp_path / "source.sqlite3")
    tab = SettingsTab(context)
    target = tmp_path / "custom" / "orders.sqlite3"
    tab.database_path.setText(str(target))
    messages: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, title, text: messages.append((title, text)),
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *_args: pytest.fail("Предупреждение не должно показываться при успешном переключении"),
    )

    tab.save()

    assert context.saved_settings is not None
    assert messages == [
        (
            "База данных подключена",
            f"Настройки сохранены. Приложение использует базу данных:\n{target.resolve(strict=False)}",
        )
    ]


def test_settings_shows_error_modal_after_failed_database_switch(tmp_path, monkeypatch, qapp) -> None:
    error = sqlite3.DatabaseError("file is not a database")
    context = FakeSettingsContext(tmp_path / "source.sqlite3", switch_error=error)
    tab = SettingsTab(context)
    target = tmp_path / "broken.sqlite3"
    tab.database_path.setText(str(target))
    messages: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, title, text: messages.append((title, text)),
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *_args: pytest.fail("Успешная модалка не должна показываться при ошибке"),
    )

    tab.save()

    assert context.saved_settings is None
    assert len(messages) == 1
    assert messages[0][0] == "Ошибка базы данных"
    assert str(target) in messages[0][1]
    assert "file is not a database" in messages[0][1]

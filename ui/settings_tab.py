from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path

from app_paths import get_default_database_path
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SettingsTab(QWidget):
    def __init__(self, app_context) -> None:
        super().__init__()
        self.app_context = app_context
        self._build_ui()
        self.load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(8)
        form = QFormLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)
        self.output_dir = QLineEdit()
        self.database_path = QLineEdit()
        self.file_template = QLineEdit()
        self.delivery_percent = QLineEdit()
        self.expenses = QLineEdit()
        self.open_after_export = QCheckBox("Открывать файл после генерации")
        self.warn_on_total_mismatch = QCheckBox("Предупреждать при расхождении итогов")
        self.block_unknown = QCheckBox("Запрещать экспорт при неизвестных партнёрах")
        database_row = QWidget()
        database_layout = QHBoxLayout(database_row)
        database_layout.setContentsMargins(0, 0, 0, 0)
        database_layout.setSpacing(6)
        choose_database = QPushButton("Выбрать")
        default_database = QPushButton("Стандартный")
        choose_database.clicked.connect(self.choose_database_path)
        default_database.clicked.connect(self.use_default_database_path)
        database_layout.addWidget(self.database_path, 1)
        database_layout.addWidget(choose_database)
        database_layout.addWidget(default_database)
        form.addRow("Файл базы данных", database_row)
        form.addRow("Путь сохранения Excel", self.output_dir)
        form.addRow("Шаблон имени", self.file_template)
        form.addRow("Доставка %", self.delivery_percent)
        form.addRow("Расходы", self.expenses)
        form.addRow("", self.open_after_export)
        form.addRow("", self.warn_on_total_mismatch)
        form.addRow("", self.block_unknown)
        layout.addLayout(form)
        save = QPushButton("Сохранить настройки")
        reset = QPushButton("Сбросить")
        save.clicked.connect(self.save)
        reset.clicked.connect(self.reset)
        layout.addWidget(save)
        layout.addWidget(reset)

    def load(self) -> None:
        settings = self.app_context.load_settings()
        self.database_path.setText(str(self.app_context.database.path.resolve(strict=False)))
        self.output_dir.setText(settings.default_output_dir)
        self.file_template.setText(settings.file_name_template)
        delivery_percent = float(settings.default_delivery_percent)
        self.delivery_percent.setText(str(int(delivery_percent * 100 if delivery_percent <= 1 else delivery_percent)))
        self.expenses.setText(str(settings.default_expenses))
        self.open_after_export.setChecked(settings.open_after_export)
        self.warn_on_total_mismatch.setChecked(settings.warn_on_total_mismatch)
        self.block_unknown.setChecked(settings.block_export_on_unknown_partner)

    def save(self) -> None:
        raw_database_path = self.database_path.text().strip()
        database_path = Path(raw_database_path).expanduser()
        if not raw_database_path or not database_path.is_absolute():
            QMessageBox.warning(
                self,
                "Некорректный путь",
                "Укажите полный путь к файлу базы данных.",
            )
            return

        settings = self.app_context.load_settings()
        settings.default_output_dir = self.output_dir.text().strip()
        settings.file_name_template = self.file_template.text().strip()
        raw_delivery = Decimal(self.delivery_percent.text().strip() or "6")
        settings.default_delivery_percent = raw_delivery / Decimal("100") if raw_delivery > 1 else raw_delivery
        settings.default_expenses = Decimal(self.expenses.text().strip() or "10")
        settings.open_after_export = self.open_after_export.isChecked()
        settings.warn_on_total_mismatch = self.warn_on_total_mismatch.isChecked()
        settings.block_export_on_unknown_partner = self.block_unknown.isChecked()
        try:
            saved_database_path = self.app_context.change_database_path(database_path)
            self.app_context.save_settings(settings)
        except (OSError, ValueError, sqlite3.Error) as exc:
            QMessageBox.warning(
                self,
                "Ошибка базы данных",
                f"Не удалось переключиться на базу данных:\n{database_path}\n\n{exc}",
            )
            return
        self.database_path.setText(str(saved_database_path))
        self.app_context.main_window.order_tab.apply_default_settings()
        QMessageBox.information(
            self,
            "База данных подключена",
            f"Настройки сохранены. Приложение использует базу данных:\n{saved_database_path}",
        )

    def reset(self) -> None:
        self.app_context.reset_settings()
        self.app_context.main_window.order_tab.apply_default_settings()
        self.load()

    def choose_database_path(self) -> None:
        dialog = QFileDialog(self, "Выберите существующую или новую базу данных")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setFileMode(QFileDialog.FileMode.AnyFile)
        dialog.setNameFilters(["SQLite (*.sqlite3 *.sqlite *.db)", "Все файлы (*)"])
        dialog.setOption(QFileDialog.Option.DontConfirmOverwrite, True)
        current_path = self.database_path.text().strip()
        if current_path:
            dialog.selectFile(current_path)
        if dialog.exec() and dialog.selectedFiles():
            path = dialog.selectedFiles()[0]
            self.database_path.setText(str(Path(path).resolve(strict=False)))

    def use_default_database_path(self) -> None:
        self.database_path.setText(str(get_default_database_path().resolve(strict=False)))

from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
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
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        form = QFormLayout()
        self.output_dir = QLineEdit()
        self.file_template = QLineEdit()
        self.delivery_percent = QLineEdit()
        self.expenses = QLineEdit()
        self.dispatch_city = QLineEdit()
        self.sender = QLineEdit()
        self.open_after_export = QCheckBox("Открывать файл после генерации")
        self.warn_on_total_mismatch = QCheckBox("Предупреждать при расхождении итогов")
        self.block_unknown = QCheckBox("Запрещать экспорт при неизвестных партнёрах")
        form.addRow("Путь по умолчанию", self.output_dir)
        form.addRow("Шаблон имени", self.file_template)
        form.addRow("Доставка %", self.delivery_percent)
        form.addRow("Расходы", self.expenses)
        form.addRow("Город отправки", self.dispatch_city)
        form.addRow("Отправитель", self.sender)
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
        self.output_dir.setText(settings.default_output_dir)
        self.file_template.setText(settings.file_name_template)
        self.delivery_percent.setText(str(settings.default_delivery_percent))
        self.expenses.setText(str(settings.default_expenses))
        self.dispatch_city.setText(settings.default_dispatch_city)
        self.sender.setText(settings.default_sender)
        self.open_after_export.setChecked(settings.open_after_export)
        self.warn_on_total_mismatch.setChecked(settings.warn_on_total_mismatch)
        self.block_unknown.setChecked(settings.block_export_on_unknown_partner)

    def save(self) -> None:
        settings = self.app_context.load_settings()
        settings.default_output_dir = self.output_dir.text().strip()
        settings.file_name_template = self.file_template.text().strip()
        settings.default_delivery_percent = Decimal(self.delivery_percent.text().strip() or "0.06")
        settings.default_expenses = Decimal(self.expenses.text().strip() or "10")
        settings.default_dispatch_city = self.dispatch_city.text().strip()
        settings.default_sender = self.sender.text().strip()
        settings.open_after_export = self.open_after_export.isChecked()
        settings.warn_on_total_mismatch = self.warn_on_total_mismatch.isChecked()
        settings.block_export_on_unknown_partner = self.block_unknown.isChecked()
        self.app_context.save_settings(settings)
        QMessageBox.information(self, "Сохранено", "Настройки обновлены.")

    def reset(self) -> None:
        self.app_context.reset_settings()
        self.load()

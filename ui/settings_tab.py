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
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(8)
        form = QFormLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)
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
        delivery_percent = float(settings.default_delivery_percent)
        self.delivery_percent.setText(str(int(delivery_percent * 100 if delivery_percent <= 1 else delivery_percent)))
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
        raw_delivery = Decimal(self.delivery_percent.text().strip() or "6")
        settings.default_delivery_percent = raw_delivery / Decimal("100") if raw_delivery > 1 else raw_delivery
        settings.default_expenses = Decimal(self.expenses.text().strip() or "10")
        settings.default_dispatch_city = self.dispatch_city.text().strip()
        settings.default_sender = self.sender.text().strip()
        settings.open_after_export = self.open_after_export.isChecked()
        settings.warn_on_total_mismatch = self.warn_on_total_mismatch.isChecked()
        settings.block_export_on_unknown_partner = self.block_unknown.isChecked()
        self.app_context.save_settings(settings)
        self.app_context.main_window.order_tab.apply_default_settings()
        QMessageBox.information(self, "Сохранено", "Настройки обновлены.")

    def reset(self) -> None:
        self.app_context.reset_settings()
        self.app_context.main_window.order_tab.apply_default_settings()
        self.load()

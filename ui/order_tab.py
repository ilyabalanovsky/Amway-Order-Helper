from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDateEdit,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from models import Order, ParsedOrder
from services.order_service import OrderService
from services.parser import OrderTextParser


class OrderTab(QWidget):
    order_saved = Signal()

    def __init__(self, app_context) -> None:
        super().__init__()
        self.app_context = app_context
        self.parser = OrderTextParser()
        self.parsed_order = ParsedOrder()
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)
        splitter = QSplitter(Qt.Orientation.Vertical)
        root.addWidget(splitter)

        top = QWidget()
        top_layout = QVBoxLayout(top)
        self.text_edit = QTextEdit()
        self.text_edit.setMinimumHeight(180)
        self.parse_button = QPushButton("Запустить парсинг")
        self.parse_button.clicked.connect(self.parse_order)
        top_layout.addWidget(QLabel("Текст с расширения (с названием полей)"))
        top_layout.addWidget(self.text_edit)
        top_layout.addWidget(self.parse_button)
        splitter.addWidget(top)

        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        form = QFormLayout()
        self.order_date = QDateEdit()
        self.order_date.setCalendarPopup(True)
        self.order_date.setDate(date.today())
        self.order_number = QLineEdit()
        self.dispatch_city = QLineEdit()
        self.sender = QLineEdit()
        self.tenge_rate = self._decimal_box(6.0, decimals=3, step=0.001)
        self.tenge_rate_fact = self._decimal_box(6.0, decimals=3, step=0.001)
        self.delivery_percent = self._decimal_box(6.0, decimals=0, step=1.0)
        self.expenses = self._decimal_box(10.0)
        form.addRow("Дата заказа", self.order_date)
        form.addRow("Номер заказа", self.order_number)
        form.addRow("Город отправки", self.dispatch_city)
        form.addRow("Отправитель", self.sender)
        form.addRow("Курс тенге", self.tenge_rate)
        form.addRow("Курс тенге фактический", self.tenge_rate_fact)
        form.addRow("Процент доставки", self.delivery_percent)
        form.addRow("Расходы", self.expenses)
        bottom_layout.addLayout(form)

        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels([
            "№", "ФИО", "Группа", "Сумма", "Скидка", "Со скидкой",
            "Рег. взнос", "Доставка (%)", "Оплатили", "Перевели", "Ошибка",
        ])
        self.table.verticalHeader().setVisible(False)
        bottom_layout.addWidget(self.table)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Сохранить заказ")
        history_btn = QPushButton("Открыть заказ из истории")
        export_new_btn = QPushButton("Сформировать новый Excel-файл")
        export_append_btn = QPushButton("Добавить лист в существующий Excel-файл")
        save_btn.clicked.connect(self.save_order)
        history_btn.clicked.connect(self.open_from_history)
        export_new_btn.clicked.connect(self.export_new)
        export_append_btn.clicked.connect(self.export_append)
        for button in (save_btn, history_btn, export_new_btn, export_append_btn):
            buttons.addWidget(button)
        bottom_layout.addLayout(buttons)
        splitter.addWidget(bottom)

    def _decimal_box(self, value: float, decimals: int = 2, step: float = 1.0) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        box.setDecimals(decimals)
        box.setRange(0, 1_000_000)
        box.setSingleStep(step)
        box.setValue(value)
        return box

    def parse_order(self) -> None:
        parsed = self.parser.parse(self.text_edit.toPlainText())
        with self.app_context.database.connect() as conn:
            enriched = OrderService(self.app_context.partner_repo(conn)).enrich_with_partners(parsed)
        self.parsed_order = enriched
        self._fill_table()
        messages = enriched.errors + enriched.warnings
        if messages:
            QMessageBox.warning(self, "Результат парсинга", "\n".join(messages))

    def _fill_table(self) -> None:
        self.table.setColumnCount(11)
        self.table.setRowCount(len(self.parsed_order.items))
        group_map = self.app_context.get_group_name_map()
        for row, item in enumerate(self.parsed_order.items):
            item.group_name = group_map.get(item.group_id, "")
            values = [
                item.source_number,
                item.full_name,
                item.group_name,
                str(item.amount_tenge),
                str(item.discount_tenge),
                str(item.amount_with_discount_tenge),
                "" if item.registration_fee is None else str(item.registration_fee),
                "" if item.delivery_percent is None else str(item.delivery_percent),
                "" if item.paid_rub is None else str(item.paid_rub),
                "" if item.transferred_rub is None else str(item.transferred_rub),
                item.parse_error,
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if col == 10 and value:
                    cell.setBackground(Qt.GlobalColor.yellow)
                    cell.setForeground(QColor("black"))
                self.table.setItem(row, col, cell)

    def _collect_order(self) -> Order:
        group_id_by_name = {name: gid for gid, name in self.app_context.get_group_name_map().items()}
        for row, item in enumerate(self.parsed_order.items):
            item.group_name = self.table.item(row, 2).text() if self.table.item(row, 2) else item.group_name
            item.group_id = group_id_by_name.get(item.group_name or "", item.group_id)
            item.registration_fee = self._decimal_or_none(row, 6)
            item.delivery_percent = self._decimal_or_none(row, 7)
            item.paid_rub = self._decimal_or_none(row, 8)
            item.transferred_rub = self._decimal_or_none(row, 9)
        return OrderService.build_order(
            self.parsed_order,
            order_number=self.order_number.text().strip(),
            order_date=self.order_date.date().toPython(),
            sender=self.sender.text().strip(),
            dispatch_city=self.dispatch_city.text().strip(),
            tenge_rate=Decimal(str(self.tenge_rate.value())),
            tenge_rate_fact=Decimal(str(self.tenge_rate_fact.value())),
            delivery_percent=Decimal(str(self.delivery_percent.value())),
            expenses=Decimal(str(self.expenses.value())),
            raw_text=self.text_edit.toPlainText(),
        )

    def _decimal_or_none(self, row: int, column: int):
        item = self.table.item(row, column)
        if not item or not item.text().strip():
            return None
        return Decimal(item.text().replace(",", "."))

    def save_order(self) -> None:
        order = self._collect_order()
        self.app_context.save_order(order)
        self.order_saved.emit()
        QMessageBox.information(self, "Сохранено", "Заказ сохранён в историю.")

    def open_from_history(self) -> None:
        self.app_context.main_window.show_history_tab()

    def export_new(self) -> None:
        order = self._collect_order()
        errors = OrderService.validate_export(order)
        if errors:
            QMessageBox.warning(self, "Экспорт невозможен", "\n".join(errors))
            return
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить Excel", "", "Excel (*.xlsx)")
        if not path:
            return
        result = self.app_context.exporter.export_new(order, self.app_context.to_path(path))
        QMessageBox.information(self, "Готово", f"Файл сохранён:\n{result.path}")

    def export_append(self) -> None:
        order = self._collect_order()
        errors = OrderService.validate_export(order)
        if errors:
            QMessageBox.warning(self, "Экспорт невозможен", "\n".join(errors))
            return
        source, _ = QFileDialog.getOpenFileName(self, "Выберите Excel", "", "Excel (*.xlsx)")
        if not source:
            return
        target, _ = QFileDialog.getSaveFileName(self, "Сохранить результат", source, "Excel (*.xlsx)")
        if not target:
            return
        result = self.app_context.exporter.append_sheet(
            order,
            self.app_context.to_path(source),
            self.app_context.to_path(target),
        )
        QMessageBox.information(self, "Готово", f"Лист добавлен:\n{result.path}")

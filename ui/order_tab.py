from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QDateEdit,
    QDoubleSpinBox,
    QGridLayout,
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
    QHeaderView,
)

from models import Order, ParsedOrder
from services.order_service import OrderService
from services.parser import OrderTextParser


class JsonDropZone(QFrame):
    file_dropped = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setObjectName("jsonDropZone")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(2)
        self.title_label = QLabel("Перетащите сюда JSON с расширения")
        self.title_label.setObjectName("dropZoneTitle")
        self.info_label = QLabel("или нажмите кнопку ниже, чтобы выбрать файл")
        self.info_label.setObjectName("dropZoneInfo")
        self.file_label = QLabel("Файл не выбран")
        self.file_label.setObjectName("dropZoneFile")
        layout.addWidget(self.title_label)
        layout.addWidget(self.info_label)
        layout.addWidget(self.file_label)

    def set_file_name(self, file_name: str) -> None:
        self.file_label.setText(file_name or "Файл не выбран")

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            urls = [url for url in event.mimeData().urls() if url.isLocalFile()]
            if urls and urls[0].toLocalFile().lower().endswith(".json"):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        urls = [url for url in event.mimeData().urls() if url.isLocalFile()]
        if not urls:
            event.ignore()
            return
        path = urls[0].toLocalFile()
        if not path.lower().endswith(".json"):
            event.ignore()
            return
        self.file_dropped.emit(path)
        event.acceptProposedAction()


class OrderTab(QWidget):
    order_saved = Signal()

    def __init__(self, app_context) -> None:
        super().__init__()
        self.app_context = app_context
        self.parser = OrderTextParser()
        self.parsed_order = ParsedOrder()
        self.current_json_text = ""
        self._build_ui()
        self.apply_default_settings()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(8)
        splitter = QSplitter(Qt.Orientation.Vertical)
        root.addWidget(splitter)

        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)
        self.drop_zone = JsonDropZone()
        self.drop_zone.file_dropped.connect(self.load_json_file)
        top_layout.addWidget(self.drop_zone)
        top_buttons = QHBoxLayout()
        top_buttons.setSpacing(8)
        self.choose_file_button = QPushButton("Выбрать JSON-файл")
        self.choose_file_button.clicked.connect(self.choose_json_file)
        self.parse_button = QPushButton("Запустить парсинг")
        self.parse_button.clicked.connect(self.parse_loaded_json)
        top_buttons.addWidget(self.choose_file_button)
        top_buttons.addWidget(self.parse_button)
        top_layout.addLayout(top_buttons)
        splitter.addWidget(top)

        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(8)
        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(6)
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
        fields = [
            ("Дата заказа", self.order_date),
            ("Номер заказа", self.order_number),
            ("Город отправки", self.dispatch_city),
            ("Отправитель", self.sender),
            ("Курс тенге", self.tenge_rate),
            ("Курс тенге фактический", self.tenge_rate_fact),
            ("Процент доставки", self.delivery_percent),
            ("Расходы", self.expenses),
        ]
        for index, (label_text, widget) in enumerate(fields):
            row = index // 2
            column = (index % 2) * 2
            form.addWidget(QLabel(label_text), row, column)
            form.addWidget(widget, row, column + 1)
        bottom_layout.addLayout(form)

        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels([
            "№", "ФИО", "Группа", "Сумма", "Скидка", "Со скидкой",
            "Рег. взнос", "Доставка (%)", "Оплатили", "Перевели", "Ошибка",
        ])
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        for column in range(3, 10):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(10, QHeaderView.ResizeMode.Stretch)
        bottom_layout.addWidget(self.table)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        save_btn = QPushButton("Сохранить в истории")
        history_btn = QPushButton("Открыть из истории")
        export_new_btn = QPushButton("Новый Excel файл")
        export_append_btn = QPushButton("Новый лист в Excel файле")
        summary_btn = QPushButton("Создать сводную таблицу")
        save_btn.clicked.connect(self.save_order)
        history_btn.clicked.connect(self.open_from_history)
        export_new_btn.clicked.connect(self.export_new)
        export_append_btn.clicked.connect(self.export_append)
        summary_btn.clicked.connect(self.export_product_summary)
        for button in (save_btn, history_btn, export_new_btn, export_append_btn, summary_btn):
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

    def choose_json_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выберите JSON ответа API", "", "JSON (*.json)")
        if not path:
            return
        self.load_json_file(path)

    def load_json_file(self, path: str) -> None:
        try:
            raw = Path(path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw = Path(path).read_text(encoding="utf-8-sig")
        except OSError as exc:
            QMessageBox.warning(self, "Ошибка открытия", f"Не удалось открыть файл:\n{exc}")
            return
        self.current_json_text = raw
        self.drop_zone.set_file_name(Path(path).name)
        self.parse_loaded_json()

    def parse_loaded_json(self) -> None:
        parsed = self.parser.parse_json_text(self.current_json_text)
        with self.app_context.database.connect() as conn:
            enriched = OrderService(self.app_context.partner_repo(conn)).enrich_with_partners(parsed)
        self.parsed_order = enriched
        self._apply_parsed_metadata()
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
            raw_text=self.current_json_text,
        )

    def _decimal_or_none(self, row: int, column: int):
        item = self.table.item(row, column)
        if not item or not item.text().strip():
            return None
        return Decimal(item.text().replace(",", "."))

    def apply_default_settings(self) -> None:
        settings = self.app_context.load_settings()
        delivery_percent = float(settings.default_delivery_percent)
        self.delivery_percent.setValue(delivery_percent * 100 if delivery_percent <= 1 else delivery_percent)
        self.expenses.setValue(float(settings.default_expenses))

    def _apply_parsed_metadata(self) -> None:
        if self.parsed_order.order_number:
            self.order_number.setText(self.parsed_order.order_number)
        if self.parsed_order.order_date:
            self.order_date.setDate(self.parsed_order.order_date)
        if self.parsed_order.dispatch_city:
            self.dispatch_city.setText(self.parsed_order.dispatch_city)
        if self.parsed_order.sender:
            self.sender.setText(self.parsed_order.sender)

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
        self._open_export_if_enabled(result.path)
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
        self._open_export_if_enabled(result.path)
        QMessageBox.information(self, "Готово", f"Лист добавлен:\n{result.path}")

    def export_product_summary(self) -> None:
        if not self.current_json_text.strip():
            QMessageBox.warning(self, "Нет данных", "Сначала загрузите JSON заказа.")
            return
        default_name = self.order_number.text().strip() or "product_summary"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить сводную таблицу",
            f"{default_name}_summary.xlsx",
            "Excel (*.xlsx)",
        )
        if not path:
            return
        try:
            result = self.app_context.product_summary_exporter.export(
                self.current_json_text,
                self.app_context.to_path(path),
                self.app_context.get_partner_group_map(),
            )
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Ошибка экспорта", str(exc))
            return
        self._open_export_if_enabled(result.path)
        QMessageBox.information(self, "Готово", f"Сводная таблица сохранена:\n{result.path}")

    def _open_export_if_enabled(self, path) -> None:
        settings = self.app_context.load_settings()
        if not settings.open_after_export:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHeaderView,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class HistoryTab(QWidget):
    open_order_requested = Signal(int)

    def __init__(self, app_context) -> None:
        super().__init__()
        self.app_context = app_context
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(8)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск по номеру, дате, отправителю")
        refresh = QPushButton("Обновить")
        delete = QPushButton("Удалить")
        open_btn = QPushButton("Открыть")
        self.search.textChanged.connect(self.refresh)
        refresh.clicked.connect(self.refresh)
        delete.clicked.connect(self.delete_selected)
        open_btn.clicked.connect(self.open_selected)
        top.addWidget(self.search)
        top.addWidget(refresh)
        top.addWidget(open_btn)
        top.addWidget(delete)
        layout.addLayout(top)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Номер", "Дата", "Отправитель", "Город", "Участники", "Сумма", "Курс",
        ])
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)

    def refresh(self) -> None:
        orders = self.app_context.load_orders(self.search.text().strip())
        self.table.setRowCount(len(orders))
        for row, order in enumerate(orders):
            summary = order.as_summary()
            values = [
                str(order.id),
                order.order_number,
                order.order_date.isoformat() if order.order_date else "",
                order.sender,
                order.dispatch_city,
                str(summary["participants"]),
                str(summary["amount_with_discount_tenge"]),
                str(order.tenge_rate),
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))

    def open_selected(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.open_order_requested.emit(int(self.table.item(row, 0).text()))

    def delete_selected(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.app_context.delete_order(int(self.table.item(row, 0).text()))
            self.refresh()

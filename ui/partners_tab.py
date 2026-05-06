from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from models import Partner
from services.normalizer import clean_name, normalize_name


class GroupEditDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Новая группа")
        self.setModal(True)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit()
        form.addRow("Название группы", self.name_edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def group_name(self) -> str:
        return clean_name(self.name_edit.text())


class BulkPartnerDialog(QDialog):
    def __init__(self, app_context, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.app_context = app_context
        self.setWindowTitle("Пакетное добавление партнёров")
        self.setModal(True)
        self.resize(520, 420)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        group_row = QHBoxLayout()
        self.group_combo = QComboBox()
        self.create_group_btn = QPushButton("Новая группа")
        self.create_group_btn.clicked.connect(self.create_group)
        group_row.addWidget(self.group_combo)
        group_row.addWidget(self.create_group_btn)
        self.comment_edit = QLineEdit()
        form.addRow("Группа", group_row)
        form.addRow("Комментарий", self.comment_edit)
        layout.addLayout(form)
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Каждая строка = новый партнёр")
        layout.addWidget(self.text_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.reload_groups()

    def reload_groups(self) -> None:
        current = self.group_combo.currentData()
        self.group_combo.clear()
        for group in self.app_context.load_groups():
            self.group_combo.addItem(group.name, group.id)
        if current is not None:
            index = self.group_combo.findData(current)
            if index >= 0:
                self.group_combo.setCurrentIndex(index)

    def create_group(self) -> None:
        dialog = GroupEditDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name = dialog.group_name()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Введите название группы.")
            return
        self.app_context.create_group(name)
        self.reload_groups()
        index = self.group_combo.findText(name, Qt.MatchFlag.MatchFixedString)
        if index >= 0:
            self.group_combo.setCurrentIndex(index)

    def partner_names(self) -> list[str]:
        return [clean_name(line) for line in self.text_edit.toPlainText().splitlines() if clean_name(line)]


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event) -> None:  # type: ignore[override]
        if self.view().isVisible():
            super().wheelEvent(event)
            return
        event.ignore()


class PartnersTab(QWidget):
    def __init__(self, app_context) -> None:
        super().__init__()
        self.app_context = app_context
        self._is_refreshing = False
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(8)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск по ФИО")
        self.group_filter = QComboBox()
        self.group_filter.currentIndexChanged.connect(self.refresh)
        self.search.textChanged.connect(self.refresh)
        filters.addWidget(self.search)
        filters.addWidget(self.group_filter)
        layout.addLayout(filters)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        add_partner = QPushButton("Добавить партнёра")
        add_group = QPushButton("Добавить группу")
        delete_partner = QPushButton("Удалить выбранного")
        add_partner.clicked.connect(self.add_bulk_partners)
        add_group.clicked.connect(self.add_group)
        delete_partner.clicked.connect(self.delete_partner)
        buttons.addWidget(add_partner)
        buttons.addWidget(add_group)
        buttons.addWidget(delete_partner)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["ФИО", "Группа", "Комментарий"])
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self.on_table_item_changed)
        layout.addWidget(self.table)

    def refresh(self) -> None:
        self._is_refreshing = True
        groups = self.app_context.load_groups()
        current_filter_group = self.group_filter.currentData()

        self.group_filter.blockSignals(True)
        self.group_filter.clear()
        self.group_filter.addItem("Все группы", None)
        for group in groups:
            self.group_filter.addItem(group.name, group.id)

        filter_index = self.group_filter.findData(current_filter_group)
        if filter_index >= 0:
            self.group_filter.setCurrentIndex(filter_index)

        self.group_filter.blockSignals(False)

        selected_group = self.group_filter.currentData()
        partners = self.app_context.load_partners(self.search.text().strip(), selected_group)
        self.table.blockSignals(True)
        self.table.setRowCount(len(partners))
        for row, partner in enumerate(partners):
            name_item = QTableWidgetItem(partner.full_name)
            name_item.setData(Qt.ItemDataRole.UserRole, partner.id)
            self.table.setItem(row, 0, name_item)

            group_cell = NoWheelComboBox()
            group_cell.addItem("", None)
            for group in groups:
                group_cell.addItem(group.name, group.id)
            group_index = group_cell.findData(partner.group_id)
            if group_index >= 0:
                group_cell.setCurrentIndex(group_index)
            group_cell.currentIndexChanged.connect(lambda _=0, r=row: self.on_group_changed(r))
            self.table.setCellWidget(row, 1, group_cell)

            comment_item = QTableWidgetItem(partner.comment)
            self.table.setItem(row, 2, comment_item)

        self.table.blockSignals(False)
        self._is_refreshing = False

    def add_group(self) -> None:
        dialog = GroupEditDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name = dialog.group_name()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Введите название группы.")
            return
        self.app_context.create_group(name)
        self.refresh()

    def add_bulk_partners(self) -> None:
        dialog = BulkPartnerDialog(self.app_context, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        names = dialog.partner_names()
        if not names:
            QMessageBox.warning(self, "Ошибка", "Добавьте хотя бы одного партнёра.")
            return
        group_id = dialog.group_combo.currentData()
        for full_name in names:
            partner = Partner(
                id=None,
                full_name=full_name,
                normalized_name=normalize_name(full_name),
                group_id=group_id,
                comment=dialog.comment_edit.text().strip(),
            )
            self.app_context.save_partner(partner)
        self.refresh()

    def delete_partner(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        partner_item = self.table.item(row, 0)
        if partner_item is None:
            return
        partner_id = partner_item.data(Qt.ItemDataRole.UserRole)
        if partner_id is None:
            return
        self.app_context.delete_partner(int(partner_id))
        self.refresh()

    def on_table_item_changed(self, item: QTableWidgetItem) -> None:
        if self._is_refreshing or item.column() not in (0, 2):
            return
        self._save_row(item.row())

    def on_group_changed(self, row: int) -> None:
        if self._is_refreshing:
            return
        self._save_row(row)

    def _save_row(self, row: int) -> None:
        name_item = self.table.item(row, 0)
        comment_item = self.table.item(row, 2)
        group_widget = self.table.cellWidget(row, 1)
        if name_item is None or comment_item is None or not isinstance(group_widget, QComboBox):
            return

        partner_id = name_item.data(Qt.ItemDataRole.UserRole)
        if partner_id is None:
            return

        full_name = clean_name(name_item.text())
        if not full_name:
            QMessageBox.warning(self, "Ошибка", "ФИО партнёра не может быть пустым.")
            self.refresh()
            return

        partner = Partner(
            id=int(partner_id),
            full_name=full_name,
            normalized_name=normalize_name(full_name),
            group_id=group_widget.currentData(),
            comment=comment_item.text().strip(),
        )
        try:
            self.app_context.update_partner(partner)
        except ValueError:
            QMessageBox.warning(self, "Ошибка", "Партнёр с таким ФИО уже существует.")
            self.refresh()
            return
        self.refresh()

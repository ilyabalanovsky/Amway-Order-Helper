from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QDialogButtonBox,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
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
        return [
            clean_name(line)
            for line in self.text_edit.toPlainText().splitlines()
            if clean_name(line)
        ]


class PartnersTab(QWidget):
    def __init__(self, app_context) -> None:
        super().__init__()
        self.app_context = app_context
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

        form = QFormLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)
        self.name_edit = QLineEdit()
        self.group_combo = QComboBox()
        self.comment_edit = QLineEdit()
        form.addRow("ФИО", self.name_edit)
        form.addRow("Группа", self.group_combo)
        form.addRow("Комментарий", self.comment_edit)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        add_partner = QPushButton("Добавить / обновить партнёра")
        add_bulk = QPushButton("Добавить пачку партнёров")
        add_group = QPushButton("Добавить группу")
        delete_partner = QPushButton("Удалить выбранного")
        add_partner.clicked.connect(self.save_partner)
        add_bulk.clicked.connect(self.add_bulk_partners)
        add_group.clicked.connect(self.add_group)
        delete_partner.clicked.connect(self.delete_partner)
        buttons.addWidget(add_partner)
        buttons.addWidget(add_bulk)
        buttons.addWidget(add_group)
        buttons.addWidget(delete_partner)
        layout.addLayout(buttons)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["ФИО", "Группа", "Комментарий"])
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

    def refresh(self) -> None:
        groups = self.app_context.load_groups()
        self.group_filter.blockSignals(True)
        self.group_combo.blockSignals(True)
        self.group_filter.clear()
        self.group_filter.addItem("Все группы", None)
        self.group_combo.clear()
        for group in groups:
            self.group_filter.addItem(group.name, group.id)
            self.group_combo.addItem(group.name, group.id)
        self.group_filter.blockSignals(False)
        self.group_combo.blockSignals(False)
        selected_group = self.group_filter.currentData()
        partners = self.app_context.load_partners(self.search.text().strip(), selected_group)
        self.table.setRowCount(len(partners))
        group_map = self.app_context.get_group_name_map()
        for row, partner in enumerate(partners):
            name_item = QTableWidgetItem(partner.full_name)
            name_item.setData(Qt.ItemDataRole.UserRole, partner.id)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(group_map.get(partner.group_id, "")))
            self.table.setItem(row, 2, QTableWidgetItem(partner.comment))

    def save_partner(self) -> None:
        full_name = clean_name(self.name_edit.text())
        if not full_name:
            QMessageBox.warning(self, "Ошибка", "Укажите ФИО партнёра.")
            return
        partner = Partner(
            id=None,
            full_name=full_name,
            normalized_name=normalize_name(full_name),
            group_id=self.group_combo.currentData(),
            comment=self.comment_edit.text().strip(),
        )
        self.app_context.save_partner(partner)
        self.refresh()

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
        partner_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        self.app_context.delete_partner(int(partner_id))
        self.refresh()

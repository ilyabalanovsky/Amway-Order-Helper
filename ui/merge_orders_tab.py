from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zipfile import BadZipFile

from openpyxl.utils.exceptions import InvalidFileException
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from services.payment_workbook_merger import PaymentWorkbookMerger, WorkbookAnalysis


class ExcelDropZone(QFrame):
    file_dropped = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setObjectName("jsonDropZone")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(2)

        title = QLabel("Перетащите сюда Excel-файл с подзаказами")
        title.setObjectName("dropZoneTitle")
        info = QLabel("Все распознанные листы будут объединены в общую сводную таблицу")
        info.setObjectName("dropZoneInfo")
        self.file_label = QLabel("Файл не выбран")
        self.file_label.setObjectName("dropZoneFile")
        layout.addWidget(title)
        layout.addWidget(info)
        layout.addWidget(self.file_label)

    def set_file_name(self, file_name: str) -> None:
        self.file_label.setText(file_name or "Файл не выбран")

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        urls = [url for url in event.mimeData().urls() if url.isLocalFile()]
        if urls and urls[0].toLocalFile().lower().endswith(".xlsx"):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        urls = [url for url in event.mimeData().urls() if url.isLocalFile()]
        if not urls:
            event.ignore()
            return
        path = urls[0].toLocalFile()
        if not path.lower().endswith(".xlsx"):
            event.ignore()
            return
        self.file_dropped.emit(path)
        event.acceptProposedAction()


class MergeOrdersTab(QWidget):
    def __init__(self, app_context) -> None:
        super().__init__()
        self.app_context = app_context
        self.merger = PaymentWorkbookMerger(app_context.exporter)
        self.current_path: Path | None = None
        self.analysis: WorkbookAnalysis | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(8)

        heading = QLabel("Объединение подзаказов")
        heading.setStyleSheet("font-size: 20px; font-weight: 700; color: #173f68;")
        description = QLabel(
            "Добавляет в выбранный файл общий лист оплаты, сформированный из заказов по 30 кг. "
            "Исходные листы не изменяются."
        )
        description.setWordWrap(True)
        root.addWidget(heading)
        root.addWidget(description)

        date_row = QHBoxLayout()
        date_label = QLabel("Дата подзаказов")
        self.order_date = QLineEdit()
        self.order_date.setPlaceholderText("ГГГГ.ММ.ДД")
        self.order_date.setMaxLength(10)
        self.order_date.setClearButtonEnabled(True)
        self.order_date.textChanged.connect(self._on_date_changed)
        date_row.addWidget(date_label)
        date_row.addWidget(self.order_date, 1)
        root.addLayout(date_row)

        self.drop_zone = ExcelDropZone()
        self.drop_zone.file_dropped.connect(self.load_file)
        self.drop_zone.setEnabled(False)
        root.addWidget(self.drop_zone)

        actions = QHBoxLayout()
        self.choose_button = QPushButton("Выбрать Excel-файл")
        self.choose_button.clicked.connect(self.choose_file)
        self.choose_button.setEnabled(False)
        self.merge_button = QPushButton("Добавить общий лист")
        self.merge_button.clicked.connect(self.merge_file)
        self.merge_button.setEnabled(False)
        actions.addWidget(self.choose_button)
        actions.addWidget(self.merge_button)
        root.addLayout(actions)

        self.summary_label = QLabel("Сначала укажите дату подзаказов в формате ГГГГ.ММ.ДД")
        root.addWidget(self.summary_label)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Лист", "Участников", "Сумма заказа", "Скидка", "Сумма со скидкой"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.table, 1)

    def choose_file(self) -> None:
        if self._valid_date_prefix() is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите Excel-файл с подзаказами",
            "",
            "Excel (*.xlsx)",
        )
        if path:
            self.load_file(path)

    def load_file(self, path: str) -> None:
        date_prefix = self._valid_date_prefix()
        if date_prefix is None:
            return
        try:
            analysis = self.merger.analyze(Path(path), date_prefix)
        except (OSError, ValueError, KeyError, BadZipFile, InvalidFileException) as exc:
            self.current_path = None
            self.analysis = None
            self.merge_button.setEnabled(False)
            QMessageBox.warning(self, "Ошибка чтения Excel", f"Не удалось прочитать файл:\n{exc}")
            return

        self.current_path = Path(path)
        self.analysis = analysis
        self.drop_zone.set_file_name(self.current_path.name)
        self._show_analysis(analysis)
        self.merge_button.setEnabled(bool(analysis.sheets))
        if analysis.warnings:
            QMessageBox.warning(self, "Результат анализа", "\n".join(analysis.warnings))

    def _show_analysis(self, analysis: WorkbookAnalysis) -> None:
        self.table.setRowCount(len(analysis.sheets))
        for row, sheet in enumerate(analysis.sheets):
            values = (
                sheet.name,
                str(sheet.participants),
                self._format_decimal(sheet.amount_tenge),
                self._format_decimal(sheet.discount_tenge),
                self._format_decimal(sheet.amount_with_discount_tenge),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                    if column == 0
                    else Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self.table.setItem(row, column, item)
        self.summary_label.setText(
            f"Распознано листов: {len(analysis.sheets)}. "
            f"Строк партнёров до объединения: {analysis.participants}."
        )

    def merge_file(self) -> None:
        date_prefix = self._valid_date_prefix()
        if self.current_path is None or date_prefix is None:
            return
        try:
            result = self.merger.merge_into_file(self.current_path, date_prefix)
        except (OSError, ValueError, KeyError, BadZipFile, InvalidFileException) as exc:
            QMessageBox.warning(
                self,
                "Не удалось добавить лист",
                f"Проверьте, что файл не открыт в Excel, и повторите попытку.\n\n{exc}",
            )
            return

        details = (
            f"В файл добавлен лист «{result.sheet_name}».\n"
            f"Объединено листов: {result.source_sheet_count}.\n"
            f"Партнёров в общем листе: {result.participant_count}."
        )
        if result.warnings:
            details += "\n\nПредупреждения:\n" + "\n".join(result.warnings)
        QMessageBox.information(self, "Общий лист создан", details)
        self.load_file(str(result.path))
        if self.app_context.load_settings().open_after_export:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(result.path)))

    @staticmethod
    def _format_decimal(value) -> str:
        return f"{value:,.0f}".replace(",", " ")

    def _on_date_changed(self) -> None:
        date_prefix = self._valid_date_prefix()
        enabled = date_prefix is not None
        self.drop_zone.setEnabled(enabled)
        self.choose_button.setEnabled(enabled)
        self.merge_button.setEnabled(False)

        if not enabled:
            self.table.setRowCount(0)
            self.summary_label.setText("Сначала укажите дату подзаказов в формате ГГГГ.ММ.ДД")
            return
        if self.current_path is not None:
            self.load_file(str(self.current_path))
        else:
            self.summary_label.setText("Дата указана. Выберите Excel-файл для анализа")

    def _valid_date_prefix(self) -> str | None:
        value = self.order_date.text().strip()
        try:
            parsed = datetime.strptime(value, "%Y.%m.%d")
        except ValueError:
            return None
        return value if parsed.strftime("%Y.%m.%d") == value else None

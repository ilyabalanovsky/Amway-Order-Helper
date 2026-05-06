from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from db.database import Database
from db.repositories import OrderRepository, PartnerGroupRepository, PartnerRepository, SettingsRepository
from models import AppSettings, Order, Partner
from services.excel_exporter import ExcelExporter
from services.product_summary_exporter import ProductSummaryExporter
from services.settings_service import SettingsService
from ui.history_tab import HistoryTab
from ui.order_tab import OrderTab
from ui.partners_tab import PartnersTab
from ui.settings_tab import SettingsTab


class AppContext:
    def __init__(self, database: Database, base_dir: Path, main_window: "MainWindow") -> None:
        self.database = database
        self.base_dir = base_dir
        self.main_window = main_window
        self.exporter = ExcelExporter()
        self.product_summary_exporter = ProductSummaryExporter()

    def to_path(self, value: str) -> Path:
        return Path(value)

    def partner_repo(self, conn):
        return PartnerRepository(conn)

    def load_groups(self):
        with self.database.connect() as conn:
            return PartnerGroupRepository(conn).list_all()

    def load_partners(self, search: str = "", group_id: int | None = None):
        with self.database.connect() as conn:
            return PartnerRepository(conn).list_all(search, group_id)

    def save_partner(self, partner: Partner) -> None:
        with self.database.connect() as conn:
            PartnerRepository(conn).upsert(partner)
            conn.commit()

    def update_partner(self, partner: Partner) -> None:
        with self.database.connect() as conn:
            PartnerRepository(conn).upsert(partner)
            conn.commit()

    def create_group(self, name: str) -> None:
        with self.database.connect() as conn:
            PartnerGroupRepository(conn).create(name)
            conn.commit()

    def delete_partner(self, partner_id: int) -> None:
        with self.database.connect() as conn:
            PartnerRepository(conn).delete(partner_id)
            conn.commit()

    def get_group_name_map(self) -> dict[int, str]:
        return {group.id: group.name for group in self.load_groups() if group.id is not None}

    def get_partner_group_map(self) -> dict[str, str]:
        group_names = self.get_group_name_map()
        result: dict[str, str] = {}
        for partner in self.load_partners():
            if not partner.normalized_name:
                continue
            result[partner.normalized_name] = group_names.get(partner.group_id, "")
            result[f"{partner.normalized_name}__comment"] = partner.comment or ""
        return result

    def save_order(self, order: Order) -> int:
        with self.database.connect() as conn:
            repo = OrderRepository(conn)
            order_id = repo.save(order)
            conn.commit()
            return order_id

    def load_orders(self, search: str = ""):
        with self.database.connect() as conn:
            repo = OrderRepository(conn)
            orders = repo.list_all(search)
            for order in orders:
                order.items = repo.list_items(order.id)
            return orders

    def load_order(self, order_id: int) -> Order | None:
        with self.database.connect() as conn:
            return OrderRepository(conn).get(order_id)

    def delete_order(self, order_id: int) -> None:
        with self.database.connect() as conn:
            OrderRepository(conn).delete(order_id)
            conn.commit()

    def load_settings(self) -> AppSettings:
        with self.database.connect() as conn:
            return SettingsService(SettingsRepository(conn)).load()

    def save_settings(self, settings: AppSettings) -> None:
        with self.database.connect() as conn:
            SettingsService(SettingsRepository(conn)).save(settings)
            conn.commit()

    def reset_settings(self) -> None:
        self.save_settings(AppSettings())


class MainWindow(QMainWindow):
    def __init__(self, database_path: Path, base_dir: Path) -> None:
        super().__init__()
        self.setWindowTitle("Order Helper")
        self.resize(1400, 900)
        icon_path = base_dir / "ui" / "amway.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.database = Database(database_path)
        self.database.initialize()
        self.context = AppContext(self.database, base_dir, self)
        self.central = QWidget()
        self.central_layout = QVBoxLayout(self.central)
        self.central_layout.setContentsMargins(10, 8, 10, 10)
        self.central_layout.setSpacing(8)
        self.header = self._build_header(icon_path)
        self.tabs = QTabWidget()
        self.central_layout.addWidget(self.header)
        self.central_layout.addWidget(self.tabs)
        self.setCentralWidget(self.central)

        self.order_tab = OrderTab(self.context)
        self.partners_tab = PartnersTab(self.context)
        self.history_tab = HistoryTab(self.context)
        self.settings_tab = SettingsTab(self.context)

        self.history_tab.open_order_requested.connect(self.load_order_into_form)
        self.order_tab.order_saved.connect(self.history_tab.refresh)

        self.tabs.addTab(self.order_tab, "Заказ")
        self.tabs.addTab(self.partners_tab, "Партнёры и группы")
        self.tabs.addTab(self.history_tab, "История заказов")
        self.tabs.addTab(self.settings_tab, "Настройки")
        self._apply_styles()

    def _build_header(self, icon_path: Path) -> QWidget:
        header = QWidget()
        header.setObjectName("appHeader")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        icon_label = QLabel()
        icon_label.setObjectName("headerIcon")
        if icon_path.exists():
            pixmap = QPixmap(str(icon_path)).scaled(
                28,
                28,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            icon_label.setPixmap(pixmap)

        title = QLabel("Amway Order Helper")
        title.setObjectName("headerTitle")
        layout.addWidget(icon_label)
        layout.addWidget(title)
        layout.addStretch(1)
        return header

    def show_history_tab(self) -> None:
        self.tabs.setCurrentWidget(self.history_tab)

    def load_order_into_form(self, order_id: int) -> None:
        order = self.context.load_order(order_id)
        if order is None:
            return
        self.tabs.setCurrentWidget(self.order_tab)
        self.order_tab.current_json_text = order.raw_text
        self.order_tab.drop_zone.set_file_name("Сохранённый заказ")
        self.order_tab.parse_loaded_json()
        self.order_tab.order_number.setText(order.order_number)
        if order.order_date:
            self.order_tab.order_date.setDate(order.order_date)
        self.order_tab.sender.setText(order.sender)
        self.order_tab.dispatch_city.setText(order.dispatch_city)
        self.order_tab.tenge_rate.setValue(float(order.tenge_rate))
        self.order_tab.tenge_rate_fact.setValue(float(order.tenge_rate_fact))
        self.order_tab.delivery_percent.setValue(float(order.delivery_percent))
        self.order_tab.expenses.setValue(float(order.expenses))

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background: #f7fbff;
                color: #17324d;
                font-size: 13px;
            }
            QMainWindow {
                background: #edf5ff;
            }
            QWidget#appHeader {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #edf6ff, stop: 1 #f9fcff
                );
                border: 1px solid #d5e4f7;
                border-radius: 14px;
            }
            QLabel#headerTitle {
                font-size: 18px;
                font-weight: 700;
                color: #1f4f7b;
            }
            QLabel#headerIcon {
                background: transparent;
            }
            QFrame#jsonDropZone {
                background: #f8fbff;
                border: 2px dashed #9fc4ef;
                border-radius: 14px;
            }
            QLabel#dropZoneTitle {
                font-size: 14px;
                font-weight: 700;
                color: #24547f;
            }
            QLabel#dropZoneInfo {
                color: #6686a6;
                font-weight: 500;
            }
            QLabel#dropZoneFile {
                color: #1f4f7b;
                font-weight: 600;
            }
            QTabWidget::pane {
                border: 1px solid #c9dcf3;
                border-radius: 14px;
                background: white;
                top: -1px;
            }
            QTabBar::tab {
                background: #dcecff;
                color: #42627f;
                border: 1px solid #c9dcf3;
                padding: 7px 14px;
                margin-right: 4px;
                border-top-left-radius: 9px;
                border-top-right-radius: 9px;
            }
            QTabBar::tab:selected {
                background: white;
                color: #12385d;
            }
            QPushButton {
                background: #2f80ed;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #256fd3;
            }
            QPushButton:pressed {
                background: #1d5bab;
            }
            QLineEdit, QTextEdit, QDateEdit, QDoubleSpinBox, QComboBox, QTableWidget {
                background: white;
                border: 1px solid #cfe0f5;
                border-radius: 10px;
                padding: 6px 8px;
            }
            QLineEdit:focus, QTextEdit:focus, QDateEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {
                border: 1px solid #5aa3ff;
            }
            QTextEdit {
                padding: 10px 12px;
            }
            QHeaderView::section {
                background: #eaf3ff;
                color: #2d5378;
                border: none;
                border-right: 1px solid #d4e4f8;
                border-bottom: 1px solid #d4e4f8;
                padding: 6px;
                font-weight: 600;
            }
            QTableWidget {
                gridline-color: #e6f0fb;
                selection-background-color: #cfe5ff;
                selection-color: #143a61;
            }
            QLabel {
                font-weight: 600;
                color: #32587c;
            }
            QSplitter::handle {
                background: #d5e6fa;
                height: 8px;
            }
            QCheckBox {
                spacing: 8px;
                color: #17324d;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 5px;
                border: 1px solid #89b4e8;
                background: white;
            }
            QCheckBox::indicator:checked {
                background: #2f80ed;
                border: 1px solid #2f80ed;
            }
            QCheckBox::indicator:unchecked:hover {
                border: 1px solid #5aa3ff;
                background: #f3f9ff;
            }
            QScrollBar:vertical {
                background: #eef5fd;
                width: 12px;
                margin: 2px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #a8c9ef;
                min-height: 28px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background: #7fb1ea;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
            QScrollBar:horizontal, QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: transparent;
                border: none;
                height: 0px;
                width: 0px;
            }
            """
        )

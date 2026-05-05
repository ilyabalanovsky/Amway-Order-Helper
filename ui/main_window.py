from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMainWindow, QTabWidget

from db.database import Database
from db.repositories import OrderRepository, PartnerGroupRepository, PartnerRepository, SettingsRepository
from models import AppSettings, Order, Partner
from services.excel_exporter import ExcelExporter
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
        self.database = Database(database_path)
        self.database.initialize()
        self.context = AppContext(self.database, base_dir, self)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

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

    def show_history_tab(self) -> None:
        self.tabs.setCurrentWidget(self.history_tab)

    def load_order_into_form(self, order_id: int) -> None:
        order = self.context.load_order(order_id)
        if order is None:
            return
        self.tabs.setCurrentWidget(self.order_tab)
        self.order_tab.text_edit.setPlainText(order.raw_text)
        self.order_tab.parse_order()
        self.order_tab.order_number.setText(order.order_number)
        if order.order_date:
            self.order_tab.order_date.setDate(order.order_date)
        self.order_tab.sender.setText(order.sender)
        self.order_tab.dispatch_city.setText(order.dispatch_city)
        self.order_tab.tenge_rate.setValue(float(order.tenge_rate))
        self.order_tab.tenge_rate_fact.setValue(float(order.tenge_rate_fact))
        self.order_tab.delivery_percent.setValue(float(order.delivery_percent))
        self.order_tab.expenses.setValue(float(order.expenses))

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from services.excel_exporter import ExcelExporter
from ui.merge_orders_tab import MergeOrdersTab


@pytest.fixture(scope="module")
def qapp():
    application = QApplication.instance() or QApplication([])
    yield application


def test_excel_import_is_disabled_until_valid_date_is_entered(qapp) -> None:
    context = SimpleNamespace(exporter=ExcelExporter())
    tab = MergeOrdersTab(context)

    assert tab.choose_button.isEnabled() is False
    assert tab.drop_zone.isEnabled() is False
    assert tab.merge_button.isEnabled() is False

    tab.order_date.setText("05.05.2026")
    assert tab.choose_button.isEnabled() is False
    assert tab.drop_zone.isEnabled() is False

    tab.order_date.setText("2026.05.05")
    assert tab.choose_button.isEnabled() is True
    assert tab.drop_zone.isEnabled() is True
    assert tab.merge_button.isEnabled() is False

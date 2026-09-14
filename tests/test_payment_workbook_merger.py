from datetime import date
from decimal import Decimal

import pytest
from openpyxl import load_workbook

from models import Order, OrderItem
from services.excel_exporter import ExcelExporter
from services.payment_workbook_merger import PaymentWorkbookMerger


def _order(number: str, amount: str, discount: str, expenses: str = "10") -> Order:
    return Order(
        order_number=number,
        order_date=date(2026, 5, 5),
        sender="Игорь Балановский",
        dispatch_city="Актобе",
        tenge_rate=Decimal("6"),
        tenge_rate_fact=Decimal("6.102"),
        delivery_percent=Decimal("6"),
        expenses=Decimal(expenses),
        items=[
            OrderItem(
                source_number="2062140",
                full_name="Игорь Балановский",
                normalized_name="игорь балановский",
                group_name="Остальные",
                amount_tenge=Decimal(amount),
                discount_tenge=Decimal(discount),
                amount_with_discount_tenge=Decimal(amount) - Decimal(discount),
                registration_fee=Decimal("500"),
            )
        ],
    )


def test_merger_adds_combined_sheet_and_preserves_sources(tmp_path) -> None:
    path = tmp_path / "suborders.xlsx"
    exporter = ExcelExporter()
    exporter.export_new(_order("101", "10000", "1000"), path)
    for index in range(2, 7):
        exporter.append_sheet(_order(f"10{index}", "10000", "1000"), path)

    workbook = load_workbook(path)
    source_names = list(workbook.sheetnames)
    for index, sheet_name in enumerate(source_names, start=1):
        worksheet = workbook[sheet_name]
        worksheet["P4"] = index * 100
        worksheet["Q4"] = index * 1000
    workbook.save(path)

    merger = PaymentWorkbookMerger(exporter)
    analysis = merger.analyze(path, "2026.05.05")
    assert len(analysis.sheets) == 6
    assert analysis.participants == 6

    result = merger.merge_into_file(path, "2026.05.05")
    assert result.sheet_name == "2026.05.05_СВОД"
    assert result.source_sheet_count == 6
    assert result.participant_count == 1

    merged_workbook = load_workbook(path, data_only=False)
    assert merged_workbook.sheetnames[: len(source_names)] == source_names
    worksheet = merged_workbook["2026.05.05_СВОД"]
    assert worksheet["C4"].value == 60000
    assert worksheet["D4"].value == 3000
    assert worksheet["E4"].value == 6000
    assert worksheet["P4"].value == 2100
    assert worksheet["Q4"].value == 21000
    assert worksheet["P5"].value == "=SUM(P4:P4)"
    assert worksheet["Q5"].value == "=SUM(Q4:Q4)"
    assert worksheet["U3"].value == 60


def test_merger_uses_unique_name_without_remerging_old_combined_sheet(tmp_path) -> None:
    path = tmp_path / "suborders.xlsx"
    exporter = ExcelExporter()
    exporter.export_new(_order("101", "10000", "0"), path)
    merger = PaymentWorkbookMerger(exporter)

    merger.merge_into_file(path, "2026.05.05")
    second = merger.merge_into_file(path, "2026.05.05")

    assert second.sheet_name == "2026.05.05_СВОД (2)"
    assert second.source_sheet_count == 1
    assert second.participant_count == 1
    workbook = load_workbook(path, data_only=False)
    assert workbook["2026.05.05_СВОД (2)"]["C4"].value == 10000


def test_merger_accepts_any_number_of_matching_sheets_and_ignores_extras(tmp_path) -> None:
    path = tmp_path / "mixed_sheets.xlsx"
    exporter = ExcelExporter()
    exporter.export_new(_order("101", "10000", "1000"), path)
    exporter.append_sheet(_order("102", "10000", "1000"), path)
    exporter.append_sheet(_order("103", "10000", "1000"), path)
    other_date_order = _order("201", "50000", "5000")
    other_date_order.order_date = date(2026, 5, 6)
    exporter.append_sheet(other_date_order, path)
    workbook = load_workbook(path)
    workbook.create_sheet("Служебный лист")
    workbook.save(path)

    merger = PaymentWorkbookMerger(exporter)
    analysis = merger.analyze(path, "2026.05.05")
    result = merger.merge_into_file(path, "2026.05.05")

    assert len(analysis.sheets) == 3
    assert result.source_sheet_count == 3
    workbook = load_workbook(path, data_only=False)
    assert workbook["2026.05.05_СВОД"]["C4"].value == 30000
    assert "2026.05.06_201" in workbook.sheetnames
    assert "Служебный лист" in workbook.sheetnames


def test_merger_rejects_invalid_date_format(tmp_path) -> None:
    with pytest.raises(ValueError, match="ГГГГ.ММ.ДД"):
        PaymentWorkbookMerger().analyze(tmp_path / "missing.xlsx", "05.05.2026")

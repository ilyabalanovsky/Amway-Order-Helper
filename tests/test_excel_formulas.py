from datetime import date
from decimal import Decimal

from openpyxl import load_workbook

from models import Order, OrderItem
from services.excel_exporter import ExcelExporter


def test_exporter_writes_expected_formulas(tmp_path) -> None:
    order = Order(
        order_number="123",
        order_date=date(2026, 5, 5),
        sender="Test",
        dispatch_city="Moscow",
        tenge_rate=Decimal("6"),
        tenge_rate_fact=Decimal("6.1"),
        delivery_percent=Decimal("6"),
        expenses=Decimal("10"),
        items=[
            OrderItem(
                source_number="1",
                full_name="Иван Иванов",
                normalized_name="иван иванов",
                group_id=1,
                group_name="гр. Тест",
                amount_tenge=Decimal("12000"),
                discount_tenge=Decimal("1000"),
                amount_with_discount_tenge=Decimal("11000"),
                registration_fee=Decimal("500"),
                delivery_percent=Decimal("6"),
                transferred_rub=Decimal("7000"),
            )
        ],
    )
    path = tmp_path / "out.xlsx"
    ExcelExporter().export_new(order, path)
    ws = load_workbook(path, data_only=False).active
    assert ws["F4"].value == "=C4-E4"
    assert ws["G4"].value == "=F4/$S$2"
    assert ws["H4"].value == "=(C4-D4)/$S$2*$H$2"
    assert ws["D4"].value == 500
    assert ws["P4"].value is None
    assert ws["M4"].value == 12000
    assert ws["D5"].value == "=SUM(D4:D4)"
    assert ws["P5"].value == "=SUM(P4:P4)"
    assert ws["Q5"].value == "=SUM(Q4:Q4)"
    assert ws["K2"].value == "=(G7+U2)/G7-1"
    assert ws["K4"].value == "=G4*$K$2"
    assert ws["U2"].value == "=SUM(U3:U6)"
    assert ws["C5"].font.color.rgb == "FF2E75B5"
    assert ws["E5"].font.color.rgb == "FF00B050"
    assert ws["B8"].value == "Номер заказа:"
    assert ws["B12"].value == "Оплатил:"
    assert ws["E15"].value == 0
    assert ws["F12"].font.color.rgb == "FF2E75B5"
    assert ws["H12"].font.color.rgb == "FFC00000"
    assert ws["I12"].font.color.rgb == "FF00B050"
    assert ws["B4"].alignment.horizontal == "left"
    assert ws["B1"].alignment.horizontal == "right"
    assert ws["B3"].alignment.horizontal == "right"
    assert ws["B5"].alignment.horizontal == "right"
    assert ws.row_dimensions[1].height == 50
    assert ws.column_dimensions["A"].width == 3.2
    assert ws.column_dimensions["B"].width == 37.0
    assert ws.column_dimensions["D"].width == 10.0
    assert ws.column_dimensions["L"].width == 11.0
    assert ws.column_dimensions["M"].width == 12.0
    assert ws.column_dimensions["O"].width == 8.17
    assert ws.column_dimensions["Q"].width == 10.5
    assert ws.column_dimensions["U"].width == 8.5
    assert ws.column_dimensions["Y"].width == 10.5
    assert ws.column_dimensions["Y"].hidden is False
    assert ws["Q1"].value == "Оплатили в тенге"
    assert ws["F12"].font.bold is True
    assert ws["C10"].alignment.horizontal == "left"
    assert ws["N11"].alignment.horizontal == "left"
    assert ws["N12"].alignment.horizontal == "left"
    assert ws["O11"].alignment.horizontal == "left"


def test_one_percent_ed_uses_named_group_delivery_totals(tmp_path) -> None:
    order = Order(
        order_number="123",
        order_date=date(2026, 5, 5),
        sender="Test",
        dispatch_city="Moscow",
        tenge_rate=Decimal("6"),
        tenge_rate_fact=Decimal("6.1"),
        delivery_percent=Decimal("6"),
        expenses=Decimal("10"),
        items=[
            OrderItem(
                source_number="1",
                full_name="\u0410",
                normalized_name="\u0430",
                group_id=1,
                group_name="\u0433\u0440. \u0415\u0434\u0440\u044b\u0448\u043e\u0432\u044b\u0445",
                amount_tenge=Decimal("12000"),
                discount_tenge=Decimal("1000"),
                amount_with_discount_tenge=Decimal("11000"),
            ),
            OrderItem(
                source_number="2",
                full_name="\u0411",
                normalized_name="\u0431",
                group_id=2,
                group_name="\u0433\u0440. \u0420\u043e\u0434\u0438\u043e\u043d\u043e\u0432\u043e\u0439",
                amount_tenge=Decimal("13000"),
                discount_tenge=Decimal("500"),
                amount_with_discount_tenge=Decimal("12500"),
            ),
            OrderItem(
                source_number="3",
                full_name="\u0412",
                normalized_name="\u0432",
                group_id=3,
                group_name="\u0433\u0440. \u041a\u0440\u0443\u043f\u0438\u043d\u043e\u0439",
                amount_tenge=Decimal("14000"),
                discount_tenge=Decimal("0"),
                amount_with_discount_tenge=Decimal("14000"),
            ),
            OrderItem(
                source_number="4",
                full_name="\u0413",
                normalized_name="\u0433",
                group_id=4,
                group_name="\u041e\u0441\u0442\u0430\u043b\u044c\u043d\u044b\u0435",
                amount_tenge=Decimal("15000"),
                discount_tenge=Decimal("0"),
                amount_with_discount_tenge=Decimal("15000"),
            ),
        ],
    )
    path = tmp_path / "out_groups.xlsx"
    ExcelExporter().export_new(order, path)
    ws = load_workbook(path, data_only=False).active
    assert ws["N21"].value == "=(H8+H11+H14)/6"

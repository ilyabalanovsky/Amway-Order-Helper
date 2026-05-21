from pathlib import Path

from openpyxl import load_workbook

from services.product_summary_exporter import ProductSummaryExporter


def test_product_summary_exporter_adds_dashed_borders_to_filled_cells(tmp_path: Path) -> None:
    raw_json = """
    {
      "orderData": {
        "code": "839997175",
        "orderedBy": {
          "name": "ИГОРЬ БАЛАНОВСКИЙ",
          "account": {"code": "2062140"}
        },
        "subTotal": {"value": 18487},
        "pointValue": 16.28,
        "cisMeasure": {"weight": 0.5},
        "entries": [
          {
            "quantity": 2,
            "product": {"alias": "124106", "name": "Зубная паста", "type": "SINGLE"}
          }
        ]
      }
    }
    """

    destination = tmp_path / "summary.xlsx"
    ProductSummaryExporter().export(raw_json, destination, {})
    worksheet = load_workbook(destination).active

    assert worksheet["A1"].border.left.style is None
    assert worksheet["A3"].border.top.style is None
    assert worksheet["B4"].border.right.style == "dashed"
    assert worksheet["C4"].border.bottom.style == "dashed"

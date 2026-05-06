from pathlib import Path

from openpyxl import load_workbook

from services.product_summary_exporter import ProductSummaryExporter


def test_product_summary_exporter_writes_cart_headers_and_products(tmp_path: Path) -> None:
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
            "product": {"alias": "124106", "name": "Многофункциональная зубная паста", "type": "SINGLE"}
          }
        ],
        "subCarts": [
          {
            "orderedBy": {
              "name": "Марина Викторовна Полякова",
              "account": {"code": "7027251953"}
            },
            "subTotal": {"value": 131670},
            "pointValue": 123.53,
            "cisMeasure": {"weight": 4.5},
            "entries": [
              {
                "quantity": 1,
                "product": {"alias": "297377", "name": "Регистрационный взнос", "type": "SERVICE", "lynxServiceType": "REGISTRATION_FEE"}
              },
              {
                "quantity": 1,
                "product": {"alias": "126461", "name": "Очищающий шампунь", "type": "SINGLE"}
              }
            ]
          }
        ]
      }
    }
    """

    destination = tmp_path / "summary.xlsx"
    exporter = ProductSummaryExporter()
    exporter.export(
        raw_json,
        destination,
        {
            "игорь балановский": "гр. Балановских",
            "игорь балановский__comment": "Организатор",
            "марина полякова": "гр. Поляковой",
            "марина полякова__comment": "Проверить оплату",
        },
    )

    workbook = load_workbook(destination)
    worksheet = workbook.active

    assert worksheet.title == "Лист1"
    assert worksheet["A1"].value == "Заказ номер: 839997175"
    assert "2062140 Ваши Позиции (гр. Балановских)" in str(worksheet["A3"].value)
    assert worksheet["A4"].value == "124106"
    assert worksheet["B4"].value == "Многофункциональная зубная паста"
    assert worksheet["C4"].value == 2
    assert "7027251953 Марина Полякова (гр. Поляковой)" in str(worksheet["A5"].value)
    assert worksheet["D3"].value == "Организатор"
    assert worksheet["D5"].value == "Проверить оплату"
    assert worksheet["A6"].value == "126461"
    assert worksheet["B6"].value == "Очищающий шампунь"

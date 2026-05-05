from services.parser import OrderTextParser


def test_parser_parses_order_and_totals() -> None:
    text = """
    № ФИО Сумма заказа в ₸ Скидка в ₸ Сумма со скидкой в ₸
    2062140 Игорь Балановский 18 487 0 18 487
    7279577 Надежда Юрьевна Меняйленко 79 598 10 000 69 598
    Всего 98 085 10 000 88 085
    """
    parsed = OrderTextParser().parse(text)
    assert len(parsed.items) == 2
    assert not parsed.errors
    assert parsed.items[1].full_name == "Надежда Меняйленко"
    assert parsed.calculated_totals.amount_tenge == 98085
    assert parsed.calculated_totals.discount_tenge == 10000


def test_parser_reports_invalid_line() -> None:
    parsed = OrderTextParser().parse("bad line")
    assert parsed.errors

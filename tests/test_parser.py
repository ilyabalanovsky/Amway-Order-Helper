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


def test_parser_handles_total_line_with_nonbreaking_spaces() -> None:
    text = (
        "№ ФИО Сумма заказа в ₸ Скидка в ₸ Сумма со скидкой в ₸\n"
        "1 Иван Иванов 12 000 2 000 10 000\n"
        "Всего\u00A012 000\u00A02 000\u00A010 000"
    )
    parsed = OrderTextParser().parse(text)
    assert not parsed.errors
    assert not parsed.warnings
    assert parsed.totals_from_text is not None

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


def test_parser_parses_json_order_payload() -> None:
    payload = {
        "orderData": {
            "code": "840181440",
            "created": 1777832668031,
            "allCartsTotalPrice": {"value": 430581},
            "grandTotalDiscount": {"value": 69528},
            "subTotal": {"value": 18487},
            "totalPrice": {"value": 18487},
            "orderedBy": {
                "name": "ИГОРЬ БАЛАНОВСКИЙ",
                "firstName": "ИГОРЬ",
                "lastName": "БАЛАНОВСКИЙ",
                "account": {"code": "2062140"},
            },
            "deliveryPointOfService": {
                "cisCity": {"cityName": "Актобе"},
            },
            "subCarts": [
                {
                    "subTotal": {"value": 79598},
                    "totalPrice": {"value": 69598},
                    "grandTotalDiscount": {"value": 10000},
                    "orderedBy": {
                        "firstName": "НАДЕЖДА",
                        "middleName": "Юрьевна",
                        "lastName": "МЕНЯЙЛЕНКО",
                        "account": {"code": "7279577"},
                    },
                },
                {
                    "subTotal": {"value": 18487},
                    "totalPrice": {"value": 18487},
                    "grandTotalDiscount": {"value": 0},
                    "orderedBy": {
                        "firstName": "ИГОРЬ",
                        "lastName": "БАЛАНОВСКИЙ",
                        "account": {"code": "2062140"},
                    },
                },
            ],
        }
    }
    parsed = OrderTextParser().parse_json_payload(payload)
    assert not parsed.errors
    assert parsed.order_number == "840181440"
    assert parsed.dispatch_city == "Актобе"
    assert parsed.sender == "Игорь Балановский"
    assert parsed.items[0].full_name == "Игорь Балановский"
    assert parsed.items[1].full_name == "Надежда Меняйленко"
    assert len(parsed.items) == 2
    assert parsed.calculated_totals.amount_tenge == 98085
    assert parsed.calculated_totals.discount_tenge == 10000
    assert parsed.calculated_totals.amount_with_discount_tenge == 88085
    assert parsed.totals_from_text is not None
    assert parsed.warnings
    assert "Сумма заказа" in parsed.warnings[0]
    assert "Сумма скидок" in parsed.warnings[0]
    assert "Сумма с учетом скидок" in parsed.warnings[0]


def test_parser_removes_patronymic_when_first_name_contains_it() -> None:
    payload = {
        "orderData": {
            "code": "1",
            "created": 1777832668031,
            "allCartsTotalPrice": {"value": 100},
            "grandTotalDiscount": {"value": 0},
            "subTotal": {"value": 100},
            "subCarts": [
                {
                    "subTotal": {"value": 100},
                    "totalPrice": {"value": 100},
                    "grandTotalDiscount": {"value": 0},
                    "orderedBy": {
                        "firstName": "НАДЕЖДА Юрьевна",
                        "middleName": "Юрьевна",
                        "lastName": "МЕНЯЙЛЕНКО",
                        "account": {"code": "7279577"},
                    },
                }
            ],
        }
    }
    parsed = OrderTextParser().parse_json_payload(payload)
    assert not parsed.errors
    assert parsed.items[0].full_name == "Надежда Меняйленко"


def test_parser_does_not_warn_when_api_totals_match_sum_of_carts() -> None:
    payload = {
        "orderData": {
            "code": "1",
            "created": 1777832668031,
            "allCartsTotalPrice": {"value": 88085},
            "grandTotalDiscount": {"value": 10000},
            "subTotal": {"value": 18487},
            "totalPrice": {"value": 18487},
            "totalDiscounts": {"value": 0},
            "orderedBy": {
                "firstName": "ИГОРЬ",
                "lastName": "БАЛАНОВСКИЙ",
                "account": {"code": "2062140"},
            },
            "subCarts": [
                {
                    "subTotal": {"value": 79598},
                    "totalPrice": {"value": 69598},
                    "grandTotalDiscount": {"value": 10000},
                    "orderedBy": {
                        "firstName": "НАДЕЖДА",
                        "middleName": "Юрьевна",
                        "lastName": "МЕНЯЙЛЕНКО",
                        "account": {"code": "7279577"},
                    },
                },
            ],
        }
    }
    parsed = OrderTextParser().parse_json_payload(payload)
    assert not parsed.errors
    assert not parsed.warnings


def test_parser_extracts_registration_fee_from_json_entries() -> None:
    payload = {
        "orderData": {
            "code": "1",
            "created": 1777832668031,
            "allCartsTotalPrice": {"value": 18300},
            "grandTotalDiscount": {"value": 0},
            "subTotal": {"value": 18300},
            "totalPrice": {"value": 18300},
            "totalDiscounts": {"value": 0},
            "orderedBy": {
                "firstName": "ИГОРЬ",
                "lastName": "БАЛАНОВСКИЙ",
                "account": {"code": "2062140"},
            },
            "entries": [
                {
                    "totalPrice": {"value": 8300},
                    "product": {"lynxServiceType": "REGISTRATION_FEE"},
                }
            ],
            "subCarts": [
                {
                    "subTotal": {"value": 10000},
                    "totalPrice": {"value": 10000},
                    "grandTotalDiscount": {"value": 0},
                    "orderedBy": {
                        "firstName": "НАДЕЖДА",
                        "lastName": "МЕНЯЙЛЕНКО",
                        "account": {"code": "7279577"},
                    },
                },
            ],
        }
    }
    parsed = OrderTextParser().parse_json_payload(payload)
    assert not parsed.errors
    assert parsed.items[0].registration_fee == 8300


def test_parser_sums_registration_and_renewal_fees_into_same_column() -> None:
    payload = {
        "orderData": {
            "code": "1",
            "created": 1777832668031,
            "allCartsTotalPrice": {"value": 28300},
            "grandTotalDiscount": {"value": 0},
            "subTotal": {"value": 28300},
            "totalPrice": {"value": 28300},
            "totalDiscounts": {"value": 0},
            "orderedBy": {
                "firstName": "ИГОРЬ",
                "lastName": "БАЛАНОВСКИЙ",
                "account": {"code": "2062140"},
            },
            "entries": [
                {
                    "totalPrice": {"value": 8300},
                    "product": {"lynxServiceType": "REGISTRATION_FEE", "name": "Регистрационный взнос"},
                },
                {
                    "totalPrice": {"value": 10000},
                    "product": {"lynxServiceType": "RENEWAL_FEE", "name": "Позднее продление"},
                }
            ],
            "subCarts": [
                {
                    "subTotal": {"value": 10000},
                    "totalPrice": {"value": 10000},
                    "grandTotalDiscount": {"value": 0},
                    "orderedBy": {
                        "firstName": "НАДЕЖДА",
                        "lastName": "МЕНЯЙЛЕНКО",
                        "account": {"code": "7279577"},
                    },
                },
            ],
        }
    }
    parsed = OrderTextParser().parse_json_payload(payload)
    assert not parsed.errors
    assert parsed.items[0].registration_fee == 18300

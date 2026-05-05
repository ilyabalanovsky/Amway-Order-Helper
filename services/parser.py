from __future__ import annotations

import re
from decimal import Decimal

from models import OrderItem, ParsedOrder, ParsedOrderTotals
from services.normalizer import normalize_name, strip_patronymic


TOTAL_RE = re.compile(r"^\s*всего\b", re.IGNORECASE)
HEADER_RE = re.compile(r"фио", re.IGNORECASE)


def parse_decimal(raw: str) -> Decimal:
    value = raw.replace(" ", "").replace(",", ".")
    return Decimal(value)


class OrderTextParser:
    def parse(self, raw_text: str) -> ParsedOrder:
        parsed = ParsedOrder()
        text = raw_text.strip()
        if not text:
            parsed.errors.append("Текст заказа пуст.")
            return parsed

        lines = [self._normalize_line(line) for line in raw_text.splitlines() if line.strip()]
        for index, line in enumerate(lines, start=1):
            if self._is_header_line(line):
                continue
            if TOTAL_RE.search(line):
                totals = self._parse_totals(line)
                if totals is None:
                    parsed.errors.append(f"Строка итога не распознана: {line}")
                else:
                    parsed.totals_from_text = totals
                continue

            item = self._parse_item_line(line)
            if not item:
                parsed.errors.append(f"Строка {index} не распознана: {line}")
                continue
            if item.amount_tenge < 0 or item.discount_tenge < 0 or item.amount_with_discount_tenge < 0:
                parsed.errors.append(f"Строка {index} содержит отрицательные суммы: {line}")
                continue
            item.sort_order = len(parsed.items) + 1
            parsed.items.append(item)

        parsed.calculated_totals = ParsedOrderTotals(
            amount_tenge=sum((item.amount_tenge for item in parsed.items), start=Decimal("0")),
            discount_tenge=sum((item.discount_tenge for item in parsed.items), start=Decimal("0")),
            amount_with_discount_tenge=sum(
                (item.amount_with_discount_tenge for item in parsed.items),
                start=Decimal("0"),
            ),
        )
        if parsed.totals_from_text and parsed.totals_from_text != parsed.calculated_totals:
            parsed.warnings.append(
                "Итоговая строка 'Всего' не совпадает с рассчитанными значениями."
            )
        return parsed

    def _parse_totals(self, line: str) -> ParsedOrderTotals | None:
        payload = line.split()[1:]
        numbers = self._split_three_numbers(payload)
        if not numbers:
            return None
        amount, discount, with_discount = numbers
        return ParsedOrderTotals(
            amount_tenge=amount,
            discount_tenge=discount,
            amount_with_discount_tenge=with_discount,
        )

    def _parse_item_line(self, line: str) -> OrderItem | None:
        tokens = line.split()
        if len(tokens) < 5 or not tokens[0].isdigit():
            return None
        source_number = tokens[0]
        rest = tokens[1:]

        first_digit_index = next((idx for idx, token in enumerate(rest) if token.isdigit()), None)
        if first_digit_index is None or first_digit_index == 0:
            return None
        name_tokens = rest[:first_digit_index]
        number_tokens = rest[first_digit_index:]
        numbers = self._split_three_numbers(number_tokens)
        if not numbers:
            return None
        amount, discount, with_discount = numbers
        return OrderItem(
            source_number=source_number,
            full_name=strip_patronymic(" ".join(name_tokens)),
            normalized_name=normalize_name(strip_patronymic(" ".join(name_tokens))),
            amount_tenge=amount,
            discount_tenge=discount,
            amount_with_discount_tenge=with_discount,
        )

    def _split_three_numbers(self, tokens: list[str]) -> tuple[Decimal, Decimal, Decimal] | None:
        for i in range(1, len(tokens) - 1):
            for j in range(i + 1, len(tokens)):
                first = parse_decimal(" ".join(tokens[:i]))
                second = parse_decimal(" ".join(tokens[i:j]))
                third = parse_decimal(" ".join(tokens[j:]))
                if first - second == third:
                    return first, second, third
        if len(tokens) >= 3:
            return (
                parse_decimal(" ".join(tokens[:-2])),
                parse_decimal(tokens[-2]),
                parse_decimal(tokens[-1]),
            )
        return None

    @staticmethod
    def _normalize_line(line: str) -> str:
        cleaned = line.replace("\u00A0", " ").replace("\t", " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    @staticmethod
    def _is_header_line(line: str) -> bool:
        lowered = line.casefold()
        return "фио" in lowered and ("сумма" in lowered or "скидка" in lowered)

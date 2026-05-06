from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from models import OrderItem, ParsedOrder, ParsedOrderTotals
from services.normalizer import clean_name, normalize_name, strip_patronymic


TOTAL_RE = re.compile(r"^\s*всего\b", re.IGNORECASE)


def parse_decimal(raw: str) -> Decimal:
    value = raw.replace(" ", "").replace(",", ".")
    return Decimal(value)


class OrderTextParser:
    def parse_json_file(self, path: Path) -> ParsedOrder:
        try:
            raw = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw = path.read_text(encoding="utf-8-sig")
        parsed = self.parse_json_text(raw)
        parsed.source_label = path.name
        return parsed

    def parse_json_text(self, raw_json: str) -> ParsedOrder:
        parsed = ParsedOrder()
        if not raw_json.strip():
            parsed.errors.append("JSON-файл пуст.")
            return parsed
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            parsed.errors.append(f"Некорректный JSON: {exc}")
            return parsed
        return self.parse_json_payload(payload)

    def parse_json_payload(self, payload: dict) -> ParsedOrder:
        parsed = ParsedOrder()
        order = payload.get("orderData")
        if not isinstance(order, dict):
            parsed.errors.append("В JSON не найден объект orderData.")
            return parsed

        parsed.order_number = str(order.get("code") or "")
        parsed.order_date = self._parse_timestamp(order.get("created"))
        parsed.sender = self._extract_sender(order)
        parsed.dispatch_city = self._extract_dispatch_city(order)

        root_item = self._parse_subcart(order, 1, is_root=True)
        if root_item is not None:
            parsed.items.append(root_item)

        subcarts = order.get("subCarts") or []
        if not isinstance(subcarts, list) or not subcarts:
            if not parsed.items:
                parsed.errors.append("В JSON не найден список участников заказа (subCarts).")
                return parsed

        for index, subcart in enumerate(subcarts, start=len(parsed.items) + 1):
            if not isinstance(subcart, dict):
                parsed.errors.append(f"Участник {index} имеет некорректную структуру.")
                continue
            item = self._parse_subcart(subcart, index, is_root=False)
            if item is None:
                parsed.errors.append(f"Не удалось разобрать участника #{index}.")
                continue
            if any(
                existing.normalized_name == item.normalized_name and existing.amount_tenge == item.amount_tenge
                for existing in parsed.items
            ):
                continue
            parsed.items.append(item)

        parsed.calculated_totals = ParsedOrderTotals(
            amount_tenge=sum((item.amount_tenge for item in parsed.items), start=Decimal("0")),
            discount_tenge=sum((item.discount_tenge for item in parsed.items), start=Decimal("0")),
            amount_with_discount_tenge=sum(
                (item.amount_with_discount_tenge for item in parsed.items),
                start=Decimal("0"),
            ),
        )

        totals_from_api = self._extract_api_totals(order)
        if totals_from_api is not None:
            parsed.totals_from_text = ParsedOrderTotals(
                amount_tenge=totals_from_api["amount_tenge"],
                discount_tenge=totals_from_api["discount_tenge"],
                amount_with_discount_tenge=totals_from_api["amount_with_discount_tenge"],
            )
            mismatch_lines = self._compare_totals(parsed.calculated_totals, totals_from_api)
            if mismatch_lines:
                parsed.warnings.append(
                    "Итоговые суммы заказа из API не совпадают с суммой распарсенных корзин:\n"
                    + "\n".join(mismatch_lines)
                )

        return parsed

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
            parsed.warnings.append("Итоговая строка 'Всего' не совпадает с рассчитанными значениями.")
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
        full_name = strip_patronymic(" ".join(name_tokens))
        return OrderItem(
            source_number=source_number,
            full_name=full_name,
            normalized_name=normalize_name(full_name),
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

    def _extract_api_totals(self, order: dict) -> dict[str, Decimal] | None:
        total_with_discount = self._money_value(order.get("allCartsTotalPrice"))
        total_discount = self._money_value(order.get("grandTotalDiscount"))
        if total_with_discount is None or total_discount is None:
            return None
        return {
            "amount_tenge": total_with_discount + total_discount,
            "discount_tenge": total_discount,
            "amount_with_discount_tenge": total_with_discount,
        }

    def _compare_totals(
        self,
        calculated: ParsedOrderTotals,
        api_totals: dict[str, Decimal],
    ) -> list[str]:
        result: list[str] = []
        comparisons = [
            ("Сумма заказа", calculated.amount_tenge, api_totals["amount_tenge"]),
            ("Сумма скидок", calculated.discount_tenge, api_totals["discount_tenge"]),
            ("Сумма с учетом скидок", calculated.amount_with_discount_tenge, api_totals["amount_with_discount_tenge"]),
        ]
        for label, parsed_value, api_value in comparisons:
            if parsed_value != api_value:
                result.append(
                    f"{label}: API = {self._fmt(api_value)}, по корзинам = {self._fmt(parsed_value)}, "
                    f"разница = {self._fmt(parsed_value - api_value)}"
                )
        return result

    def _parse_subcart(self, subcart: dict, index: int, *, is_root: bool) -> OrderItem | None:
        ordered_by = subcart.get("orderedBy") or {}
        full_name = self._extract_person_name(ordered_by)
        if not full_name:
            return None

        amount = self._money_value(subcart.get("subTotal"))
        with_discount = self._money_value(subcart.get("totalPrice")) or self._money_value(subcart.get("grandTotalPrice"))
        if is_root:
            discount = (
                self._money_value(subcart.get("totalDiscounts"))
                or self._money_value(subcart.get("totalCouponsDiscounts"))
            )
            if discount is None and amount is not None and with_discount is not None:
                discount = amount - with_discount
        else:
            discount = self._money_value(subcart.get("grandTotalDiscount"))

        if amount is None or discount is None or with_discount is None:
            return None

        account = ordered_by.get("account") or {}
        source_number = str(account.get("code") or ordered_by.get("customerId") or index)
        return OrderItem(
            source_number=source_number,
            full_name=full_name,
            normalized_name=normalize_name(full_name),
            amount_tenge=amount,
            discount_tenge=discount,
            amount_with_discount_tenge=with_discount,
            registration_fee=self._extract_registration_fee(subcart),
            sort_order=index,
        )

    def _extract_registration_fee(self, subcart: dict) -> Decimal | None:
        total = Decimal("0")
        found = False
        for entry in subcart.get("entries") or []:
            if not isinstance(entry, dict):
                continue
            product = entry.get("product") or {}
            service_type = str(product.get("lynxServiceType") or "")
            product_name = str(product.get("name") or "").casefold()
            if service_type not in {"REGISTRATION_FEE", "RENEWAL_FEE"} and "продлен" not in product_name:
                continue
            value = self._money_value(entry.get("totalPrice")) or self._money_value(entry.get("basePrice"))
            if value is None:
                continue
            total += value
            found = True
        return total if found else None

    @staticmethod
    def _money_value(value) -> Decimal | None:
        if isinstance(value, dict):
            raw = value.get("value")
            if raw is None:
                return None
            return Decimal(str(raw))
        if isinstance(value, (int, float, str)):
            return Decimal(str(value))
        return None

    @staticmethod
    def _parse_timestamp(value) -> date | None:
        if value in (None, ""):
            return None
        try:
            timestamp = int(value) / 1000
        except (TypeError, ValueError):
            return None
        return datetime.fromtimestamp(timestamp).date()

    @staticmethod
    def _extract_person_name(person: dict) -> str:
        explicit_name = OrderTextParser._pretty_name(str(person.get("name") or ""))
        if explicit_name:
            return strip_patronymic(explicit_name)

        raw_parts = [
            str(person.get("firstName") or ""),
            str(person.get("middleName") or ""),
            str(person.get("lastName") or ""),
        ]
        normalized_parts: list[str] = []
        seen: set[str] = set()
        for raw_part in raw_parts:
            for token in clean_name(raw_part).split():
                pretty = OrderTextParser._pretty_name_part(token)
                key = pretty.casefold()
                if pretty and key not in seen:
                    normalized_parts.append(pretty)
                    seen.add(key)
        return strip_patronymic(" ".join(normalized_parts))

    def _extract_sender(self, order: dict) -> str:
        sender = self._extract_person_name(order.get("orderedBy") or {})
        if sender:
            return sender
        billing_abo = order.get("billingAbo") or {}
        primary_party = billing_abo.get("primaryParty") or {}
        return self._extract_person_name(primary_party)

    @staticmethod
    def _extract_dispatch_city(order: dict) -> str:
        delivery_pos = order.get("deliveryPointOfService") or {}
        cis_city = delivery_pos.get("cisCity") or {}
        if cis_city.get("cityName"):
            return clean_name(str(cis_city["cityName"]))
        delivery_address = order.get("deliveryAddress") or {}
        town = delivery_address.get("town")
        if town:
            return clean_name(str(town)).removeprefix("г. ").removeprefix("Г. ")
        return ""

    @staticmethod
    def _fmt(value: Decimal) -> str:
        integral = value.quantize(Decimal("1")) if value == value.to_integral_value() else value.normalize()
        return format(integral, "f").replace(".", ",").rstrip("0").rstrip(",") if "." in format(integral, "f") else f"{int(integral):,}".replace(",", " ")

    @staticmethod
    def _pretty_name_part(value: str) -> str:
        value = clean_name(value)
        return value[:1].upper() + value[1:].lower() if value else ""

    @staticmethod
    def _pretty_name(value: str) -> str:
        return " ".join(OrderTextParser._pretty_name_part(part) for part in clean_name(value).split())

    @staticmethod
    def _normalize_line(line: str) -> str:
        cleaned = line.replace("\u00A0", " ").replace("\t", " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    @staticmethod
    def _is_header_line(line: str) -> bool:
        lowered = line.casefold()
        return "фио" in lowered and ("сумма" in lowered or "скидка" in lowered)

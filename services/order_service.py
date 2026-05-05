from __future__ import annotations

from decimal import Decimal

from db.repositories import PartnerRepository
from models import Order, ParsedOrder


class OrderService:
    def __init__(self, partner_repository: PartnerRepository) -> None:
        self.partner_repository = partner_repository

    def enrich_with_partners(self, parsed: ParsedOrder) -> ParsedOrder:
        for item in parsed.items:
            partner = self.partner_repository.get_by_normalized_name(item.normalized_name)
            if not partner:
                item.parse_error = "Партнёр не найден в справочнике."
                continue
            item.partner_id = partner.id
            item.group_id = partner.group_id
            if not partner.group_id:
                item.parse_error = "У партнёра не указана группа."
        return parsed

    @staticmethod
    def build_order(
        parsed: ParsedOrder,
        *,
        order_number: str,
        order_date,
        sender: str,
        dispatch_city: str,
        tenge_rate: Decimal,
        tenge_rate_fact: Decimal,
        delivery_percent: Decimal,
        expenses: Decimal,
        raw_text: str,
    ) -> Order:
        return Order(
            order_number=order_number,
            order_date=order_date,
            sender=sender,
            dispatch_city=dispatch_city,
            tenge_rate=tenge_rate,
            tenge_rate_fact=tenge_rate_fact,
            delivery_percent=delivery_percent,
            expenses=expenses,
            raw_text=raw_text,
            items=parsed.items,
        )

    @staticmethod
    def validate_export(order: Order) -> list[str]:
        errors: list[str] = []
        if not order.items:
            errors.append("В заказе нет строк для экспорта.")
        for item in order.items:
            if not item.group_id:
                errors.append(f"Для участника '{item.full_name}' не назначена группа.")
        if order.tenge_rate <= 0 or order.tenge_rate_fact <= 0:
            errors.append("Курс тенге должен быть больше нуля.")
        return errors


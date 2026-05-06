from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any


@dataclass(slots=True)
class PartnerGroup:
    id: int | None
    name: str
    sort_order: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class Partner:
    id: int | None
    full_name: str
    normalized_name: str
    group_id: int | None
    is_active: bool = True
    comment: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class OrderItem:
    id: int | None = None
    order_id: int | None = None
    source_number: str = ""
    full_name: str = ""
    normalized_name: str = ""
    partner_id: int | None = None
    group_id: int | None = None
    amount_tenge: Decimal = Decimal("0")
    discount_tenge: Decimal = Decimal("0")
    amount_with_discount_tenge: Decimal = Decimal("0")
    registration_fee: Decimal | None = None
    delivery_percent: Decimal | None = None
    paid_rub: Decimal | None = None
    transferred_rub: Decimal | None = None
    received_tenge: Decimal | None = None
    received_rub: Decimal | None = None
    comment: str = ""
    sort_order: int = 0
    parse_error: str = ""
    group_name: str = ""


@dataclass(slots=True)
class ParsedOrderTotals:
    amount_tenge: Decimal = Decimal("0")
    discount_tenge: Decimal = Decimal("0")
    amount_with_discount_tenge: Decimal = Decimal("0")


@dataclass(slots=True)
class ParsedOrder:
    items: list[OrderItem] = field(default_factory=list)
    totals_from_text: ParsedOrderTotals | None = None
    calculated_totals: ParsedOrderTotals = field(default_factory=ParsedOrderTotals)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    order_number: str = ""
    order_date: date | None = None
    sender: str = ""
    dispatch_city: str = ""
    source_label: str = ""


@dataclass(slots=True)
class Order:
    id: int | None = None
    order_number: str = ""
    order_date: date | None = None
    sender: str = ""
    dispatch_city: str = ""
    tenge_rate: Decimal = Decimal("6")
    tenge_rate_fact: Decimal = Decimal("6")
    delivery_percent: Decimal = Decimal("0.06")
    expenses: Decimal = Decimal("10")
    raw_text: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    items: list[OrderItem] = field(default_factory=list)

    def as_summary(self) -> dict[str, Any]:
        return {
            "participants": len(self.items),
            "amount_tenge": sum((item.amount_tenge for item in self.items), start=Decimal("0")),
            "discount_tenge": sum((item.discount_tenge for item in self.items), start=Decimal("0")),
            "amount_with_discount_tenge": sum(
                (item.amount_with_discount_tenge for item in self.items),
                start=Decimal("0"),
            ),
        }


@dataclass(slots=True)
class AppSettings:
    default_output_dir: str = ""
    file_name_template: str = "{date}_{order_number}.xlsx"
    default_delivery_percent: Decimal = Decimal("0.06")
    default_expenses: Decimal = Decimal("10")
    default_dispatch_city: str = ""
    default_sender: str = ""
    open_after_export: bool = False
    warn_on_total_mismatch: bool = True
    block_export_on_unknown_partner: bool = True

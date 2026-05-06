from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal
from typing import Iterable

from models import Order, OrderItem, Partner, PartnerGroup


def _decimal(value: str | None) -> Decimal | None:
    return Decimal(value) if value not in (None, "") else None


class PartnerGroupRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def list_all(self) -> list[PartnerGroup]:
        rows = self.conn.execute(
            "SELECT * FROM partner_groups ORDER BY sort_order, name"
        ).fetchall()
        return [PartnerGroup(**dict(row)) for row in rows]

    def create(self, name: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO partner_groups(name, sort_order) VALUES (?, COALESCE((SELECT MAX(sort_order) + 1 FROM partner_groups), 1))",
            (name,),
        )
        return int(cur.lastrowid)

    def rename(self, group_id: int, name: str) -> None:
        self.conn.execute(
            "UPDATE partner_groups SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (name, group_id),
        )

    def delete(self, group_id: int) -> None:
        self.conn.execute("DELETE FROM partner_groups WHERE id = ?", (group_id,))


class PartnerRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def list_all(self, search: str = "", group_id: int | None = None) -> list[Partner]:
        sql = "SELECT * FROM partners WHERE 1=1"
        params: list[object] = []
        if search:
            sql += " AND full_name LIKE ?"
            params.append(f"%{search}%")
        if group_id is not None:
            sql += " AND group_id = ?"
            params.append(group_id)
        sql += " ORDER BY full_name"
        rows = self.conn.execute(sql, params).fetchall()
        return [Partner(**dict(row)) for row in rows]

    def get_by_normalized_name(self, normalized_name: str) -> Partner | None:
        row = self.conn.execute(
            "SELECT * FROM partners WHERE normalized_name = ?",
            (normalized_name,),
        ).fetchone()
        return Partner(**dict(row)) if row else None

    def upsert(self, partner: Partner) -> int:
        if partner.id is not None:
            existing = self.get_by_normalized_name(partner.normalized_name)
            if existing and existing.id != partner.id:
                raise ValueError("partner_with_same_name_exists")
            self.conn.execute(
                """
                UPDATE partners
                SET full_name = ?, normalized_name = ?, group_id = ?, is_active = ?, comment = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    partner.full_name,
                    partner.normalized_name,
                    partner.group_id,
                    int(partner.is_active),
                    partner.comment,
                    partner.id,
                ),
            )
            return int(partner.id)
        existing = self.get_by_normalized_name(partner.normalized_name)
        if existing:
            self.conn.execute(
                """
                UPDATE partners
                SET full_name = ?, group_id = ?, is_active = ?, comment = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (partner.full_name, partner.group_id, int(partner.is_active), partner.comment, existing.id),
            )
            return int(existing.id)
        cur = self.conn.execute(
            """
            INSERT INTO partners(full_name, normalized_name, group_id, is_active, comment)
            VALUES (?, ?, ?, ?, ?)
            """,
            (partner.full_name, partner.normalized_name, partner.group_id, int(partner.is_active), partner.comment),
        )
        return int(cur.lastrowid)

    def delete(self, partner_id: int) -> None:
        self.conn.execute("DELETE FROM partners WHERE id = ?", (partner_id,))


class OrderRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def list_all(self, search: str = "") -> list[Order]:
        sql = "SELECT * FROM orders"
        params: list[object] = []
        if search:
            sql += " WHERE order_number LIKE ? OR sender LIKE ? OR order_date LIKE ?"
            params.extend([f"%{search}%"] * 3)
        sql += " ORDER BY COALESCE(order_date, '' ) DESC, id DESC"
        rows = self.conn.execute(sql, params).fetchall()
        return [self._row_to_order(row) for row in rows]

    def get(self, order_id: int) -> Order | None:
        row = self.conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not row:
            return None
        order = self._row_to_order(row)
        order.items = self.list_items(order_id)
        return order

    def save(self, order: Order) -> int:
        payload = (
            order.order_number,
            order.order_date.isoformat() if order.order_date else None,
            order.sender,
            order.dispatch_city,
            str(order.tenge_rate),
            str(order.tenge_rate_fact),
            str(order.delivery_percent),
            str(order.expenses),
            order.raw_text,
        )
        if order.id is None:
            cur = self.conn.execute(
                """
                INSERT INTO orders(
                    order_number, order_date, sender, dispatch_city, tenge_rate,
                    tenge_rate_fact, delivery_percent, expenses, raw_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                payload,
            )
            order_id = int(cur.lastrowid)
        else:
            order_id = int(order.id)
            self.conn.execute(
                """
                UPDATE orders SET
                    order_number = ?, order_date = ?, sender = ?, dispatch_city = ?,
                    tenge_rate = ?, tenge_rate_fact = ?, delivery_percent = ?, expenses = ?,
                    raw_text = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                payload + (order_id,),
            )
            self.conn.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
        self._save_items(order_id, order.items)
        return order_id

    def delete(self, order_id: int) -> None:
        self.conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))

    def list_items(self, order_id: int) -> list[OrderItem]:
        rows = self.conn.execute(
            "SELECT * FROM order_items WHERE order_id = ? ORDER BY sort_order, id",
            (order_id,),
        ).fetchall()
        items: list[OrderItem] = []
        for row in rows:
            data = dict(row)
            items.append(
                OrderItem(
                    id=data["id"],
                    order_id=data["order_id"],
                    source_number=data["source_number"],
                    full_name=data["full_name"],
                    normalized_name=data["normalized_name"],
                    partner_id=data["partner_id"],
                    group_id=data["group_id"],
                    amount_tenge=Decimal(data["amount_tenge"]),
                    discount_tenge=Decimal(data["discount_tenge"]),
                    amount_with_discount_tenge=Decimal(data["amount_with_discount_tenge"]),
                    registration_fee=_decimal(data["registration_fee"]),
                    delivery_percent=_decimal(data["delivery_percent"]),
                    paid_rub=_decimal(data["paid_rub"]),
                    transferred_rub=_decimal(data["transferred_rub"]),
                    received_tenge=_decimal(data["received_tenge"]),
                    received_rub=_decimal(data["received_rub"]),
                    comment=data["comment"],
                    sort_order=data["sort_order"],
                )
            )
        return items

    def _save_items(self, order_id: int, items: Iterable[OrderItem]) -> None:
        for idx, item in enumerate(items, start=1):
            self.conn.execute(
                """
                INSERT INTO order_items(
                    order_id, source_number, full_name, normalized_name, partner_id, group_id,
                    amount_tenge, discount_tenge, amount_with_discount_tenge, registration_fee,
                    delivery_percent,
                    paid_rub, transferred_rub, received_tenge, received_rub, comment, sort_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    item.source_number,
                    item.full_name,
                    item.normalized_name,
                    item.partner_id,
                    item.group_id,
                    str(item.amount_tenge),
                    str(item.discount_tenge),
                    str(item.amount_with_discount_tenge),
                    str(item.registration_fee) if item.registration_fee is not None else None,
                    str(item.delivery_percent) if item.delivery_percent is not None else None,
                    str(item.paid_rub) if item.paid_rub is not None else None,
                    str(item.transferred_rub) if item.transferred_rub is not None else None,
                    str(item.received_tenge) if item.received_tenge is not None else None,
                    str(item.received_rub) if item.received_rub is not None else None,
                    item.comment,
                    idx,
                ),
            )

    @staticmethod
    def _row_to_order(row: sqlite3.Row) -> Order:
        data = dict(row)
        return Order(
            id=data["id"],
            order_number=data["order_number"],
            order_date=date.fromisoformat(data["order_date"]) if data["order_date"] else None,
            sender=data["sender"],
            dispatch_city=data["dispatch_city"],
            tenge_rate=Decimal(data["tenge_rate"]),
            tenge_rate_fact=Decimal(data["tenge_rate_fact"]),
            delivery_percent=Decimal(data["delivery_percent"]),
            expenses=Decimal(data["expenses"]),
            raw_text=data["raw_text"],
        )


class SettingsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get_all(self) -> dict[str, str]:
        rows = self.conn.execute("SELECT key, value FROM app_settings").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def set_many(self, values: dict[str, str]) -> None:
        self.conn.executemany(
            "INSERT INTO app_settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            list(values.items()),
        )

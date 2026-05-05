from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS partner_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS partners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    group_id INTEGER REFERENCES partner_groups(id) ON DELETE SET NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    comment TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_number TEXT NOT NULL,
    order_date TEXT,
    sender TEXT NOT NULL DEFAULT '',
    dispatch_city TEXT NOT NULL DEFAULT '',
    tenge_rate TEXT NOT NULL,
    tenge_rate_fact TEXT NOT NULL,
    delivery_percent TEXT NOT NULL,
    expenses TEXT NOT NULL,
    raw_text TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    source_number TEXT NOT NULL DEFAULT '',
    full_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    partner_id INTEGER REFERENCES partners(id) ON DELETE SET NULL,
    group_id INTEGER REFERENCES partner_groups(id) ON DELETE SET NULL,
    amount_tenge TEXT NOT NULL,
    discount_tenge TEXT NOT NULL,
    amount_with_discount_tenge TEXT NOT NULL,
    registration_fee TEXT,
    delivery_percent TEXT,
    paid_rub TEXT,
    transferred_rub TEXT,
    received_tenge TEXT,
    received_rub TEXT,
    comment TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            self._migrate(conn)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(order_items)").fetchall()
        }
        if "delivery_percent" not in columns:
            conn.execute("ALTER TABLE order_items ADD COLUMN delivery_percent TEXT")

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from models import Order, OrderItem
from services.excel_exporter import ExcelExporter
from services.normalizer import normalize_name


@dataclass(slots=True)
class PaymentSheetSummary:
    name: str
    participants: int
    amount_tenge: Decimal
    discount_tenge: Decimal
    amount_with_discount_tenge: Decimal


@dataclass(slots=True)
class WorkbookAnalysis:
    path: Path
    sheets: list[PaymentSheetSummary] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def participants(self) -> int:
        return sum(sheet.participants for sheet in self.sheets)


@dataclass(slots=True)
class MergeResult:
    path: Path
    sheet_name: str
    source_sheet_count: int
    participant_count: int
    warnings: list[str] = field(default_factory=list)


class PaymentWorkbookMerger:
    COMBINED_SHEET_SUFFIX = "_СВОД"

    def __init__(self, exporter: ExcelExporter | None = None) -> None:
        self.exporter = exporter or ExcelExporter()

    def analyze(self, path: Path, order_date_prefix: str) -> WorkbookAnalysis:
        self._validate_date_prefix(order_date_prefix)
        workbook = load_workbook(path, data_only=False, read_only=True)
        try:
            analysis = WorkbookAnalysis(path=path)
            for worksheet in workbook.worksheets:
                if not self._matches_order_date(worksheet.title, order_date_prefix):
                    continue
                items = self._read_items(worksheet)
                if not items:
                    continue
                analysis.sheets.append(
                    PaymentSheetSummary(
                        name=worksheet.title,
                        participants=len(items),
                        amount_tenge=sum((item.amount_tenge for item in items), Decimal("0")),
                        discount_tenge=sum((item.discount_tenge for item in items), Decimal("0")),
                        amount_with_discount_tenge=sum(
                            (item.amount_with_discount_tenge for item in items), Decimal("0")
                        ),
                    )
                )
            if not analysis.sheets:
                analysis.warnings.append(
                    f"Не найдено листов оплаты, названия которых начинаются с «{order_date_prefix}_»."
                )
            return analysis
        finally:
            workbook.close()

    def merge_into_file(self, path: Path, order_date_prefix: str) -> MergeResult:
        self._validate_date_prefix(order_date_prefix)
        workbook = load_workbook(path, data_only=False)
        temporary_path = path.with_name(f".{path.stem}.merge.tmp.xlsx")
        try:
            source_sheets = [
                worksheet
                for worksheet in workbook.worksheets
                if self._matches_order_date(worksheet.title, order_date_prefix)
                and self._read_items(worksheet)
            ]
            if not source_sheets:
                raise ValueError(
                    f"В файле не найдено листов оплаты с префиксом «{order_date_prefix}_»."
                )

            order, warnings = self._build_combined_order(source_sheets)
            sheet_name = self._unique_sheet_name(order_date_prefix, workbook.sheetnames)
            target_sheet = workbook.create_sheet(sheet_name)
            self.exporter.render_sheet(target_sheet, order)
            workbook.calculation.fullCalcOnLoad = True
            workbook.calculation.forceFullCalc = True
            workbook.save(temporary_path)
            workbook.close()
            os.replace(temporary_path, path)
            return MergeResult(
                path=path,
                sheet_name=sheet_name,
                source_sheet_count=len(source_sheets),
                participant_count=len(order.items),
                warnings=warnings,
            )
        except Exception:
            workbook.close()
            if temporary_path.exists():
                temporary_path.unlink()
            raise

    def _build_combined_order(self, sheets: list[Worksheet]) -> tuple[Order, list[str]]:
        merged: dict[tuple[str, str], OrderItem] = {}
        warnings: list[str] = []
        parameters = [self._read_parameters(sheet) for sheet in sheets]

        for sheet in sheets:
            for item in self._read_items(sheet):
                key = (item.group_name.casefold().strip(), item.normalized_name)
                existing = merged.get(key)
                if existing is None:
                    item.sort_order = len(merged)
                    merged[key] = item
                    continue
                existing.amount_tenge += item.amount_tenge
                existing.discount_tenge += item.discount_tenge
                existing.amount_with_discount_tenge += item.amount_with_discount_tenge
                existing.registration_fee = self._sum_optional(
                    existing.registration_fee, item.registration_fee
                )
                existing.manual_transferred = self._sum_optional(
                    existing.manual_transferred, item.manual_transferred
                )
                existing.paid_tenge = self._sum_optional(existing.paid_tenge, item.paid_tenge)
                existing.received_rub = self._sum_optional(existing.received_rub, item.received_rub)
                existing.transferred_rub = self._sum_optional(
                    existing.transferred_rub, item.transferred_rub
                )

        first = parameters[0]
        self._warn_if_different(parameters, "курс тенге", "tenge_rate", warnings)
        self._warn_if_different(parameters, "фактический курс тенге", "tenge_rate_fact", warnings)
        self._warn_if_different(parameters, "процент доставки", "delivery_percent", warnings)
        self._warn_if_different(parameters, "дату заказа", "order_date", warnings)
        self._warn_if_different(parameters, "город отправки", "dispatch_city", warnings)
        self._warn_if_different(parameters, "отправителя", "sender", warnings)

        order_numbers = [value["order_number"] for value in parameters if value["order_number"]]
        order_number = ", ".join(dict.fromkeys(order_numbers))
        expenses = sum((value["expenses"] for value in parameters), Decimal("0"))
        order = Order(
            order_number=order_number or "СВОД",
            order_date=first["order_date"],
            sender=first["sender"],
            dispatch_city=first["dispatch_city"],
            tenge_rate=first["tenge_rate"],
            tenge_rate_fact=first["tenge_rate_fact"],
            delivery_percent=first["delivery_percent"],
            expenses=expenses,
            items=list(merged.values()),
        )
        return order, warnings

    def _read_items(self, worksheet: Worksheet) -> list[OrderItem]:
        headers = self._header_columns(worksheet)
        if "фио" not in headers or "сумма заказа в тенге" not in headers:
            return []

        number_column = headers.get("№", 1)
        name_column = headers["фио"]
        amount_column = headers["сумма заказа в тенге"]
        discount_column = headers.get("скидка тенге", 5)
        registration_column = headers.get("рег. взнос", 4)
        received_rub_column = headers.get("пришло в рублях")
        transferred_column = headers.get("перевели")
        paid_tenge_column = headers.get("оплатили в тенге")

        items: list[OrderItem] = []
        current_group = "Без группы"
        for row in range(2, worksheet.max_row + 1):
            number = worksheet.cell(row, number_column).value
            name = worksheet.cell(row, name_column).value
            amount = self._decimal_or_none(worksheet.cell(row, amount_column).value)
            if number not in (None, "") and isinstance(name, str) and amount is not None:
                discount = self._decimal_or_none(worksheet.cell(row, discount_column).value) or Decimal("0")
                item = OrderItem(
                    source_number=str(number),
                    full_name=name.strip(),
                    normalized_name=normalize_name(name),
                    group_name=current_group,
                    amount_tenge=amount,
                    discount_tenge=discount,
                    amount_with_discount_tenge=amount - discount,
                    registration_fee=self._decimal_or_none(
                        worksheet.cell(row, registration_column).value
                    ),
                    manual_transferred=self._constant_decimal(worksheet, row, transferred_column),
                    paid_tenge=self._constant_decimal(worksheet, row, paid_tenge_column),
                    received_rub=self._constant_decimal(worksheet, row, received_rub_column),
                    transferred_rub=self._constant_decimal(worksheet, row, 25),
                )
                items.append(item)
                continue

            if (
                isinstance(name, str)
                and name.strip()
                and number in (None, "")
                and amount is None
                and worksheet.cell(row, name_column).font.bold
                and not self._is_summary_label(name)
            ):
                current_group = name.strip()
        return items

    def _read_parameters(self, worksheet: Worksheet) -> dict[str, object]:
        headers = self._header_columns(worksheet)
        date_column = headers.get("дата заказа", 18)
        rate_column = headers.get("курс тенге", 19)
        fact_rate_column = headers.get("курс тенге факт", 20)
        expenses_column = headers.get("расходы", 21)
        delivery_column = headers.get("доставка", 8)
        return {
            "order_date": self._date_or_none(worksheet.cell(2, date_column).value),
            "tenge_rate": self._decimal_or_none(worksheet.cell(2, rate_column).value) or Decimal("6"),
            "tenge_rate_fact": self._decimal_or_none(worksheet.cell(2, fact_rate_column).value)
            or Decimal("6"),
            "delivery_percent": self._decimal_or_none(worksheet.cell(2, delivery_column).value)
            or Decimal("0.06"),
            "expenses": self._decimal_or_none(worksheet.cell(3, expenses_column).value)
            or Decimal("0"),
            "order_number": self._find_footer_value(worksheet, "номер заказа"),
            "dispatch_city": self._find_footer_value(worksheet, "город отправки"),
            "sender": self._find_footer_value(worksheet, "отправитель"),
        }

    @staticmethod
    def _header_columns(worksheet: Worksheet) -> dict[str, int]:
        result: dict[str, int] = {}
        for cell in worksheet[1]:
            if isinstance(cell.value, str):
                result[" ".join(cell.value.casefold().split())] = cell.column
        return result

    @staticmethod
    def _find_footer_value(worksheet: Worksheet, label: str) -> str:
        for row in range(2, worksheet.max_row + 1):
            value = worksheet.cell(row, 2).value
            if isinstance(value, str) and value.casefold().strip().rstrip(":") == label:
                result = worksheet.cell(row, 3).value
                return "" if result is None else str(result).strip()
        return ""

    @staticmethod
    def _is_summary_label(value: str) -> bool:
        normalized = value.casefold().strip().rstrip(":")
        return normalized.startswith("всего") or normalized.startswith("итого") or normalized in {
            "номер заказа",
            "город отправки",
            "отправитель",
            "оплатил",
            "остаток",
            "факт. остаток",
            "оплатил через bcc",
        }

    @classmethod
    def _constant_decimal(cls, worksheet: Worksheet, row: int, column: int | None) -> Decimal | None:
        if column is None:
            return None
        value = worksheet.cell(row, column).value
        if isinstance(value, str) and value.startswith("="):
            return None
        return cls._decimal_or_none(value)

    @staticmethod
    def _decimal_or_none(value: object) -> Decimal | None:
        if value in (None, "") or isinstance(value, bool):
            return None
        try:
            return Decimal(str(value).replace(" ", "").replace(",", "."))
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _date_or_none(value: object) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            for pattern in ("%d.%m.%Y", "%Y.%m.%d", "%Y-%m-%d"):
                try:
                    return datetime.strptime(value.strip(), pattern).date()
                except ValueError:
                    continue
        return None

    @staticmethod
    def _sum_optional(left: Decimal | None, right: Decimal | None) -> Decimal | None:
        if left is None and right is None:
            return None
        return (left or Decimal("0")) + (right or Decimal("0"))

    @staticmethod
    def _warn_if_different(
        parameters: list[dict[str, object]], label: str, key: str, warnings: list[str]
    ) -> None:
        values = {str(parameters[index][key]) for index in range(len(parameters))}
        if len(values) > 1:
            warnings.append(
                f"Листы содержат разные значения поля «{label}». В общем листе использовано значение первого листа."
            )

    def _unique_sheet_name(self, order_date_prefix: str, existing_names: list[str]) -> str:
        base_name = f"{order_date_prefix}{self.COMBINED_SHEET_SUFFIX}"
        if base_name not in existing_names:
            return base_name
        index = 2
        while f"{base_name} ({index})" in existing_names:
            index += 1
        return f"{base_name} ({index})"

    @staticmethod
    def _validate_date_prefix(value: str) -> None:
        try:
            parsed = datetime.strptime(value, "%Y.%m.%d")
        except ValueError as exc:
            raise ValueError("Дата должна быть указана в формате ГГГГ.ММ.ДД.") from exc
        if parsed.strftime("%Y.%m.%d") != value:
            raise ValueError("Дата должна быть указана в формате ГГГГ.ММ.ДД.")

    @staticmethod
    def _matches_order_date(sheet_name: str, order_date_prefix: str) -> bool:
        summary_prefix = f"{order_date_prefix}{PaymentWorkbookMerger.COMBINED_SHEET_SUFFIX}"
        return sheet_name.startswith(f"{order_date_prefix}_") and not sheet_name.startswith(
            summary_prefix
        )

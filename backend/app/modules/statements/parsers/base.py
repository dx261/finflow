"""Statement parser base: shared extraction pipeline.

Every bank parser follows the same flow: load the grid -> detect anchors
for header metadata -> locate the table dynamically -> map columns ->
coerce rows into normalized :class:`ParsedTransaction` objects.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from app.modules.statements.parsers.anchor_detector import detect_anchors
from app.modules.statements.parsers.table_detector import Table, detect_table
from app.modules.statements.parsers.validators import (
    to_date,
    to_decimal,
    to_direction,
)


class StatementSource(Protocol):
    """Anything loadable into a raw cell grid (satisfied by StatementFile)."""

    path: Path

    def load(self) -> list[list[Any]]: ...


class Direction(StrEnum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


@dataclass
class ParsedTransaction:
    transaction_date: date | None
    description: str
    amount: Decimal
    direction: Direction | None
    posting_date: date | None = None
    counterparty_name: str | None = None
    balance_after: Decimal | None = None
    reference: str | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedStatement:
    file_name: str
    transactions: list[ParsedTransaction] = field(default_factory=list)
    account_number: str | None = None
    balance: Decimal | None = None
    currency: str | None = None
    statement_date: date | None = None


def cell_value(row: list[Any], columns: dict[str, int], field: str) -> Any:
    col = columns.get(field)
    if col is None or col >= len(row):
        return None
    return row[col]


def cell_text(row: list[Any], columns: dict[str, int], field: str) -> str | None:
    value = cell_value(row, columns, field)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class BaseStatementParser:
    """Parses a statement file into normalized transactions."""

    def parse(self, file: StatementSource) -> ParsedStatement:
        grid = file.load()
        return self._parse_grid(grid, file.path.name)

    def _parse_grid(self, grid: list[list[Any]], file_name: str) -> ParsedStatement:
        anchors = detect_anchors(grid)
        table = detect_table(grid)
        transactions = [t for t in self._extract_rows(grid, table) if t is not None]

        return ParsedStatement(
            file_name=file_name,
            transactions=transactions,
            account_number=self._anchor_str(anchors, "account_number"),
            balance=anchors["balance"].value if "balance" in anchors else None,
            currency=anchors["currency"].value if "currency" in anchors else None,
            statement_date=(
                anchors["statement_date"].value if "statement_date" in anchors else None
            ),
        )

    @staticmethod
    def _anchor_str(anchors: dict[str, Any], key: str) -> str | None:
        anchor = anchors.get(key)
        if anchor is None:
            return None
        text = str(anchor.value).strip()
        return text or None

    def _extract_rows(self, grid: list[list[Any]], table: Table) -> list[ParsedTransaction | None]:
        transactions: list[ParsedTransaction | None] = []
        for row in grid[table.header_row + 1 :]:
            if self._is_blank_row(row):
                continue
            transactions.append(self._build_transaction(row, table.columns))
        return transactions

    @staticmethod
    def _is_blank_row(row: list[Any]) -> bool:
        return all(cell is None or cell == "" for cell in row)

    def _build_transaction(
        self, row: list[Any], columns: dict[str, int]
    ) -> ParsedTransaction | None:
        amount, direction = self._resolve_amount(row, columns)
        if amount is None:
            return None

        raw: dict[str, Any] = {}
        for col_name, col in columns.items():
            if col < len(row):
                raw[col_name] = row[col]

        return ParsedTransaction(
            transaction_date=to_date(cell_value(row, columns, "transaction_date")),
            posting_date=to_date(cell_value(row, columns, "posting_date")),
            description=cell_text(row, columns, "description") or "",
            counterparty_name=cell_text(row, columns, "counterparty"),
            amount=amount,
            direction=direction,
            balance_after=to_decimal(cell_value(row, columns, "balance")),
            reference=cell_text(row, columns, "reference"),
            raw_data=raw,
        )

    def _resolve_amount(
        self, row: list[Any], columns: dict[str, int]
    ) -> tuple[Decimal | None, Direction | None]:
        """Determine amount and direction from the available columns.

        Prefers an explicit ``amount`` + ``direction`` pair; otherwise
        derives from separate debit/credit columns; otherwise returns None.
        """
        amount = to_decimal(cell_value(row, columns, "amount"))
        direction = to_direction(cell_value(row, columns, "direction"))
        if amount is not None:
            return abs(amount), Direction(direction) if direction else None

        debit = to_decimal(cell_value(row, columns, "debit_amount"))
        if debit is not None:
            return abs(debit), Direction.DEBIT

        credit = to_decimal(cell_value(row, columns, "credit_amount"))
        if credit is not None:
            return abs(credit), Direction.CREDIT

        return None, None

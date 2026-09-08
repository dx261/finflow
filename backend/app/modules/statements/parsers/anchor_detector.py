"""Floating coordinate anchor detection.

Header metadata (account number, balance, date, currency) sits at
different coordinates in every bank export. Instead of assuming a
position, we scan the grid for label cells, then extract the value with a
right-search followed by a down-search, validated against the expected
type. This makes the parser immune to rows shifting around.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.modules.statements.parsers.normalizer import normalize_text


@dataclass(frozen=True)
class Anchor:
    """A located header key-value pair."""

    key: str
    value: Any
    row: int
    col: int


Validator = Callable[[Any], Any]

ANCHORS: dict[str, list[str]] = {
    "balance": ["balance", "账户余额", "可用余额", "当前余额"],
    "account_number": ["account", "account number", "账号", "卡号"],
    "statement_date": ["statement date", "对账日期", "交易日期", "日期"],
    "currency": ["currency", "币种", "币别"],
}


def _validate_balance(value: Any) -> Decimal | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace("，", "").strip()
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None
    return None


def _validate_account_number(value: Any) -> str | None:
    if isinstance(value, str):
        digits = re.sub(r"[^\d]", "", value)
        return digits if len(digits) >= 4 else None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(int(value))
    return None


def _validate_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日", "%Y%m%d"):
            try:
                return datetime.strptime(cleaned, fmt).date()
            except ValueError:
                continue
    return None


def _validate_currency(value: Any) -> str | None:
    if isinstance(value, str):
        code = value.strip().upper()
        return code if len(code) == 3 and code.isalpha() else None
    return None


VALIDATORS: dict[str, Validator] = {
    "balance": _validate_balance,
    "account_number": _validate_account_number,
    "statement_date": _validate_date,
    "currency": _validate_currency,
}

_DOWN_SEARCH_LIMIT = 5


def _extract_value(grid: list[list[Any]], row: int, col: int, key: str) -> Any | None:
    """Right-search then down-search for the value next to a label."""
    validator = VALIDATORS[key]

    # Right search: the cell immediately to the right of the label.
    if col + 1 < len(grid[row]):
        validated = validator(grid[row][col + 1])
        if validated is not None:
            return validated

    # Down search: look below the label for up to _DOWN_SEARCH_LIMIT rows.
    for offset in range(1, _DOWN_SEARCH_LIMIT + 1):
        row_index = row + offset
        if row_index >= len(grid):
            break
        if col < len(grid[row_index]):
            validated = validator(grid[row_index][col])
            if validated is not None:
                return validated
    return None


def detect_anchors(grid: list[list[Any]]) -> dict[str, Anchor]:
    """Locate header anchors in the grid.

    Returns a mapping of anchor key -> :class:`Anchor` for every type
    that could be found and validated. Missing anchors are simply absent.
    """
    found: dict[str, Anchor] = {}
    for key, variants in ANCHORS.items():
        normalized_variants = {normalize_text(variant) for variant in variants}
        for row_index, row in enumerate(grid):
            for col_index, cell in enumerate(row):
                if not isinstance(cell, str):
                    continue
                if normalize_text(cell) not in normalized_variants:
                    continue
                value = _extract_value(grid, row_index, col_index, key)
                if value is not None:
                    found[key] = Anchor(key=key, value=value, row=row_index, col=col_index)
                    break
            if key in found:
                break
    return found

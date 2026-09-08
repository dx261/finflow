"""Dynamic transaction table detection.

The header row is never assumed to be at a fixed line. Every grid row is
scored by how many recognized transaction-column headers it covers; the
highest-scoring row above a threshold is the header. This tolerates extra
title rows, blank rows and shifted layouts.
"""

from dataclasses import dataclass
from typing import Any

from app.modules.statements.parsers.normalizer import normalize_text

# Minimum number of distinct recognized columns required to accept a header.
MIN_HEADER_SCORE = 3


class TableNotFoundError(Exception):
    """Raised when no transaction header row can be located."""


@dataclass(frozen=True)
class Table:
    """Located transaction table: its header row and column mapping."""

    header_row: int
    columns: dict[str, int]


HEADER_FIELDS: dict[str, list[str]] = {
    "transaction_date": ["交易日期", "记账日期", "交易日", "date"],
    "posting_date": ["入账日期", "起息日期", "posting date"],
    "description": ["摘要", "交易摘要", "描述", "备注", "description", "附言"],
    "counterparty": ["对方户名", "对方名称", "交易对手", "商户名称", "counterparty", "对方账号"],
    "amount": ["金额", "交易金额", "发生额", "amount"],
    "debit_amount": ["借方金额", "支出金额", "支出", "debit"],
    "credit_amount": ["贷方金额", "收入金额", "收入", "credit"],
    "balance": ["余额", "账户余额", "balance"],
    "direction": ["借贷标志", "借贷", "方向", "收/支", "借贷方向"],
    "reference": ["交易流水号", "流水号", "参考号", "reference"],
}

_NORMALIZED_VARIANTS: dict[str, set[str]] = {
    field: {normalize_text(variant) for variant in variants}
    for field, variants in HEADER_FIELDS.items()
}


def score_header_row(row: list[Any]) -> int:
    """Count distinct recognized transaction-column headers in a row."""
    matched: set[str] = set()
    for cell in row:
        if not isinstance(cell, str):
            continue
        normalized = normalize_text(cell)
        for field, variants in _NORMALIZED_VARIANTS.items():
            if field in matched:
                continue
            if normalized in variants:
                matched.add(field)
                break
    return len(matched)


def detect_table(grid: list[list[Any]]) -> Table:
    """Locate the transaction table in the grid.

    Picks the row with the highest header-coverage score. Returns the
    header row index and a mapping of field -> column index.
    """
    best_row = -1
    best_score = 0
    for row_index, row in enumerate(grid):
        score = score_header_row(row)
        if score > best_score:
            best_score = score
            best_row = row_index

    if best_row < 0 or best_score < MIN_HEADER_SCORE:
        raise TableNotFoundError(f"No transaction table found (best score {best_score}).")

    columns: dict[str, int] = {}
    for col_index, cell in enumerate(grid[best_row]):
        if not isinstance(cell, str):
            continue
        normalized = normalize_text(cell)
        for field, variants in _NORMALIZED_VARIANTS.items():
            if field in columns:
                continue
            if normalized in variants:
                columns[field] = col_index
                break

    return Table(header_row=best_row, columns=columns)

"""Cell value coercion helpers.

Cells arrive as raw Excel/CSV values (float, int, str, date). These
helpers convert them into canonical Python types with strict validation.
Money is always ``Decimal`` — floats are never used for amounts.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.modules.statements.parsers.normalizer import normalize_text


def to_decimal(value: Any) -> Decimal | None:
    """Coerce a cell to a Decimal amount, or None if invalid/empty."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace("，", "").replace("¥", "").strip()
        if not cleaned or cleaned in ("-", "--"):
            return None
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None
    return None


def to_date(value: Any) -> date | None:
    """Coerce a cell to a date, or None if invalid/empty."""
    if value is None:
        return None
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


def to_direction(value: Any) -> str | None:
    """Map a direction cell to ``DEBIT`` / ``CREDIT``, or None."""
    if value is None:
        return None
    text = normalize_text(value)
    if text in ("借", "debit", "支出", "转出", "扣款", "付"):
        return "DEBIT"
    if text in ("贷", "credit", "收入", "转入", "存款", "收"):
        return "CREDIT"
    return None

"""Anchor detection tests."""

from datetime import date
from decimal import Decimal

from app.modules.statements.parsers.anchor_detector import detect_anchors


def test_detect_balance_anchor() -> None:
    grid = [
        ["中国工商银行", None, None],
        ["账户余额", "12000.50", None],
        ["账号", "6222 0212 3456", None],
        ["币种", "CNY", None],
    ]
    anchors = detect_anchors(grid)
    assert anchors["balance"].value == Decimal("12000.50")
    assert anchors["account_number"].value == "622202123456"
    assert anchors["currency"].value == "CNY"
    assert "statement_date" not in anchors


def test_detect_date_anchor() -> None:
    grid = [["对账日期：", "2026年09月05日", None]]
    anchors = detect_anchors(grid)
    assert anchors["statement_date"].value == date(2026, 9, 5)


def test_english_labels() -> None:
    grid = [
        ["Account Number", "62220212"],
        ["Balance", "5000"],
    ]
    anchors = detect_anchors(grid)
    assert anchors["account_number"].value == "62220212"
    assert anchors["balance"].value == Decimal("5000")


def test_down_search_fallback() -> None:
    # The value is below the label, not to its right.
    grid = [
        ["账户余额", None],
        [None, None],
        ["5000.00", None],
    ]
    anchors = detect_anchors(grid)
    assert anchors["balance"].value == Decimal("5000.00")


def test_invalid_balance_rejected() -> None:
    grid = [["账户余额", "not-a-number", None]]
    anchors = detect_anchors(grid)
    assert "balance" not in anchors


def test_normalized_label_with_colon() -> None:
    grid = [["账户余额：", "8000", None]]
    anchors = detect_anchors(grid)
    assert anchors["balance"].value == Decimal("8000")

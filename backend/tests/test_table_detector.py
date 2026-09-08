"""Dynamic table detection tests."""

import pytest
from app.modules.statements.parsers.table_detector import (
    TableNotFoundError,
    detect_table,
    score_header_row,
)


def test_standard_table() -> None:
    grid = [
        ["中国工商银行流水", None, None, None],
        ["交易日期", "摘要", "金额", "余额"],
        ["2026-09-01", "工资", 8000, 50000],
    ]
    table = detect_table(grid)
    assert table.header_row == 1
    assert table.columns["transaction_date"] == 0
    assert table.columns["description"] == 1
    assert table.columns["amount"] == 2
    assert table.columns["balance"] == 3


def test_shifted_extra_title_rows() -> None:
    grid = [
        ["ICBC Bank Statement", None, None, None, None],
        ["打印日期：", "2026-09-05", None, None, None],
        [None, None, None, None, None],
        ["交易日期", "交易摘要", "金额", "对方户名", "余额"],
        ["2026-09-01", "购物", -100, "某商户", 49900],
    ]
    table = detect_table(grid)
    assert table.header_row == 3
    assert table.columns["counterparty"] == 3


def test_chinese_colon_in_header() -> None:
    grid = [
        ["交易日期：", "摘要", "金额：", "余额"],
        ["2026-09-01", "工资", 8000, 50000],
    ]
    table = detect_table(grid)
    assert table.header_row == 0
    assert table.columns["transaction_date"] == 0
    assert table.columns["amount"] == 2


def test_english_headers() -> None:
    grid = [
        ["Transaction Date", "Description", "Amount", "Balance"],
        ["2026-09-01", "Salary", 8000, 50000],
    ]
    table = detect_table(grid)
    assert table.header_row == 0
    assert table.columns["amount"] == 2


def test_no_table_raises() -> None:
    grid = [
        ["这是", "一段", "没有", "表格", "的文本"],
        ["第二行", "也没有", "交易", "表头", "字段"],
    ]
    with pytest.raises(TableNotFoundError):
        detect_table(grid)


def test_score_counts_distinct_fields_once() -> None:
    row = ["交易日期", "摘要", "金额", "金额", "余额"]
    assert score_header_row(row) == 4


def test_metadata_row_scores_low() -> None:
    row = ["账户余额", "5000", "币种", "CNY", "账号", "1234"]
    assert score_header_row(row) < 3

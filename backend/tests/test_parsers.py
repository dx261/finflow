"""Bank-specific parser tests."""

from decimal import Decimal
from pathlib import Path

from app.modules.statements.parsers.base import Direction, ParsedStatement
from app.modules.statements.parsers.cmb import CMBParser
from app.modules.statements.parsers.factory import get_parser
from app.modules.statements.parsers.generic import GenericStatementParser, StatementFile
from app.modules.statements.parsers.icbc import ICBCParser
from openpyxl import Workbook


def _parse_grid(grid: list[list[object]], name: str = "statement.xlsx") -> ParsedStatement:
    return ICBCParser()._parse_grid(grid, name)  # noqa: SLF001


def test_icbc_debit_credit_columns() -> None:
    grid = [
        ["中国工商银行", None, None, None, None],
        ["账号", "6222020200112233445", None, None, None],
        ["账户余额", "50000.00", None, None, None],
        ["币种", "CNY", None, None, None],
        ["交易日期", "摘要", "借方金额", "贷方金额", "余额"],
        ["2026-09-01", "工资", None, 8000.00, 50000.00],
        ["2026-09-02", "购物", 120.50, None, 49879.50],
    ]
    result = _parse_grid(grid)

    assert result.account_number == "6222020200112233445"
    assert result.balance == Decimal("50000.00")
    assert result.currency == "CNY"
    assert len(result.transactions) == 2

    salary, shopping = result.transactions
    assert salary.amount == Decimal("8000.00")
    assert salary.direction == Direction.CREDIT
    assert salary.transaction_date.year == 2026
    assert shopping.amount == Decimal("120.50")
    assert shopping.direction == Direction.DEBIT


def test_cmb_income_expense_columns() -> None:
    grid = [
        ["招商银行", None, None, None, None],
        ["交易日期", "交易摘要", "收入金额", "支出金额", "余额"],
        ["2026-09-01", "转账存入", 3000.00, None, 20000.00],
        ["2026-09-02", "便利店", None, 45.50, 19954.50],
    ]
    result = CMBParser()._parse_grid(grid, "cmb.xlsx")  # noqa: SLF001

    deposit, purchase = result.transactions
    assert deposit.direction == Direction.CREDIT
    assert deposit.amount == Decimal("3000.00")
    assert purchase.direction == Direction.DEBIT
    assert purchase.amount == Decimal("45.50")
    assert purchase.balance_after == Decimal("19954.50")


def test_generic_amount_with_direction_column() -> None:
    grid = [
        ["通用流水", None, None, None, None],
        ["交易日期", "摘要", "金额", "借贷标志", "余额"],
        ["2026-09-01", "利息", 50.00, "贷", 10050.00],
        ["2026-09-02", "取款", 100.00, "借", 9950.00],
    ]
    result = GenericStatementParser()._parse_grid(grid, "generic.xlsx")  # noqa: SLF001

    interest, withdrawal = result.transactions
    assert interest.direction == Direction.CREDIT
    assert withdrawal.direction == Direction.DEBIT


def test_blank_rows_are_skipped() -> None:
    grid = [
        ["交易日期", "摘要", "金额", "余额"],
        ["2026-09-01", "收入", 100.00, 1100.00],
        [None, None, None, None],
        ["2026-09-02", "支出", 50.00, 1050.00],
    ]
    result = _parse_grid(grid)
    assert len(result.transactions) == 2


def test_money_is_decimal_not_float() -> None:
    grid = [
        ["交易日期", "摘要", "金额", "余额"],
        ["2026-09-01", "工资", 8000.5, 50000.0],
    ]
    result = _parse_grid(grid)
    assert isinstance(result.transactions[0].amount, Decimal)
    assert result.transactions[0].amount == Decimal("8000.5")


def test_invalid_row_skipped_when_no_amount() -> None:
    grid = [
        ["交易日期", "摘要", "借方金额", "贷方金额"],
        ["2026-09-01", "有效", None, 100.00],
        ["2026-09-02", "无金额", None, None],
    ]
    result = _parse_grid(grid)
    assert len(result.transactions) == 1


def test_factory_routing() -> None:
    assert isinstance(get_parser("ICBC"), ICBCParser)
    assert isinstance(get_parser("CMB"), CMBParser)
    assert isinstance(get_parser("GENERIC"), GenericStatementParser)
    assert isinstance(get_parser("UNKNOWN"), GenericStatementParser)


def test_full_xlsx_end_to_end(tmp_path: Path) -> None:
    path = tmp_path / "icbc_standard.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["中国工商银行", None, None, None, None])
    ws.append(["账号", "6222020", None, None, None])
    ws.append(["交易日期", "摘要", "借方金额", "贷方金额", "余额"])
    ws.append(["2026-09-01", "工资", None, 8000.0, 50000.0])
    ws.append(["2026-09-02", "购物", 120.5, None, 49879.5])
    wb.save(path)

    result = get_parser("ICBC").parse(StatementFile(path))
    assert result.file_name == "icbc_standard.xlsx"
    assert len(result.transactions) == 2
    assert result.transactions[0].direction == Direction.CREDIT
    assert result.transactions[1].direction == Direction.DEBIT

"""Generic statement file loader tests."""

from pathlib import Path

import pytest
from app.modules.statements.parsers.generic import StatementFile, StatementFileError
from openpyxl import Workbook


def _write_xlsx(path: Path, rows: list[list[object]]) -> None:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    wb.save(path)


def test_load_xlsx_preserves_grid(tmp_path: Path) -> None:
    path = tmp_path / "statement.xlsx"
    _write_xlsx(
        path,
        [
            ["Bank Statement", None, None],
            ["账户余额", 5000.00, None],
            ["交易日期", "摘要", "金额"],
            ["2026-09-01", "工资", 8000],
        ],
    )

    grid = StatementFile(path).load()
    assert grid[0][0] == "Bank Statement"
    # Numeric cells keep their native type (float) for later Decimal conversion;
    # empty cells are normalized to None.
    assert grid[1] == ["账户余额", 5000.0, None]
    assert grid[2] == ["交易日期", "摘要", "金额"]
    assert grid[3] == ["2026-09-01", "工资", 8000]


def test_load_utf8_csv(tmp_path: Path) -> None:
    path = tmp_path / "statement.csv"
    path.write_text("交易日期,摘要,金额\n2026-09-01,工资,8000\n", encoding="utf-8-sig")

    grid = StatementFile(path).load()
    assert grid[0] == ["交易日期", "摘要", "金额"]
    assert grid[1] == ["2026-09-01", "工资", "8000"]


def test_load_gb18030_csv(tmp_path: Path) -> None:
    path = tmp_path / "statement.csv"
    path.write_bytes("交易日期,摘要,金额\n2026-09-01,房租,8000\n".encode("gb18030"))

    grid = StatementFile(path).load()
    assert grid[0] == ["交易日期", "摘要", "金额"]
    assert grid[1] == ["2026-09-01", "房租", "8000"]


def test_load_trim_csv_whitespace(tmp_path: Path) -> None:
    path = tmp_path / "statement.csv"
    path.write_text("交易日期 , 摘要 \n2026-09-01, 工资 \n", encoding="utf-8")

    grid = StatementFile(path).load()
    assert grid[0] == ["交易日期", "摘要"]
    assert grid[1] == ["2026-09-01", "工资"]


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(StatementFileError):
        StatementFile(tmp_path / "missing.xlsx").load()


def test_non_excel_extension(tmp_path: Path) -> None:
    path = tmp_path / "statement.txt"
    path.write_text("not excel", encoding="utf-8")
    with pytest.raises(StatementFileError):
        StatementFile(path).load()

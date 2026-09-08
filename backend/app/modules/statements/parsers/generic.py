"""Low-level statement file loading.

Loads an Excel or CSV statement into a raw 2D grid of cell values while
preserving the original coordinates (rows and columns are never assumed to
start at a fixed position). Higher layers find the header row and table by
scoring, not by hardcoded coordinates.

Excel is read with python-calamine; CSV is decoded with encoding detection
(UTF-8 with BOM first, then GB18030 for Chinese bank exports).
"""

import csv
import io
from pathlib import Path
from typing import Any

from python_calamine import CalamineWorkbook

_ENCODINGS = ("utf-8-sig", "gb18030")


class StatementFileError(Exception):
    """Raised when a statement file cannot be read."""


class StatementFile:
    """Reads a single statement file into a raw cell grid."""

    def __init__(self, path: Path) -> None:
        self.path = path

    @property
    def is_csv(self) -> bool:
        return self.path.suffix.lower() == ".csv"

    def load(self) -> list[list[Any]]:
        """Return the sheet as a grid: a list of rows of cell values.

        Empty cells are ``None``; values keep their native type (str, int,
        float, date, ...). Only the first sheet of a workbook is used.
        """
        try:
            return self._load_csv() if self.is_csv else self._load_excel()
        except StatementFileError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalize all load failures
            raise StatementFileError(f"Failed to read {self.path.name}: {exc}") from exc

    def _load_excel(self) -> list[list[Any]]:
        if not self.path.exists():
            raise StatementFileError(f"File not found: {self.path}")
        workbook = CalamineWorkbook.from_path(str(self.path))
        sheet = workbook.get_sheet_by_index(0)
        grid = sheet.to_python()
        return [[self._clean(cell) for cell in row] for row in grid]

    def _load_csv(self) -> list[list[str | None]]:
        text = self._read_csv_text()
        rows: list[list[str | None]] = []
        for row in csv.reader(io.StringIO(text)):
            rows.append([self._clean(cell) for cell in row])
        return rows

    @staticmethod
    def _clean(cell: Any) -> Any:
        """Normalize empty cells to ``None`` (uniform grid convention)."""
        if cell is None:
            return None
        if isinstance(cell, str):
            stripped = cell.strip()
            return stripped if stripped else None
        return cell

    def _read_csv_text(self) -> str:
        last_error: Exception | None = None
        for encoding in _ENCODINGS:
            try:
                return self.path.read_text(encoding=encoding)
            except (UnicodeDecodeError, FileNotFoundError) as exc:
                last_error = exc
        if last_error is not None:
            raise StatementFileError(f"Could not decode {self.path.name}") from last_error
        return self.path.read_text(encoding="utf-8", errors="replace")

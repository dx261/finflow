"""CMB (招商银行) statement parser.

CMB exports carry 收入金额 / 支出金额 columns; the base pipeline resolves
amount and direction from them. Extension point for CMB-specific quirks.
"""

from app.modules.statements.parsers.base import BaseStatementParser


class CMBParser(BaseStatementParser):
    """Parses CMB statement files."""

    name = "CMB"

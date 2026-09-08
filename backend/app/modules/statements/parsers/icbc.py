"""ICBC (中国工商银行) statement parser.

ICBC exports typically carry separate 借方金额 / 贷方金额 columns; the
base pipeline resolves amount and direction from them. This class exists
as the extension point for ICBC-specific quirks (date formats, summary
normalization) as they are discovered.
"""

from app.modules.statements.parsers.base import BaseStatementParser


class ICBCParser(BaseStatementParser):
    """Parses ICBC statement files."""

    name = "ICBC"

"""Parser factory: route a bank code to its statement parser."""

from app.modules.statements.parsers.base import BaseStatementParser
from app.modules.statements.parsers.cmb import CMBParser
from app.modules.statements.parsers.generic import GenericStatementParser
from app.modules.statements.parsers.icbc import ICBCParser

_PARSERS: dict[str, type[BaseStatementParser]] = {
    "ICBC": ICBCParser,
    "CMB": CMBParser,
    "GENERIC": GenericStatementParser,
}


def get_parser(bank_code: str) -> BaseStatementParser:
    """Return a parser instance for the given bank code.

    Unknown codes fall back to the generic parser so imports never fail
    purely because a bank has no dedicated parser yet.
    """
    parser_cls = _PARSERS.get(bank_code.upper(), GenericStatementParser)
    return parser_cls()

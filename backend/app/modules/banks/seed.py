"""Default bank catalog seeding.

Idempotent: only inserts banks whose code is not already present.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.banks.models import Bank

DEFAULT_BANKS: list[dict[str, str]] = [
    {"code": "ICBC", "name": "中国工商银行", "country": "CN", "statement_parser_type": "ICBC"},
    {"code": "CMB", "name": "招商银行", "country": "CN", "statement_parser_type": "CMB"},
    {"code": "CCB", "name": "中国建设银行", "country": "CN", "statement_parser_type": "GENERIC"},
    {"code": "BOC", "name": "中国银行", "country": "CN", "statement_parser_type": "GENERIC"},
    {"code": "ALIPAY", "name": "支付宝", "country": "CN", "statement_parser_type": "GENERIC"},
    {"code": "WECHAT", "name": "微信支付", "country": "CN", "statement_parser_type": "GENERIC"},
    {"code": "GENERIC", "name": "通用格式", "country": "CN", "statement_parser_type": "GENERIC"},
]


async def seed_default_banks(session: AsyncSession) -> int:
    """Insert any missing default banks; returns the number created."""
    created = 0
    for item in DEFAULT_BANKS:
        exists = await session.scalar(select(Bank).where(Bank.code == item["code"]))
        if exists is None:
            session.add(Bank(**item))
            created += 1
    if created:
        await session.commit()
    return created

"""Default category seeding (idempotent)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.categories.classifier import CategoryCode
from app.modules.categories.models import Category

_CATEGORY_NAMES: dict[CategoryCode, str] = {
    CategoryCode.SALARY: "工资",
    CategoryCode.RENT: "房租",
    CategoryCode.FOOD: "餐饮",
    CategoryCode.TRANSPORT: "交通",
    CategoryCode.SHOPPING: "购物",
    CategoryCode.EDUCATION: "教育",
    CategoryCode.SUBSCRIPTION: "订阅",
    CategoryCode.MEDICAL: "医疗",
    CategoryCode.INVESTMENT: "投资",
    CategoryCode.TRANSFER: "转账",
    CategoryCode.REFUND: "退款",
    CategoryCode.CREDIT_CARD_REPAYMENT: "信用卡还款",
    CategoryCode.OTHER: "其他",
}


async def seed_default_categories(session: AsyncSession) -> int:
    """Insert any missing default categories; returns the count created."""
    created = 0
    for code, name in _CATEGORY_NAMES.items():
        exists = await session.scalar(select(Category).where(Category.code == code.value))
        if exists is None:
            session.add(Category(code=code.value, name=name, is_system=True))
            created += 1
    if created:
        await session.commit()
    return created

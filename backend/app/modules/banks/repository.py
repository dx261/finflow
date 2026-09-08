"""Bank data access."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.banks.models import Bank
from app.modules.banks.schemas import BankCreate, BankUpdate


class BankRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[Bank]:
        result = await self.session.scalars(select(Bank).order_by(Bank.code))
        return list(result)

    async def get_by_id(self, bank_id: uuid.UUID) -> Bank | None:
        return await self.session.get(Bank, bank_id)

    async def get_by_code(self, code: str) -> Bank | None:
        result = await self.session.scalar(select(Bank).where(Bank.code == code))
        return result

    async def create(self, payload: BankCreate) -> Bank:
        bank = Bank(
            code=payload.code,
            name=payload.name,
            country=payload.country,
            logo=payload.logo,
            statement_parser_type=payload.statement_parser_type,
        )
        self.session.add(bank)
        await self.session.flush()
        return bank

    async def update(self, bank: Bank, payload: BankUpdate) -> Bank:
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(bank, field, value)
        await self.session.flush()
        return bank

    async def delete(self, bank: Bank) -> None:
        await self.session.delete(bank)
        await self.session.flush()

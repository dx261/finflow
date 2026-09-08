"""Bank catalog business logic."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.banks.models import Bank
from app.modules.banks.repository import BankRepository
from app.modules.banks.schemas import BankCreate, BankUpdate


class BankService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = BankRepository(session)
        self.session = session

    async def list_banks(self) -> list[Bank]:
        return await self.repository.list_all()

    async def get_bank(self, bank_id: uuid.UUID) -> Bank:
        bank = await self.repository.get_by_id(bank_id)
        if bank is None:
            raise NotFoundError("Bank not found.")
        return bank

    async def create_bank(self, payload: BankCreate) -> Bank:
        if await self.repository.get_by_code(payload.code) is not None:
            raise ConflictError(f"Bank code {payload.code!r} already exists.")
        bank = await self.repository.create(payload)
        await self.session.commit()
        return bank

    async def update_bank(self, bank_id: uuid.UUID, payload: BankUpdate) -> Bank:
        bank = await self.get_bank(bank_id)
        updated = await self.repository.update(bank, payload)
        await self.session.commit()
        return updated

    async def delete_bank(self, bank_id: uuid.UUID) -> None:
        bank = await self.get_bank(bank_id)
        await self.repository.delete(bank)
        await self.session.commit()

"""Bank catalog endpoints.

Reads are available to any authenticated user; writes require OWNER.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.deps import CurrentUser, OwnerUser
from app.modules.banks.schemas import BankCreate, BankRead, BankUpdate
from app.modules.banks.service import BankService

DbSession = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter(prefix="/banks", tags=["banks"])


@router.get("", response_model=list[BankRead])
async def list_banks(current_user: CurrentUser, session: DbSession) -> list[BankRead]:
    banks = await BankService(session).list_banks()
    return [BankRead.model_validate(bank) for bank in banks]


@router.get("/{bank_id}", response_model=BankRead)
async def get_bank(bank_id: uuid.UUID, current_user: CurrentUser, session: DbSession) -> BankRead:
    return BankRead.model_validate(await BankService(session).get_bank(bank_id))


@router.post("", response_model=BankRead, status_code=201)
async def create_bank(payload: BankCreate, owner: OwnerUser, session: DbSession) -> BankRead:
    return BankRead.model_validate(await BankService(session).create_bank(payload))


@router.put("/{bank_id}", response_model=BankRead)
async def update_bank(
    bank_id: uuid.UUID, payload: BankUpdate, owner: OwnerUser, session: DbSession
) -> BankRead:
    return BankRead.model_validate(await BankService(session).update_bank(bank_id, payload))


@router.delete("/{bank_id}", status_code=204)
async def delete_bank(bank_id: uuid.UUID, owner: OwnerUser, session: DbSession) -> None:
    await BankService(session).delete_bank(bank_id)

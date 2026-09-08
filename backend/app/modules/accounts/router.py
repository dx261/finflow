"""Account endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.accounts.schemas import AccountCreate, AccountRead, AccountUpdate
from app.modules.accounts.service import AccountService
from app.modules.auth.deps import CurrentUser, OwnerUser

DbSession = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountRead])
async def list_accounts(current_user: CurrentUser, session: DbSession) -> list[AccountRead]:
    return await AccountService(session).list_accounts(current_user.id)


@router.get("/{account_id}", response_model=AccountRead)
async def get_account(
    account_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> AccountRead:
    return await AccountService(session).get_account(account_id, current_user)


@router.post("", response_model=AccountRead, status_code=201)
async def create_account(
    payload: AccountCreate, owner: OwnerUser, session: DbSession
) -> AccountRead:
    return await AccountService(session).create_account(owner.id, payload)


@router.put("/{account_id}", response_model=AccountRead)
async def update_account(
    account_id: uuid.UUID, payload: AccountUpdate, owner: OwnerUser, session: DbSession
) -> AccountRead:
    return await AccountService(session).update_account(account_id, payload, owner)


@router.delete("/{account_id}", status_code=204)
async def delete_account(account_id: uuid.UUID, owner: OwnerUser, session: DbSession) -> None:
    await AccountService(session).delete_account(account_id, owner)

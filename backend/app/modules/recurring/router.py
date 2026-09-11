"""Recurring payment endpoints."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.deps import CurrentUser, OwnerUser
from app.modules.recurring.schemas import RecurringCreate, RecurringRead, RecurringUpdate
from app.modules.recurring.service import RecurringService

DbSession = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter(prefix="/recurring", tags=["recurring"])


@router.get("", response_model=list[RecurringRead])
async def list_recurring(current_user: CurrentUser, session: DbSession) -> list[RecurringRead]:
    items = await RecurringService(session).list(current_user.id)
    return [RecurringRead.model_validate(item) for item in items]


@router.post("", response_model=RecurringRead, status_code=201)
async def create_recurring(
    payload: RecurringCreate, owner: OwnerUser, session: DbSession
) -> RecurringRead:
    return RecurringRead.model_validate(await RecurringService(session).create(owner.id, payload))


@router.put("/{recurring_id}", response_model=RecurringRead)
async def update_recurring(
    recurring_id: uuid.UUID,
    payload: RecurringUpdate,
    owner: OwnerUser,
    session: DbSession,
) -> RecurringRead:
    return RecurringRead.model_validate(
        await RecurringService(session).update(owner.id, recurring_id, payload)
    )


@router.delete("/{recurring_id}", status_code=204)
async def delete_recurring(recurring_id: uuid.UUID, owner: OwnerUser, session: DbSession) -> None:
    await RecurringService(session).delete(owner.id, recurring_id)


@router.post("/generate", response_model=dict)
async def generate_plans(
    owner: OwnerUser,
    session: DbSession,
    from_date: date,
    to_date: date,
) -> dict:
    """Idempotently materialize due recurring payments as PLANNED plans."""
    created = await RecurringService(session).generate_due_plans(owner.id, from_date, to_date)
    return {"created": created}

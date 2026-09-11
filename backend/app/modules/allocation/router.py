"""Allocation endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.allocation.schemas import AllocationItem, AllocationRead
from app.modules.allocation.service import AllocationService
from app.modules.auth.deps import CurrentUser, OwnerUser

DbSession = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter(prefix="/payments/{payment_id}/allocations", tags=["allocations"])


@router.get("", response_model=list[AllocationRead])
async def list_allocations(
    payment_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> list[AllocationRead]:
    allocations = await AllocationService(session).list_for_payment(current_user.id, payment_id)
    return [AllocationRead.model_validate(a) for a in allocations]


@router.post("/preview", response_model=list[AllocationRead])
async def preview_allocations(
    payment_id: uuid.UUID, owner: OwnerUser, session: DbSession
) -> list[AllocationRead]:
    """Run the engine and store a PROPOSED plan (nothing reserved)."""
    allocations = await AllocationService(session).generate_preview(owner.id, payment_id)
    return [AllocationRead.model_validate(a) for a in allocations]


@router.put("/override", response_model=list[AllocationRead])
async def override_allocations(
    payment_id: uuid.UUID,
    items: list[AllocationItem],
    owner: OwnerUser,
    session: DbSession,
) -> list[AllocationRead]:
    """Replace the proposed plan with a user-defined allocation (validated)."""
    allocations = await AllocationService(session).manual_override(owner.id, payment_id, items)
    return [AllocationRead.model_validate(a) for a in allocations]


@router.post("/confirm", response_model=list[AllocationRead])
async def confirm_allocations(
    payment_id: uuid.UUID, owner: OwnerUser, session: DbSession
) -> list[AllocationRead]:
    """Accept the proposal: PROPOSED -> RESERVED (virtual reservation)."""
    allocations = await AllocationService(session).confirm_reservation(owner.id, payment_id)
    return [AllocationRead.model_validate(a) for a in allocations]

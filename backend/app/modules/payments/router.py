"""Payment plan endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.deps import CurrentUser, OwnerUser
from app.modules.payments.models import PaymentStatus
from app.modules.payments.schemas import (
    PaymentCreate,
    PaymentRead,
    PaymentTransition,
    PaymentUpdate,
)
from app.modules.payments.service import PaymentService

DbSession = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("", response_model=list[PaymentRead])
async def list_payments(
    current_user: CurrentUser,
    session: DbSession,
    status: PaymentStatus | None = None,
) -> list[PaymentRead]:
    payments = await PaymentService(session).list_payments(current_user.id, status)
    return [PaymentRead.model_validate(payment) for payment in payments]


@router.post("", response_model=PaymentRead, status_code=201)
async def create_payment(
    payload: PaymentCreate, owner: OwnerUser, session: DbSession
) -> PaymentRead:
    return PaymentRead.model_validate(
        await PaymentService(session).create_payment(owner.id, payload)
    )


@router.get("/{payment_id}", response_model=PaymentRead)
async def get_payment(
    payment_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> PaymentRead:
    return PaymentRead.model_validate(
        await PaymentService(session).get_payment(current_user.id, payment_id)
    )


@router.put("/{payment_id}", response_model=PaymentRead)
async def update_payment(
    payment_id: uuid.UUID,
    payload: PaymentUpdate,
    owner: OwnerUser,
    session: DbSession,
) -> PaymentRead:
    return PaymentRead.model_validate(
        await PaymentService(session).update_payment(owner.id, payment_id, payload)
    )


@router.delete("/{payment_id}", status_code=204)
async def delete_payment(payment_id: uuid.UUID, owner: OwnerUser, session: DbSession) -> None:
    await PaymentService(session).delete_payment(owner.id, payment_id)


@router.post("/{payment_id}/transition", response_model=PaymentRead)
async def transition_payment(
    payment_id: uuid.UUID,
    payload: PaymentTransition,
    owner: OwnerUser,
    session: DbSession,
) -> PaymentRead:
    return PaymentRead.model_validate(
        await PaymentService(session).transition(owner.id, payment_id, payload.target_status)
    )

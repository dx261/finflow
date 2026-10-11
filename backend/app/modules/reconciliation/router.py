"""Reconciliation endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.deps import DataOwnerId, OwnerUser
from app.modules.payments.models import PaymentStatus
from app.modules.reconciliation.schemas import ReconRead, SelectTransaction
from app.modules.reconciliation.service import ReconciliationService

DbSession = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter(tags=["reconciliation"])
payments_router = APIRouter(prefix="/payments", tags=["reconciliation"])


@payments_router.post("/{payment_id}/reconcile", response_model=ReconRead)
async def reconcile_payment(
    payment_id: uuid.UUID, owner: OwnerUser, session: DbSession
) -> ReconRead:
    """Score the payment against candidate transactions and auto-match."""
    recon = await ReconciliationService(session).run_for_payment(owner.id, payment_id)
    return ReconRead.model_validate(recon)


@payments_router.get("/{payment_id}/reconciliations", response_model=list[ReconRead])
async def list_payment_reconciliations(
    payment_id: uuid.UUID, data_owner_id: DataOwnerId, session: DbSession
) -> list[ReconRead]:
    items = await ReconciliationService(session).list_for_payment(data_owner_id, payment_id)
    return [ReconRead.model_validate(item) for item in items]


@payments_router.post("/{payment_id}/release", response_model=dict)
async def release_payment(
    payment_id: uuid.UUID, owner: OwnerUser, session: DbSession, target: PaymentStatus
) -> dict:
    """Release reserved funds: target must be PLANNED or CANCELLED."""
    payment = await ReconciliationService(session).release_reservations(
        owner.id, payment_id, target
    )
    return {"id": str(payment.id), "status": payment.status.value}


@router.get("/reconciliations/pending", response_model=list[ReconRead])
async def pending_reconciliations(
    data_owner_id: DataOwnerId, session: DbSession
) -> list[ReconRead]:
    """Review workbench: high-confidence and review-required open matches."""
    items = await ReconciliationService(session).list_pending(data_owner_id)
    return [ReconRead.model_validate(item) for item in items]


@router.post("/reconciliations/{recon_id}/confirm", response_model=ReconRead)
async def confirm_reconciliation(
    recon_id: uuid.UUID, owner: OwnerUser, session: DbSession
) -> ReconRead:
    """Confirm the match and settle the payment + allocations."""
    recon = await ReconciliationService(session).confirm(owner.id, recon_id)
    return ReconRead.model_validate(recon)


@router.post("/reconciliations/{recon_id}/reject", response_model=ReconRead)
async def reject_reconciliation(
    recon_id: uuid.UUID, owner: OwnerUser, session: DbSession
) -> ReconRead:
    recon = await ReconciliationService(session).reject(owner.id, recon_id)
    return ReconRead.model_validate(recon)


@router.post("/reconciliations/{recon_id}/select-transaction", response_model=ReconRead)
async def select_transaction(
    recon_id: uuid.UUID,
    payload: SelectTransaction,
    owner: OwnerUser,
    session: DbSession,
) -> ReconRead:
    recon = await ReconciliationService(session).select_transaction(
        owner.id, recon_id, payload.transaction_id
    )
    return ReconRead.model_validate(recon)

"""Payment plan business logic.

Status transitions are NOT performed here directly — they go through the
state machine (TASK-024). This service owns CRUD and ownership checks.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.accounts.models import Account
from app.modules.payments.models import PaymentPlan, PaymentStatus
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.schemas import PaymentCreate, PaymentUpdate
from app.modules.payments.state_machine import assert_transition

_EDITABLE_STATUSES = {PaymentStatus.DRAFT, PaymentStatus.PLANNED}


class PaymentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = PaymentRepository(session)

    async def _get_owned_account(self, user_id: uuid.UUID, account_id: uuid.UUID) -> Account:
        account = await self.session.get(Account, account_id)
        if account is None or account.user_id != user_id:
            raise NotFoundError("Account not found.")
        return account

    async def list_payments(
        self, user_id: uuid.UUID, status: PaymentStatus | None = None
    ) -> list[PaymentPlan]:
        return await self.repository.list_by_user(user_id, status)

    async def get_payment(self, user_id: uuid.UUID, payment_id: uuid.UUID) -> PaymentPlan:
        payment = await self.repository.get_by_id(payment_id)
        if payment is None or payment.user_id != user_id:
            raise NotFoundError("Payment not found.")
        return payment

    async def create_payment(self, user_id: uuid.UUID, payload: PaymentCreate) -> PaymentPlan:
        if payload.preferred_account_id is not None:
            await self._get_owned_account(user_id, payload.preferred_account_id)
        payment = await self.repository.create(user_id, payload)
        await self.session.commit()
        return payment

    async def update_payment(
        self, user_id: uuid.UUID, payment_id: uuid.UUID, payload: PaymentUpdate
    ) -> PaymentPlan:
        payment = await self.get_payment(user_id, payment_id)
        if payment.status not in _EDITABLE_STATUSES:
            raise ConflictError("Payment can only be edited in DRAFT or PLANNED.")
        if payload.preferred_account_id is not None:
            await self._get_owned_account(user_id, payload.preferred_account_id)
        updated = await self.repository.update(payment, payload)
        await self.session.commit()
        return updated

    async def delete_payment(self, user_id: uuid.UUID, payment_id: uuid.UUID) -> None:
        payment = await self.get_payment(user_id, payment_id)
        if payment.status not in _EDITABLE_STATUSES:
            raise ConflictError("Only DRAFT or PLANNED payments can be deleted.")
        await self.repository.delete(payment)
        await self.session.commit()

    async def transition(
        self, user_id: uuid.UUID, payment_id: uuid.UUID, target: PaymentStatus
    ) -> PaymentPlan:
        """Advance a payment to ``target``, validated by the state machine."""
        payment = await self.get_payment(user_id, payment_id)
        assert_transition(payment.status, target)
        payment.status = target
        await self.session.commit()
        return payment

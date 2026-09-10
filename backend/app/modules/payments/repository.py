"""Payment plan data access."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payments.models import PaymentPlan, PaymentStatus
from app.modules.payments.schemas import PaymentCreate, PaymentUpdate


class PaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_user(
        self, user_id: uuid.UUID, status: PaymentStatus | None = None
    ) -> list[PaymentPlan]:
        query = select(PaymentPlan).where(PaymentPlan.user_id == user_id)
        if status is not None:
            query = query.where(PaymentPlan.status == status)
        query = query.order_by(PaymentPlan.planned_date, PaymentPlan.created_at)
        result = await self.session.scalars(query)
        return list(result)

    async def get_by_id(self, payment_id: uuid.UUID) -> PaymentPlan | None:
        return await self.session.get(PaymentPlan, payment_id)

    async def create(self, user_id: uuid.UUID, payload: PaymentCreate) -> PaymentPlan:
        payment = PaymentPlan(
            user_id=user_id,
            name=payload.name,
            description=payload.description,
            payee_name=payload.payee_name,
            amount=payload.amount,
            currency=payload.currency,
            planned_date=payload.planned_date,
            priority=payload.priority,
            preferred_account_id=payload.preferred_account_id,
            status=PaymentStatus.DRAFT,
        )
        self.session.add(payment)
        await self.session.flush()
        return payment

    async def update(self, payment: PaymentPlan, payload: PaymentUpdate) -> PaymentPlan:
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(payment, field, value)
        await self.session.flush()
        return payment

    async def delete(self, payment: PaymentPlan) -> None:
        await self.session.delete(payment)
        await self.session.flush()

    async def upcoming(
        self, user_id: uuid.UUID, from_date: date, to_date: date
    ) -> list[PaymentPlan]:
        result = await self.session.scalars(
            select(PaymentPlan)
            .where(
                PaymentPlan.user_id == user_id,
                PaymentPlan.planned_date >= from_date,
                PaymentPlan.planned_date <= to_date,
            )
            .order_by(PaymentPlan.planned_date)
        )
        return list(result)

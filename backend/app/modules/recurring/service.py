"""Recurring payment generation logic.

Given a recurring payment and a date window, compute the occurrence dates
and materialize PaymentPlans — idempotently, so re-running the job never
duplicates the same month's rent.
"""

import calendar
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.modules.payments.models import PaymentPlan, PaymentStatus
from app.modules.payments.repository import PaymentRepository
from app.modules.recurring.models import RecurringFrequency, RecurringPayment
from app.modules.recurring.schemas import RecurringCreate, RecurringUpdate

_MONTH_STEP = {
    RecurringFrequency.MONTHLY: 1,
    RecurringFrequency.QUARTERLY: 3,
    RecurringFrequency.YEARLY: 12,
}


def next_due_dates(recurring: RecurringPayment, from_date: date, to_date: date) -> list[date]:
    """Compute occurrence dates within ``[from_date, to_date]``."""
    if not recurring.enabled:
        return []
    if recurring.end_date is not None and from_date > recurring.end_date:
        return []

    if recurring.frequency == RecurringFrequency.WEEKLY:
        cursor = recurring.start_date
        due: list[date] = []
        while cursor <= to_date:
            if (
                cursor >= from_date
                and cursor >= recurring.start_date
                and (recurring.end_date is None or cursor <= recurring.end_date)
            ):
                due.append(cursor)
            cursor += timedelta(days=7)
        return due

    step = _MONTH_STEP[recurring.frequency]
    year, month = recurring.start_date.year, recurring.start_date.month
    due = []
    while True:
        day = min(recurring.day_of_month, calendar.monthrange(year, month)[1])
        candidate = date(year, month, day)
        if candidate > to_date:
            break
        if (
            candidate >= from_date
            and candidate >= recurring.start_date
            and (recurring.end_date is None or candidate <= recurring.end_date)
        ):
            due.append(candidate)
        month += step
        while month > 12:
            month -= 12
            year += 1
    return due


class RecurringService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.payment_repo = PaymentRepository(session)

    async def _get_owned(self, user_id: uuid.UUID, recurring_id: uuid.UUID) -> RecurringPayment:
        recurring = await self.session.get(RecurringPayment, recurring_id)
        if recurring is None or recurring.user_id != user_id:
            raise NotFoundError("Recurring payment not found.")
        return recurring

    async def create(self, user_id: uuid.UUID, payload: RecurringCreate) -> RecurringPayment:
        if payload.preferred_account_id is not None:
            await self._owned_account(user_id, payload.preferred_account_id)
        recurring = RecurringPayment(
            user_id=user_id,
            name=payload.name,
            amount=payload.amount,
            currency=payload.currency,
            frequency=payload.frequency,
            day_of_month=payload.day_of_month,
            start_date=payload.start_date,
            end_date=payload.end_date,
            preferred_account_id=payload.preferred_account_id,
            priority=payload.priority,
            enabled=True,
        )
        self.session.add(recurring)
        await self.session.commit()
        return recurring

    async def list(self, user_id: uuid.UUID) -> list[RecurringPayment]:
        result = await self.session.scalars(
            select(RecurringPayment)
            .where(RecurringPayment.user_id == user_id)
            .order_by(RecurringPayment.name)
        )
        return list(result)

    async def update(
        self, user_id: uuid.UUID, recurring_id: uuid.UUID, payload: RecurringUpdate
    ) -> RecurringPayment:
        recurring = await self._get_owned(user_id, recurring_id)
        data = payload.model_dump(exclude_unset=True)
        if "preferred_account_id" in data and data["preferred_account_id"] is not None:
            await self._owned_account(user_id, data["preferred_account_id"])
        for field, value in data.items():
            setattr(recurring, field, value)
        await self.session.commit()
        return recurring

    async def delete(self, user_id: uuid.UUID, recurring_id: uuid.UUID) -> None:
        recurring = await self._get_owned(user_id, recurring_id)
        await self.session.delete(recurring)
        await self.session.commit()

    async def generate_due_plans(self, user_id: uuid.UUID, from_date: date, to_date: date) -> int:
        """Create PLANNED payments for due occurrences (idempotent)."""
        result = await self.session.scalars(
            select(RecurringPayment).where(
                RecurringPayment.user_id == user_id, RecurringPayment.enabled.is_(True)
            )
        )
        created = 0
        for recurring in list(result):
            existing = set(
                await self.session.scalars(
                    select(PaymentPlan.occurrence_date).where(
                        PaymentPlan.source_recurring_id == recurring.id,
                        PaymentPlan.occurrence_date.is_not(None),
                    )
                )
            )
            for due_date in next_due_dates(recurring, from_date, to_date):
                if due_date in existing:
                    continue
                plan = PaymentPlan(
                    user_id=user_id,
                    name=recurring.name,
                    amount=recurring.amount,
                    currency=recurring.currency,
                    planned_date=due_date,
                    priority=recurring.priority,
                    preferred_account_id=recurring.preferred_account_id,
                    status=PaymentStatus.PLANNED,
                    source_recurring_id=recurring.id,
                    occurrence_date=due_date,
                )
                self.session.add(plan)
                existing.add(due_date)
                created += 1
        if created:
            await self.session.commit()
        return created

    async def _owned_account(self, user_id: uuid.UUID, account_id: uuid.UUID) -> None:
        from app.modules.accounts.models import Account

        account = await self.session.get(Account, account_id)
        if account is None or account.user_id != user_id:
            raise NotFoundError("Account not found.")

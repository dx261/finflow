"""Forecast service: load data, project balances, collect warnings."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.modules.accounts.models import Account, AccountStatus
from app.modules.allocation.models import AllocationStatus, FundAllocation
from app.modules.forecast.engine import ForecastAccount, ForecastDay, ForecastFlow, forecast_account
from app.modules.forecast.models import CashFlowPlan, CashFlowPlanStatus, CashFlowPlanType
from app.modules.forecast.schemas import (
    CashFlowPlanCreate,
    CashFlowPlanUpdate,
    ForecastDayRead,
    ForecastResponse,
)
from app.modules.payments.models import PaymentPlan, PaymentStatus

_UPCOMING_PAYMENT_STATUSES = [
    PaymentStatus.PLANNED,
    PaymentStatus.ALLOCATED,
    PaymentStatus.RESERVED,
    PaymentStatus.WAITING_MANUAL_EXECUTION,
]


class ForecastService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- CashFlowPlan CRUD ------------------------------------------------

    async def create_plan(self, user_id: uuid.UUID, payload: CashFlowPlanCreate) -> CashFlowPlan:
        plan = CashFlowPlan(
            user_id=user_id,
            type=payload.type,
            name=payload.name,
            amount=payload.amount,
            date=payload.date,
            account_id=payload.account_id,
            is_recurring=payload.is_recurring,
        )
        self.session.add(plan)
        await self.session.commit()
        return plan

    async def list_plans(self, user_id: uuid.UUID) -> list[CashFlowPlan]:
        result = await self.session.scalars(
            select(CashFlowPlan).where(CashFlowPlan.user_id == user_id).order_by(CashFlowPlan.date)
        )
        return list(result)

    async def update_plan(
        self, user_id: uuid.UUID, plan_id: uuid.UUID, payload: CashFlowPlanUpdate
    ) -> CashFlowPlan:
        plan = await self._get_plan(user_id, plan_id)
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(plan, field, value)
        await self.session.commit()
        return plan

    async def delete_plan(self, user_id: uuid.UUID, plan_id: uuid.UUID) -> None:
        plan = await self._get_plan(user_id, plan_id)
        await self.session.delete(plan)
        await self.session.commit()

    async def _get_plan(self, user_id: uuid.UUID, plan_id: uuid.UUID) -> CashFlowPlan:
        plan = await self.session.get(CashFlowPlan, plan_id)
        if plan is None or plan.user_id != user_id:
            raise NotFoundError("Cash flow plan not found.")
        return plan

    # --- forecast -----------------------------------------------------------

    async def _payment_targets(self, payment: PaymentPlan) -> list[tuple[str, Decimal]]:
        if payment.status == PaymentStatus.RESERVED:
            allocations = list(
                await self.session.scalars(
                    select(FundAllocation).where(
                        FundAllocation.payment_id == payment.id,
                        FundAllocation.status == AllocationStatus.RESERVED,
                    )
                )
            )
            if allocations:
                return [(str(a.account_id), a.allocated_amount) for a in allocations]
        if payment.preferred_account_id is not None:
            return [(str(payment.preferred_account_id), payment.amount)]
        return []

    async def forecast(self, user_id: uuid.UUID, horizon_days: int) -> ForecastResponse:
        today = date.today()
        accounts = list(
            await self.session.scalars(
                select(Account).where(
                    Account.user_id == user_id,
                    Account.status == AccountStatus.ACTIVE,
                )
            )
        )
        payments = list(
            await self.session.scalars(
                select(PaymentPlan).where(
                    PaymentPlan.user_id == user_id,
                    PaymentPlan.status.in_(_UPCOMING_PAYMENT_STATUSES),
                    PaymentPlan.planned_date >= today,
                )
            )
        )
        incomes = list(
            await self.session.scalars(
                select(CashFlowPlan).where(
                    CashFlowPlan.user_id == user_id,
                    CashFlowPlan.type == CashFlowPlanType.INCOME,
                    CashFlowPlan.status == CashFlowPlanStatus.ACTIVE,
                    CashFlowPlan.date >= today,
                )
            )
        )

        flows: list[ForecastFlow] = []
        for payment in payments:
            for account_id, amount in await self._payment_targets(payment):
                flows.append(ForecastFlow(payment.planned_date, amount, account_id, "expense"))
        for income in incomes:
            if income.account_id is not None:
                flows.append(
                    ForecastFlow(income.date, income.amount, str(income.account_id), "income")
                )

        per_account: dict[str, list[ForecastDayRead]] = {}
        warnings: list[dict] = []
        for account in accounts:
            account_flows = [f for f in flows if f.account_id == str(account.id)]
            days = forecast_account(
                ForecastAccount(
                    id=str(account.id),
                    actual_balance=account.actual_balance,
                    minimum_balance=account.minimum_balance,
                    currency=account.currency,
                ),
                account_flows,
                horizon_days,
                start=today,
            )
            per_account[str(account.id)] = [_read_day(d) for d in days]
            for day in days:
                if day.below_minimum:
                    warnings.append(
                        {
                            "account_id": str(account.id),
                            "date": day.date.isoformat(),
                            "projected_balance": str(day.ending_balance),
                            "minimum_balance": str(account.minimum_balance),
                        }
                    )

        aggregate = self._aggregate(per_account, horizon_days, today)
        return ForecastResponse(accounts=per_account, aggregate=aggregate, warnings=warnings)

    @staticmethod
    def _aggregate(
        per_account: dict[str, list[ForecastDayRead]],
        horizon_days: int,
        start: date,
    ) -> list[ForecastDayRead]:
        days: list[ForecastDayRead] = []
        for offset in range(horizon_days):
            day_date = start + timedelta(days=offset)
            starting = sum((d[offset].starting_balance for d in per_account.values()), Decimal("0"))
            income = sum((d[offset].expected_income for d in per_account.values()), Decimal("0"))
            expense = sum((d[offset].expected_expense for d in per_account.values()), Decimal("0"))
            ending = sum((d[offset].ending_balance for d in per_account.values()), Decimal("0"))
            below = any(d[offset].below_minimum for d in per_account.values())
            days.append(
                ForecastDayRead(
                    date=day_date,
                    starting_balance=starting,
                    expected_income=income,
                    expected_expense=expense,
                    ending_balance=ending,
                    below_minimum=below,
                )
            )
        return days


def _read_day(day: ForecastDay) -> ForecastDayRead:
    return ForecastDayRead(
        date=day.date,
        starting_balance=day.starting_balance,
        expected_income=day.expected_income,
        expected_expense=day.expected_expense,
        ending_balance=day.ending_balance,
        below_minimum=day.below_minimum,
    )

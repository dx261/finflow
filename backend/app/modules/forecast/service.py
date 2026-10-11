"""Forecast service: load data, project balances, collect warnings."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.accounts.models import Account, AccountStatus
from app.modules.allocation.models import AllocationStatus, FundAllocation
from app.modules.forecast.engine import ForecastAccount, ForecastDay, ForecastFlow, forecast_account
from app.modules.forecast.models import CashFlowPlan, CashFlowPlanStatus, CashFlowPlanType
from app.modules.forecast.schemas import (
    CashFlowPlanCreate,
    CashFlowPlanUpdate,
    ForecastDayRead,
    ForecastResponse,
    ForecastUnassignedRead,
    ForecastWarningRead,
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
        account = None
        if payload.account_id is not None:
            account = await self._get_owned_account(user_id, payload.account_id)
        currency = payload.currency or (account.currency if account is not None else "CNY")
        if account is not None and currency != account.currency:
            raise ConflictError("Cash flow currency must match the selected account.")
        plan = CashFlowPlan(
            user_id=user_id,
            type=payload.type,
            name=payload.name,
            amount=payload.amount,
            currency=currency,
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
        target_account_id = data.get("account_id", plan.account_id)
        target_account = None
        if target_account_id is not None:
            target_account = await self._get_owned_account(user_id, target_account_id)
        if target_account is not None and "account_id" in data and "currency" not in data:
            data["currency"] = target_account.currency
        if data.get("currency") is None:
            data.pop("currency", None)
        target_currency = data.get("currency", plan.currency)
        if target_account is not None and target_currency != target_account.currency:
            raise ConflictError("Cash flow currency must match the selected account.")
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

    async def _get_owned_account(self, user_id: uuid.UUID, account_id: uuid.UUID) -> Account:
        account = await self.session.get(Account, account_id)
        if account is None or account.user_id != user_id:
            raise NotFoundError("Account not found.")
        return account

    # --- forecast -----------------------------------------------------------

    async def _payment_targets(self, payment: PaymentPlan) -> list[tuple[str, Decimal]]:
        allocation_status = None
        if payment.status in (
            PaymentStatus.RESERVED,
            PaymentStatus.WAITING_MANUAL_EXECUTION,
        ):
            allocation_status = AllocationStatus.RESERVED
        elif payment.status == PaymentStatus.ALLOCATED:
            allocation_status = AllocationStatus.PROPOSED
        if allocation_status is not None:
            allocations = list(
                await self.session.scalars(
                    select(FundAllocation).where(
                        FundAllocation.payment_id == payment.id,
                        FundAllocation.status == allocation_status,
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
        horizon_end = today + timedelta(days=horizon_days - 1)
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
                    PaymentPlan.planned_date <= horizon_end,
                )
            )
        )
        cashflow_plans = list(
            await self.session.scalars(
                select(CashFlowPlan).where(
                    CashFlowPlan.user_id == user_id,
                    CashFlowPlan.status == CashFlowPlanStatus.ACTIVE,
                    CashFlowPlan.date >= today,
                    CashFlowPlan.date <= horizon_end,
                )
            )
        )

        flows: list[ForecastFlow] = []
        unassigned: list[ForecastUnassignedRead] = []
        for payment in payments:
            targets = await self._payment_targets(payment)
            for account_id, amount in targets:
                flows.append(ForecastFlow(payment.planned_date, amount, account_id, "expense"))
            if not targets:
                unassigned.append(
                    ForecastUnassignedRead(
                        id=payment.id,
                        source_type="PAYMENT",
                        name=payment.name,
                        date=payment.planned_date,
                        amount=payment.amount,
                        currency=payment.currency,
                        flow_type="expense",
                        reason="No allocation or preferred account.",
                    )
                )
        for plan in cashflow_plans:
            if plan.account_id is not None:
                flows.append(
                    ForecastFlow(
                        plan.date,
                        plan.amount,
                        str(plan.account_id),
                        "income" if plan.type == CashFlowPlanType.INCOME else "expense",
                    )
                )
            else:
                unassigned.append(
                    ForecastUnassignedRead(
                        id=plan.id,
                        source_type="CASHFLOW_PLAN",
                        name=plan.name,
                        date=plan.date,
                        amount=plan.amount,
                        currency=plan.currency,
                        flow_type=("income" if plan.type == CashFlowPlanType.INCOME else "expense"),
                        reason="No account selected.",
                    )
                )

        per_account: dict[str, list[ForecastDayRead]] = {}
        warnings: list[ForecastWarningRead] = []
        account_currencies: dict[str, str] = {}
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
            account_currencies[str(account.id)] = account.currency
            for day in days:
                if day.below_minimum:
                    warnings.append(
                        ForecastWarningRead(
                            account_id=account.id,
                            account_name=account.name,
                            currency=account.currency,
                            date=day.date,
                            projected_balance=day.ending_balance,
                            minimum_balance=account.minimum_balance,
                        )
                    )

        aggregates_by_currency: dict[str, list[ForecastDayRead]] = {}
        for currency in sorted(set(account_currencies.values())):
            currency_accounts = {
                account_id: days
                for account_id, days in per_account.items()
                if account_currencies[account_id] == currency
            }
            aggregates_by_currency[currency] = self._aggregate(
                currency_accounts, horizon_days, today
            )
        aggregate_currency = (
            next(iter(aggregates_by_currency)) if len(aggregates_by_currency) == 1 else None
        )
        aggregate = (
            aggregates_by_currency[aggregate_currency] if aggregate_currency is not None else []
        )
        return ForecastResponse(
            accounts=per_account,
            aggregate=aggregate,
            aggregate_currency=aggregate_currency,
            aggregates_by_currency=aggregates_by_currency,
            warnings=warnings,
            unassigned=unassigned,
        )

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

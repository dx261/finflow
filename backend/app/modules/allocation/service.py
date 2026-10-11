"""Allocation business logic: preview, manual override, reservation."""

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    InsufficientPlanningFundsError,
    NotFoundError,
)
from app.modules.accounts.models import Account
from app.modules.allocation.engine import (
    AccountInput,
    PaymentInput,
    Priority,
    allocate,
)
from app.modules.allocation.models import AllocationStatus, FundAllocation
from app.modules.allocation.repository import AllocationRepository
from app.modules.allocation.schemas import AllocationItem
from app.modules.audit.service import AuditService
from app.modules.payments.models import PaymentPlan, PaymentStatus
from app.modules.payments.state_machine import assert_transition


async def sum_reserved_amount(session: AsyncSession, account_id: uuid.UUID) -> Decimal:
    """Sum of currently reserved allocations for an account."""
    return (await sum_reserved_amounts(session, [account_id])).get(account_id, Decimal("0"))


async def sum_reserved_amounts(
    session: AsyncSession, account_ids: list[uuid.UUID]
) -> dict[uuid.UUID, Decimal]:
    """Load reserved totals for several accounts in one grouped query."""
    if not account_ids:
        return {}
    rows = (
        await session.execute(
            select(FundAllocation.account_id, func.sum(FundAllocation.allocated_amount))
            .where(
                FundAllocation.account_id.in_(account_ids),
                FundAllocation.status == AllocationStatus.RESERVED,
            )
            .group_by(FundAllocation.account_id)
        )
    ).all()
    return {account_id: Decimal(str(total)) for account_id, total in rows}


class AllocationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = AllocationRepository(session)

    # --- helpers ----------------------------------------------------------

    async def _get_payment(self, user_id: uuid.UUID, payment_id: uuid.UUID) -> PaymentPlan:
        payment = await self.session.get(PaymentPlan, payment_id)
        if payment is None or payment.user_id != user_id:
            raise NotFoundError("Payment not found.")
        return payment

    async def _get_payment_for_update(
        self, user_id: uuid.UUID, payment_id: uuid.UUID
    ) -> PaymentPlan:
        payment = await self.session.scalar(
            select(PaymentPlan)
            .where(PaymentPlan.id == payment_id, PaymentPlan.user_id == user_id)
            .with_for_update()
        )
        if payment is None:
            raise NotFoundError("Payment not found.")
        return payment

    async def _get_owned_account(self, user_id: uuid.UUID, account_id: uuid.UUID) -> Account:
        account = await self.session.get(Account, account_id)
        if account is None or account.user_id != user_id:
            raise NotFoundError("Account not found.")
        return account

    async def _planning_available(self, account: Account) -> Decimal:
        reserved = await sum_reserved_amount(self.session, account.id)
        return (account.actual_balance - reserved - account.minimum_balance).quantize(
            Decimal("0.01")
        )

    async def _load_account_inputs(self, user_id: uuid.UUID) -> list[AccountInput]:
        result = await self.session.scalars(select(Account).where(Account.user_id == user_id))
        accounts = list(result)
        reserved = await sum_reserved_amounts(self.session, [account.id for account in accounts])
        inputs = []
        for account in accounts:
            planning_available = (
                account.actual_balance
                - reserved.get(account.id, Decimal("0"))
                - account.minimum_balance
            ).quantize(Decimal("0.01"))
            inputs.append(
                AccountInput(
                    id=str(account.id),
                    currency=account.currency,
                    planning_available=planning_available,
                    include_in_allocation=account.include_in_allocation,
                )
            )
        return inputs

    def _payment_input(self, payment: PaymentPlan) -> PaymentInput:
        priority = Priority(payment.priority.value)
        return PaymentInput(
            id=str(payment.id),
            amount=payment.amount,
            currency=payment.currency,
            planned_date=payment.planned_date,
            priority=priority,
            preferred_account_id=(
                str(payment.preferred_account_id) if payment.preferred_account_id else None
            ),
        )

    # --- preview (TASK-029) -----------------------------------------------

    async def generate_preview(
        self, user_id: uuid.UUID, payment_id: uuid.UUID
    ) -> list[FundAllocation]:
        """Run the engine and store a PROPOSED plan (no funds reserved)."""
        payment = await self._get_payment_for_update(user_id, payment_id)
        if payment.status != PaymentStatus.PLANNED:
            raise ConflictError("Only PLANNED payments can be allocated.")

        accounts = await self._load_account_inputs(user_id)
        result = allocate([self._payment_input(payment)], accounts)[0]
        if result.shortage > 0:
            raise InsufficientPlanningFundsError(
                f"Insufficient planning funds; shortage is {result.shortage:.2f}."
            )

        await self.repository.delete_proposed(payment_id)
        allocations = [
            FundAllocation(
                payment_id=payment.id,
                account_id=uuid.UUID(account_id),
                allocated_amount=amount,
                status=AllocationStatus.PROPOSED,
                algorithm_version="v1",
            )
            for account_id, amount in result.allocations
        ]
        self.session.add_all(allocations)

        assert_transition(payment.status, PaymentStatus.ALLOCATED)
        payment.status = PaymentStatus.ALLOCATED
        await AuditService(self.session).record(
            user_id=user_id,
            action="ALLOCATION_PREVIEWED",
            resource_type="payment",
            resource_id=str(payment.id),
            after_data={"allocations": len(allocations), "amount": str(payment.amount)},
        )
        await self.session.commit()
        return allocations

    # --- manual override (TASK-030) ---------------------------------------

    async def manual_override(
        self, user_id: uuid.UUID, payment_id: uuid.UUID, items: list[AllocationItem]
    ) -> list[FundAllocation]:
        """Replace the proposed plan with the user's allocation (validated)."""
        payment = await self._get_payment_for_update(user_id, payment_id)
        if payment.status != PaymentStatus.ALLOCATED:
            raise ConflictError("Payment must be in ALLOCATED state to override.")

        total = sum((item.amount for item in items), Decimal("0"))
        if total != payment.amount:
            raise ConflictError("Allocated total must equal the payment amount.")

        per_account: dict[uuid.UUID, Decimal] = {}
        for item in items:
            account = await self._get_owned_account(user_id, item.account_id)
            if account.currency != payment.currency:
                raise ConflictError("Allocation currency must match the payment.")
            if not account.include_in_allocation:
                raise ConflictError("Account is excluded from allocation.")
            per_account[item.account_id] = (
                per_account.get(item.account_id, Decimal("0")) + item.amount
            )

        for account_id, amount in per_account.items():
            existing = await self.session.get(Account, account_id)
            if existing is None:
                raise NotFoundError("Account not found.")
            available = await self._planning_available(existing)
            if amount > available:
                raise InsufficientPlanningFundsError(
                    f"Account {existing.name} has insufficient planning funds."
                )

        await self.repository.delete_proposed(payment_id)
        allocations = [
            FundAllocation(
                payment_id=payment.id,
                account_id=item.account_id,
                allocated_amount=item.amount,
                status=AllocationStatus.PROPOSED,
                algorithm_version="manual",
            )
            for item in items
        ]
        self.session.add_all(allocations)
        await AuditService(self.session).record(
            user_id=user_id,
            action="ALLOCATION_OVERRIDDEN",
            resource_type="payment",
            resource_id=str(payment.id),
            after_data={"allocations": len(allocations), "amount": str(payment.amount)},
        )
        await self.session.commit()
        return allocations

    # --- confirm / reserve (TASK-031) -------------------------------------

    async def confirm_reservation(
        self, user_id: uuid.UUID, payment_id: uuid.UUID
    ) -> list[FundAllocation]:
        """Accept the proposed plan: PROPOSED -> RESERVED (virtual only)."""
        payment = await self._get_payment_for_update(user_id, payment_id)
        if payment.status != PaymentStatus.ALLOCATED:
            raise ConflictError("Only ALLOCATED payments can be reserved.")

        allocations = await self.repository.list_for_payment(payment_id)
        active = [a for a in allocations if a.status == AllocationStatus.PROPOSED]
        if not active:
            raise ConflictError("No proposed allocations to confirm.")

        # Lock every funding account in deterministic order, then re-check
        # availability.  A proposal is only a preview and may be stale by
        # the time the user confirms it.
        proposed_by_account: dict[uuid.UUID, Decimal] = {}
        for allocation in active:
            proposed_by_account[allocation.account_id] = (
                proposed_by_account.get(allocation.account_id, Decimal("0"))
                + allocation.allocated_amount
            )
        account_ids = sorted(proposed_by_account)
        locked_accounts = list(
            await self.session.scalars(
                select(Account)
                .where(Account.id.in_(account_ids))
                .order_by(Account.id)
                .with_for_update()
            )
        )
        accounts_by_id = {account.id: account for account in locked_accounts}
        for account_id in account_ids:
            account = accounts_by_id.get(account_id)
            if account is None or account.user_id != user_id:
                raise NotFoundError("Account not found.")
            if account.currency != payment.currency or not account.include_in_allocation:
                raise ConflictError("Funding account is no longer eligible for allocation.")
            if proposed_by_account[account_id] > await self._planning_available(account):
                raise InsufficientPlanningFundsError(
                    f"Account {account.name} no longer has sufficient planning funds."
                )

        for allocation in active:
            allocation.status = AllocationStatus.RESERVED

        assert_transition(payment.status, PaymentStatus.RESERVED)
        payment.status = PaymentStatus.RESERVED
        await AuditService(self.session).record(
            user_id=user_id,
            action="FUNDS_RESERVED",
            resource_type="payment",
            resource_id=str(payment.id),
            after_data={
                "status": payment.status.value,
                "amount": str(sum((a.allocated_amount for a in active), Decimal("0"))),
            },
        )
        await self.session.commit()
        return active

    async def list_for_payment(
        self, user_id: uuid.UUID, payment_id: uuid.UUID
    ) -> list[FundAllocation]:
        await self._get_payment(user_id, payment_id)
        return await self.repository.list_for_payment(payment_id)

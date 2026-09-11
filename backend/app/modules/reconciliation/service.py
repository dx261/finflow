"""Reconciliation service: auto-match, settle, release.

Confirms whether the user actually completed a payment by matching the
payment against real bank transactions.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.allocation.models import AllocationStatus, FundAllocation
from app.modules.payments.models import PaymentPlan, PaymentStatus
from app.modules.payments.state_machine import assert_transition
from app.modules.reconciliation.models import Reconciliation, ReconStatus
from app.modules.reconciliation.scoring import (
    PaymentMatchSide,
    ScoreResult,
    TransactionMatchSide,
    score_match,
)
from app.modules.statements.models import Transaction


class ReconciliationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- auto matching (TASK-034) -----------------------------------------

    async def _get_payment(self, user_id: uuid.UUID, payment_id: uuid.UUID) -> PaymentPlan:
        payment = await self.session.get(PaymentPlan, payment_id)
        if payment is None or payment.user_id != user_id:
            raise NotFoundError("Payment not found.")
        return payment

    async def _get_recon(self, user_id: uuid.UUID, recon_id: uuid.UUID) -> Reconciliation:
        recon = await self.session.get(Reconciliation, recon_id)
        if recon is None:
            raise NotFoundError("Reconciliation not found.")
        payment = await self.session.get(PaymentPlan, recon.payment_id)
        if payment is None or payment.user_id != user_id:
            raise NotFoundError("Reconciliation not found.")
        return recon

    async def run_for_payment(self, user_id: uuid.UUID, payment_id: uuid.UUID) -> Reconciliation:
        """Score the payment against candidate transactions and pick the best."""
        payment = await self._get_payment(user_id, payment_id)
        if payment.status not in (
            PaymentStatus.MANUALLY_EXECUTED,
            PaymentStatus.RECONCILING,
        ):
            raise ConflictError("Only MANUALLY_EXECUTED or RECONCILING payments can be reconciled.")

        account_id = payment.manual_execution_account_id or payment.preferred_account_id
        if account_id is None:
            raise ConflictError("No execution account recorded for this payment.")

        candidates = list(
            await self.session.scalars(
                select(Transaction).where(
                    Transaction.account_id == account_id,
                    Transaction.direction == "DEBIT",
                )
            )
        )

        payment_side = PaymentMatchSide(
            amount=payment.amount,
            planned_date=payment.planned_date,
            payee_name=payment.payee_name,
            bank_reference=payment.bank_reference,
            account_id=str(account_id),
        )

        best: tuple[Reconciliation | None, float] = (None, 0.0)
        for txn in candidates:
            txn_side = TransactionMatchSide(
                amount=txn.amount,
                transaction_date=txn.transaction_date,
                counterparty=txn.counterparty_name,
                reference=txn.external_reference,
                account_id=str(txn.account_id),
            )
            score = score_match(payment_side, txn_side)
            if score.total > best[1]:
                best = (
                    self._build_recon(payment, txn, score.total, score),
                    score.total,
                )

        if best[0] is None:
            raise ConflictError("No candidate transactions to reconcile against.")

        recon = best[0]
        self.session.add(recon)

        assert_transition(payment.status, PaymentStatus.RECONCILING)
        payment.status = PaymentStatus.RECONCILING
        await self.session.commit()
        return recon

    @staticmethod
    def _build_recon(
        payment: PaymentPlan, txn: Transaction, total: float, score: ScoreResult
    ) -> Reconciliation:
        status = (
            ReconStatus.AUTO_MATCHED
            if total >= settings.auto_match_threshold
            else ReconStatus.REVIEW_REQUIRED
        )
        return Reconciliation(
            payment_id=payment.id,
            transaction_id=txn.id,
            total_score=total,
            amount_score=score.amount,
            account_score=score.account,
            date_score=score.date,
            counterparty_score=score.counterparty,
            reference_score=score.reference,
            status=status,
        )

    # --- settlement (TASK-036) ---------------------------------------------

    async def confirm(self, user_id: uuid.UUID, recon_id: uuid.UUID) -> Reconciliation:
        """Confirm the match and settle the payment and its allocations."""
        recon = await self._get_recon(user_id, recon_id)
        if recon.status not in (ReconStatus.AUTO_MATCHED, ReconStatus.REVIEW_REQUIRED):
            raise ConflictError("Reconciliation already resolved.")

        payment = await self._get_payment(user_id, recon.payment_id)
        assert_transition(payment.status, PaymentStatus.SETTLED)
        payment.status = PaymentStatus.SETTLED

        allocations = list(
            await self.session.scalars(
                select(FundAllocation).where(
                    FundAllocation.payment_id == payment.id,
                    FundAllocation.status == AllocationStatus.RESERVED,
                )
            )
        )
        for allocation in allocations:
            allocation.status = AllocationStatus.SETTLED
            allocation.settled_at = datetime.now(UTC)

        recon.status = ReconStatus.CONFIRMED
        recon.confirmed_by = user_id
        recon.confirmed_at = datetime.now(UTC)
        await self.session.commit()
        return recon

    async def reject(self, user_id: uuid.UUID, recon_id: uuid.UUID) -> Reconciliation:
        """Reject a suggested match (it does not settle the payment)."""
        recon = await self._get_recon(user_id, recon_id)
        if recon.status not in (ReconStatus.AUTO_MATCHED, ReconStatus.REVIEW_REQUIRED):
            raise ConflictError("Reconciliation already resolved.")
        recon.status = ReconStatus.REJECTED
        await self.session.commit()
        return recon

    async def select_transaction(
        self, user_id: uuid.UUID, recon_id: uuid.UUID, transaction_id: uuid.UUID
    ) -> Reconciliation:
        """Rebind the match to a different transaction chosen by the user."""
        recon = await self._get_recon(user_id, recon_id)
        if recon.status in (ReconStatus.CONFIRMED, ReconStatus.REJECTED):
            raise ConflictError("Reconciliation already resolved.")

        payment = await self._get_payment(user_id, recon.payment_id)
        txn = await self.session.get(Transaction, transaction_id)
        if txn is None:
            raise NotFoundError("Transaction not found.")

        txn_side = TransactionMatchSide(
            amount=txn.amount,
            transaction_date=txn.transaction_date,
            counterparty=txn.counterparty_name,
            reference=txn.external_reference,
            account_id=str(txn.account_id),
        )
        score = score_match(
            PaymentMatchSide(
                amount=payment.amount,
                planned_date=payment.planned_date,
                payee_name=payment.payee_name,
                bank_reference=payment.bank_reference,
                account_id=str(txn.account_id),
            ),
            txn_side,
        )

        recon.transaction_id = txn.id
        recon.total_score = score.total
        recon.amount_score = score.amount
        recon.account_score = score.account
        recon.date_score = score.date
        recon.counterparty_score = score.counterparty
        recon.reference_score = score.reference
        recon.status = (
            ReconStatus.AUTO_MATCHED
            if score.total >= settings.auto_match_threshold
            else ReconStatus.REVIEW_REQUIRED
        )
        await self.session.commit()
        return recon

    # --- reservation release (TASK-037) -------------------------------------

    async def release_reservations(
        self, user_id: uuid.UUID, payment_id: uuid.UUID, target: PaymentStatus
    ) -> PaymentPlan:
        """Release reserved funds when the payment fails or is cancelled."""
        payment = await self._get_payment(user_id, payment_id)
        if payment.status not in (
            PaymentStatus.RESERVED,
            PaymentStatus.WAITING_MANUAL_EXECUTION,
        ):
            raise ConflictError("Only reserved payments can be released.")
        if target not in (PaymentStatus.PLANNED, PaymentStatus.CANCELLED):
            raise ConflictError("Release target must be PLANNED or CANCELLED.")

        allocations = list(
            await self.session.scalars(
                select(FundAllocation).where(
                    FundAllocation.payment_id == payment.id,
                    FundAllocation.status == AllocationStatus.RESERVED,
                )
            )
        )
        for allocation in allocations:
            allocation.status = AllocationStatus.RELEASED
            allocation.released_at = datetime.now(UTC)

        assert_transition(payment.status, target)
        payment.status = target
        await self.session.commit()
        return payment

    # --- query --------------------------------------------------------------

    async def list_pending(self, user_id: uuid.UUID) -> list[Reconciliation]:
        """Workbench: REVIEW_REQUIRED matches for the user's payments."""
        result = await self.session.scalars(
            select(Reconciliation)
            .join(PaymentPlan, PaymentPlan.id == Reconciliation.payment_id)
            .where(
                PaymentPlan.user_id == user_id,
                Reconciliation.status == ReconStatus.REVIEW_REQUIRED,
            )
            .order_by(Reconciliation.created_at)
        )
        return list(result)

    async def list_for_payment(
        self, user_id: uuid.UUID, payment_id: uuid.UUID
    ) -> list[Reconciliation]:
        await self._get_payment(user_id, payment_id)
        result = await self.session.scalars(
            select(Reconciliation)
            .where(Reconciliation.payment_id == payment_id)
            .order_by(Reconciliation.created_at.desc())
        )
        return list(result)

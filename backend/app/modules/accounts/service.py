"""Account business logic and planning-balance computation."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.modules.accounts.models import Account
from app.modules.accounts.repository import AccountRepository
from app.modules.accounts.schemas import (
    AccountCreate,
    AccountRead,
    AccountUpdate,
    BalanceSnapshotCreate,
    BalanceSnapshotRead,
)
from app.modules.auth.models import User, UserRole


class AccountService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = AccountRepository(session)
        self.session = session

    # --- planning balances -------------------------------------------------

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        """Quantize a money value to 2 decimal places."""
        return value.quantize(Decimal("0.01"))

    def reserved_amount(self, account: Account) -> Decimal:
        """Virtual funds reserved for future payment allocations.

        Currently zero because allocations do not exist yet; TASK-031
        (virtual reservation) sums the account's active FundAllocations
        here. The value is never persisted — it is derived on read.
        """
        return Decimal("0.00")

    def planning_available(self, account: Account) -> Decimal:
        """actual_balance - reserved_amount - minimum_balance (§13)."""
        value = account.actual_balance - self.reserved_amount(account) - account.minimum_balance
        return self._money(value)

    def to_read(self, account: Account) -> AccountRead:
        return AccountRead(
            id=account.id,
            user_id=account.user_id,
            bank_id=account.bank_id,
            name=account.name,
            masked_account_no=account.masked_account_no,
            account_type=account.account_type,
            currency=account.currency,
            actual_balance=account.actual_balance,
            balance_as_of=account.balance_as_of,
            minimum_balance=account.minimum_balance,
            include_in_allocation=account.include_in_allocation,
            status=account.status,
            reserved_amount=self.reserved_amount(account),
            planning_available=self.planning_available(account),
            created_at=account.created_at,
            updated_at=account.updated_at,
        )

    # --- CRUD ----------------------------------------------------------------

    async def list_accounts(self, user_id: uuid.UUID) -> list[AccountRead]:
        accounts = await self.repository.list_by_user(user_id)
        return [self.to_read(account) for account in accounts]

    async def get_account(self, account_id: uuid.UUID, current_user: User) -> AccountRead:
        account = await self._owned_account(account_id, current_user)
        return self.to_read(account)

    async def create_account(self, user_id: uuid.UUID, payload: AccountCreate) -> AccountRead:
        account = await self.repository.create(user_id, payload)
        await self.session.commit()
        return self.to_read(account)

    async def update_account(
        self, account_id: uuid.UUID, payload: AccountUpdate, current_user: User
    ) -> AccountRead:
        account = await self._owned_account(account_id, current_user)
        updated = await self.repository.update(account, payload)
        await self.session.commit()
        return self.to_read(updated)

    async def delete_account(self, account_id: uuid.UUID, current_user: User) -> None:
        account = await self._owned_account(account_id, current_user)
        await self.repository.delete(account)
        await self.session.commit()

    # --- balance snapshots -------------------------------------------------

    async def list_snapshots(
        self, account_id: uuid.UUID, current_user: User
    ) -> list[BalanceSnapshotRead]:
        account = await self._owned_account(account_id, current_user)
        snapshots = await self.repository.list_snapshots(account.id)
        return [BalanceSnapshotRead.model_validate(s) for s in snapshots]

    async def create_snapshot(
        self, account_id: uuid.UUID, payload: BalanceSnapshotCreate, current_user: User
    ) -> BalanceSnapshotRead:
        account = await self._owned_account(account_id, current_user)
        snapshot = await self.repository.create_snapshot(
            account_id=account.id,
            balance=account.actual_balance,
            available_balance=self.planning_available(account),
            snapshot_date=payload.snapshot_date or date.today(),
            source=payload.source,
        )
        await self.session.commit()
        return BalanceSnapshotRead.model_validate(snapshot)

    async def _owned_account(self, account_id: uuid.UUID, current_user: User) -> Account:
        account = await self.repository.get_by_id(account_id)
        if account is None:
            raise NotFoundError("Account not found.")
        if account.user_id != current_user.id and current_user.role != UserRole.OWNER:
            raise PermissionDeniedError("You do not own this account.")
        return account

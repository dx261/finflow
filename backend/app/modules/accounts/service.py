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
from app.modules.allocation.service import sum_reserved_amount, sum_reserved_amounts
from app.modules.audit.service import AuditService
from app.modules.auth.models import User


class AccountService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = AccountRepository(session)
        self.session = session

    # --- planning balances -------------------------------------------------

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        """Quantize a money value to 2 decimal places."""
        return value.quantize(Decimal("0.01"))

    async def reserved_amount(self, account: Account) -> Decimal:
        """Virtual funds reserved for this account (sum of RESERVED
        allocations). Derived on read — never persisted."""
        return await sum_reserved_amount(self.session, account.id)

    async def planning_available(self, account: Account) -> Decimal:
        """actual_balance - reserved_amount - minimum_balance (§13)."""
        reserved = await self.reserved_amount(account)
        value = account.actual_balance - reserved - account.minimum_balance
        return self._money(value)

    async def to_read(
        self, account: Account, reserved_amount: Decimal | None = None
    ) -> AccountRead:
        reserved = (
            await self.reserved_amount(account) if reserved_amount is None else reserved_amount
        )
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
            reserved_amount=self._money(reserved),
            planning_available=self._money(
                account.actual_balance - reserved - account.minimum_balance
            ),
            reservation_shortfall=self._money(
                max(
                    Decimal("0"),
                    reserved + account.minimum_balance - account.actual_balance,
                )
            ),
            created_at=account.created_at,
            updated_at=account.updated_at,
        )

    # --- CRUD ----------------------------------------------------------------

    async def list_accounts(self, user_id: uuid.UUID) -> list[AccountRead]:
        accounts = await self.repository.list_by_user(user_id)
        reserved = await sum_reserved_amounts(self.session, [account.id for account in accounts])
        return [
            await self.to_read(account, reserved.get(account.id, Decimal("0")))
            for account in accounts
        ]

    async def get_account(self, account_id: uuid.UUID, data_owner_id: uuid.UUID) -> AccountRead:
        account = await self._account_for_owner(account_id, data_owner_id)
        return await self.to_read(account)

    async def create_account(self, user_id: uuid.UUID, payload: AccountCreate) -> AccountRead:
        account = await self.repository.create(user_id, payload)
        await AuditService(self.session).record(
            user_id=user_id,
            action="ACCOUNT_CREATED",
            resource_type="account",
            resource_id=str(account.id),
            after_data=(await self.to_read(account)).model_dump(mode="json"),
        )
        await self.session.commit()
        return await self.to_read(account)

    async def update_account(
        self, account_id: uuid.UUID, payload: AccountUpdate, current_user: User
    ) -> AccountRead:
        account = await self._owned_account(account_id, current_user)
        before_data = (await self.to_read(account)).model_dump(mode="json")
        updated = await self.repository.update(account, payload)
        await AuditService(self.session).record(
            user_id=current_user.id,
            action="ACCOUNT_UPDATED",
            resource_type="account",
            resource_id=str(account_id),
            before_data=before_data,
            after_data=(await self.to_read(updated)).model_dump(mode="json"),
        )
        await self.session.commit()
        return await self.to_read(updated)

    async def delete_account(self, account_id: uuid.UUID, current_user: User) -> None:
        account = await self._owned_account(account_id, current_user)
        await AuditService(self.session).record(
            user_id=current_user.id,
            action="ACCOUNT_DELETED",
            resource_type="account",
            resource_id=str(account.id),
            before_data=(await self.to_read(account)).model_dump(mode="json"),
        )
        await self.repository.delete(account)
        await self.session.commit()

    # --- balance snapshots -------------------------------------------------

    async def list_snapshots(
        self, account_id: uuid.UUID, data_owner_id: uuid.UUID
    ) -> list[BalanceSnapshotRead]:
        account = await self._account_for_owner(account_id, data_owner_id)
        snapshots = await self.repository.list_snapshots(account.id)
        return [BalanceSnapshotRead.model_validate(s) for s in snapshots]

    async def create_snapshot(
        self, account_id: uuid.UUID, payload: BalanceSnapshotCreate, current_user: User
    ) -> BalanceSnapshotRead:
        account = await self._owned_account(account_id, current_user)
        snapshot = await self.repository.create_snapshot(
            account_id=account.id,
            balance=account.actual_balance,
            available_balance=await self.planning_available(account),
            snapshot_date=payload.snapshot_date or date.today(),
            source=payload.source,
        )
        await AuditService(self.session).record(
            user_id=current_user.id,
            action="BALANCE_SNAPSHOT_CREATED",
            resource_type="account_balance_snapshot",
            resource_id=str(snapshot.id),
            after_data={
                "account_id": str(account.id),
                "balance": str(snapshot.balance),
                "snapshot_date": snapshot.snapshot_date.isoformat(),
            },
        )
        await self.session.commit()
        return BalanceSnapshotRead.model_validate(snapshot)

    async def _owned_account(self, account_id: uuid.UUID, current_user: User) -> Account:
        return await self._account_for_owner(account_id, current_user.id)

    async def _account_for_owner(self, account_id: uuid.UUID, data_owner_id: uuid.UUID) -> Account:
        account = await self.repository.get_by_id(account_id)
        if account is None:
            raise NotFoundError("Account not found.")
        if account.user_id != data_owner_id:
            raise PermissionDeniedError("You do not have access to this account.")
        return account

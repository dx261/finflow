"""Account data access."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounts.models import Account, AccountBalanceSnapshot, BalanceSource
from app.modules.accounts.schemas import AccountCreate, AccountUpdate


class AccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_user(self, user_id: uuid.UUID) -> list[Account]:
        result = await self.session.scalars(
            select(Account).where(Account.user_id == user_id).order_by(Account.name)
        )
        return list(result)

    async def get_by_id(self, account_id: uuid.UUID) -> Account | None:
        return await self.session.get(Account, account_id)

    async def create(self, user_id: uuid.UUID, payload: AccountCreate) -> Account:
        account = Account(
            user_id=user_id,
            bank_id=payload.bank_id,
            name=payload.name,
            masked_account_no=payload.masked_account_no,
            account_type=payload.account_type,
            currency=payload.currency,
            actual_balance=payload.actual_balance,
            balance_as_of=payload.balance_as_of,
            minimum_balance=payload.minimum_balance,
            include_in_allocation=payload.include_in_allocation,
        )
        self.session.add(account)
        await self.session.flush()
        return account

    async def update(self, account: Account, payload: AccountUpdate) -> Account:
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(account, field, value)
        await self.session.flush()
        return account

    async def delete(self, account: Account) -> None:
        await self.session.delete(account)
        await self.session.flush()

    async def list_snapshots(self, account_id: uuid.UUID) -> list[AccountBalanceSnapshot]:
        result = await self.session.scalars(
            select(AccountBalanceSnapshot)
            .where(AccountBalanceSnapshot.account_id == account_id)
            .order_by(AccountBalanceSnapshot.snapshot_date.desc())
        )
        return list(result)

    async def create_snapshot(
        self,
        account_id: uuid.UUID,
        balance: Decimal,
        available_balance: Decimal,
        snapshot_date: date,
        source: BalanceSource,
    ) -> AccountBalanceSnapshot:
        snapshot = AccountBalanceSnapshot(
            account_id=account_id,
            balance=balance,
            available_balance=available_balance,
            snapshot_date=snapshot_date,
            source=source,
        )
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot

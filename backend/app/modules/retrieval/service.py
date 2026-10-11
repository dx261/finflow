"""Transaction search service (§61)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.modules.accounts.models import Account
from app.modules.statements.models import Transaction, TransactionDirection


class TransactionSearch:
    def __init__(
        self,
        *,
        account_id: uuid.UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        min_amount: Decimal | None = None,
        max_amount: Decimal | None = None,
        category: str | None = None,
        keyword: str | None = None,
        direction: TransactionDirection | None = None,
    ) -> None:
        self.account_id = account_id
        self.date_from = date_from
        self.date_to = date_to
        self.min_amount = min_amount
        self.max_amount = max_amount
        self.category = category
        self.keyword = keyword
        self.direction = direction


class RetrievalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_transaction(self, user_id: uuid.UUID, transaction_id: uuid.UUID) -> Transaction:
        transaction = await self.session.get(Transaction, transaction_id)
        if transaction is None:
            raise NotFoundError("Transaction not found.")
        account = await self.session.get(Account, transaction.account_id)
        if account is None or account.user_id != user_id:
            raise NotFoundError("Transaction not found.")
        return transaction

    async def list_transactions(
        self, user_id: uuid.UUID, search: TransactionSearch, limit: int = 50
    ) -> list[Transaction]:
        """Return the user's transactions matching the search filters."""
        account_ids = list(
            await self.session.scalars(select(Account.id).where(Account.user_id == user_id))
        )
        if not account_ids:
            return []

        query = select(Transaction).where(Transaction.account_id.in_(account_ids))

        if search.account_id is not None:
            account = await self.session.get(Account, search.account_id)
            if account is None or account.user_id != user_id:
                raise NotFoundError("Account not found.")
            query = query.where(Transaction.account_id == search.account_id)
        if search.date_from is not None:
            query = query.where(Transaction.transaction_date >= search.date_from)
        if search.date_to is not None:
            query = query.where(Transaction.transaction_date <= search.date_to)
        if search.min_amount is not None:
            query = query.where(Transaction.amount >= search.min_amount)
        if search.max_amount is not None:
            query = query.where(Transaction.amount <= search.max_amount)
        if search.direction is not None:
            query = query.where(Transaction.direction == search.direction)
        if search.category is not None:
            query = query.where(Transaction.category_id == uuid.UUID(search.category))
        if search.keyword:
            like = f"%{search.keyword}%"
            query = query.where(
                or_(
                    Transaction.description.ilike(like),
                    Transaction.counterparty_name.ilike(like),
                )
            )

        query = query.order_by(Transaction.transaction_date.desc()).limit(limit)
        result = await self.session.scalars(query)
        return list(result)
